#!/usr/bin/env python3
"""Independent R5 design audit from source annotations and saved graph metadata."""
from pathlib import Path
import csv,json,hashlib,itertools,statistics
ROOT=Path(__file__).resolve().parents[4];BASE=ROOT/'papers/security_evaluation';OUT=Path(__file__).resolve().parent

def read(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvout(p,rows):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
projection_path=BASE/'dependency_audit/graph_scope_ablation_recovered_20261025/historical_projection.csv'
tests_path=BASE/'revision2/graph_mechanics/run_20261028_v1/labelblind_test_memberships.csv'
annotation_manifest=BASE/'runs/dev_fixed_t_20261025_v1/label_input_hashes.json'
project_curve=BASE/'revision2/graph_mechanics/project_coverage_20261028_v1/whole_project_curves.csv'
file_curve=BASE/'revision1/graph_mechanism/run_20261025_v1/component_curves.csv'
inputs=[projection_path,tests_path,annotation_manifest,project_curve,file_curve]
freeze=OUT/'AUDIT_INPUTS.json'
if freeze.exists():raise FileExistsError('Use a new audit directory')
freeze.write_text(json.dumps({'date':'2026-10-28','purpose':'Read-only independent design audit before R5 model fits; no model fitting or outcome-based selection','inputs':{str(p.relative_to(ROOT)):sha(p) for p in inputs},'script_sha256':sha(Path(__file__))},indent=2)+'\n')
proj=read(projection_path);S={r['path']:r for r in proj if r['dataset']=='dappscan'}
from collections import Counter,defaultdict
oldgiant=Counter(r['A_observed'] for r in S.values()).most_common(1)[0][0];giant={p for p,r in S.items() if r['A_observed']==oldgiant}
annotations=json.loads(annotation_manifest.read_text());matched={p:h for p,h in annotations.items() if p.startswith('data/raw/DAppSCAN/')}
for p,h in matched.items():assert sha(ROOT/p)==h,p
labels={}
for path,r in S.items():
 ap=ROOT/Path(path.replace('/contracts/','/SWCsource/')).with_suffix('.json')
 y={'reentrancy':0,'unchecked':0}
 if ap.exists():
  relative=str(ap.relative_to(ROOT));assert relative in matched
  data=json.loads(ap.read_text());assert data['filePath']==path.removeprefix('data/raw/DAppSCAN/')
  cats={v['category'].split('-')[1] for v in data.get('SWCs',[]) if v.get('category','').startswith('SWC-')}
  y={'reentrancy':int('107' in cats),'unchecked':int('104' in cats)}
 labels[path]=y
selected=defaultdict(set)
for r in read(tests_path):
 if r['frame']=='inside_historical_giant':selected[r['test_id']].add(r['path'])
assert len(selected)==10
selected['full_historical_giant']=giant
oldtests=read(BASE/'runs/dev_fixed_t_20261025_v1/memberships.csv');selected['original_model_test_1082']={r['path'] for r in oldtests if r['role']=='test'}
rows=[];allpools=[]
for name,t in sorted(selected.items()):
 assert t<=giant
 pools={}
 for label,col in [('B','B_historical_legacy'),('C','C_uncapped_reference_legacy')]:
  components={S[p][col] for p in t};pools[label]={p for p,r in S.items() if r[col] not in components}
 assert pools['C']<=pools['B'];linked=pools['B']-pools['C']
 rows.append({'test_id':name,'test_files':len(t),'test_reentrancy_positive':sum(labels[p]['reentrancy'] for p in t),'test_unchecked_positive':sum(labels[p]['unchecked'] for p in t),
 'B_pool_files':len(pools['B']),'B_pool_reentrancy_positive':sum(labels[p]['reentrancy'] for p in pools['B']),
 'C_pool_files':len(pools['C']),'C_pool_reentrancy_positive':sum(labels[p]['reentrancy'] for p in pools['C']),
 'C_linked_B_only_files':len(linked),'C_linked_B_only_positive':sum(labels[p]['reentrancy'] for p in linked),
 'B_pool_hash':hashlib.sha256('\n'.join(sorted(pools['B'])).encode()).hexdigest(),'C_pool_hash':hashlib.sha256('\n'.join(sorted(pools['C'])).encode()).hexdigest()})
 allpools.append(pools)
assert all(p==allpools[0] for p in allpools)
assert len(giant)==5408 and sum(labels[p]['reentrancy'] for p in giant)==83
assert all((r['B_pool_files'],r['B_pool_reentrancy_positive'],r['C_pool_files'],r['C_pool_reentrancy_positive'],r['C_linked_B_only_files'],r['C_linked_B_only_positive'])==(1179,31,708,24,471,7) for r in rows)
csvout(OUT/'giant_and_internal_tests.csv',rows)
internal={k:v for k,v in selected.items() if k.startswith('inside_historical')};overlaps=[]
for (n,a),(m,b) in itertools.combinations(sorted(internal.items()),2):overlaps.append({'test_a':n,'test_b':m,'shared_files':len(a&b),'shared_reentrancy_positives':sum(labels[p]['reentrancy'] for p in a&b),'jaccard':len(a&b)/len(a|b)})
csvout(OUT/'internal_test_overlap.csv',overlaps)
whole=read(project_curve);file=read(file_curve);coverage=[]
for norm in ['legacy','string_aware']:
 for policy in ['project_only','clone_only','joint']:
  for design,data,fracfield in [('whole_project',whole,'giant_fraction_sampled_files'),('file',file,'giant_fraction')]:
   chosen=[r for r in data if r['normalization']==norm and r['policy']==policy and float(r['threshold'])==.8 and int(r['seed'])>=0 and float(r['nominal_project_percent' if design=='whole_project' else 'dapp_percent'])==10]
   assert len(chosen)==5;v=[float(r[fracfield]) for r in chosen]
   coverage.append({'normalizer':norm,'sampling_unit':design,'policy':policy,'nominal_percent':10,'seed_count':5,'giant_fraction_mean':statistics.mean(v),'giant_fraction_median':statistics.median(v),'giant_fraction_min':min(v),'giant_fraction_max':max(v)})
csvout(OUT/'coverage_baselines_10percent.csv',coverage)
doses=[]
for numerator in [0,1,2,3,4]:
 lp=[0,2,4,5,7][numerator];ln=[0,116,232,348,464][numerator];total=lp+ln
 doses.append({'nominal_linked_pool_retention_fraction':numerator/4,'linked_positive':lp,'linked_proxy_zero':ln,'linked_total':total,'safe_positive':24-lp,'safe_proxy_zero':684-ln,'safe_total':708-total,'training_files':708,'training_positive':24,'realized_linked_pool_retention_fraction':total/471,'linked_fraction_of_training':total/708,'realized_positive_pool_retention_fraction':lp/7,'realized_proxy_zero_pool_retention_fraction':ln/464})
csvout(OUT/'planned_dose_allocation_nearest.csv',doses)
result={'date':'2026-10-28','status':'PASS','annotation_hashes_verified':len(matched),'historical_population_files':len(S),'historical_population_reentrancy_positive':sum(v['reentrancy'] for v in labels.values()),'historical_giant_files':len(giant),'historical_giant_reentrancy_positive':sum(labels[p]['reentrancy'] for p in giant),'historical_giant_unchecked_positive':sum(labels[p]['unchecked'] for p in giant),'all12evaluations_share_identical_B_C_training_pools':True,'internal_tests':10,'internal_test_n':1062,'internal_test_reentrancy_range':[min(r['test_reentrancy_positive'] for r in rows if r['test_id'] in internal),max(r['test_reentrancy_positive'] for r in rows if r['test_id'] in internal)],'internal_test_union_files':len(set().union(*internal.values())),'pairwise_overlap_minmax':[min(r['shared_files'] for r in overlaps),max(r['shared_files'] for r in overlaps)],'new_model_fits':0,'note':'Dose allocation matches the model-owner declared nearest-integer totals and positives; execution is owned separately. It is not claimed as executed. Ten internal tests are overlapping subsets of one giant, not independent families.','outputs':{p.name:sha(p) for p in OUT.glob('*.csv')}}
(OUT/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));print(json.dumps(coverage,indent=2))
