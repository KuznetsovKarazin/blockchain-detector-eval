"""Frozen post-review B/C exclusion-policy comparison on the historical test."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys
import time
import traceback

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

import analyze as audit
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'papers/security_evaluation'))
from campaign import run_development as trainer

CODE=['papers/security_evaluation/revision2/model_link/expanded_contrast.py',
      'papers/security_evaluation/revision2/model_link/analyze.py',
      'papers/security_evaluation/campaign/run_development.py',
      'src/bal/features/contract_features.py',
      'papers/security_evaluation/evaluation_metrics.py']
METHODS=['raw_tfidf_lr','normalized_tfidf_lr','pattern_rf','pattern_lightgbm']
sha=audit.sha
dump=audit.dump


def now():return datetime.now(timezone.utc).isoformat()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def prepare(out):
    if out.exists():raise ValueError('New directory required')
    inv=pd.read_csv(audit.PILOT/'source_inventory.csv').set_index('file_id',drop=False)
    labels,_=audit.read_labels(inv.reset_index(drop=True),ROOT/'data/raw/DAppSCAN')
    old=json.loads((audit.RUN/'config.json').read_text())
    prior=next(j for j in old['jobs'] if j['regime']=='joint_project_clone_disjoint')
    test=prior['test_ids'];projection=pd.read_csv(audit.PROJECTION).set_index('file_id')
    groups={c:set(projection.loc[test,c]) for c in ['B_historical_legacy','C_uncapped_reference_legacy']}
    dapp=inv[inv.dataset.eq('dappscan')].file_id.tolist()
    pools={name:sorted(i for i in dapp if projection.loc[i,col] not in groups[col]) for name,col in [('B','B_historical_legacy'),('C','C_uncapped_reference_legacy')]}
    assert pools['B']==prior['train_ids'] and len(pools['C'])==708 and set(pools['C'])<=set(pools['B'])
    assert sum(labels[i]['reentrancy'] for i in pools['C'])==24
    selected={};member_rows=[]
    for draw in range(5):
        for name in ['B','C']:
            ids=[]
            for y,n in [(0,684),(1,24)]:
                candidates=[i for i in pools[name] if labels[i]['reentrancy']==y]
                salt=f'expanded-graph-post-review-v1|draw={draw}|class={y}'
                candidates.sort(key=lambda i:(hashlib.sha256((salt+'|'+inv.loc[i,'path']).encode()).hexdigest(),inv.loc[i,'path']))
                ids.extend(candidates[:n])
            ids=sorted(ids);assert len(ids)==708 and sum(labels[i]['reentrancy'] for i in ids)==24 and not set(ids)&set(test)
            selected[(draw,name)]=ids
            for i in ids:member_rows.append({'draw':draw,'policy':name,'role':'train','file_id':i,'reentrancy_proxy':labels[i]['reentrancy']})
    jobs=[];canonical={}
    for draw in range(5):
        for name in ['B','C']:
            for method in METHODS:
                for seed in ([0] if method.endswith('tfidf_lr') else range(5)):
                    ids=selected[(draw,name)];physical_key=fingerprint([method,seed,ids,test])
                    j={'job_id':f'd{draw}_{name}_{method}_s{seed}','draw':draw,'policy':name,'method':method,'seed':seed,'class':'reentrancy','train_ids':ids,'test_ids':test,'training_membership_sha256':fingerprint(ids),'reuse_from':canonical.get(physical_key)}
                    canonical.setdefault(physical_key,j['job_id']);jobs.append(j)
    used=sorted(set(test)|{i for j in jobs for i in j['train_ids']})
    inventory=inv.loc[used].copy()
    for row in inventory.itertuples(index=False):
        if sha(ROOT/row.path)!=row.file_sha256:raise ValueError(f'Source changed: {row.path}')
    out.mkdir(parents=True)
    inventory.to_csv(out/'source_inventory.csv',index=False)
    pd.DataFrame(member_rows).to_csv(out/'memberships.csv',index=False)
    dump(out/'labels.json',{str(i):labels[i] for i in used})
    dump(out/'test_ids.json',test)
    dump(out/'pool_ids.json',pools)
    config={'schema':'expanded_graph_policy_contrast_postreview_v1','created_utc':now(),'purpose':'Conditional score effect of B-versus-C graph exclusion at matchedtrainingcounts on the already observed historical proxy-labeled test','prior_exposure':'Review-triggered new design; prior historical scores and graph patterns already observed. No preregistration or untouched test claim.','test_n':1082,'test_positive':21,'train_n':708,'train_positive':24,'B_pool_n':1179,'B_pool_positive':31,'C_pool_n':708,'C_pool_positive':24,'main_draws':[0,1,2,3,4],'tree_estimator_seeds':[0,1,2,3,4],'lr_seed':0,'model_config':old['model_config'],'jobs':jobs,'physical_fits':len(canonical),'logical_evaluations':len(jobs),'selection':'Prespecified SHA256 pathranking independently withinproxyclasses;same rankruleforB/C;Cfullpoolallfiveindices.','stopping_rule':'Every frozen job attempted once. Failures and all warnings retained; no selective retry or score-based changes.','saving':'Save source/config/runtime hashes, memberships, predictions and per-attempttimings/status; do not save fittedmodel binaries.','review_budgets':[54,108,216],'external_execution':False,'claimed_causal_effect':False,'old_campaign_gates':'Unchanged; this is a separately named post-review conditional diagnostic, not authorization of the failed outside-giant campaign.','interpretation':'B intentionally uses a smaller graph population; its retained training may connect through omittedreferencefiles inC. C is disjoint only under the frozen observedCgraph. One historicaltest cannot supportnew-familyinference.'}
    assert config['physical_fits']==72 and config['logical_evaluations']==120
    dump(out/'config.json',config)
    runtime={'python':sys.version,'platform':platform.platform(),'packages':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','scikit-learn','lightgbm','threadpoolctl']},'lightgbm_wheel_sha256':'cb19b5afea55b5b61cbb2131095f50538bd608a00655f23ad5d25ae3e3bf1c8d','original_wheel_byte_identity':'Original numericalpackageversionsmatch; oldLightGBMwheelhashwasnotretained, so sameoldbinaryidentity is notclaimed.'}
    dump(out/'environment.json',runtime)
    hashes={p:sha(ROOT/p) for p in CODE}
    for p in CODE:
        dest=out/'code_snapshot'/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,dest)
    inputs={p:sha(ROOT/p) for p in ['papers/security_evaluation/revision1/sampling_variance/run_20261025_v2/config.json','papers/security_evaluation/dependency_audit/graph_scope_ablation_recovered_20261025/historical_projection.csv','papers/security_evaluation/runs/dev_fixed_t_20261025_v1/label_input_hashes.json']}
    freeze={'schema':'expanded_graph_policy_contrast_freeze_v1','prepared_utc':now(),'source_hashes':hashes,'input_hashes':inputs,'prepared_files':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'physical_fits':72,'logical_evaluations':120,'fit_has_started':False}
    dump(out/'FREEZE_BEFORE_FITTING.json',freeze)
    print(json.dumps({'prepared':str(out),'freeze_sha256':sha(out/'FREEZE_BEFORE_FITTING.json'),'physical':72,'logical':120}),flush=True)


def run(out):
    if (out/'execution_started.json').exists():raise ValueError('No retries or restarts in this run directory')
    freeze=json.loads((out/'FREEZE_BEFORE_FITTING.json').read_text())
    for p,h in freeze['source_hashes'].items():
        if sha(ROOT/p)!=h or sha(out/'code_snapshot'/p)!=h:raise ValueError('Source hash mismatch')
    for p,h in freeze['input_hashes'].items():
        if sha(ROOT/p)!=h:raise ValueError('Input hash mismatch')
    for p,h in freeze['prepared_files'].items():
        if sha(out/p)!=h:raise ValueError('Prepared file mismatch')
    config=json.loads((out/'config.json').read_text());inv=pd.read_csv(out/'source_inventory.csv')
    sources={}
    for row in inv.itertuples():
        if sha(ROOT/row.path)!=row.file_sha256:raise ValueError('Source bytes changed')
        sources[row.file_id]=(ROOT/row.path).read_text(encoding='utf-8',errors='replace')
    labels={int(k):v for k,v in json.loads((out/'labels.json').read_text()).items()}
    dump(out/'execution_started.json',{'started_utc':now(),'freeze_sha256':sha(out/'FREEZE_BEFORE_FITTING.json')})
    completed={};summaries=[];start=time.perf_counter()
    for idx,job in enumerate(config['jobs']):
        dest=out/'fits'/job['job_id'];dest.mkdir(parents=True)
        dump(dest/'started.json',{'utc':now(),'job':job,'freeze_sha256':sha(out/'FREEZE_BEFORE_FITTING.json')})
        result={'job_id':job['job_id'],'physical_fit':job['reuse_from'] is None,'reuse_from':job['reuse_from']}
        try:
            if job['reuse_from']:
                source=completed[job['reuse_from']]
                if source['status']!='ok':raise ValueError('Canonical fit failed; no substitute fit')
                score=pd.read_csv(out/'fits'/job['reuse_from']/'predictions.csv',float_precision='round_trip').score.to_numpy()
                resources={'physical_fit':False,'reused_job':job['reuse_from'],'total_seconds':0.0}
            else:score,resources=trainer.fit_predict(job,config,sources,labels)
            pd.DataFrame({'file_id':job['test_ids'],'score':score,'status':'ok'}).to_csv(dest/'predictions.csv',index=False)
            dump(dest/'resources.json',resources)
            y=np.array([labels[i]['reentrancy'] for i in job['test_ids']])
            metrics={'ap_proxy':float(average_precision_score(y,score))}
            for b in [54,108,216]:metrics[f'expected_findings_{b}']=float(np.sum(audit.expected_review(score,b)*y))
            dump(dest/'metrics.json',metrics);result.update({'status':'ok','metrics':metrics,'resources':resources,'artifacts':{p.name:sha(p) for p in dest.iterdir() if p.is_file()}})
        except Exception as exc:
            result.update({'status':'failed','error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),'artifacts':{p.name:sha(p) for p in dest.iterdir() if p.is_file()}})
        result['finished_utc']=now();dump(dest/'result.json',result);completed[job['job_id']]=result
        row={k:job[k] for k in ['job_id','draw','policy','method','seed','reuse_from','training_membership_sha256']};row.update({'status':result['status'],'physical_fit':result['physical_fit']});row.update(result.get('metrics',{}));summaries.append(row)
        print(json.dumps({'completed':idx+1,'total':120,'job':job['job_id'],'status':result['status']}),flush=True)
    pd.DataFrame(summaries).to_csv(out/'logical_results.csv',index=False)
    dump(out/'COMPLETE.json',{'finished_utc':now(),'logical':len(summaries),'physical':sum(x['physical_fit'] for x in summaries),'failed':sum(x['status']!='ok' for x in summaries),'elapsed_seconds':time.perf_counter()-start,'freeze_sha256':sha(out/'FREEZE_BEFORE_FITTING.json'),'result_hashes':{j['job_id']:sha(out/'fits'/j['job_id']/'result.json') for j in config['jobs']},'summary_sha256':sha(out/'logical_results.csv'),'new_external_scores':0})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('--out',type=Path,required=True);a=p.parse_args();globals()[a.action](a.out)
