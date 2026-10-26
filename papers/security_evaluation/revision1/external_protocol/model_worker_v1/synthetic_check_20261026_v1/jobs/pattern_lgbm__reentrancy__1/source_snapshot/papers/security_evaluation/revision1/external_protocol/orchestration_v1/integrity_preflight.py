"""Read-only content-addressed provenance preflight; no executable dispatch.

A trusted expected binding digest must be supplied separately by the caller.
This detects changed/missing artifacts relative to that selected anchor. It does
not authenticate humans, certify timestamps, or grant execution authorization.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
sys.path.insert(0,str(HERE));import validate_gate_v2 as gate
sys.path.insert(0,str(HERE.parent));from review_estimators import analyze_review

@dataclass(frozen=True)
class Profile:
    training_files:int=691
    external_files:int=1998
    sample_cases:int=180
    strata:int=17
    solc_versions:int=30
    slither_versions:int=1
    dependency_artifacts:int=47
    synthetic:bool=False
    def __post_init__(self):
        if not self.synthetic and (self.training_files,self.external_files,self.sample_cases,self.strata,self.solc_versions,self.slither_versions,self.dependency_artifacts)!=(691,1998,180,17,30,1,47):
            raise ValueError('Production cohort/toolchain counts are fixed; overrides require explicit synthetic profile')

class IntegrityError(ValueError):pass

def require(condition,message):
    if not condition:raise IntegrityError(message)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

LIVE_CODE_PATHS={'integrity_preflight':Path(__file__).resolve(),'validate_gate_v2':Path(gate.__file__).resolve(),
                 'review_estimators':Path(sys.modules[analyze_review.__module__].__file__).resolve()}
LIVE_CODE_DIGESTS={role:sha(path) for role,path in LIVE_CODE_PATHS.items()}

def local(root,name):
    require(isinstance(name,str) and name and not Path(name).is_absolute() and '..' not in Path(name).parts,'nonrelative_or_traversing_path')
    path=root/name
    require(path.resolve().is_relative_to(root.resolve()),'path_escapes_binding_root')
    return path

def artifact(root,ref):
    require(isinstance(ref,dict) and set(ref)=={'path','sha256'},'artifact_reference_schema')
    require(isinstance(ref['sha256'],str) and re.fullmatch('[0-9a-f]{64}',ref['sha256']) is not None,'invalid_artifact_digest')
    path=local(root,ref['path']);require(path.is_file(),'missing_artifact:'+ref['path'])
    require(sha(path)==ref['sha256'],'artifact_hash_mismatch:'+ref['path'])
    return path

def read_json(path):
    try:return json.loads(path.read_text())
    except (OSError,ValueError) as exc:raise IntegrityError('invalid_json:'+str(path)) from exc

def csv(path):return pd.read_csv(path,keep_default_na=False)

def timestamp(value):
    require(isinstance(value,str),'timestamp_missing')
    try:out=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as exc:raise IntegrityError('invalid_timestamp') from exc
    require(out.tzinfo is not None,'timezone_required')
    require(out<=datetime.now(timezone.utc),'future_event_timestamp')
    return out

def header(root,binding_path,expected_sha256,phase,profile):
    """Read public bindings/code/policy only, never training or review labels."""
    require(phase in gate.PHASES,'unknown_phase')
    require(isinstance(expected_sha256,str) and re.fullmatch('[0-9a-f]{64}',expected_sha256) is not None,'separate_expected_binding_digest_required')
    require(sha(binding_path)==expected_sha256,'binding_anchor_mismatch')
    binding=read_json(binding_path);require(binding.get('schema')=='external_B_orchestration_binding_v1','binding_schema')
    require(set(binding.get('artifacts',{}))==gate.ARTIFACT_ROLES and set(binding.get('code',{}))==gate.CODE_ROLES,'required_binding_roles_missing')
    require(binding.get('synthetic_fixture') is profile.synthetic,'fixture_profile_mismatch')
    protocol=read_json(artifact(root,binding['artifacts']['protocol']))
    bad=gate.blockers(protocol,phase)
    if phase!='setup':require(not bad,'protocol_gate:'+','.join(bad))
    for ref in binding['code'].values():artifact(root,ref)
    if not profile.synthetic:
        for role,path in LIVE_CODE_PATHS.items():
            require(sha(path)==LIVE_CODE_DIGESTS[role]==binding['code'][role]['sha256'],'live_validator_code_differs_from_binding:'+role)
    if protocol.get('schema')==gate.SCHEMA:
        wanted={role:ref['sha256'] for role,ref in binding['artifacts'].items() if role!='protocol'}
        wanted.update({'code.'+role:ref['sha256'] for role,ref in binding['code'].items()})
        require(protocol['hashes']==wanted,'protocol_binding_hashes_differ')
    policy_path=artifact(root,binding['artifacts']['inference_policy']);policy=read_json(policy_path)
    require(policy.get('schema')=='external_B_inference_policy_v1' and policy.get('applicable_scope')=='fixed_external_probability_sample','inference_policy_schema_or_scope')
    if not profile.synthetic:
        evidence=policy.get('evidence_hashes');require(isinstance(evidence,dict) and bool(evidence),'inference_evidence_bindings_required')
        for name,digest in evidence.items():
            path=local(policy_path.parent,name);require(path.is_file() and sha(path)==digest,'inference_evidence_hash_mismatch:'+name)
    inference_ok=policy.get('survey_weighted_performance_and_interval_tests_complete') is True and policy.get('external_ap_confirmatory_uncertainty') is True
    if phase!='setup':require(inference_ok,'inference_policy_blocks_confirmatory_external_study')
    config=read_json(artifact(root,binding['artifacts']['method_config']))
    jobs=job_plan(config,protocol)
    if not profile.synthetic:
        expected=[{'job_id':f'{method}:{cls}:{seed}','kind':'learned','method':method,'class':cls,'seed':seed}
                  for method in ['raw_tfidf_lr','normalized_tfidf_lr','pattern_rf','pattern_lgbm']
                  for cls in ['reentrancy','unchecked']
                  for seed in ([0] if method.endswith('_lr') else range(5))]
        require([job for job in jobs if job['kind']=='learned']==expected,'production_24_learned_job_inventory_changed')
    return binding,protocol,config,jobs,bad,inference_ok


def admission_preflight(root,binding_path,expected_sha256,release_path,profile=Profile(),phase='begin_scoring'):
    """Review admission before worker training-label/source reads.

    May read the private probability sample key/allocation and sealed review
    forms, but never training_labels, source_labels, source bodies or scores.
    This is not independent authentication of people or claimed event times.
    """
    out={'admission_artifacts_consistent':False,'execution_authorized':False,'human_identity_authenticated':False,
         'training_label_keys_read':False,'model_source_bodies_read':False,'scores_read':False,'operations_executed':0,'blockers':[]}
    root=Path(root).resolve()
    try:
        require(phase in ('begin_scoring','analyze'),'admission_phase')
        binding,protocol,config,jobs,_,_=header(root,Path(binding_path),expected_sha256,phase,profile)
        release=read_json(Path(release_path))
        require(release.get('schema')=='external_B_release_chain_v1' and isinstance(release.get('events'),list),'release_chain_schema')
        require(len(release['events'])==(3 if phase=='begin_scoring' else 4),'release_phase_count_or_reentry')
        events=[];previous=None;last=None
        for index,ref in enumerate(release['events'][:3]):
            event=read_json(artifact(root,ref))
            require(event.get('schema')=='external_B_release_event_v1' and event.get('phase')==gate.RELEASE_ORDER[index],'release_event_order')
            require(event.get('binding_sha256')==expected_sha256 and event.get('previous_event_sha256')==previous,'release_chain_binding')
            time=timestamp(event.get('sealed_utc'));require(last is None or time>=last,'release_chronology')
            require(isinstance(event.get('artifacts'),dict),'release_artifacts_missing')
            events.append((event,time));previous=ref['sha256'];last=time
        require(set(events[0][0]['artifacts'])=={'freeze_record'},'freeze_record_missing')
        freeze=read_json(artifact(root,events[0][0]['artifacts']['freeze_record']))
        require(freeze.get('binding_sha256')==expected_sha256 and freeze.get('human_judgments_completed')==0 and freeze.get('model_fits_completed')==0 and freeze.get('external_scores_completed')==0,'freeze_after_results')
        require(isinstance(freeze.get('immutable_record_reference'),str) and bool(freeze['immutable_record_reference'].strip()),'freeze_record_reference_missing')
        key=csv(artifact(root,binding['artifacts']['sample_key']));allocation=csv(artifact(root,binding['artifacts']['allocation']))
        require(len(key)==profile.sample_cases and len(allocation)==profile.strata and int(allocation.N_h.sum())==2*profile.external_files,'review_sample_design_counts')
        forms=initial_reviews(root,events[1][0]['artifacts'],key,[r['reviewer_id'] for r in protocol['reviewers']])
        for form in forms:
            for value in form.reviewed_utc:require(events[0][1]<=timestamp(value)<=events[1][1],'initial_review_before_freeze_or_after_seal')
        require(set(events[2][0]['artifacts'])=={'adjudication'},'adjudication_artifact_set')
        adjud=csv(artifact(root,events[2][0]['artifacts']['adjudication']))
        analyze_review(key,allocation,forms[0],forms[1],adjud)
        for value in adjud.adjudicated_utc:require(events[1][1]<=timestamp(value)<=events[2][1],'adjudication_before_initial_seal_or_after_own_seal')
        out.update(admission_artifacts_consistent=True,binding_sha256=expected_sha256,reference_event_sha256=release['events'][2]['sha256'],
                   protocol_sha256=binding['artifacts']['protocol']['sha256'],declared_jobs=jobs,
                   scope='Content/provenance consistency only; separate procedural runtime authorization and full source/tool integrity required')
    except (IntegrityError,OSError,ValueError,KeyError,TypeError,AttributeError) as exc:out['blockers']=[str(exc)]
    return out

def bind_sources(root,binding,profile):
    arts=binding['artifacts'];train=csv(artifact(root,arts['training_manifest']));test=csv(artifact(root,arts['test_manifest']))
    require({'file_id','node_id','path','component','file_sha256'}<=set(train),'training_columns')
    require({'node_id','path','source_id','file_hash','address_expanded_080'}<=set(test),'test_columns')
    require(len(train)==profile.training_files and len(test)==profile.external_files,'fixed_cohort_counts')
    require(train.path.is_unique and train.file_id.is_unique and test.path.is_unique,'duplicate_manifest_identity')
    require(pd.concat([train.node_id,test.node_id]).is_unique,'train_test_node_overlap')
    require(not set(train.component)&set(test.address_expanded_080),'train_test_component_overlap')
    training_labels=csv(artifact(root,arts['training_labels']))
    require({'file_id','path','reentrancy','unchecked'}<=set(training_labels),'training_label_columns')
    require(len(training_labels)==len(train) and training_labels.file_id.tolist()==train.file_id.tolist() and training_labels.path.tolist()==train.path.tolist(),'training_label_identity_or_order')
    require(training_labels[['reentrancy','unchecked']].isin([0,1]).all().all(),'training_proxy_label_values')
    if not profile.synthetic:require(training_labels.reentrancy.sum()==23 and training_labels.unchecked.sum()==18,'training_proxy_class_counts')
    require(set(binding['source_roots'])=={'train','external'},'source_root_set')
    source_digests=[]
    for role,frame in [('train',train),('external',test)]:
        source_root=local(root,binding['source_roots'][role])
        for r in frame.itertuples():
            path=local(source_root,r.path);expected=r.file_sha256 if role=='train' else r.file_hash
            require(path.is_file() and sha(path)==expected,'source_hash_mismatch:'+role+':'+r.path)
            source_digests.append(expected)
    labels=csv(artifact(root,arts['source_labels']));key=csv(artifact(root,arts['sample_key']));allocation=csv(artifact(root,arts['allocation']))
    require({'path','class','label_status','binary_target'}<=set(labels),'label_manifest_columns')
    frame=labels[labels.path.isin(test.path)].merge(test[['path','source_id']],on='path',validate='many_to_one')
    require(len(frame)==2*profile.external_files and not frame[['path','class']].duplicated().any(),'complete_file_class_frame')
    require(set(frame['class'])=={'reentrancy','unchecked'} and frame.binary_target.eq('').all(),'source_labels_not_human_truth')
    require(len(key)==profile.sample_cases and key.case_id.is_unique and not key[['path','class']].duplicated().any(),'selected_case_identity')
    strata=['source_id','class','label_status']
    require(len(allocation)==profile.strata and not allocation[strata].duplicated().any(),'allocation_identity')
    tab=allocation.set_index(strata);grouped=key.groupby(strata,sort=True);counts=frame.groupby(strata).size()
    require(set(tab.index)==set(grouped.groups)==set(counts.index),'sampling_stratum_set')
    for group,rows in grouped:
        alloc=tab.loc[group];N,n=float(alloc.N_h),float(alloc.n_h)
        require(np.isfinite([N,n]).all() and N.is_integer() and n.is_integer() and 1<=n<=N,'sampling_integer_counts')
        require(int(N)==int(counts.loc[group]) and int(n)==len(rows),'sampling_population_counts')
        require(n>=2 or n==N,'noncensus_singleton_stratum')
        require(np.isfinite(rows[['N_h','n_h','inclusion_probability','design_weight']].to_numpy(dtype=float)).all(),'nonfinite_sampling_values')
        require(rows.N_h.astype(float).eq(N).all() and rows.n_h.astype(float).eq(n).all(),'sample_key_counts_differ_from_allocation')
        require(np.allclose(rows.inclusion_probability.astype(float),n/N,rtol=0,atol=1e-12) and np.allclose(rows.design_weight.astype(float),N/n,rtol=0,atol=1e-12),'sampling_weights')
    joined=key.merge(frame[['path',*strata]],on=['path','class'],validate='one_to_one',how='left',suffixes=('','_frame'),indicator=True)
    require(joined['_merge'].eq('both').all(),'sample_outside_frame')
    for name in ['source_id','label_status']:require(joined[name].equals(joined[name+'_frame']),'sample_metadata_changed')
    return train,test,key,allocation,frame,dict(training_files=len(train),external_files=len(test),source_bytes_checked=len(source_digests),sample_cases=len(key),strata=len(allocation))

def bind_toolchain(root,inventory,profile):
    require(isinstance(inventory,dict) and inventory.get('schema')=='external_B_runtime_binding_v1','runtime_inventory_schema')
    executables=inventory.get('executables');deps=inventory.get('dependency_artifacts')
    require(isinstance(executables,list) and isinstance(deps,list),'runtime_inventory_lists')
    require(Counter(x.get('kind') for x in executables)==Counter({'solc':profile.solc_versions,'slither':profile.slither_versions}),'executable_inventory_counts')
    require(len({(x['kind'],x['version']) for x in executables})==len(executables),'duplicate_executable_identity')
    require(len({x['path'] for x in executables})==len(executables),'duplicate_executable_path')
    require(len(deps)==profile.dependency_artifacts,'dependency_artifact_count')
    require(len({x['path'] for x in deps})==len(deps) and len({x['sha256'] for x in deps})==len(deps),'duplicate_dependency_artifact')
    require(all(isinstance(x.get('package'),str) and x['package'].strip() and isinstance(x.get('version'),str) and x['version'].strip() for x in deps),'dependency_package_identity')
    require(len({re.sub('[-_.]+','-',x['package'].lower()) for x in deps})==len(deps),'duplicate_dependency_package')
    plans=csv(artifact(root,inventory['compiler_plans']))
    require('candidate_versions' in plans,'compiler_plan_columns')
    required_versions={version for value in plans.candidate_versions for version in value.split('|') if version}
    require({x['version'] for x in executables if x['kind']=='solc'}==required_versions,'compiler_versions_differ_from_frozen_plans')
    if not profile.synthetic:
        origins=inventory.get('metadata_origins')
        expected={'manifest.json','solc_inventory.json','slither_inventory.json','python_artifacts.json','requirements.lock','installed_freeze.txt','amendment_v2/verification_receipt.json'}
        require(isinstance(origins,dict) and set(origins)==expected,'runtime_metadata_origin_set')
        for ref in origins.values():artifact(root,ref)
    for item in executables+deps:
        artifact(root,{'path':item['path'],'sha256':item['sha256']})
    require(all(x['version']=='0.11.6' for x in executables if x['kind']=='slither'),'slither_version_changed')
    return dict(executables_checked=len(executables),dependency_artifacts_checked=len(deps),executables_invoked=0)

def job_plan(config,protocol):
    require(config.get('schema')=='external_B_method_jobs_v1','method_config_schema')
    require(config.get('model_configurations')==protocol.get('model_configurations'),'model_config_differs_from_protocol')
    require(config.get('slither')==protocol.get('slither'),'slither_config_differs_from_protocol')
    require(set(config['model_configurations'])=={'raw_tfidf_lr','normalized_tfidf_lr','pattern_rf','pattern_lgbm'},'declared_method_set')
    status_map=config.get('score_status_mapping')
    allowed={'ok','compile_error','tool_error','timeout','missing_dependency','unsupported_pragma','missing_score','preprocessing_error','unavailable_binary','model_error'}
    require(isinstance(status_map,dict) and status_map.get('ok')=='ok' and set(status_map.values())<=allowed,'explicit_score_status_mapping_required')
    require(all(value!='ok' for key,value in status_map.items() if key!='ok'),'failure_cannot_map_to_ok')
    jobs=[]
    for method,parameters in config['model_configurations'].items():
        seeds=parameters.get('seeds');require(isinstance(seeds,list) and seeds and all(type(s) is int and s>=0 for s in seeds) and len(set(seeds))==len(seeds),'method_seed_set')
        for cls in ['reentrancy','unchecked']:
            for seed in seeds:jobs.append({'job_id':f'{method}:{cls}:{seed}','kind':'learned','method':method,'class':cls,'seed':seed})
    require(config.get('static_comparator_required') is True,'slither_comparator_must_not_be_silently_omitted')
    for cls in ['reentrancy','unchecked']:jobs.append({'job_id':f'slither:{cls}:0','kind':'static','method':'slither','class':cls,'seed':0})
    return jobs

def initial_reviews(root,refs,key,reviewer_ids):
    require(set(refs)=={'reviewer_1','reviewer_2'},'initial_review_artifact_set')
    forms=[]
    for i,name in enumerate(['reviewer_1','reviewer_2']):
        form=csv(artifact(root,refs[name]));require(set(form.case_id)==set(key.case_id) and form.case_id.is_unique,'incomplete_initial_review')
        ordered=form.set_index('case_id').loc[key.case_id]
        require(ordered['class'].tolist()==key['class'].tolist(),'initial_review_class_changed')
        require(set(ordered['judgment_positive_negative_unknown'])<={'positive','negative','unknown'},'blank_or_invalid_initial_judgment')
        require({gate.normalized_identity(x) for x in ordered.reviewer_id}=={gate.normalized_identity(reviewer_ids[i])},'initial_reviewer_id_mismatch')
        for col in ['reviewer_id','reviewed_utc','reason']:
            require(ordered[col].astype(str).str.strip().ne('').all(),'initial_review_provenance_missing')
        forms.append(form)
    return forms

def sealed_scores(root,event_refs,jobs,test,train,binding_hash,method_hash,reference_hash,status_map,toolchain_hash):
    require(set(event_refs)=={'scores','run_receipt'},'score_release_artifact_set')
    scores=csv(artifact(root,event_refs['scores']));receipt=read_json(artifact(root,event_refs['run_receipt']))
    require({'job_id','path','class','execution_status','status','score'}<=set(scores),'score_columns')
    require(receipt.get('binding_sha256')==binding_hash and receipt.get('method_config_sha256')==method_hash and receipt.get('reference_event_sha256')==reference_hash,'run_receipt_binding')
    require(receipt.get('scores_sha256')==event_refs['scores']['sha256'],'run_receipt_score_hash')
    require(set(scores.job_id)=={j['job_id'] for j in jobs},'score_job_set')
    statuses=[]
    for job in jobs:
        sub=scores[scores.job_id==job['job_id']]
        require(len(sub)==len(test) and sub.path.is_unique and set(sub.path)==set(test.path),'score_population_missing_or_changed')
        require(sub['class'].eq(job['class']).all(),'score_class_changed')
        require(set(sub.execution_status)<=set(status_map),'unknown_execution_status')
        require(sub.execution_status.map(status_map).equals(sub.status),'score_status_mapping_changed')
        ok=sub.status.eq('ok');numeric=pd.to_numeric(sub.loc[ok,'score'],errors='coerce')
        require(np.isfinite(numeric.to_numpy()).all(),'nonfinite_success_score')
        require(sub.loc[~ok,'score'].eq('').all(),'failure_must_not_have_synthetic_score')
        statuses.append({'job_id':job['job_id'],'status_counts':sub.status.value_counts().to_dict(),'original_execution_status_counts':sub.execution_status.value_counts().to_dict(),'rows_preserved':len(sub)})
    learned=[job for job in jobs if job['kind']=='learned'];static=[job for job in jobs if job['kind']=='static']
    fits=receipt.get('fitted_states');require(isinstance(fits,list) and {x.get('job_id') for x in fits}=={j['job_id'] for j in learned},'fitted_state_job_set')
    require(len(fits)==len(learned),'duplicate_fitted_state')
    for fit in fits:
        require(fit.get('training_manifest_sha256')==receipt.get('training_manifest_sha256') and fit.get('fit_scope')=='training_manifest_only','fitted_state_training_scope')
        state=read_json(artifact(root,fit['state_artifact']))
        require(state.get('schema')=='external_B_fitted_state_binding_v1' and state.get('job_id')==fit['job_id'],'fitted_state_identity')
        require(state.get('binding_sha256')==binding_hash and state.get('method_config_sha256')==method_hash and state.get('training_manifest_sha256')==receipt['training_manifest_sha256'],'fitted_state_hash_bindings')
        require(state.get('training_node_ids')==train.node_id.astype(str).tolist() and state.get('training_source_sha256')==train.file_sha256.tolist(),'fitted_state_training_members_changed')
        require(state.get('fit_scope')=='training_manifest_only','fitted_state_fit_scope')
        require(state.get('fit_status') in ('ok','failed'),'fit_status_required')
        if state['fit_status']=='failed':
            require(state.get('fitted_object') is None,'failed_fit_must_not_invent_model')
            artifact(root,state['failure_log'])
            require(scores.loc[scores.job_id==fit['job_id'],'status'].eq('model_error').all(),'failed_fit_must_preserve_all_model_error_rows')
        else:artifact(root,state['fitted_object'])
    static_runs=receipt.get('static_runs')
    require(isinstance(static_runs,list) and len(static_runs)==len(static) and {x.get('job_id') for x in static_runs}=={j['job_id'] for j in static},'static_comparator_receipt_set')
    for run in static_runs:
        require(run.get('toolchain_inventory_sha256')==toolchain_hash and run.get('reference_event_sha256')==reference_hash,'static_comparator_binding')
        log=read_json(artifact(root,run['tool_log']))
        require(log.get('job_id')==run['job_id'] and log.get('binding_sha256')==binding_hash and log.get('outside_pragma_attempts')==0,'static_log_identity_or_policy')
        require(set(log.get('source_paths',[]))==set(test.path) and len(log['source_paths'])==len(test),'static_log_source_coverage')
    return statuses,receipt


def check(root,binding_path,expected_sha256,phase='setup',release_path=None,profile=Profile()):
    """Return fail-closed report; NEVER fit, score, write artifacts or invoke tools."""
    root=Path(root).resolve();binding_path=Path(binding_path)
    result={'schema':'external_B_integrity_preflight_result_v1','requested_phase':phase,'phase_integrity_pass':False,
            'execution_authorized':False,'human_identity_authenticated':False,'timestamp_authenticity_established':False,
            'operations_executed':0,'synthetic_profile':profile.synthetic,'blockers':[]}
    result['data_access_scope']='Coordinator integrity check may read source annotation/proxy labels and private sampling keys; not annotation-blind compiler setup'
    result['production_model_dispatch_implemented']=False
    try:
        if phase in ('begin_scoring','analyze'):
            admission=admission_preflight(root,binding_path,expected_sha256,release_path,profile,phase)
            result['review_admission']=admission
            require(admission['admission_artifacts_consistent'],'review_admission:'+','.join(admission['blockers']))
        binding,protocol,config,jobs,schema_bad,inference_ok=header(root,binding_path,expected_sha256,phase,profile)
        result['protocol_blockers']=schema_bad;result['inference_policy_allows_confirmatory_scope']=inference_ok
        paths={role:artifact(root,ref) for role,ref in binding['artifacts'].items()}
        train,test,key,allocation,frame,summary=bind_sources(root,binding,profile);result['input_summary']=summary
        result['toolchain']=bind_toolchain(root,read_json(paths['toolchain_inventory']),profile)
        jobs=job_plan(config,protocol);result['declared_jobs']=jobs
        required_events={'setup':0,'begin_review':1,'initial_reviews':2,'adjudication':3,'begin_scoring':3,'analyze':4}[phase]
        release=read_json(Path(release_path)) if release_path else {'schema':'external_B_release_chain_v1','events':[]}
        require(release.get('schema')=='external_B_release_chain_v1' and isinstance(release.get('events'),list),'release_chain_schema')
        require(len(release['events'])==required_events,'release_phase_count_or_reentry')
        previous=None;last_time=None;events=[];forms=None
        for index,ref in enumerate(release['events']):
            event=read_json(artifact(root,ref));require(event.get('schema')=='external_B_release_event_v1','release_event_schema')
            require(event.get('phase')==gate.RELEASE_ORDER[index],'release_event_order')
            require(event.get('binding_sha256')==expected_sha256 and event.get('previous_event_sha256')==previous,'release_chain_binding')
            created=timestamp(event.get('sealed_utc'));require(last_time is None or created>=last_time,'release_chronology')
            refs=event.get('artifacts');require(isinstance(refs,dict),'release_artifacts_missing')
            if index==0:
                require(set(refs)=={'freeze_record'},'freeze_record_missing')
                record=read_json(artifact(root,refs['freeze_record']))
                require(record.get('binding_sha256')==expected_sha256 and record.get('human_judgments_completed')==0 and record.get('model_fits_completed')==0 and record.get('external_scores_completed')==0,'freeze_after_results')
                require(isinstance(record.get('immutable_record_reference'),str) and bool(record['immutable_record_reference'].strip()),'freeze_record_reference_missing')
            elif index==1:
                forms=initial_reviews(root,refs,key,[r['reviewer_id'] for r in protocol['reviewers']])
                for form in forms:
                    for value in form.reviewed_utc:require(events[0]['_time']<=timestamp(value)<=created,'initial_review_before_freeze_or_after_seal')
            elif index==2:
                require(set(refs)=={'adjudication'},'adjudication_artifact_set')
                adjud=csv(artifact(root,refs['adjudication']))
                # Full alignment, provenance, distinct IDs and unknown handling; no model scores read.
                analyze_review(key,allocation,forms[0],forms[1],adjud)
                for value in adjud.adjudicated_utc:require(last_time<=timestamp(value)<=created,'adjudication_before_initial_seal_or_after_own_seal')
            elif index==3:
                statuses,receipt=sealed_scores(root,refs,jobs,test,train,expected_sha256,binding['artifacts']['method_config']['sha256'],previous,config['score_status_mapping'],binding['artifacts']['toolchain_inventory']['sha256'])
                require(receipt.get('training_manifest_sha256')==binding['artifacts']['training_manifest']['sha256'],'run_receipt_wrong_training_manifest')
                started=timestamp(receipt.get('fit_started_utc'));ended=timestamp(receipt.get('scoring_completed_utc'))
                require(last_time<=started<=ended<=created,'fitting_or_scoring_before_adjudication_seal')
                for static_run in receipt['static_runs']:
                    require(last_time<=timestamp(static_run['scan_started_utc'])<=timestamp(static_run['scan_completed_utc'])<=created,'static_analysis_before_adjudication_seal')
                result['score_coverage']=statuses
            event['_time']=created;events.append(event);previous=ref['sha256'];last_time=created
        result['phase_integrity_pass']=True
        result['sealed_events_checked']=len(events)
        result['binding_sha256']=expected_sha256
        result['scope']='Integrity relative to caller-selected digest; no human authentication, timestamp certification or execution permission'
    except (IntegrityError,OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
        result['blockers']=[str(exc)]
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--binding',type=Path,required=True);ap.add_argument('--expected-binding-sha256',required=True)
    ap.add_argument('--phase',choices=gate.PHASES,default='setup');ap.add_argument('--release',type=Path)
    args=ap.parse_args();result=check(args.root,args.binding,args.expected_binding_sha256,args.phase,args.release)
    print(json.dumps(result,indent=2,allow_nan=False));return 0 if result['phase_integrity_pass'] else 2
if __name__=='__main__':raise SystemExit(main())
