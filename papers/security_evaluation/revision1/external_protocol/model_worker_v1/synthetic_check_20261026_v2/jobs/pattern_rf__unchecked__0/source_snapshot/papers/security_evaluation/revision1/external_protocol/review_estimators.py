"""Design-based human annotation assessment for a fixed stratified finite frame.

No source unknown becomes a negative. No model is run. Blank human forms are
rejected. Exact hypergeometric intervals are simultaneous across input strata;
unknown-reference outcomes give identification bounds, not imputed answers.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import hypergeom

STRATA=['source_id','class','label_status']
CATEGORIES=('positive','negative','unknown')
POS='source_reported_positive_pending_adjudication'
NONPOS={'source_class_not_listed_pending_adjudication','source_reported_no_finding_pending_adjudication'}

def hypergeometric_interval(N,n,k,alpha=.05):
    """Equal-tailed exact confidence set for integer population success count K.

    Invert hypergeom.sf(k-1;N,K,n)>=alpha/2 and cdf(k;N,K,n)>=alpha/2.
    Discreteness makes coverage conservative. A census has no sampling error.
    """
    if any(isinstance(x,bool) or not isinstance(x,(int,np.integer)) for x in [N,n,k]):raise ValueError('N,n,k must be integers')
    if not 0<=k<=n<=N or not 0<alpha<1:raise ValueError('Invalid finite-population counts or alpha')
    if n==0:return 0,int(N)
    if n==N:return int(k),int(k)
    lower,upper=int(k),int(N-n+k)
    lo,hi=lower,upper
    while lo<hi:
        mid=(lo+hi)//2
        if hypergeom.sf(k-1,N,mid,n)<alpha/2:lo=mid+1
        else:hi=mid
    Klo=lo;lo,hi=lower,upper
    while lo<hi:
        mid=(lo+hi+1)//2
        if hypergeom.cdf(k,N,mid,n)<alpha/2:hi=mid-1
        else:lo=mid
    return int(Klo),int(lo)

def stratum_bounds(N,outcomes,alpha=.05):
    if isinstance(N,bool) or not isinstance(N,(int,np.integer)) or N<1:raise ValueError('N must be a positive integer')
    y=np.asarray([np.nan if x is None else x for x in outcomes],dtype=float);n=len(y)
    if not 1<=n<=N or not np.isin(y[np.isfinite(y)],[0,1]).all() or np.isinf(y).any():raise ValueError('Expected binary/unknown sampled outcomes and valid population size')
    if n==1 and N>1:raise ValueError('Non-census n=1 cannot estimate design variance')
    unknown=np.isnan(y);lower=np.where(unknown,0,y);upper=np.where(unknown,1,y)
    k=int(lower.sum());u=int(unknown.sum())
    Klo=hypergeometric_interval(N,n,k,alpha)[0]
    Khi=hypergeometric_interval(N,n,k+u,alpha)[1]
    def variance(z):return 0. if n==N else float(N*N*(1-n/N)*np.var(z,ddof=1)/n)
    return {'N_h':int(N),'n_h':n,'known_successes':k,'unknown_n':u,
      'estimated_total_lower':float(N*lower.mean()),'estimated_total_upper':float(N*upper.mean()),
      'variance_total_lower_indicator':variance(lower),'variance_total_upper_indicator':variance(upper),
      'sampling_confidence_total_lower':Klo,'sampling_confidence_total_upper':Khi,
      'stratum_alpha':alpha,'unknowns_imputed':False}

def finite_population_domain(strata,alpha=.05,simultaneous_strata=None):
    """Aggregate complete sampling strata for a fixed known-size domain.

    strata is [(N_h, sampled binary/None outcomes), ...]. All selected cases,
    including unknowns, must occur. The sampling confidence envelope combines
    exact stratum intervals with Bonferroni familywise coverage.
    """
    if not strata:raise ValueError('Empty domain')
    H=len(strata) if simultaneous_strata is None else simultaneous_strata
    if isinstance(H,bool) or not isinstance(H,(int,np.integer)) or H<len(strata):raise ValueError('Invalid simultaneous stratum count')
    rows=[stratum_bounds(N,y,alpha/H) for N,y in strata]
    N=sum(x['N_h'] for x in rows);n=sum(x['n_h'] for x in rows)
    low=sum(x['estimated_total_lower'] for x in rows)/N;up=sum(x['estimated_total_upper'] for x in rows)/N
    vl=sum(x['variance_total_lower_indicator'] for x in rows)/(N*N)
    vu=sum(x['variance_total_upper_indicator'] for x in rows)/(N*N)
    complete=all(x['unknown_n']==0 for x in rows)
    return {'population_domain_N':N,'sample_domain_n':n,'unknown_sample_n':sum(x['unknown_n'] for x in rows),
      'point_rate':low if complete else None,'point_variance':vl if complete else None,
      'identification_rate_lower':low,'identification_rate_upper':up,
      'variance_lower_indicator':vl,'variance_upper_indicator':vu,
      'sampling_confidence_envelope_lower':sum(x['sampling_confidence_total_lower'] for x in rows)/N,
      'sampling_confidence_envelope_upper':sum(x['sampling_confidence_total_upper'] for x in rows)/N,
      'confidence_level_at_least':1-alpha,'simultaneous_strata':int(H),
      'coverage_scope':'this outcome/domain envelope; not simultaneous across all differently defined outcomes',
      'interval':'exact finite hypergeometric per stratum; Bonferroni aggregation; unknown envelope',
      'estimand':'fixed finite-population reference outcome; not superpopulation or perfect-ground-truth accuracy',
      'strata':rows}

def agreement(first,second,weights=None):
    """Raw or survey-weighted nominal 3-category agreement; no truth claim."""
    a=list(first);b=list(second)
    if len(a)!=len(b) or not a:raise ValueError('Nonempty paired reviewer answers required')
    if set(a+b)-set(CATEGORIES):raise ValueError('Reviewer answers must be positive/negative/unknown')
    w=np.ones(len(a)) if weights is None else np.asarray(weights,dtype=float)
    if w.shape!=(len(a),) or not np.isfinite(w).all() or (w<=0).any():raise ValueError('Positive finite aligned weights required')
    table=np.zeros((3,3))
    for x,y,z in zip(a,b,w):table[CATEGORIES.index(x),CATEGORIES.index(y)]+=z
    prob=table/table.sum();p1=prob.sum(axis=1);p2=prob.sum(axis=0)
    observed=float(np.trace(prob));expected=float(p1@p2)
    kappa=None if math.isclose(expected,1.,rel_tol=0.,abs_tol=1e-14) else (observed-expected)/(1-expected)
    category={name:(float(2*prob[i,i]/(p1[i]+p2[i])) if p1[i]+p2[i]>0 else None) for i,name in enumerate(CATEGORIES)}
    return {'categories':list(CATEGORIES),'table_estimated_counts':table.tolist(),
      'reviewer_1_marginals':p1.tolist(),'reviewer_2_marginals':p2.tolist(),
      'agreement':observed,'expected_marginal_agreement':expected,'cohen_kappa':kappa,
      'kappa_status':'undefined_expected_agreement_one' if kappa is None else 'defined_descriptive_only',
      'category_specific_agreement':category,'survey_weighted':weights is not None,
      'correctness_inferred':False,'kappa_interval':None}

def analyze_review(key,allocation,first,second,adjudication,alpha=.05):
    """Require every preselected case; labels/metadata cannot be silently swapped."""
    for name,d in [('key',key),('first',first),('second',second),('adjudication',adjudication)]:
        if not d.case_id.is_unique:raise ValueError(name+': duplicate case IDs')
        if set(d.case_id)!=set(key.case_id):raise ValueError(name+': incomplete or unexpected cases')
    if key[['path','class']].duplicated().any():raise ValueError('Duplicate probability unit')
    if allocation[STRATA].duplicated().any():raise ValueError('Duplicate allocation strata')
    counts=allocation[['N_h','n_h']].to_numpy(dtype=float)
    if not np.isfinite(counts).all() or (counts<1).any() or (counts!=np.floor(counts)).any() or (counts[:,1]>counts[:,0]).any():raise ValueError('Allocation requires positive integer counts with n_h <= N_h')
    a=allocation.set_index(STRATA)
    grouped=key.groupby(STRATA,sort=True)
    if set(grouped.groups)!=set(a.index):raise ValueError('Stratum frame mismatch')
    for s,g in grouped:
        r=a.loc[s]
        if len(g)!=r.n_h:raise ValueError('Wrong selected count in '+str(s))
        for c,want in [('N_h',r.N_h),('n_h',r.n_h),('inclusion_probability',r.n_h/r.N_h),('design_weight',r.N_h/r.n_h)]:
            if not np.allclose(g[c].astype(float),want,rtol=1e-12,atol=1e-12):raise ValueError('Incorrect '+c)
    d=key.set_index('case_id').copy()
    for name,form,column in [('first',first,'judgment_positive_negative_unknown'),('second',second,'judgment_positive_negative_unknown'),('reference',adjudication,'adjudicated_judgment')]:
        f=form.set_index('case_id').loc[d.index]
        if not f['class'].equals(d['class']):raise ValueError('Class mismatch: '+name)
        if set(f[column])-set(CATEGORIES):raise ValueError('Pending or invalid human judgments: '+name)
        provenance=['adjudicator_id','adjudication_reason','adjudicated_utc'] if name=='reference' else ['reviewer_id','reviewed_utc','reason']
        for c in provenance:
            if c not in f or f[c].isna().any() or f[c].astype(str).str.strip().eq('').any():raise ValueError('Missing human provenance: '+name+':'+c)
        d[name]=f[column]
    reviewer_ids=[set(form.reviewer_id.astype(str).str.strip().str.casefold()) for form in [first,second]]
    if any(len(ids)!=1 for ids in reviewer_ids) or reviewer_ids[0]&reviewer_ids[1]:raise ValueError('Two distinct identified reviewers must each complete their own form')
    adj=adjudication.set_index('case_id').loc[d.index]
    for c,name in [('reviewer_1_judgment','first'),('reviewer_2_judgment','second')]:
        if c not in adj or not adj[c].equals(d[name]):raise ValueError('Adjudication does not preserve initial judgments: '+name)
    d=d.reset_index();domains=[]
    for (cls,status),sub in d.groupby(['class','label_status'],sort=True):
        if status!=POS and status not in NONPOS:raise ValueError('Unknown source-status domain cannot be silently binary-labelled')
        strata=[];unknown_strata=[]
        for s,g in sub.groupby(STRATA,sort=True):
            N=int(a.loc[s].N_h)
            y=[None if x=='unknown' else int(x==('negative' if status==POS else 'positive')) for x in g.reference]
            strata.append((N,y));unknown_strata.append((N,[int(x=='unknown') for x in g.reference]))
        domains.append({'class':cls,'source_status':status,
          'outcome':'expert_negative_among_source_positive' if status==POS else 'expert_positive_among_source_nonpositive',
          'assessment':finite_population_domain(strata,alpha,len(a)),
          'unknown_reference_rate':finite_population_domain(unknown_strata,alpha,len(a))})
    ag={}
    for cls,sub in d.groupby('class'):
        ag[cls]={'raw_selected_sample':agreement(sub['first'],sub['second']),
                 'finite_population_weighted':agreement(sub['first'],sub['second'],sub.design_weight)}
    return {'schema':'probability_human_review_estimates_v1','case_unit':'file by class',
      'sample_cases':len(d),'population_cases':int(allocation.N_h.sum()),'domains':domains,'agreement_by_class':ag,
      'unknowns_not_dropped_or_relabelled':True,'human_reference':'expert-adjudicated conditional reference, not infallible truth',
      'no_models_or_external_scores_used':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['key','allocation','first','second','adjudication','out']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--alpha',type=float,default=.05);a=p.parse_args()
    if a.out.exists():raise FileExistsError('Never overwrite existing analysis')
    args=[pd.read_csv(getattr(a,n),keep_default_na=False) for n in ['key','allocation','first','second','adjudication']]
    result=analyze_review(*args,alpha=a.alpha)
    result['input_sha256']={n:hashlib.sha256(getattr(a,n).read_bytes()).hexdigest() for n in ['key','allocation','first','second','adjudication']}
    result['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':'complete','sample_cases':result['sample_cases'],'models_executed':0}))
if __name__=='__main__':main()
