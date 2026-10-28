"""Inactive amendment's pure in-memory reporting adapter; no actual input CLI.

No models, file-based human judgments or score files are opened. Numerical
functions do not authenticate reviewers or activate the scientific amendment.
"""
from __future__ import annotations
import hashlib,json,math,re,sys
from fractions import Fraction
from pathlib import Path
from types import ModuleType
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
B=HERE.parent

def _load(name,path):
    source=path.read_bytes();module=ModuleType(name);module.__file__=str(path)
    module.__loaded_sha256__=hashlib.sha256(source).hexdigest();sys.modules[name]=module
    exec(compile(source,str(path),'exec'),module.__dict__)
    return module

review=_load('_reporting_exact_review',B/'review_estimators.py')
v1=_load('_reporting_exact_performance_v1',B/'performance_v1/performance.py')
v1.review=review
v2=_load('_reporting_exact_performance_v2',B/'performance_v2/performance.py')
v2.v1=v1
bounds=_load('_reporting_exact_ap_bounds',B/'ap_bounds_v1/ap_bounds.py')
DEPENDENCY_DIGESTS={str(Path(m.__file__).relative_to(B)):m.__loaded_sha256__ for m in [review,v1,v2,bounds]}
PRIMARY_METHODS=('raw_tfidf_lr','normalized_tfidf_lr','pattern_rf','pattern_lgbm','slither')
CLASSES=('reentrancy','unchecked')

def _require(condition,message):
    if not condition:raise ValueError(message)

def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def primary_inventory(target_class):
    _require(target_class in CLASSES,'Unknown class')
    out=[]
    for method in PRIMARY_METHODS:
        for seed in (range(5) if method in ('pattern_rf','pattern_lgbm') else [0]):
            job=f'slither:{target_class}:0' if method=='slither' else f'{method}:{target_class}:{seed}'
            out.append({'job_id':job,'method':method,'class':target_class,'seed':seed,'variant':'primary'})
    return out

def production_admission(*args,**kwargs):
    """Closed before opening any binding, label, score or arbitrary path.

    A future reviewed version must bind reporting/AP code and the adopted
    analysis policy to the original sealed-release chain. No names or boolean
    supplied by a caller can activate this inactive amendment.
    """
    return {'admitted':False,'reason':'inactive_inference_amendment_no_production_reporting_release',
            'labels_opened':False,'scores_opened':False,'execution_authorized':False,
            'human_identity_authenticated':False,'files_opened':0}

def _identity_checks(frame,sample,case_manifest,first,second,adjudication):
    keys=['case_id','path','class','source_id','label_status']
    for name,data in [('sample',sample),('frozen_case_manifest',case_manifest)]:
        _require(set(keys)<=set(data),'Missing joint case/file/class bindings: '+name)
        _require(data.case_id.is_unique and not data[['path','class']].duplicated().any(),'Duplicate reference identity: '+name)
        _require(not data[keys].isna().any().any(),'Missing reference identity: '+name)
    left=sample[keys].sort_values('case_id').reset_index(drop=True)
    right=case_manifest[keys].sort_values('case_id').reset_index(drop=True)
    _require(left.equals(right),'Case/file/class mapping differs from frozen case manifest')
    for name,form in [('first',first),('second',second),('adjudication',adjudication)]:
        _require({'case_id','class'}<=set(form) and form.case_id.is_unique,'Missing or duplicate review identity: '+name)
        _require(set(form.case_id)==set(sample.case_id),'Missing or unexpected review case: '+name)
        aligned=form.set_index('case_id').loc[left.case_id]
        _require(aligned['class'].tolist()==left['class'].tolist(),'Review case/class mismatch: '+name)
        if 'path' in aligned:_require(aligned.path.tolist()==left.path.tolist(),'Review case/file mismatch: '+name)
    return _digest(left.to_dict('records'))

