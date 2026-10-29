#!/usr/bin/env python3
"""Post-review graph controls: metadata only; no labels or model scores used."""
from pathlib import Path
import argparse, csv, hashlib, heapq, json, time
from collections import defaultdict
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'papers/security_evaluation'
OUT = Path(__file__).resolve().parent
INPUTS = {
 'projection': BASE/'dependency_audit/graph_scope_ablation_recovered_20261025/historical_projection.csv',
 'legacy_nodes': BASE/'dependency_audit/legacy_recovered_20261025/nodes.csv',
 'legacy_edges': BASE/'dependency_audit/legacy_recovered_20261025/edges.csv',
 'corrected_nodes': BASE/'dependency_audit/string_aware_recovered_20261025/nodes.csv',
 'corrected_edges': BASE/'dependency_audit/string_aware_recovered_20261025/edges.csv',
 'seed2': BASE/'design_feasibility/selected_outside_p90_seed2_recovered_v2/selected_memberships.csv.gz',
 'seed4': BASE/'design_feasibility/selected_outside_p90_seed4_recovered_v2/selected_memberships.csv.gz',
 'model': BASE/'runs/dev_fixed_t_20261025_v1/memberships.csv',
 'original_summary': BASE/'dependency_audit/graph_scope_ablation_recovered_20261025/fixed_test_feasibility.csv',
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,data): p.write_text(json.dumps(data,indent=2)+'\n')
def csvout(p,rows):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def plan():
 target=OUT/'PLAN_BEFORE_COMPUTATION.json'
 if target.exists(): raise FileExistsError(target)
 dump(target,{'schema':'post_review_graph_mechanics_v1','date':'2026-10-28',
 'purpose':'Explain original eligibility losses and add label-blind post-review sensitivities; not externally preregistered or confirmatory.',
 'inputs':{str(p.relative_to(ROOT)):sha(p) for p in INPUTS.values()},'script_sha256':sha(Path(__file__)),
 'test_controls':{'seeds':list(range(1301,1311)),'size':1062,'frames':['all_historical_dappscan','outside_historical_giant','inside_historical_giant'],
 'ranking':'ascending SHA256(UTF8(article1-r4-labelblind-v1:SEED:PATH)), path tie-break; same rank over each frame; no labels or outcomes'},
 'old_tests':['outside_p90_seed2','outside_p90_seed4','historical_model_test_1082'],
 'graphs':['A_observed','B_historical_legacy','C_uncapped_reference_legacy','D_with_candidate_legacy','B_historical_string_aware','C_uncapped_reference_string_aware','D_with_candidate_string_aware'],
 'witness_method':'Contract B components; keep added C\\B files individually; represent each project/raw-equality group as a zero-cost hub, preserving conceptual cliques. Lexical pairs J>=0.8. Find minimum-added-file paths from old giant to newly joined old test components, tie-break by minimum hops then deterministic vertex order. Union is a sufficient witness, not a minimum cut or minimum-cardinality simultaneous connector.',
 'guardrails':['no source rescoring','no label or score selection','no model fitting','no modification of historical evidence']})
 print(target)
