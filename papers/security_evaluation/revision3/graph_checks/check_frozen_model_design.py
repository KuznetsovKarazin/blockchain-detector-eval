#!/usr/bin/env python3
from pathlib import Path
import json,csv,hashlib,math
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;BASE=ROOT/'papers/security_evaluation';run=BASE/'revision3/model_link/run_20261029_v1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
f=read(run/'FREEZE_BEFORE_FITTING.json');p=read(run/'PLAN_BEFORE_FITTING.json');assert f['fits_started'] is False
for name,h in f['source_hashes'].items():assert sha(ROOT/name)==h and sha(run/'code_snapshot'/name)==h
for name,h in f['input_hashes'].items():assert sha(ROOT/name)==h
for name,h in f['prepared_files'].items():assert sha(run/name)==h
with (BASE/'dependency_audit/graph_scope_ablation_recovered_20261025/historical_projection.csv').open() as stream:projection={int(r['file_id']):r for r in csv.DictReader(stream) if r['dataset']=='dappscan'}
labels=read(run/'labels.json');ids=read(run/'membership_ids.json');frames=read(run/'evaluation_frames.json');pools=read(run/'pool_ids.json');giant=set(frames['giant_primary']);assert len(giant)==5408
# Cross-check all frozen DAppSCAN labels directly against the SWC-code annotation schema.
for i,row in projection.items():
 path=row['path'];ap=ROOT/Path(path.replace('/contracts/','/SWCsource/',1)).with_suffix('.json');codes=set()
 if ap.exists():
  doc=read(ap);assert doc['filePath']==path.removeprefix('data/raw/DAppSCAN/');codes={v['category'].split('-')[1] for v in doc.get('SWCs',[]) if v.get('category','').startswith('SWC-')}
 assert labels[str(i)]=={'reentrancy':int('107' in codes),'unchecked':int('104' in codes)}
pos=lambda ids:sum(labels[str(i)]['reentrancy'] for i in ids)
assert pos(giant)==83
for tag,col in [('B','B_historical_legacy'),('C','C_uncapped_reference_legacy')]:
 tc={projection[i][col] for i in giant};expected={i for i,r in projection.items() if r[col] not in tc};assert set(pools[tag])==expected
B=set(pools['B']);C=set(pools['C']);linked=B-C;assert (len(B),pos(B),len(C),pos(C),len(linked),pos(linked))==(1179,31,708,24,471,7)
assert set(pools['C_linked_B_minus_C'])==linked and not B&giant
for name,values in ids.items():assert len(set(values))==len(values)==708 and pos(values)==24 and set(values)<=B
rank=lambda candidates,salt:sorted(candidates,key=lambda i:(hashlib.sha256((salt+'|'+projection[i]['path']).encode()).hexdigest(),projection[i]['path']))
for draw in range(50):
 expected=[]
 for y,n in [(0,684),(1,24)]:expected+=rank([i for i in B if labels[str(i)]['reentrancy']==y],f'expanded-graph-post-review-v1|draw={draw}|class={y}')[:n]
 assert ids[f'B_draw{draw:02d}']==sorted(expected)
assert set(ids['C_full'])==C
for comp in range(5):
 ranks={(group,y):rank([i for i in pool if labels[str(i)]['reentrancy']==y],f'r5-linked-retention-v1|composition={comp}|pool={group}|class={y}') for group,pool in [('linked',linked),('safe',C)] for y in [0,1]}
 prev_link=set();prev_safe=C
 for d in p['dose_schedule']:
  nominal=d['nominal_linked_retention_percent'];q=d['linked_files'];qp=d['linked_positive']
  assert (q,qp)=={0:(0,0),25:(118,2),50:(236,4),75:(353,5),100:(471,7)}[nominal]
  expected=sorted(ranks[('linked',1)][:qp]+ranks[('linked',0)][:q-qp]+ranks[('safe',1)][:24-qp]+ranks[('safe',0)][:684-(q-qp)])
  actual=ids['C_full'] if nominal==0 else ids[f'dose{nominal:03d}_composition{comp}'];assert actual==expected
  now_link=set(actual)&linked;now_safe=set(actual)&C;assert prev_link<=now_link and now_safe<=prev_safe
  assert math.isclose(d['realized_linked_retention'],q/471) and math.isclose(d['linked_fraction_of_training'],q/708)
  prev_link,prev_safe=now_link,now_safe
for name,frame in frames.items():
 assert set(frame)<=giant
 for tag,col in [('B','B_historical_legacy'),('C','C_uncapped_reference_legacy')]:
  tc={projection[i][col] for i in frame};assert {i for i,r in projection.items() if r[col] not in tc}==set(pools[tag])
with (BASE/'revision2/graph_mechanics/run_20261028_v1/labelblind_test_memberships.csv').open() as stream:
 old={}
 for r in csv.DictReader(stream):
  if r['frame']=='inside_historical_giant':old.setdefault(r['test_id'],set()).add(r['path'])
for name,paths in old.items():assert any({projection[i]['path'] for i in frame}==paths for frame in frames.values())
assert len(p['jobs'])==852 and len({j['physical_key'] for j in p['jobs']})==852
for j in p['jobs']:assert j['membership'] in ids and j['method'] in ['raw_tfidf_lr','normalized_tfidf_lr','pattern_rf','pattern_lightgbm'] and j['seed'] in ([0] if j['method'].endswith('tfidf_lr') else range(5))
assert len(ids)==71 and len(frames)==12
result={'status':'PASS','freeze_sha256':sha(run/'FREEZE_BEFORE_FITTING.json'),'plan_sha256':sha(run/'PLAN_BEFORE_FITTING.json'),'script_sha256':sha(Path(__file__)),'checked_before_fit':not(run/'execution_started.json').exists(),'all_source_and_prepared_hashes_match':True,'independent_annotation_labels_checked':len(labels),'giant_files':5408,'giant_positive':83,'frames_checked':12,'old_internal_frames_reused_exactly':10,'same_B_C_pools_all_frames':True,'memberships_checked':71,'B_draw_hash_ranks_recomputed':50,'dose_nested_hash_rank_compositions_recomputed':5,'unique_physical_fit_keys':852,'dose_nonzero_connects_all_giant_test_files':True,'main_tree_ECDF_unit':'50drawseed-averages,not250IIDcells','claimed_causal_edge_effect':False,'fits_started_by_this_check':0}
(HERE/'MODEL_FREEZE_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