def _scores(scores,target_class,paths):
    required={'job_id','method','class','seed','variant','path','execution_status','status','score'}
    _require(required<=set(scores),'Complete job, seed, variant and execution status fields required')
    ids=['job_id','method','class','variant','path','execution_status','status']
    _require(not scores[ids].isna().any().any() and all(isinstance(x,str) and x.strip() for x in scores[ids].to_numpy().ravel()),'Blank score identity or status')
    _require(set(scores['class'])=={target_class},'Exactly one declared score class required')
    _require(not scores[['job_id','path']].duplicated().any(),'Duplicate job/file score rows')
    seeds=scores.seed.to_numpy()
    _require(all(not isinstance(x,(bool,np.bool_)) and isinstance(x,(int,np.integer)) and x>=0 for x in seeds),'Integer seed IDs required')
    inventory=primary_inventory(target_class);expected={x['job_id']:x for x in inventory}
    broad_id=f'slither_broad:{target_class}:0'
    observed=set(scores.job_id)
    _require(observed in (set(expected),set(expected)|{broad_id}),'Exactly13 primary vectors and optional broad Slither required')
    for job,rows in scores.groupby('job_id',sort=False):
        identity=expected.get(job,{'job_id':broad_id,'method':'slither','class':target_class,'seed':0,'variant':'broad_secondary'})
        for column in ['method','class','seed','variant']:_require(rows[column].eq(identity[column]).all(),'Job identity mismatch: '+job+':'+column)
        _require(len(rows)==len(paths) and set(rows.path)==set(paths),'Every job must retain exactly the full file population')
        _require(set(rows.status)<={'ok',*v2.FAILURE_STATUSES},'Unknown canonical status')
        good=rows.status.eq('ok');numeric=rows.score.to_numpy(dtype=float)
        _require(np.isfinite(numeric[good]).all() and np.isnan(numeric[~good]).all(),'Finite success and missing failure scores required')
        _require(rows.execution_status.eq('ok').equals(good),'Raw execution success must agree with canonical success')
        if identity['method']=='slither':_require(np.isin(numeric[good],[0,1]).all(),'Slither union scores must be binary')
    if broad_id in observed:
        a=scores[scores.job_id.eq(f'slither:{target_class}:0')].set_index('path').loc[paths]
        b=scores[scores.job_id.eq(broad_id)].set_index('path').loc[paths]
        for field in ['status','execution_status']:_require(a[field].equals(b[field]),'Primary and broad Slither must share scan status')
        if 'scan_trace_sha256' in scores:
            _require(all(isinstance(x,str) and re.fullmatch('[0-9a-f]{64}',x) for x in a.scan_trace_sha256) and a.scan_trace_sha256.equals(b.scan_trace_sha256),'Primary and broad scan trace identities differ')
        ok=a.status.eq('ok');left=a.loc[ok,'score'].to_numpy(dtype=float);right=b.loc[ok,'score'].to_numpy(dtype=float)
        _require(np.all(right>=left) if target_class=='reentrancy' else np.array_equal(left,right),'Broad Slither violates the unchanged class union rule')
    main=scores[scores.job_id.isin(expected)].copy();main['method']=main.job_id
    broad=scores[scores.job_id.eq(broad_id)].copy();broad['method']=broad.job_id
    return inventory,main,broad

def _ht_summary(coeff,domain,full_labels,selected,allocation,y,positions):
    """Signed linear totals; endpoint estimates are not logical bounds."""
    coeff=np.asarray(coeff,dtype=float);domain=np.asarray(domain,dtype=bool)
    _require(coeff.shape==domain.shape==full_labels.shape and np.isfinite(coeff).all(),'Aligned finite full-frame contributions required')
    _require(np.all(coeff[~domain]==0),'Outside-domain contribution must be zero')
    c=coeff[positions];d=domain[positions];missing=np.isnan(y)&d
    known=np.where(np.isfinite(y),y,0.0)*c
    low=known+np.where(missing,np.minimum(c,0),0)
    high=known+np.where(missing,np.maximum(c,0),0)
    lo=v1.ht_total(low,selected,allocation);hi=v1.ht_total(high,selected,allocation)
    point=None if missing.any() else v1.ht_total(known,selected,allocation)
    unobserved=np.isnan(full_labels)&domain
    fixed=float(np.sum(coeff*np.where(np.isfinite(full_labels),full_labels,0)))
    hard=[fixed+float(np.minimum(coeff[unobserved],0).sum()),fixed+float(np.maximum(coeff[unobserved],0).sum())]
    return {'estimator':'HT_linear_total_original_stratified_SRSWOR_design_unclipped',
      'status':'suppressed_unknown_sample_outcomes_in_target' if missing.any() else 'defined',
      'point':point,'unknown_sample_in_domain_n':int(missing.sum()),
      'unknown_sample_outside_domain_n':int((np.isnan(y)&~d).sum()),
      'endpoint_estimates':{'lower':lo,'upper':hi,'meaning':'HT estimates of completed endpoint variables, not hard population bounds'},
      'logical_population_bounds':{'lower':hard[0],'upper':hard[1],'unknown_population_n':int(unobserved.sum()),
        'meaning':'Hard bounds from known labels and every remaining unassessed or unresolved file'},
      'confidence_interval':None,'variance_zero_means_certainty':False,'unknowns_dropped_or_negative':False,
      'sampling_design_redefined':False,'outcome_scope':'fixed finite frame conditional on reference process and fixed queue'}

