"""Post-hoc descriptive model/graph linkage; never fits or scans contracts."""
from __future__ import annotations
import argparse
from collections import defaultdict
from itertools import combinations
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
RUN = ROOT / 'papers/security_evaluation/revision1/sampling_variance/run_20261025_v2'
PILOT = ROOT / 'papers/security_evaluation/runs/dev_fixed_t_20261025_v1'
GRAPH = ROOT / 'papers/security_evaluation/dependency_audit/legacy_recovered_20261025'
PROJECTION = ROOT / 'papers/security_evaluation/dependency_audit/graph_scope_ablation_recovered_20261025/historical_projection.csv'
REGIMES = ['other_files_unrestricted','project_disjoint','clone_disjoint','joint_project_clone_disjoint']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p, value):
    p.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def expected_review(scores, budget):
    boundary = np.sort(scores)[-budget]
    above = scores > boundary
    at = scores == boundary
    weight = above.astype(float)
    weight[at] = (budget-int(above.sum())) / int(at.sum())
    assert np.isclose(weight.sum(),budget)
    return weight


def read_labels(inventory, labels_root):
    hashes = json.loads((PILOT/'label_input_hashes.json').read_text())
    prefix='data/raw/DAppSCAN/'
    relevant={p:h for p,h in hashes.items() if p.startswith(prefix)}
    for p,h in relevant.items():
        source=labels_root/p.removeprefix(prefix)
        if not source.is_file() or sha(source)!=h:
            raise ValueError(f'Pinned annotation missing or changed: {p}')
    labels={}
    for row in inventory[inventory.dataset.eq('dappscan')].itertuples():
        suffix=Path(row.path.removeprefix('data/raw/DAppSCAN/DAppSCAN-source/contracts/')).with_suffix('.json')
        p=labels_root/'DAppSCAN-source/SWCsource'/suffix
        ys={'reentrancy':0,'unchecked':0}
        if p.exists():
            key=prefix+str(p.relative_to(labels_root))
            if key not in relevant:raise ValueError(f'Unrecorded annotation: {key}')
            d=json.loads(p.read_text())
            if d.get('filePath')!=row.path.removeprefix(prefix):raise ValueError('Label/source mapping mismatch')
            codes={x.get('category','').split('-')[1] for x in d.get('SWCs',[]) if x.get('category','').startswith('SWC-')}
            ys={'reentrancy':int('107' in codes),'unchecked':int('104' in codes)}
        labels[row.file_id]=ys
    return labels,len(relevant)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--labels-root',type=Path)
    args=ap.parse_args();out=args.out
    if out.exists():raise ValueError('Use a new output directory')
    plan=json.loads((HERE/'PLAN_BEFORE_ANALYSIS.json').read_text())
    for p,h in plan['inputs'].items():
        if sha(ROOT/p)!=h:raise ValueError(f'Changed input {p}')
    out.mkdir(parents=True)
    config=json.loads((RUN/'config.json').read_text());manifest=json.loads((RUN/'manifest.json').read_text())
    if sha(RUN/'config.json')!=manifest['config_sha256']:raise ValueError('Original config changed')
    for p,h in manifest['summary_hashes'].items():
        if sha(RUN/p)!=h:raise ValueError(f'Original summary changed {p}')
    ranking=pd.read_csv(RUN/'summary/per_evaluation_ranking.csv');workload=pd.read_csv(RUN/'summary/per_evaluation_workload.csv')
    main_panel=ranking[ranking.panel.eq('training_draw')]
    paired=[];panel=[];seed=[]
    for method,rows in main_panel.groupby('method',sort=True):
        wide=rows.pivot(index='draw',columns='regime',values='ap_proxy')
        assert len(wide)==20 and not wide.isna().any().any()
        for left,right in combinations(REGIMES,2):
            x=wide[left]-wide[right]
            paired.append({'method':method,'left':left,'right':right,'n':20,'mean':x.mean(),'sd':x.std(ddof=1),'min':x.min(),'q025':x.quantile(.025),'median':x.median(),'q975':x.quantile(.975),'max':x.max(),'positive_draws':int((x>0).sum()),'negative_draws':int((x<0).sum()),'zero_draws':int((x==0).sum())})
        for regime in REGIMES:
            x=wide[regime];panel.append({'method':method,'regime':regime,'mean':x.mean(),'sd':x.std(ddof=1),'min':x.min(),'max':x.max()})
        s=ranking[ranking.panel.eq('joint_estimator_seed')&ranking.method.eq(method)].sort_values('estimator_seed')
        if len(s):
            x=s.ap_proxy;effect=wide.project_disjoint.mean()-wide.joint_project_clone_disjoint.mean()
            seed.append({'method':method,'n':len(s),'joint_seed_mean':x.mean(),'joint_seed_sd':x.std(ddof=1),'joint_seed_min':x.min(),'joint_seed_max':x.max(),'joint_seed_range':x.max()-x.min(),'seed0':s[s.estimator_seed.eq(0)].ap_proxy.iloc[0],'seed0_rank_ascending':int(x.rank(method='min').iloc[0]),'project_minus_seed0_joint_mean':effect,'effect_over_joint_seed_sd':effect/x.std(ddof=1),'project_mean_minus_joint_seed_mean':wide.project_disjoint.mean()-x.mean(),'project_draw_sd_seed0':wide.project_disjoint.std(ddof=1)})
    pd.DataFrame(paired).to_csv(out/'paired_ap_contrasts.csv',index=False)
    pd.DataFrame(panel).to_csv(out/'main_ap_summary.csv',index=False)
    pd.DataFrame(seed).to_csv(out/'seed_comparison.csv',index=False)
    pd.DataFrame([{'test_n':1082,'proxy_positive':21,'review_budget':b,'random_expected_findings':b*21/1082,'random_expected_recall':b/1082,'random_expected_precision':21/1082} for b in [54,108,216]]).to_csv(out/'random_review_reference.csv',index=False)
    inventory=pd.read_csv(PILOT/'source_inventory.csv').set_index('file_id',drop=False)
    projection=pd.read_csv(PROJECTION).set_index('file_id',drop=False)
    nodes=pd.read_csv(GRAPH/'nodes.csv').fillna('');edges=pd.read_csv(GRAPH/'edges.csv')
    assert not inventory.path.duplicated().any() and not nodes.path.duplicated().any()
    node_by_path=dict(zip(nodes.path,nodes.node_id));node_to_file={node_by_path[row.path]:row.file_id for row in inventory.itertuples(index=False)}
    for row in inventory.itertuples(index=False):
        n=nodes[nodes.node_id.eq(node_by_path[row.path])].iloc[0]
        if n.file_sha256!=row.file_sha256:raise ValueError('Node/source inventory identity mismatch')
    source_hash=dict(zip(inventory.file_id,inventory.file_sha256));project=dict(zip(inventory.file_id,inventory['group']))
    near=defaultdict(set)
    # Equality/project groups are complete conceptual relations, not their storage stars.
    for row in edges[edges.edge_type.eq('normalized_shingle')&edges.jaccard.ge(.8)&(~edges.address_expanded_only)].itertuples():
        if row.left in node_to_file and row.right in node_to_file:
            a,b=node_to_file[row.left],node_to_file[row.right];near[a].add(b);near[b].add(a)
    jobs=[j for j in config['jobs'] if j['panel']=='training_draw']
    test_ids=np.array(jobs[0]['test_ids'],dtype=int)
    assert len(test_ids)==1082 and all(j['test_ids']==test_ids.tolist() for j in jobs)
    labels=None;label_info={'available':False}
    if args.labels_root:
        labels,n_annotations=read_labels(inventory.reset_index(drop=True),args.labels_root)
        label_info={'available':True,'annotations_verified':n_annotations,'test_reentrancy_positive':sum(labels[i]['reentrancy'] for i in test_ids),'test_unchecked_positive':sum(labels[i]['unchecked'] for i in test_ids),'population_reentrancy_positive':sum(v['reentrancy'] for v in labels.values()),'population_unchecked_positive':sum(v['unchecked'] for v in labels.values())}
        assert label_info['test_reentrancy_positive']==21
    categories={};rows=[]
    for job in jobs:
        key=(job['draw'],job['regime'])
        if key in categories:continue
        train=set(job['train_ids']);train_projects={project[i] for i in train};train_hashes={source_hash[i] for i in train}
        group_sets={g:set(projection.loc[list(train),g]) for g in ['A_observed','B_historical_legacy','C_uncapped_reference_legacy']}
        flags=[]
        for fid in test_ids:
            dp=project[fid] in train_projects;dc=source_hash[fid] in train_hashes or bool(near[fid]&train)
            ca=projection.loc[fid,'A_observed'] in group_sets['A_observed'];cb=projection.loc[fid,'B_historical_legacy'] in group_sets['B_historical_legacy'];cc=projection.loc[fid,'C_uncapped_reference_legacy'] in group_sets['C_uncapped_reference_legacy']
            assert not ((dp or dc) and not cb) and not (cb and not cc)
            category='direct_union' if dp or dc else 'B_transitive_only' if cb else 'newly_connected_C' if cc else 'disconnected_C'
            row={'draw':job['draw'],'regime':job['regime'],'file_id':int(fid),'direct_project':dp,'direct_clone':dc,'A_connected':ca,'B_connected':cb,'C_connected':cc,'connection_class':category}
            if labels:row.update(labels[fid])
            flags.append(row);rows.append(row)
        categories[key]=pd.DataFrame(flags).set_index('file_id').loc[test_ids]
    flags=pd.DataFrame(rows);flags.to_csv(out/'test_training_connection_classes.csv',index=False)
    summary=flags.groupby(['draw','regime','connection_class'],as_index=False).agg(n_test=('file_id','size'),n_direct_project=('direct_project','sum'),n_direct_clone=('direct_clone','sum'))
    if labels:summary=summary.merge(flags.groupby(['draw','regime','connection_class'],as_index=False).agg(n_reentrancy_positive=('reentrancy','sum'),n_unchecked_positive=('unchecked','sum')))
    summary.to_csv(out/'connection_counts.csv',index=False)
    metric_rows=[];used_predictions={}
    if labels:
        y=np.array([labels[int(i)]['reentrancy'] for i in test_ids])
        for job in jobs:
            path=RUN/'fits'/job['job_id']/'result.json';result=json.loads(path.read_text());predpath=path.parent/result['predictions_path']
            expected=result['artifact_hashes'][result['predictions_path']]
            if sha(predpath)!=expected:raise ValueError('Prediction checksum mismatch')
            used_predictions[str(predpath.relative_to(ROOT))]=expected
            pred=pd.read_csv(predpath,float_precision='round_trip').set_index('file_id').loc[test_ids]
            score=pred.score.to_numpy();assert np.isfinite(score).all()
            original=ranking[ranking.job_id.eq(job['job_id'])].iloc[0].ap_proxy
            if not np.isclose(average_precision_score(y,score),original,rtol=0,atol=1e-14):raise ValueError('Original AP not reproduced')
            cf=categories[(job['draw'],job['regime'])]
            weights={b:expected_review(score,b) for b in [54,108,216]}
            for category in ['direct_union','B_transitive_only','newly_connected_C','disconnected_C']:
                mask=cf.connection_class.eq(category).to_numpy();k=int(y[mask].sum());n=int(mask.sum())
                row={'job_id':job['job_id'],'draw':job['draw'],'regime':job['regime'],'method':job['method'],'connection_class':category,'n_test':n,'n_positive':k,'within_class_ap':float(average_precision_score(y[mask],score[mask])) if k else None,'ap_status':'defined' if k else 'undefined_no_positives','prevalence':k/n if n else None}
                for b,w in weights.items():
                    row[f'full_test_review_{b}_slots_in_class']=float(w[mask].sum());row[f'full_test_review_{b}_findings_in_class']=float((w[mask]*y[mask]).sum())
                metric_rows.append(row)
            for b,w in weights.items():
                old=workload[workload.job_id.eq(job['job_id'])&workload.review_count_requested.eq(b)].iloc[0].known_positive_reviewed_expected
                if not np.isclose(np.sum(w*y),old,rtol=0,atol=1e-12):raise ValueError('Original full-test review yield not reproduced')
        pd.DataFrame(metric_rows).to_csv(out/'connection_conditioned_metrics.csv',index=False)
    evidence={'schema':'posthoc_model_graph_linkage_completed_v1','plan_sha256':sha(HERE/'PLAN_BEFORE_ANALYSIS.json'),'analysis_source_sha256':sha(__file__),'new_fits':0,'external_scores':0,'direct_graph':'legacy normalized-shingle >=0.8 plus conceptual exact-byte/project equivalence','connection_class_order':['direct_union','B_transitive_only','newly_connected_C','disconnected_C'],'labels':label_info,'logical_main_evaluations':len(jobs),'distinct_draw_regime_cells':len(categories),'distinct_training_memberships':len({j['training_membership_sha256'] for j in jobs}),'prediction_artifacts_verified':len(used_predictions),'input_hashes':plan['inputs'],'prediction_hashes':used_predictions,'interpretation':'post-hoc association and design diagnostics; no causal leakage effect, semantic validity, equality/equivalence test or new-family confidence interval','outputs':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
    dump(out/'RESULT.json',evidence)
    print(json.dumps({k:v for k,v in evidence.items() if k not in ['input_hashes','prediction_hashes','outputs']},indent=2))


if __name__=='__main__':main()
