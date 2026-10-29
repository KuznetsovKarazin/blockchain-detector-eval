#!/usr/bin/env python3
"""Label-blind whole-project coverage control using saved exhaustive edges."""
from pathlib import Path
import argparse, hashlib, json, time
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
ROOT=Path(__file__).resolve().parents[4]; BASE=ROOT/'papers/security_evaluation'; OUT=Path(__file__).resolve().parent
INPUTS={
 'legacy_nodes':BASE/'dependency_audit/legacy_recovered_20261025/nodes.csv',
 'legacy_edges':BASE/'dependency_audit/legacy_recovered_20261025/edges.csv',
 'string_aware_nodes':BASE/'dependency_audit/string_aware_recovered_20261025/nodes.csv',
 'string_aware_edges':BASE/'dependency_audit/string_aware_recovered_20261025/edges.csv',
 'original_curves':BASE/'revision1/graph_mechanism/run_20261025_v1/component_curves.csv'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def plan():
 p=OUT/'PROJECT_COVERAGE_PLAN_BEFORE_COMPUTATION.json'; assert not p.exists()
 dump(p,{'schema':'whole_project_coverage_control_v1','date':'2026-10-28','status':'plan_written_before_new_computation; post-review sensitivity, not external preregistration',
 'script_sha256':sha(Path(__file__)),'inputs':{str(p.relative_to(ROOT)):sha(p) for p in INPUTS.values()},
 'seeds':list(range(1301,1306)),'project_prefix_percentages':list(range(10,100,10)),
 'ranking':'SHA256(UTF8(revision2-project|SEED|PROJECT_ID)), project-id tie break; floor(percent * 608 / 100)',
 'population':'All files of each selected DAppSCAN project plus all493 other reference files; full21950 commonendpoint',
 'normalizers':['legacy','string_aware'],'thresholds':[.8,1.0],'policies':['project_only','clone_only','joint'],
 'selection_uses_labels':False,'denominators':'Component concentration within sampledDAppSCAN; also report coverage against21457files and608projects; never treat absentSfiles as isolated observedvertices',
 'comparison':'Published file-prefix rows from the original run, same threshold/normalizer/policy; no matching of realised file counts or statistical inference'})
 print(p)
def stars(nodes,selected,field):
 a=[];b=[]
 for _,g in nodes.loc[selected].query(f'{field} != ""').groupby(field):
  ids=sorted(g.node_id);a.extend([ids[0]]*(len(ids)-1));b.extend(ids[1:])
 return np.array(a,dtype=int),np.array(b,dtype=int)
def run():
 cfg=json.loads((OUT/'PROJECT_COVERAGE_PLAN_BEFORE_COMPUTATION.json').read_text());assert cfg['script_sha256']==sha(Path(__file__))
 for path,h in cfg['inputs'].items():assert sha(ROOT/path)==h
 out=OUT/'project_coverage_20261028_v1';out.mkdir(exist_ok=False);start=time.monotonic();rows=[];ranks=[]
 for normal in cfg['normalizers']:
  nodes=pd.read_csv(INPUTS[normal+'_nodes'],keep_default_na=False).set_index('node_id',drop=False);assert len(nodes)==24131
  dapp=nodes[nodes.dataset=='dappscan'];assert len(dapp)==21457
  other=nodes[(nodes.scope=='upstream')&(nodes.dataset!='dappscan')].node_id.to_numpy();assert len(other)==493
  projects=sorted(dapp.project_id.unique());assert len(projects)==608
  e=pd.read_csv(INPUTS[normal+'_edges']);e=e[e.edge_type=='normalized_shingle']; assert e.jaccard.ge(.7).all()
  cohorts=[('complete',-1,100,set(projects))]
  for seed in cfg['seeds']:
   rank=sorted(projects,key=lambda p:(hashlib.sha256(f'revision2-project|{seed}|{p}'.encode()).digest(),p))
   if normal=='legacy':ranks.extend({'seed':seed,'rank':i+1,'project_id':p,'project_files':int((dapp.project_id==p).sum())} for i,p in enumerate(rank))
   for pct in cfg['project_prefix_percentages']:cohorts.append((f'whole_project_seed{seed}_{pct:03d}',seed,pct,set(rank[:len(rank)*pct//100])))
  for name,seed,pct,selected_projects in cohorts:
   sd=dapp.loc[dapp.project_id.isin(selected_projects),'node_id'].to_numpy();selected=np.sort(np.r_[sd,other]);chosen=np.zeros(len(nodes),bool);chosen[selected]=True
   lexical=e[chosen[e.left.to_numpy()]&chosen[e.right.to_numpy()]];project=stars(nodes,selected,'project_id');raw=stars(nodes,selected,'file_sha256'); previous={}
   for threshold in cfg['thresholds']:
    le=lexical[lexical.jaccard.ge(threshold)];lex=(le.left.to_numpy(),le.right.to_numpy())
    for policy in cfg['policies']:
     pairs=[project] if policy=='project_only' else [raw,lex] if policy=='clone_only' else [project,raw,lex]
     left=np.concatenate([p[0] for p in pairs]);right=np.concatenate([p[1] for p in pairs]);adj=coo_matrix((np.ones(len(left),np.int8),(left,right)),shape=(len(nodes),len(nodes))).tocsr();_,labels=connected_components(adj,directed=False)
     sizes=np.unique(labels[sd],return_counts=True)[1]
     if policy in previous:
      chk=pd.DataFrame({'current':labels[selected],'previous':previous[policy]});assert chk.groupby('current').previous.nunique().max()==1
     previous[policy]=labels[selected]
     rows.append({'normalization':normal,'cohort':name,'policy':policy,'threshold':threshold,'seed':seed,'nominal_project_percent':pct,
      'dapp_files':len(sd),'dapp_file_coverage_fraction':len(sd)/21457,'projects':len(selected_projects),'project_coverage_fraction':len(selected_projects)/608,
      'all_population_files':len(selected),'components':len(sizes),'giant_files':int(sizes.max()),'giant_fraction_sampled_files':float(sizes.max()/len(sd)),
      'giant_fraction_full_corpus':float(sizes.max()/21457),'effective_components':float(len(sd)**2/np.dot(sizes.astype(float),sizes))})
 df=pd.DataFrame(rows);df.to_csv(out/'whole_project_curves.csv',index=False);pd.DataFrame(ranks).to_csv(out/'whole_project_rankings.csv',index=False)
 original=pd.read_csv(INPUTS['original_curves']);comparison=[]
 for row in df[df.cohort=='complete'].itertuples():
  old=original[(original.cohort=='full_upstream_21950')&(original.normalization==row.normalization)&(original.policy==row.policy)&(original.threshold==row.threshold)].iloc[0]
  assert old.giant_files==row.giant_files and old.components==row.components
 for normal in cfg['normalizers']:
  for threshold in cfg['thresholds']:
   for policy in cfg['policies']:
    for pct in cfg['project_prefix_percentages']:
     new=df[(df.normalization==normal)&(df.threshold==threshold)&(df.policy==policy)&(df.nominal_project_percent==pct)]
     old=original[(original.normalization==normal)&(original.threshold==threshold)&(original.policy==policy)&(original.dapp_percent==pct)&(original.seed>=0)]
     assert len(new)==len(old)==5
     comparison.append({'normalization':normal,'threshold':threshold,'policy':policy,'nominal_coverage_percent':pct,
      'file_sampling_giant_fraction_mean':old.giant_fraction.mean(),'file_sampling_giant_fraction_min':old.giant_fraction.min(),'file_sampling_giant_fraction_max':old.giant_fraction.max(),
      'file_sampling_projects_mean':old.project_groups_represented.mean(),'file_sampling_files_mean':old.files.mean(),
      'project_sampling_giant_fraction_mean':new.giant_fraction_sampled_files.mean(),'project_sampling_giant_fraction_min':new.giant_fraction_sampled_files.min(),'project_sampling_giant_fraction_max':new.giant_fraction_sampled_files.max(),
      'project_sampling_projects':int(new.projects.iloc[0]),'project_sampling_files_mean':new.dapp_files.mean(),'project_sampling_files_min':int(new.dapp_files.min()),'project_sampling_files_max':int(new.dapp_files.max())})
 pd.DataFrame(comparison).to_csv(out/'file_vs_project_sampling.csv',index=False)
 dump(out/'RESULT.json',{'schema':'whole_project_coverage_result_v1','status':'complete','plan_sha256':sha(OUT/'PROJECT_COVERAGE_PLAN_BEFORE_COMPUTATION.json'),
 'script_sha256':sha(Path(__file__)),'new_graph_outcomes':len(rows),'ranked_project_rows':len(ranks),'comparison_rows':len(comparison),'full_population_endpoints_match_published':True,
 'selection_uses_labels':False,'model_fits':0,'runtime_seconds':time.monotonic()-start,'output_sha256':{p.name:sha(p) for p in out.glob('*.csv')}})
 print(df[(df.normalization=='legacy')&(df.threshold==.8)&(df.policy=='joint')].groupby('nominal_project_percent')[['dapp_files','giant_fraction_sampled_files']].agg(['mean','min','max']).to_string())
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['plan','run']);a=ap.parse_args();plan() if a.action=='plan' else run()
