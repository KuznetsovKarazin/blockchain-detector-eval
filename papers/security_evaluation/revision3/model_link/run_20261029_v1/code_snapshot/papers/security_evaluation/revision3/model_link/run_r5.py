"""Private frozen R5 giant-population, composition and linked-retention study."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime,timezone
import gzip
import hashlib
import importlib.metadata
import json
import multiprocessing
import os
from pathlib import Path
import pickle
import platform
import shutil
import sys
import time
import traceback

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
R4=ROOT/'papers/security_evaluation/revision2/model_link'
PRECURSOR=R4/'expanded_contrast_20261028_v1'
sys.path.insert(0,str(R4))
import analyze as oldaudit
sys.path.insert(0,str(ROOT/'papers/security_evaluation'))
from campaign import run_development as trainer

METHODS=['raw_tfidf_lr','normalized_tfidf_lr','pattern_rf','pattern_lightgbm']
DOSES=[(0,0,0),(25,118,2),(50,236,4),(75,353,5),(100,471,7)]
CODE=[str(Path(__file__).relative_to(ROOT)),
      'papers/security_evaluation/revision2/model_link/analyze.py',
      'papers/security_evaluation/campaign/run_development.py',
      'papers/security_evaluation/evaluation_metrics.py',
      'src/bal/features/contract_features.py']
sha=oldaudit.sha
dump=oldaudit.dump
SOURCES={};LABELS={};TEXT_CACHE={};PATTERN_CACHE={};PATTERN_COLUMNS=[]
CONFIG={};MEMBERSHIPS={};TEST_IDS=[]


def utc():return datetime.now(timezone.utc).isoformat()
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write_csv(path,frame):
    if str(path).endswith('.gz'):
        with path.open('wb') as raw:
            with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as binary:
                binary.write(frame.to_csv(index=False).encode())
    else:frame.to_csv(path,index=False)


def prepare(out):
    if out.exists():raise ValueError('New run directory required')
    inv=pd.read_csv(oldaudit.PILOT/'source_inventory.csv').set_index('file_id',drop=False)
    labels,_=oldaudit.read_labels(inv.reset_index(drop=True),ROOT/'data/raw/DAppSCAN')
    dapp=inv[inv.dataset.eq('dappscan')]
    r4=json.loads((PRECURSOR/'config.json').read_text());original=r4['jobs'][0]['test_ids']
    gids=set(inv.loc[original,'joint_id']);assert len(gids)==1
    giant=sorted(dapp[dapp.joint_id.isin(gids)].file_id.tolist())
    assert len(giant)==5408 and sum(labels[i]['reentrancy'] for i in giant)==83
    projection=pd.read_csv(oldaudit.PROJECTION).set_index('file_id')
    pools={}
    for name,col in [('B','B_historical_legacy'),('C','C_uncapped_reference_legacy')]:
        tg=set(projection.loc[giant,col]);pools[name]=sorted(i for i in dapp.file_id if projection.loc[i,col] not in tg)
    linked=sorted(set(pools['B'])-set(pools['C']))
    assert len(pools['B'])==1179 and len(pools['C'])==708 and len(linked)==471
    assert [sum(labels[i]['reentrancy'] for i in ids) for ids in [pools['B'],pools['C'],linked]]==[31,24,7]
    internal_path=ROOT/'papers/security_evaluation/revision2/graph_mechanics/run_20261028_v1/labelblind_test_memberships.csv'
    internals=pd.read_csv(internal_path);internals=internals[internals.frame.eq('inside_historical_giant')]
    by_path=dict(zip(dapp.path,dapp.file_id))
    frames={'giant_primary':giant,'original_1082_precursor':original}
    for name,df in internals.groupby('test_id',sort=True):frames[name]=sorted(by_path[p] for p in df.path)
    assert len(frames)==12 and all(set(ids)<=set(giant) for ids in frames.values())
    assert all(len(ids)==1062 for n,ids in frames.items() if n.startswith('inside_'))
    memberships={'C_full':pools['C']};membership_rows=[];jobs=[]
    def order(ids,salt):return sorted(ids,key=lambda i:(hashlib.sha256((salt+'|'+inv.loc[i,'path']).encode()).hexdigest(),inv.loc[i,'path']))
    for draw in range(50):
        ids=[]
        for y,n in [(0,684),(1,24)]:
            ids+=order([i for i in pools['B'] if labels[i]['reentrancy']==y],f'expanded-graph-post-review-v1|draw={draw}|class={y}')[:n]
        memberships[f'B_draw{draw:02d}']=sorted(ids)
    for comp in range(5):
        ranks={}
        for name,pool in [('linked',linked),('safe',pools['C'])]:
            for y in [0,1]:ranks[(name,y)]=order([i for i in pool if labels[i]['reentrancy']==y],f'r5-linked-retention-v1|composition={comp}|pool={name}|class={y}')
        for percent,q,qp in DOSES[1:]:
            ids=ranks[('linked',1)][:qp]+ranks[('linked',0)][:q-qp]+ranks[('safe',1)][:24-qp]+ranks[('safe',0)][:684-(q-qp)]
            memberships[f'dose{percent:03d}_composition{comp}']=sorted(ids)
    for name,ids in memberships.items():
        assert len(ids)==708 and len(set(ids))==708 and sum(labels[i]['reentrancy'] for i in ids)==24 and not set(ids)&set(giant)
        for i in ids:membership_rows.append({'membership':name,'file_id':i,'reentrancy_proxy':labels[i]['reentrancy'],'C_linked':i in linked})
    for name in ['C_full']+[f'B_draw{i:02d}' for i in range(50)]+[f'dose{p:03d}_composition{c}' for c in range(5) for p,_,_ in DOSES[1:]]:
        for method in METHODS:
            for seed in ([0] if method.endswith('tfidf_lr') else range(5)):
                jobs.append({'job_id':f'{name}_{method}_s{seed}','membership':name,'method':method,'seed':seed,'physical_key':fingerprint([memberships[name],method,seed])})
    assert len(jobs)==852 and len({j['physical_key'] for j in jobs})==852
    # The first five B draws and all C configurations exactly replay the R4 fits.
    r4map={}
    for j in r4['jobs']:
        name='C_full' if j['policy']=='C' else f"B_draw{j['draw']:02d}"
        assert memberships[name]==j['train_ids']
        key=f"{name}_{j['method']}_s{j['seed']}"
        if key not in r4map:r4map[key]=j['job_id']
    assert len(r4map)==72
    out.mkdir(parents=True)
    dapp.to_csv(out/'source_inventory.csv',index=False)
    write_csv(out/'memberships.csv.gz',pd.DataFrame(membership_rows))
    dump(out/'membership_ids.json',memberships);dump(out/'labels.json',{str(i):labels[i] for i in dapp.file_id})
    dump(out/'evaluation_frames.json',frames);dump(out/'pool_ids.json',{**pools,'C_linked_B_minus_C':linked})
    dump(out/'r4_replay_mapping.json',r4map)
    frame_rows=[{'frame':name,'n':len(ids),'reentrancy_positive':sum(labels[i]['reentrancy'] for i in ids),'unchecked_positive':sum(labels[i]['unchecked'] for i in ids)} for name,ids in frames.items()]
    pd.DataFrame(frame_rows).to_csv(out/'frame_counts.csv',index=False)
    runtime={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'cpu_count':os.cpu_count(),'packages':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','scikit-learn','lightgbm','threadpoolctl']}}
    dump(out/'environment.json',runtime)
    plan={'schema':'r5_model_giant_composition_linked_retention_v1','created_utc':utc(),'status':'frozen_before_any_R5_fit','primary_frame':'giant_primary','secondary_frames':'Original1082precursor plus10already-definedlabel-blindinsidegiant1062slices. Nestedoverlappingdescriptivesensitivity,notindependentfamilies.','full_giant':{'n':5408,'reentrancy_positive':83},'training':{'n':708,'positive':24,'B_pool_n':1179,'B_positive':31,'C_pool_n':708,'C_positive':24,'linked_n':471,'linked_positive':7},'main_composition_draws':50,'main_draw_salt':'expanded-graph-post-review-v1|draw={draw}|class={y}; first5exactR4prefix','tree_seeds':[0,1,2,3,4],'lr_seed':0,'dose_compositions':5,'dose_schedule':[{'nominal_linked_retention_percent':p,'linked_files':q,'linked_positive':qp,'linked_no_finding':q-qp,'safe_files':708-q,'safe_positive':24-qp,'safe_no_finding':684-(q-qp),'realized_linked_retention':q/471,'linked_fraction_of_training':q/708} for p,q,qp in DOSES],'dose_design':'Nested percomposition perpool perclass pathhashranks. Linkedprefix expands andsafeprefixcontracts;0doseisfixedCpoolandisreused.100%meansretainingall471linkedfiles,66.5254%of708training;never100%training.','model_config':r4['model_config'],'jobs':jobs,'physical_fits':852,'main_physical_fits':612,'dose_additional_physical_fits':240,'memoization':'Only deterministicraw_text,normalised_text,pattern_matrix outputs cachedbyunchangedsource text. Originaltrainerfunctioncodeunchanged. Cacheoutputsrecomputedandcheckedexactly oncebeforefits. TFIDFvectorizer,scalerandmodelarefittedanewoneachtrainset.','parallelism':{'workers':2,'per_tree_fit_threads':4,'per_LR_fit_threads':1,'allowed_adaptation':'workerscanbereduced forobservedresourcepressureonly,neverbasedonscores'},'saving':'gzipscorevectorson5408filesperphysicalfit;allattemptstart/status/resources/hashes;nomodeljoblib. Deterministiccacheoptionalprivate/dev/shm,notpublicationartifact.','replay_gate':'First72R4configurations refitted and old1082scores extractedfromgiantpredictions; requireallfinitecoverageandmaxabsolutescoredifference<=1e-12beforelaunchremaining780. Recordbitwiseequalityseparately. No claimoldmodelswerepreserved.','summary_plan':'PrimarytreecompositionECDF across50Baveragesover5seeds comparedwithCmeanover5seeds; reportstrict/weakECDFandmidrank. Separateseed-matchedECDFacross50BdrawsforeachseedandCseed. Nevertreat250treecellsasindependentcompositiondraws. LR50BvsoneC. Dosefullallmethods×3reviewbudgetfractions andAP, all5compositions/seeds retained, nofitdosecurveoroutcome-selectedcontrast.','review_budgets':'floor(5%,10%,20%)ofeachframe;complete4methods×3budgetswithuniformboundaryties. Primarygiantbudgets270,540,1081; original1082budgets54,108,216;1062slices53,106,212.','stopping_rule':'Everyfrozenfitonce;retainfailures/warnings;nohyperparametersearch,selection,retryornewdosefromobservedoutcomes. Technicalprefixcompatibilityfailureblocksremainingfits.','interpretation':'Post-reviewconditionalcomputationalexperimentonhistoricalproxylabels. Entiregiantlargercoverageisnotnewdeploymentpopulation. Noindependent-familyconfidenceinterval,p-value,semanticclonegroundtruthorindividualedgecausality.','public_actions':False}
    dump(out/'PLAN_BEFORE_FITTING.json',plan)
    for p in CODE:
        dest=out/'code_snapshot'/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,dest)
    inputs={str(p.relative_to(ROOT)):sha(p) for p in [oldaudit.PILOT/'source_inventory.csv',oldaudit.PILOT/'label_input_hashes.json',oldaudit.PROJECTION,internal_path,PRECURSOR/'config.json',PRECURSOR/'COMPLETE.json']}
    freeze={'schema':'r5_model_freeze_v1','created_utc':utc(),'source_hashes':{p:sha(ROOT/p) for p in CODE},'input_hashes':inputs,'prepared_files':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'fits_started':False,'physical_fits':852}
    dump(out/'FREEZE_BEFORE_FITTING.json',freeze)
    print(json.dumps({'run':str(out),'freeze_sha256':sha(out/'FREEZE_BEFORE_FITTING.json'),'physical_fits':852,'frames':frame_rows}))


def cache_raw(s):return TEXT_CACHE[s][0]
def cache_normalized(s):return TEXT_CACHE[s][1]
def cache_patterns(sources):return pd.DataFrame([PATTERN_CACHE[s] for s in sources],columns=PATTERN_COLUMNS)


def build_cache(out):
    global SOURCES,LABELS,TEXT_CACHE,PATTERN_CACHE,PATTERN_COLUMNS,CONFIG,MEMBERSHIPS,TEST_IDS
    start=time.perf_counter();CONFIG=json.loads((out/'PLAN_BEFORE_FITTING.json').read_text());MEMBERSHIPS=json.loads((out/'membership_ids.json').read_text());TEST_IDS=json.loads((out/'evaluation_frames.json').read_text())['giant_primary'];LABELS={int(k):v for k,v in json.loads((out/'labels.json').read_text()).items()}
    inv=pd.read_csv(out/'source_inventory.csv');sources=[]
    for row in inv.itertuples():
        if sha(ROOT/row.path)!=row.file_sha256:raise ValueError('Source bytes changed')
        s=(ROOT/row.path).read_text(encoding='utf-8',errors='replace');SOURCES[row.file_id]=s;sources.append(s)
    raw,normalized,patterns=trainer.raw_text,trainer.normalised_text,trainer.pattern_matrix
    unique=list(dict.fromkeys(sources))
    for s in unique:TEXT_CACHE[s]=(raw(s),normalized(s))
    matrix=patterns(unique);PATTERN_COLUMNS=matrix.columns.tolist()
    for i,s in enumerate(unique):PATTERN_CACHE[s]=matrix.iloc[i].to_numpy(copy=True)
    for s in unique:
        if raw(s)!=TEXT_CACHE[s][0] or normalized(s)!=TEXT_CACHE[s][1]:raise ValueError('Token cache equality failed')
    original=patterns(sources).to_numpy();cached=cache_patterns(sources).to_numpy()
    if not np.array_equal(original,cached) or not np.array_equal(original.astype(np.float32),cached.astype(np.float32)):raise ValueError('Pattern cache equality failed')
    tmp=Path('/dev/shm')/f'article1_r5_feature_cache_{os.getpid()}.pickle'
    with tmp.open('wb') as f:pickle.dump((TEXT_CACHE,PATTERN_CACHE,PATTERN_COLUMNS),f,protocol=5)
    receipt={'source_files':len(SOURCES),'distinct_decoded_source_texts':len(unique),'raw_and_normalized_exact_rechecks':2*len(unique),'pattern_matrix_recheck_rows':len(sources),'pattern_float64_and_float32_bitwise_equal':True,'elapsed_seconds':time.perf_counter()-start,'cache_sha256':sha(tmp),'cache_bytes':tmp.stat().st_size,'cache_location':str(tmp),'cache_is_deterministic_features_only':True,'learned_fit_state_cached':False}
    dump(out/'FEATURE_CACHE_VERIFICATION.json',receipt)
    trainer.raw_text=cache_raw;trainer.normalised_text=cache_normalized;trainer.pattern_matrix=cache_patterns
    return receipt


def fit_one(pair):
    out_string,j=pair;out=Path(out_string);folder=out/'fits'/j['job_id'];folder.mkdir(parents=True)
    dump(folder/'started.json',{'started_utc':utc(),'job':j,'membership_sha256':fingerprint(MEMBERSHIPS[j['membership']]),'giant_test_sha256':fingerprint(TEST_IDS)})
    result={'job_id':j['job_id'],'status':'started','method':j['method'],'seed':j['seed'],'membership':j['membership']}
    try:
        job={**j,'train_ids':MEMBERSHIPS[j['membership']],'test_ids':TEST_IDS,'class':'reentrancy'}
        scores,resources=trainer.fit_predict(job,CONFIG,SOURCES,LABELS)
        write_csv(folder/'predictions.csv.gz',pd.DataFrame({'file_id':TEST_IDS,'score':scores,'status':'ok'}))
        dump(folder/'resources.json',resources);result['status']='ok'
    except BaseException as e:result.update({'status':'failed','exception_type':type(e).__name__,'exception':str(e),'traceback':traceback.format_exc()})
    result['finished_utc']=utc();result['artifact_hashes']={p.name:sha(p) for p in folder.iterdir() if p.is_file()};dump(folder/'result.json',result)
    return result


def replay_gate(out):
    mapping=json.loads((out/'r4_replay_mapping.json').read_text());rows=[]
    for new_id,old_id in mapping.items():
        result=json.loads((out/'fits'/new_id/'result.json').read_text())
        if result['status']!='ok':raise ValueError('R4 prefix fit failed')
        oldresult=json.loads((PRECURSOR/'fits'/old_id/'result.json').read_text())
        path=PRECURSOR/'fits'/old_id/'predictions.csv'
        if sha(path)!=oldresult['artifacts']['predictions.csv']:raise ValueError('R4 scores changed')
        old=pd.read_csv(path,float_precision='round_trip');new=pd.read_csv(out/'fits'/new_id/'predictions.csv.gz',float_precision='round_trip').set_index('file_id').loc[old.file_id]
        delta=float(np.max(np.abs(new.score.to_numpy()-old.score.to_numpy())))
        rows.append({'new_job':new_id,'R4_job':old_id,'n_scores':len(old),'maximum_absolute_score_difference':delta,'bitwise_equal_scores':bool(np.array_equal(new.score.to_numpy(),old.score.to_numpy())),'passed_tolerance':delta<=1e-12})
    receipt={'schema':'r5_refit_R4_prefix_compatibility_v1','physical_configurations_checked':72,'score_values_checked':72*1082,'maximum_absolute_score_difference':max(x['maximum_absolute_score_difference'] for x in rows),'all_passed':all(x['passed_tolerance'] for x in rows),'all_bitwise_equal':all(x['bitwise_equal_scores'] for x in rows),'rows':rows}
    dump(out/'R4_PREFIX_COMPATIBILITY.json',receipt)
    return receipt['all_passed']


def execute(out,workers):
    if (out/'execution_started.json').exists():raise ValueError('No automatic retry/resume; preserve interrupted run')
    freeze=json.loads((out/'FREEZE_BEFORE_FITTING.json').read_text())
    for p,h in freeze['source_hashes'].items():
        if sha(ROOT/p)!=h or sha(out/'code_snapshot'/p)!=h:raise ValueError('Frozen source changed')
    for p,h in freeze['input_hashes'].items():
        if sha(ROOT/p)!=h:raise ValueError('Frozen input changed')
    for p,h in freeze['prepared_files'].items():
        if sha(out/p)!=h:raise ValueError('Prepared artifact changed')
    environment=json.loads((out/'environment.json').read_text())
    for package,version in environment['packages'].items():
        if importlib.metadata.version(package)!=version:raise ValueError('Runtime package version changed')
    if workers not in [1,2]:raise ValueError('Predeclared maximum two workers')
    dump(out/'execution_started.json',{'started_utc':utc(),'freeze_sha256':sha(out/'FREEZE_BEFORE_FITTING.json'),'workers':workers})
    cache=build_cache(out);jobs=CONFIG['jobs'];mapping=json.loads((out/'r4_replay_mapping.json').read_text());prefix=[j for j in jobs if j['job_id'] in mapping];remaining=[j for j in jobs if j['job_id'] not in mapping];assert len(prefix)==72 and len(remaining)==780
    start=time.perf_counter();results={}
    with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('fork')) as pool:
        for stage,items in [('R4_replay',prefix),('new_main_and_dose',remaining)]:
            if stage=='new_main_and_dose' and not replay_gate(out):raise ValueError('Frozen technical replay gate failed; remaining fits not launched')
            futures={pool.submit(fit_one,(str(out),j)):j['job_id'] for j in items}
            for f in as_completed(futures):
                result=f.result();results[result['job_id']]=result
                print(json.dumps({'stage':stage,'completed':len(results),'total':852,'job_id':result['job_id'],'status':result['status']}),flush=True)
    complete={'schema':'r5_model_fit_execution_complete_v1','finished_utc':utc(),'physical_fits_attempted':len(results),'failed':sum(r['status']!='ok' for r in results.values()),'fit_wall_seconds':time.perf_counter()-start,'feature_cache_seconds':cache['elapsed_seconds'],'freeze_sha256':sha(out/'FREEZE_BEFORE_FITTING.json'),'result_hashes':{j:sha(out/'fits'/j/'result.json') for j in results},'external_scores':0,'human_annotations':0,'model_binaries_saved':False}
    dump(out/'COMPLETE.json',complete)
    Path(cache['cache_location']).unlink(missing_ok=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','execute']);p.add_argument('--out',type=Path,required=True);p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    prepare(a.out) if a.action=='prepare' else execute(a.out,a.workers)
