#!/usr/bin/env python3
"""Independent union-find reconstruction, nested-sample checks, fixed external T."""
import argparse, collections, hashlib, json, shutil, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'src'))
from bal.data.contracts import load_all,label_files
from run_mechanism import THRESHOLDS,SEEDS,POLICIES,dump,sha,saveframe

class UF:
    def __init__(self,n):self.p=np.arange(n,dtype=np.int32)
    def find(self,x):
        while self.p[x]!=x:self.p[x]=self.p[self.p[x]];x=int(self.p[x])
        return x
    def join(self,x,y):
        x,y=self.find(x),self.find(y)
        if x!=y:self.p[max(x,y)]=min(x,y)

def groups_join(u,nodes,field,scope=None):
    buckets={}
    for row in nodes.itertuples():
        if scope is not None and row.scope!=scope:continue
        value=getattr(row,field)
        if value:
            if value in buckets:u.join(buckets[value],row.node_id)
            else:buckets[value]=row.node_id

def pair_differences(x,y):
    q=pd.DataFrame({'a':x,'b':y});a=q.a.value_counts();b=q.b.value_counts();both=q.groupby(['a','b']).size()
    same=lambda counts:int(sum(int(z)*(int(z)-1)//2 for z in counts))
    return dict(canonical_representative_changes=int(np.sum(x!=y)),old_components_split=int((q.groupby('a').b.nunique()>1).sum()),
      new_components_merging_multiple_old=int((q.groupby('b').a.nunique()>1).sum()),same_component_pair_disagreements=same(a)+same(b)-2*same(both))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.run=a.run.resolve();a.out.mkdir(exist_ok=False);start=time.monotonic()
    base=ROOT/'papers/security_evaluation/dependency_audit';nodefile=base/'legacy_recovered_20261025/nodes.csv'
    nodes=pd.read_csv(nodefile,keep_default_na=False).set_index('node_id',drop=False)
    private=ROOT/'data/derived/security_external_recovered_20261025/provisional_label_manifest.csv'
    inputs=[nodefile,a.run/'config_before_compute.json',a.run/'population_ranks.csv.gz',*sorted(a.run.glob('memberships_*.csv.gz')),
      *[base/f'{n}_recovered_20261025/edges.csv' for n in ['legacy','string_aware']],private]
    code=[Path(__file__),Path(__file__).with_name('run_mechanism.py'),ROOT/'src/bal/data/contracts.py']
    cfg=dict(schema='graph_mechanism_independent_check_v1',input_sha256={str(p.relative_to(ROOT)):sha(p) for p in inputs},
      code_sha256={str(p.relative_to(ROOT)):sha(p) for p in code},label_input_sha256={str(p):sha(ROOT/p) for p in label_files()},
      independent_reconstruction='union-find, group membership bucket joins generated independently of scipy generator; exhaustive saved lexical pairs reused, not independently regenerated',
      checked_thresholds=[.7,.8,.95,1.0],fixed_external_test='candidate_test flag from frozen fullgraph metadata = diagnostic1998; no eligibility or ground-truth claim',
      training_scope='historical6587DAppSCAN only, zero means no published finding',no_model_scores=True)
    dump(a.out/'config_before_verify.json',cfg)
    for p in code:shutil.copy2(p,a.out/p.name)
    ranks=pd.read_csv(a.run/'population_ranks.csv.gz');dapp=nodes.index[nodes.dataset.eq('dappscan')].to_numpy();assert len(dapp)==21457
    for seed in SEEDS:
        expected=sorted(dapp,key=lambda i:hashlib.sha256(f'revision1|{seed}|{nodes.at[i,"path"]}'.encode()).digest())
        actual=ranks[ranks.seed.eq(seed)].sort_values('rank').node_id.tolist();assert expected==actual and len(set(actual))==21457
    reports=[];comparisons=[]
    cohorts=['historical_7080','full_dappscan_21457','full_upstream_21950','full_combined_24131']
    for normal in ['legacy','string_aware']:
        edge=pd.read_csv(base/f'{normal}_recovered_20261025/edges.csv');edge=edge[edge.edge_type.eq('normalized_shingle')]
        for cohort in cohorts:
            m=pd.read_csv(a.run/f'memberships_{normal}_{cohort}.csv.gz').set_index('node_id');selected=set(m.index);sub=nodes.loc[m.index]
            e=edge[edge.left.isin(selected)&edge.right.isin(selected)]
            for threshold in [.7,.8,.95,1.0]:
                le=e[e.jaccard.ge(threshold)]
                for policy in POLICIES:
                    u=UF(len(nodes))
                    if policy!='clone_only':groups_join(u,sub,'project_id','upstream');groups_join(u,sub,'identifier_key','external')
                    if policy!='project_only':
                        groups_join(u,sub,'file_sha256')
                        for left,right in zip(le.left,le.right):u.join(int(left),int(right))
                    result=np.array([u.find(int(i)) for i in m.index]);column=f'{policy}_{round(threshold*100):03d}'
                    assert np.array_equal(result,m[column].to_numpy())
                    reports.append(dict(normalization=normal,cohort=cohort,threshold=threshold,policy=policy,status='pass',selected_nodes=len(m)))
            if normal=='legacy':
                corrected=pd.read_csv(a.run/f'memberships_string_aware_{cohort}.csv.gz').set_index('node_id')
                for column in m.columns:
                    comparisons.append(dict(cohort=cohort,partition=column,**pair_differences(m[column].to_numpy(),corrected[column].to_numpy())))
    saveframe(a.out/'independent_union_find_checks.csv',pd.DataFrame(reports));saveframe(a.out/'normalizer_partition_comparison.csv',pd.DataFrame(comparisons))
    full=load_all().set_index('path');hid=nodes.index[nodes.historical_train & nodes.dataset.eq('dappscan')].to_numpy()
    y=full.loc[nodes.loc[hid,'path'],['reentrancy','unchecked']].to_numpy();tids=nodes.index[nodes.candidate_test].to_numpy();assert len(tids)==1998
    lab=pd.read_csv(private);pmap={c:set(lab[(lab['class']==c)&lab.label_status.eq('source_reported_positive_pending_adjudication')].path) for c in ['reentrancy','unchecked']}
    rows=[]
    for normal in ['legacy','string_aware']:
        m=pd.read_csv(a.run/f'memberships_{normal}_full_combined_24131.csv.gz').set_index('node_id')
        for policy in POLICIES:
            for t in THRESHOLDS:
                cp=m[f'{policy}_{round(t*100):03d}'];tc=set(cp.loc[tids]);keep=~cp.loc[hid].isin(tc).to_numpy();tr=hid[keep]
                for j,cls in enumerate(['reentrancy','unchecked']):
                    positive=int(y[keep,j].sum());epos=[i for i in tids if nodes.at[i,'path'] in pmap[cls]]
                    rows.append(dict(normalization=normal,policy=policy,threshold=t,**{'class':cls},candidate_test_files=len(tids),
                      candidate_source_reported_positive_files=len(epos),candidate_positive_components=cp.loc[epos].nunique(),candidate_components=len(tc),
                      historical_dapp_train_files=len(tr),train_proxy_positive=positive,train_proxy_zero=len(tr)-positive,train_components=cp.loc[tr].nunique(),
                      positive_train_components=cp.loc[tr[y[keep,j]==1]].nunique(),two_proxy_classes=0<positive<len(tr)))
    ext=pd.DataFrame(rows);assert set(ext[(ext.policy=='joint')&(ext.threshold==.8)].historical_dapp_train_files)=={691}
    saveframe(a.out/'external_fixed_test_feasibility.csv',ext)
    dump(a.out/'summary.json',dict(status='passed',union_find_graph_checks=len(reports),all5_nested_hash_rankings_verified=True,
      external_fixed_test_cases=len(rows),runtime_seconds=time.monotonic()-start,config_sha256=sha(a.out/'config_before_verify.json'),
      limitation='validates partitions from recorded exhaustive pairlists, not an independent allpair source search',
      output_sha256={p.name:sha(p) for p in a.out.iterdir() if p.is_file()}))
    print('Complete',len(reports),'graph checks',flush=True)
if __name__=='__main__':main()