def fixed_queue_ht(coeff,domain,full_labels,sample,allocation,y,positions):
    """Expose the signed finite-frame total for independent numerical checks.

    `positions` maps the unchanged sampled rows into the full population arrays.
    This low-level function expects already validated binary/unknown references.
    """
    full_labels=np.asarray(full_labels,dtype=float);y=np.asarray(y,dtype=float)
    positions=np.asarray(positions)
    _require(full_labels.ndim==1 and np.asarray(domain).dtype==np.bool_,'One-dimensional population labels and explicit boolean domain required')
    _require(np.isfinite(np.asarray(coeff,dtype=float)).all() and np.all(np.abs(np.asarray(coeff,dtype=float))<=1),'Queue or paired-queue coefficients must be in [-1,1]')
    _require(y.shape==(len(sample),) and positions.shape==y.shape,'Sample alignment required')
    _require(positions.dtype.kind in 'iu' and len(set(positions.tolist()))==len(positions) and
             np.all((positions>=0)&(positions<len(full_labels))),'Unique valid sample positions required')
    for values in [full_labels,y]:
        _require(not np.isinf(values).any() and np.isin(values[np.isfinite(values)],[0,1]).all(),'Binary or unknown labels required')
    _require(np.array_equal(full_labels[positions],y,equal_nan=True),'Sample and full reference labels differ')
    return _ht_summary(coeff,domain,full_labels,sample,allocation,y,positions)

def _ap_record(scores,success,domain,labels,paths,domain_id):
    ids=np.flatnonzero(domain);p=[paths[i] for i in ids];lab=[None if np.isnan(labels[i]) else int(labels[i]) for i in ids]
    meta={'domain_id':domain_id,'paths':p,'reference_completion_id':_digest(list(zip(p,lab))),
          'no_confidence_level':True,'unassessed_or_unresolved_are_unknown':True}
    if not len(ids):
        return {**meta,'status':'undefined_empty_domain','defined_completions_exist':False,'undefined_possible':True,
                'lower_ap':None,'upper_ap':None,'identified_ap':None,'unknown_count':0}
    if not np.all(success[domain]):
        return {**meta,'status':'suppressed_missing_scores_no_complete_queue','defined_completions_exist':None,
                'undefined_possible':None,'lower_ap':None,'upper_ap':None,'identified_ap':None,
                'unknown_count':sum(x is None for x in lab),'failed_score_n':int((~success[domain]).sum())}
    result=bounds.result_record(bounds.sharp_ap_completion_bounds([float(scores[i]) for i in ids],lab))
    return {**result,**meta,'status':'defined_bounds' if result['defined_completions_exist'] else 'undefined_no_positive_completion'}

def ap_difference_envelope(left,right):
    _require(left['domain_id']==right['domain_id'] and left['reference_completion_id']==right['reference_completion_id'],
             'AP contrast requires same domain and label completions')
    possible=None if left['undefined_possible'] is None or right['undefined_possible'] is None else bool(left['undefined_possible'] or right['undefined_possible'])
    out={'kind':'conservative_generally_nonsharp_AP_difference_envelope_not_confidence_interval',
         'direction':'left_minus_raw_LR','undefined_possible':possible,'lower':None,'upper':None,
         'domain_id':left['domain_id'],'reference_completion_id':left['reference_completion_id'],
         'conditional_on_both_APs_defined':True,'separate_endpoint_completions_may_be_incompatible':True,
         'confidence_level':None,'superiority_claim':False}
    if left['defined_completions_exist'] is not True or right['defined_completions_exist'] is not True:
        return {**out,'status':'suppressed_missing_or_undefined_component'}
    f=lambda x:Fraction(int(x['numerator']),int(x['denominator']))
    return {**out,'status':'defined_completion_envelope','lower':bounds.rational_record(f(left['lower_ap'])-f(right['upper_ap'])),
            'upper':bounds.rational_record(f(left['upper_ap'])-f(right['lower_ap']))}

