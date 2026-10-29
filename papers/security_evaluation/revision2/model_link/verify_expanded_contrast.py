"""Recompute completed contrast metrics directly from scores with a separate implementation."""
from __future__ import annotations
import argparse
from collections import Counter
from itertools import groupby
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze import sha,dump


def calculate(labels,scores,budgets):
    ranked=sorted(zip(scores,labels),key=lambda x:-x[0])
    n=k=0;positives=sum(labels);ap=0.;yields={b:0. for b in budgets}
    for _,items in groupby(ranked,key=lambda x:x[0]):
        group=list(items);size=len(group);kp=sum(x[1] for x in group)
        for b in budgets:
            slots=max(0,min(size,b-n));yields[b]+=kp*slots/size
        n+=size;k+=kp;ap+=(kp/positives)*(k/n)
    return ap,yields


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();r=a.run
    if (r/'VERIFICATION.json').exists():raise ValueError('Verification already exists')
    complete=json.loads((r/'COMPLETE.json').read_text());config=json.loads((r/'config.json').read_text());freeze=json.loads((r/'FREEZE_BEFORE_FITTING.json').read_text());labels={int(k):v for k,v in json.loads((r/'labels.json').read_text()).items()}
    if sha(r/'FREEZE_BEFORE_FITTING.json')!=complete['freeze_sha256']:raise ValueError('Freeze changed')
    for path,h in freeze['prepared_files'].items():
        if sha(r/path)!=h:raise ValueError(f'Prepared file changed {path}')
    for path,h in freeze['source_hashes'].items():
        if sha(r/'code_snapshot'/path)!=h:raise ValueError('Frozen source copy changed')
    jobs={j['job_id']:j for j in config['jobs']};verified=[];maxdiff=0.;warnings=Counter();convergence=0;physical_seconds=0.
    for jid,j in jobs.items():
        folder=r/'fits'/jid;result=json.loads((folder/'result.json').read_text())
        if sha(folder/'result.json')!=complete['result_hashes'][jid]:raise ValueError('Changed result')
        if result['status']!='ok':continue
        for path,h in result['artifacts'].items():
            if sha(folder/path)!=h:raise ValueError('Changed artifact')
        pred=pd.read_csv(folder/'predictions.csv',float_precision='round_trip')
        if pred.file_id.tolist()!=j['test_ids'] or not pred.status.eq('ok').all() or not np.isfinite(pred.score).all():raise ValueError('Invalid score coverage')
        y=[labels[i]['reentrancy'] for i in j['test_ids']]
        if len(y)!=1082 or sum(y)!=21:raise ValueError('Changed test')
        if len(j['train_ids'])!=708 or sum(labels[i]['reentrancy'] for i in j['train_ids'])!=24:raise ValueError('Changed training counts')
        if set(j['train_ids'])&set(j['test_ids']):raise ValueError('Train/test object overlap')
        ap,ys=calculate(y,pred.score.tolist(),[54,108,216]);old=json.loads((folder/'metrics.json').read_text())
        diffs=[abs(ap-old['ap_proxy']),*[abs(ys[b]-old[f'expected_findings_{b}']) for b in ys]]
        if max(diffs)>1e-12:raise ValueError('Independent metric mismatch')
        maxdiff=max(maxdiff,max(diffs))
        if j['reuse_from']:
            parent=jobs[j['reuse_from']]
            if any(j[k]!=parent[k] for k in ['train_ids','test_ids','method','seed']):raise ValueError('Incorrect reuse')
            if sha(folder/'predictions.csv')!=sha(r/'fits'/j['reuse_from']/'predictions.csv'):raise ValueError('Reused scores changed')
        else:
            resources=json.loads((folder/'resources.json').read_text());warnings.update(resources.get('warnings',[]));convergence+=bool(resources.get('convergence_warning'));physical_seconds+=resources['total_seconds']
        row={k:j[k] for k in ['job_id','draw','policy','method','seed']};row.update({'ap_proxy':ap,**{f'findings_{b}':ys[b] for b in ys}});verified.append(row)
    d=pd.DataFrame(verified);d.to_csv(r/'independently_recomputed_scores.csv',index=False)
    pairs=[]
    for method,md in d.groupby('method'):
        for metric in ['ap_proxy','findings_54','findings_108','findings_216']:
            w=md.pivot(index=['draw','seed'],columns='policy',values=metric)
            for (draw,seed),row in w.iterrows():pairs.append({'method':method,'metric':metric,'draw':draw,'seed':seed,'B':row['B'],'C':row['C'],'B_minus_C':row['B']-row['C']})
    pair=pd.DataFrame(pairs);pair.to_csv(r/'paired_policy_differences.csv',index=False)
    rows=[]
    for (method,metric),g in pair.groupby(['method','metric']):
        x=g.B_minus_C
        rows.append({'method':method,'metric':metric,'logical_pairs':len(g),'B_mean':g.B.mean(),'C_mean':g.C.mean(),'difference_mean':x.mean(),'difference_min':x.min(),'difference_max':x.max(),'positive_pairs':int(x.gt(0).sum()),'negative_pairs':int(x.lt(0).sum()),'zero_pairs':int(x.eq(0).sum()),'interpretation':'descriptive paired scores on one reused test; C reused across draws; no inferential CI'})
    pd.DataFrame(rows).to_csv(r/'policy_comparison_summary.csv',index=False)
    pair.groupby(['method','metric','draw'],as_index=False)[['B','C','B_minus_C']].mean().to_csv(r/'seed_averaged_draw_contrasts.csv',index=False)
    pair.groupby(['method','metric','seed'],as_index=False)[['B','C','B_minus_C']].mean().to_csv(r/'draw_averaged_seed_contrasts.csv',index=False)
    receipt={'schema':'expanded_graph_policy_contrast_independent_metric_recompute_v1','independent_implementation':'Manual equal-score-group AP and full-budget positive counts; does not call sklearn average_precision_score or execution metric code. This is a separate computational check, not a human peer review.','script_sha256':sha(__file__),'logical_predictions_checked':len(verified),'physical_fits':sum(j['reuse_from'] is None for j in jobs.values()),'failed':complete['failed'],'maximum_absolute_metric_difference':maxdiff,'convergence_warning_fits':convergence,'warning_counts_physical':dict(warnings),'physical_fit_total_seconds':physical_seconds,'complete_sha256':sha(r/'COMPLETE.json'),'summary_hashes':{p.name:sha(p) for p in r.glob('*.csv')},'external_scores':0,'causal_or_new_family_inference':False}
    dump(r/'VERIFICATION.json',receipt)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