def run():
 cfg=json.loads((OUT/'PLAN_BEFORE_COMPUTATION.json').read_text()); assert cfg['script_sha256']==sha(Path(__file__))
 for p,h in cfg['inputs'].items(): assert sha(ROOT/p)==h,p
 destination=OUT/'run_20261028_v1';destination.mkdir(exist_ok=False); start=time.monotonic()
 p=pd.read_csv(INPUTS['projection']);s=p[p.dataset=='dappscan'].copy().set_index('path'); assert len(s)==6587
 oldgiant=int(s.A_observed.value_counts().idxmax());giant=set(s.index[s.A_observed==oldgiant]);assert len(giant)==5408
 tests={}
 for seed in (2,4):
  m=pd.read_csv(INPUTS[f'seed{seed}'],usecols=['path','role']);tests[f'outside_p90_seed{seed}']=set(m.loc[m.role=='test','path'])
 m=pd.read_csv(INPUTS['model'],usecols=['path','role']);tests['historical_model_test_1082']=set(m.loc[m.role=='test','path'])
 fixed_names=list(tests)
 frames={'all_historical_dappscan':set(s.index),'outside_historical_giant':set(s.index)-giant,'inside_historical_giant':giant}
 testmeta={name:{'kind':'historical_selected' if name.startswith('outside') else 'historical_model','frame':'outside_historical_giant' if name.startswith('outside') else 'inside_historical_giant','seed':''} for name in fixed_names}
 memberships=[]
 for frame,paths in frames.items():
  for seed in cfg['test_controls']['seeds']:
   rank=sorted(paths,key=lambda path:(hashlib.sha256(f'article1-r4-labelblind-v1:{seed}:{path}'.encode()).hexdigest(),path))
   name=f'{frame}_seed{seed}';tests[name]=set(rank[:1062]);testmeta[name]={'kind':'post_review_labelblind','frame':frame,'seed':seed}
   for i,path in enumerate(rank[:1062]):memberships.append({'test_id':name,'path':path,'rank':i,'seed':seed,'frame':frame})
 csvout(destination/'labelblind_test_memberships.csv',memberships)
 rows=[];lossrows=[]
 for name,paths in tests.items():
  assert paths<=set(s.index); eligible={}
  for graph in cfg['graphs']:
   tc=set(s.loc[sorted(paths),graph]);a=set(s.index[~s[graph].isin(tc)]);eligible[graph]=a
   sizes=s.loc[sorted(paths),graph].value_counts();fullgiant=int(s[graph].value_counts().idxmax())
   rows.append({'test_id':name,**testmeta[name],'graph':graph,'test_files':len(paths),'test_in_historical_giant':len(paths&giant),
    'test_in_current_giant':int(s.loc[sorted(paths),graph].eq(fullgiant).sum()),'test_components':len(sizes),'largest_test_component_files':int(sizes.max()),
    'eligible_training_files':len(a),'historical_giant_eligible':len(a&giant)})
  for normalizer in ['legacy','string_aware']:
   a=eligible['A_observed'];b=eligible[f'B_historical_{normalizer}'];c=eligible[f'C_uncapped_reference_{normalizer}'];d=eligible[f'D_with_candidate_{normalizer}']; assert c<=b and d<=c
   lost=b-c
   lossrows.append({'test_id':name,**testmeta[name],'normalizer':normalizer,'A_eligible':len(a),'B_eligible':len(b),'C_eligible':len(c),'D_eligible':len(d),
    'B_C_lost_total':len(lost),'B_C_lost_historical_giant':len(lost&giant),'B_C_lost_other':len(lost-giant),
    'test_files_joining_historical_giant_component':int(s.loc[sorted(paths),f'C_uncapped_reference_{normalizer}'].isin(set(s.loc[sorted(giant),f'C_uncapped_reference_{normalizer}'])).sum()),
    'B_C_any_gain':len(c-b),'C_D_additional_loss':len(c-d)})
 csvout(destination/'all_test_feasibility.csv',rows);csvout(destination/'eligibility_loss_decomposition.csv',lossrows)
 old=pd.read_csv(INPUTS['original_summary']);new=pd.DataFrame(rows)
 for row in old.itertuples():
  n=new[(new.test_id==row.test_id)&(new.graph==row.graph)].iloc[0]
  assert n.eligible_training_files==row.joint_raw_train_files
  assert n.largest_test_component_files==row.largest_test_component_files
 # Build C as a quotient of complete B components. Hubs avoid star-anchor path artifacts.
 witnessrows=[];witnessfiles=[]; witnesssummary=[]
 for norm,key in [('legacy','legacy'),('string_aware','corrected')]:
  nodes=pd.read_csv(INPUTS[key+'_nodes'],keep_default_na=False);edges=pd.read_csv(INPUTS[key+'_edges'])
  nodes=nodes[nodes.scope=='upstream'].copy(); ids=set(nodes.node_id);hist=p.set_index('path')[f'B_historical_{norm}'];cpart=p.set_index('path')[f'C_uncapped_reference_{norm}']
  mapping={int(n.node_id):('old:'+str(hist[n.path]) if n.path in hist.index else 'new:'+str(n.node_id)) for n in nodes.itertuples()}
  adj=defaultdict(set)
  def link(a,b):
   if a!=b:adj[a].add(b);adj[b].add(a)
  for n in mapping.values(): adj[n]
  for row in edges[(edges.edge_type=='normalized_shingle')&edges.jaccard.ge(.8)&edges.left.isin(ids)&edges.right.isin(ids)].itertuples():link(mapping[int(row.left)],mapping[int(row.right)])
  for field in ['project_id','file_sha256']:
   for value,g in nodes[nodes[field].ne('')].groupby(field,sort=True):
    members=set(mapping[int(i)] for i in g.node_id)
    if len(members)>1:
     hub=f'hub:{field}:{value}'
     for v in members:link(hub,v)
  # Verify the quotient graph exactly reproduces saved C on all historical files.
  comps={};ncomp=0
  for vertex in sorted(adj):
   if vertex in comps:continue
   comps[vertex]=ncomp;stack=[vertex]
   while stack:
    v=stack.pop()
    for w in adj[v]:
     if w not in comps:comps[w]=ncomp;stack.append(w)
   ncomp+=1
  check=pd.DataFrame({'saved':cpart,'built':['x'+str(comps['old:'+str(hist[path])]) for path in cpart.index]},index=cpart.index)
  assert check.groupby('saved').built.nunique().max()==1 and check.groupby('built').saved.nunique().max()==1
  rootold=set(hist.loc[sorted(giant)]);assert len(rootold)==1;root='old:'+str(next(iter(rootold)))
  # Deterministic Dijkstra: each newly admitted file costs one on entry; hubs and old components cost zero.
  distance={root:(0,0)};parent={};q=[(0,0,root)]
  while q:
   cost,hops,v=heapq.heappop(q)
   if distance.get(v)!=(cost,hops):continue
   for w in sorted(adj[v]):
    candidate=(cost+int(w.startswith('new:')),hops+1)
    if w not in distance or candidate<distance[w]:distance[w]=candidate;parent[w]=v;heapq.heappush(q,(*candidate,w))
  lookup=nodes.set_index('node_id');outside=set(int(k.split(':')[1]) for k,v in comps.items() if k.startswith('new:') and v==comps[root])
  for name in fixed_names[:2]:
   paths=tests[name];targets=sorted(set('old:'+str(hist[path]) for path in paths if 'old:'+str(hist[path]) in distance))
   used=set();costs=[];wpaths=[]
   for target in targets:
    walk=[target]
    while walk[-1]!=root:walk.append(parent[walk[-1]])
    walk.reverse();newids=[int(v.split(':')[1]) for v in walk if v.startswith('new:')];assert len(newids)==distance[target][0]
    used.update(newids);costs.append(len(newids));wpaths.append(walk)
    witnessrows.append({'normalizer':norm,'test_id':name,'old_test_component':target,'test_files_in_old_component':sum('old:'+str(hist[path])==target for path in paths),
     'minimum_added_files':len(newids),'hops':len(walk)-1,'path_vertices':json.dumps(walk),'added_node_ids':json.dumps(newids)})
   allowed={v for v in adj if not v.startswith('new:')}|{f'new:{i}' for i in used}
   reached={root};queue=[root]
   while queue:
    v=queue.pop()
    for w in adj[v]:
     if w in allowed and w not in reached:reached.add(w);queue.append(w)
   assert set(targets)<=reached
   for i in sorted(used):
    row=lookup.loc[i];witnessfiles.append({'normalizer':norm,'test_id':name,'node_id':i,'path':row.path,'file_sha256':row.file_sha256,'project_id':row.project_id})
   witnesssummary.append({'normalizer':norm,'test_id':name,'newly_joined_old_test_components':len(targets),'test_files_in_joined_components':sum(sum('old:'+str(hist[path])==t for path in paths) for t in targets),
    'added_files_in_full_giant':len(outside),'minimum_added_files_per_target_min':min(costs),'minimum_added_files_per_target_max':max(costs),'sufficient_witness_union_added_files':len(used),
    'witness_union_reconnects_all_targets':True,'minimum_simultaneous_connector_claim':False,'new_graph_matches_saved_C_partition':True})
 csvout(destination/'outside_population_witness_paths.csv',witnessrows);csvout(destination/'outside_population_witness_files.csv',witnessfiles);csvout(destination/'outside_population_witness_summary.csv',witnesssummary)
 result={'schema':'post_review_graph_mechanics_result_v1','status':'complete','plan_sha256':sha(OUT/'PLAN_BEFORE_COMPUTATION.json'),'script_sha256':sha(Path(__file__)),
 'historical_dappscan_files':len(s),'historical_giant_files':len(giant),'historical_fixed_tests':3,'new_labelblind_controls':30,'graph_variants':len(cfg['graphs']),
 'all_test_graph_outcomes':len(rows),'original_fixed_test_feasibility_reproduced':True,'witness_summaries':witnesssummary,'no_labels_or_scores_used_in_selection':True,
 'runtime_seconds':time.monotonic()-start,'outputs':{x.name:sha(x) for x in destination.glob('*.csv')}}
 dump(destination/'RESULT.json',result)
 print(json.dumps(result,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['plan','run']);args=ap.parse_args();plan() if args.action=='plan' else run()