def _exploratory_record(record):
    return {'point':record.get('point'),'percentile_range':record.get('interval'),
      'range_label':'exploratory_design_approximate_percentiles_not_calibrated_confidence_interval',
      'status':record.get('status'),'invalid_replicates':record.get('invalid_replicates'),
      'replicates_requested':record.get('replicates_requested'),'replicate_id':record.get('replicate_id'),
      'interval_coverage_validated':False,'invalid_replicates_dropped':False}

def report_class(frame,sample,allocation,first,second,adjudication,scores,target_class,*,case_manifest,
                 expected_files=1998,expected_sample_cases=180,review_fractions=(.05,.1,.2),
                 include_exploratory=False,replicates=2000,seed=20261026,alpha=.05,synthetic_fixture=False):
    """Pure numerical API. Call only on authorized in-memory inputs.

    This does not open source/label/score files and supplies no production
    authorization. The separate production admission is deliberately inactive.
    `case_manifest` is the independently retained frozen case-to-file mapping.
    """
    _require(isinstance(synthetic_fixture,bool),'Explicit boolean synthetic profile required')
    _require(synthetic_fixture or (expected_files,expected_sample_cases)==(1998,180),'Count overrides require an explicit synthetic fixture')
    _require(isinstance(include_exploratory,bool),'Explicit boolean exploratory flag required')
    _require(synthetic_fixture or (tuple(review_fractions)==(.05,.1,.2) and replicates==2000 and seed==20261026 and alpha==.05),'Analysis parameter overrides require an explicit synthetic fixture')
    v1._alpha(alpha)
    paths=v2._frame(frame,target_class,expected_files,CLASSES)
    inventory,main,broad=_scores(scores,target_class,paths)
    methods=[x['job_id'] for x in inventory]
    # All domains and queues are fixed using statuses/scores before reference joins.
    plan=v2.plan_score_domains(frame,main,target_class,methods=methods,expected_files=expected_files,classes=CLASSES,review_fractions=review_fractions)
    case_digest=_identity_checks(frame,sample,case_manifest,first,second,adjudication)
    selected,alloc,y=v2._references(frame,sample,allocation,first,second,adjudication,target_class,expected_sample_cases)
    pos={path:i for i,path in enumerate(paths)};ids=np.asarray([pos[x] for x in selected.path])
    labels=np.full(len(paths),np.nan);labels[ids]=y
    baseline=f'raw_tfidf_lr:{target_class}:0'
    domains={}
    for name,domain in plan['domains'].items():
        mask=domain['mask'];domain_id=domain['domain_id'];vectors={};contrasts=[]
        positive=_ht_summary(mask.astype(float),mask,labels,selected,alloc,y,ids)
        for job in methods:
            data=plan['methods'][job];work=[]
            for queue in domain['methods'][job]['queues']:
                work.append({**{k:v for k,v in queue.items() if k!='q'},
                             'positive_yield':_ht_summary(queue['q'],mask,labels,selected,alloc,y,ids)})
            vectors[job]={'ap_completion':_ap_record(data['scores'],data['success'],mask,labels,paths,domain_id),'workload':work}
        for job in methods[1:]:
            paired=[]
            for left,right in zip(domain['methods'][job]['queues'],domain['methods'][baseline]['queues']):
                paired.append({'review_fraction':left['review_fraction'],'review_count_requested':left['review_count_requested'],
                  'positive_yield_difference':_ht_summary(left['q']-right['q'],mask,labels,selected,alloc,y,ids)})
            contrasts.append({'left':job,'right':baseline,'direction':'left_minus_raw_LR','workload':paired,
              'ap_difference_envelope':ap_difference_envelope(vectors[job]['ap_completion'],vectors[baseline]['ap_completion'])})
        domains[name]={'population_n':domain['population_n'],'domain_id':domain_id,
          'target_population_changed_from_full':name=='common_success' and domain['population_n']!=len(paths),
          'selected_outside_domain_retained_n':int((~mask[ids]).sum()),'sample_design_redefined':False,
          'reference_positive_total':positive,'vectors':vectors,'raw_LR_reference_contrasts':contrasts,
          'ranking_defined':bool(mask.any())}
    coverage={job:{'full_frame_n':len(paths),'success_n':int(data['success'].sum()),'failure_n':int((~data['success']).sum()),
      'canonical_status_counts':data['status_counts'],'original_execution_status_counts':scores[scores.job_id.eq(job)].execution_status.value_counts().to_dict()}
      for job,data in plan['methods'].items()}
    secondary=None
    if len(broad):
        job=broad.job_id.iloc[0];bplan=v2.plan_score_domains(frame,broad,target_class,methods=[job],expected_files=expected_files,classes=CLASSES,review_fractions=review_fractions)
        bdata=bplan['methods'][job];bdom=bplan['domains']['full_frame_pipeline']
        secondary={'label':'prespecified_broad_Slither_secondary_sensitivity','job_id':job,'excluded_from_primary_common_domain':True,
          'success_n':int(bdata['success'].sum()),'status_counts':bdata['status_counts'],
          'ap_completion':_ap_record(bdata['scores'],bdata['success'],bdom['mask'],labels,paths,bdom['domain_id']),
          'workload':[{**{k:v for k,v in q.items() if k!='q'},'positive_yield':_ht_summary(q['q'],bdom['mask'],labels,selected,alloc,y,ids)} for q in bdom['methods'][job]['queues']]}
    result={'schema':'external_B_inactive_reporting_v1','synthetic_fixture':synthetic_fixture,'class':target_class,'primary_inventory':inventory,'primary_vector_count':13,
      'paired_reference':baseline,'paired_contrasts_per_domain':12,'case_manifest_identity_sha256':case_digest,
      'primary':{'coverage':coverage,'domains':domains},'secondary_broad_slither':secondary,
      'annotation_audit':review.analyze_review(sample,allocation,first,second,adjudication,alpha),
      'exploratory':None,'engine_audit':None,'dependency_source_sha256':DEPENDENCY_DIGESTS,
      'policy':{'amendment_active':False,'production_release_authorized':False,'queues_before_reference_join':True,
        'no_model_fits_or_tool_calls':True,'primary_has_no_default_Wald_or_bootstrap_CI':True,
        'HT_totals_unclipped':True,'AP_bounds_are_logical_not_confidence':True,
        'reference_errors_and_new_family_inference_not_covered':True,'seeds_not_independent_external_populations':True}}
    if include_exploratory:
        engine=v2.evaluate_methods(frame,sample,allocation,first,second,adjudication,main,target_class,methods=methods,
          expected_files=expected_files,expected_sample_cases=expected_sample_cases,review_fractions=review_fractions,
          replicates=replicates,seed=seed,alpha=alpha)
        filtered={}
        for name,domain in engine['domains'].items():
            vectors={job:{'AP':_exploratory_record(data['ap']),'workload':[{'review_fraction':q['review_fraction'],
                'recall':_exploratory_record(q['recall']),'yield':_exploratory_record(q['yield'])} for q in data['workload']]}
                for job,data in domain['methods'].items()}
            contrasts=[];census=bool((alloc.N_h==alloc.n_h).all())
            for job in methods[1:]:
                a,b=domain['methods'][job],domain['methods'][baseline]
                record={'left':job,'right':baseline,'AP':_exploratory_record(v2.paired_difference(a['ap'],b['ap'],alpha=alpha,census=census)),'workload':[]}
                for qa,qb in zip(a['workload'],b['workload']):
                    record['workload'].append({'review_fraction':qa['review_fraction'],**{metric:_exploratory_record(v2.paired_difference(qa[metric],qb[metric],alpha=alpha,census=census)) for metric in ['yield','recall']}})
                contrasts.append(record)
            filtered[name]={'vectors':vectors,'raw_LR_reference_contrasts':contrasts}
        result['exploratory']={'label':'design_approximate_diagnostics_not_confirmatory_uncertainty','bootstrap':engine['bootstrap'],'domains':filtered}
        result['engine_audit']={'label':'UNFILTERED_FROZEN_ENGINE_AUDIT_NOT_PRIMARY_REPORT','raw_output':engine}
    return result
