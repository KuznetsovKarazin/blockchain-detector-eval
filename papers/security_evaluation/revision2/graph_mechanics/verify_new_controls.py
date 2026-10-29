#!/usr/bin/env python3
"""Separate implementations verify new metadata controls; no experiments rerun."""
from pathlib import Path
from collections import Counter,defaultdict,deque
import csv,hashlib,json,time
ROOT=Path(__file__).resolve().parents[4]; BASE=ROOT/'papers/security_evaluation';HERE=Path(__file__).resolve().parent

def read(path):
 with path.open(newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class UF:
 def __init__(self,ids):self.p={i:i for i in ids}
 def root(self,x):
  while x!=self.p[x]:self.p[x]=self.p[self.p[x]];x=self.p[x]
  return x
 def join(self,a,b):
  a,b=self.root(a),self.root(b)
  if a!=b:self.p[max(a,b)]=min(a,b)
def partition(nodes,edges,selected):
 uf=UF(selected)
 for field in ['project_id','file_sha256']:
  groups={}
  for i in sorted(selected):
   key=nodes[i][field]
   if key:
    if key in groups:uf.join(i,groups[key])
    else:groups[key]=i
 for a,b,j in edges:
  if a in selected and b in selected:uf.join(a,b)
 return uf
start=time.monotonic();projection=read(BASE/'dependency_audit/graph_scope_ablation_recovered_20261025/historical_projection.csv');S={r['path']:r for r in projection if r['dataset']=='dappscan'}
run=HERE/'run_20261028_v1';tests=defaultdict(set)
for r in read(run/'labelblind_test_memberships.csv'):tests[r['test_id']].add(r['path'])
oldgiant=Counter(r['A_observed'] for r in S.values()).most_common(1)[0][0];giant={p for p,r in S.items() if r['A_observed']==oldgiant}
for name,paths in tests.items():
 frame,seed=name.rsplit('_seed',1);pool=set(S) if frame=='all_historical_dappscan' else giant if frame=='inside_historical_giant' else set(S)-giant
 expected=set(sorted(pool,key=lambda p:(hashlib.sha256(f'article1-r4-labelblind-v1:{seed}:{p}'.encode()).hexdigest(),p))[:1062]);assert paths==expected
checks=[]
for row in read(run/'all_test_feasibility.csv'):
 if row['test_id'] not in tests:continue
 t=tests[row['test_id']];g=row['graph'];tcomps={S[p][g] for p in t};allowed={p for p,r in S.items() if r[g] not in tcomps}
 assert len(allowed)==int(row['eligible_training_files']);checks.append((row['test_id'],g))
projectrows=read(HERE/'project_coverage_20261028_v1/whole_project_curves.csv');witnessrows=read(run/'outside_population_witness_paths.csv');wf=read(run/'outside_population_witness_files.csv');wsummary=read(run/'outside_population_witness_summary.csv')
projectchecks=[];witnesschecks=[];minpathchecks=0
for norm in ['legacy','string_aware']:
 source=BASE/f'dependency_audit/{norm}_recovered_20261025';nodes={int(r['node_id']):r for r in read(source/'nodes.csv') if r['scope']=='upstream'}
 edges=[(int(r['left']),int(r['right']),float(r['jaccard'])) for r in read(source/'edges.csv') if r['edge_type']=='normalized_shingle' and float(r['jaccard'])>=.8]
 edges=[r for r in edges if r[0] in nodes and r[1] in nodes];oldids={i for i,r in nodes.items() if r['historical_train']=='True'};assert len(oldids)==7080
 projgroups=sorted({r['project_id'] for r in nodes.values() if r['dataset']=='dappscan'})
 for seed,pct,threshold in [(1301,10,.8),(1302,50,1.0),(1305,90,.8)]:
  projects=set(sorted(projgroups,key=lambda p:(hashlib.sha256(f'revision2-project|{seed}|{p}'.encode()).digest(),p))[:len(projgroups)*pct//100]);selected={i for i,r in nodes.items() if r['dataset']!='dappscan' or r['project_id'] in projects}
  uf=partition(nodes,[e for e in edges if e[2]>=threshold],selected);counts=Counter(uf.root(i) for i in selected if nodes[i]['dataset']=='dappscan')
  expected=next(r for r in projectrows if r['normalization']==norm and int(r['seed'])==seed and int(r['nominal_project_percent'])==pct and float(r['threshold'])==threshold and r['policy']=='joint')
  assert max(counts.values())==int(expected['giant_files']);assert len(counts)==int(expected['components'])
  projectchecks.append({'normalizer':norm,'seed':seed,'percent':pct,'threshold':threshold,'giant':max(counts.values()),'components':len(counts)})
 # Verify each sufficient witness on the full file graph, with union-find, without B contraction/hubs.
 node_by_path={r['path']:i for i,r in nodes.items()};anchor=node_by_path[min(giant)]
 for test in ['outside_p90_seed2','outside_p90_seed4']:
  added={int(r['node_id']) for r in wf if r['normalizer']==norm and r['test_id']==test};assert not added&oldids
  uf=partition(nodes,edges,oldids|added);expected=next(r for r in wsummary if r['normalizer']==norm and r['test_id']==test)
  import gzip
  seed=test[-1]
  with gzip.open(BASE/f'design_feasibility/selected_outside_p90_seed{seed}_recovered_v2/selected_memberships.csv.gz','rt') as f:t={r['path'] for r in csv.DictReader(f) if r['role']=='test'}
  joined=sum(uf.root(node_by_path[p])==uf.root(anchor) for p in t);assert joined==int(expected['test_files_in_joined_components'])
  assert all(uf.root(node_by_path[p])==uf.root(anchor) for p in giant)
  witnesschecks.append({'normalizer':norm,'test_id':test,'added_files':len(added),'test_files_joined':joined,'old_giant_preserved_and_joined':True})
 # Independent 0-1 BFS on the uncontracted full file graph validates minimum added-file count.
 adj={i:set() for i in nodes};hub=max(nodes)+1
 for a,b,j in edges:adj[a].add(b);adj[b].add(a)
 for field in ['project_id','file_sha256']:
  groups=defaultdict(list)
  for i,r in nodes.items():
   if r[field]:groups[r[field]].append(i)
  for ids in groups.values():
   if len(ids)<2:continue
   adj[hub]=set(ids)
   for i in ids:adj[i].add(hub)
   hub+=1
 added=set(nodes)-oldids;dist={anchor:0};q=deque([anchor])
 while q:
  u=q.popleft()
  for v in adj[u]:
   cost=int(v in added);nd=dist[u]+cost
   if v not in dist or nd<dist[v]:
    dist[v]=nd
    if cost:q.append(v)
    else:q.appendleft(v)
 bcol=f'B_historical_{norm}';byold=defaultdict(list)
 for r in projection:byold['old:'+r[bcol]].append(node_by_path[r['path']])
 for r in witnessrows:
  if r['normalizer']!=norm:continue
  assert min(dist.get(i,10**9) for i in byold[r['old_test_component']])==int(r['minimum_added_files']);minpathchecks+=1
result={'schema':'separate_implementation_graph_verification_v1','date':'2026-10-28','status':'PASS','verification_kind':'Separate algorithms by the same analysis agent; not human review or an independently collected source graph',
 'script_sha256':sha(Path(__file__)),'labelblind_hash_samples_reconstructed':len(tests),'labelblind_graph_outcomes_recomputed_by_stdlib_sets':len(checks),
 'whole_project_sampled_cases_verified_by_union_find':projectchecks,'sufficient_witness_subgraphs_verified_by_union_find':witnesschecks,'witness_minimum_added_distances_verified_by_uncontracted_01_BFS':minpathchecks,
 'runtime_seconds':time.monotonic()-start,'evidence_sha256':{str(p.relative_to(HERE)):sha(p) for p in [run/'RESULT.json',HERE/'project_coverage_20261028_v1/RESULT.json']}}
(HERE/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
