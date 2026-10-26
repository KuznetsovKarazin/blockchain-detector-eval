"""Enumerated design checks and regression tests; no real human labels created."""
import importlib.util,itertools
from pathlib import Path
import numpy as np
import pytest
BASE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('review_estimators',BASE/'review_estimators.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_exact_hypergeometric_interval_coverage_enumerated():
    for N in range(2,10):
        for n in range(1,N+1):
            for K in range(N+1):
                y=[1]*K+[0]*(N-K);covered=total=0
                for ids in itertools.combinations(range(N),n):
                    k=sum(y[i] for i in ids);lo,hi=m.hypergeometric_interval(N,n,k,.1)
                    total+=1;covered+=lo<=K<=hi
                assert covered/total>=.9-1e-12


def test_ht_design_variance_matches_exact_sampling_distribution():
    populations=[([1,0,0,0],2),([1,1,1,0,0,0],3)]
    estimates=[];estimated_variances=[]
    for first in itertools.combinations(populations[0][0],2):
        for second in itertools.combinations(populations[1][0],3):
            r=m.finite_population_domain([(4,first),(6,second)])
            estimates.append(r['point_rate']);estimated_variances.append(r['point_variance'])
    assert np.mean(estimates)==pytest.approx(.4)
    assert np.mean(estimated_variances)==pytest.approx(np.var(estimates,ddof=0),rel=1e-12)


def test_unequal_inclusion_probabilities_need_weights():
    # S1 all positive n=2/2; S2 all negative n=2/8. Raw sample rate .5 vs true .2.
    r=m.finite_population_domain([(2,[1,1]),(8,[0,0])])
    assert r['point_rate']==pytest.approx(.2)
    assert np.mean([1,1,0,0])==.5


def test_zero_observed_errors_does_not_imply_zero_width_interval():
    r=m.finite_population_domain([(100,[0]*10)])
    assert r['point_rate']==0 and r['point_variance']==0
    assert r['sampling_confidence_envelope_upper']>0


def test_unknowns_give_bounds_and_no_fabricated_point_estimate():
    r=m.finite_population_domain([(20,[1,0,None,None])])
    assert r['point_rate'] is None and r['point_variance'] is None
    assert r['identification_rate_lower']==.25 and r['identification_rate_upper']==.75
    assert r['unknown_sample_n']==2
    assert r['sampling_confidence_envelope_lower']<=.25 and r['sampling_confidence_envelope_upper']>=.75


def test_unknown_census_has_no_sampling_error_but_reference_uncertainty():
    r=m.finite_population_domain([(4,[1,0,None,None])])
    assert r['sampling_confidence_envelope_lower']==.25
    assert r['sampling_confidence_envelope_upper']==.75
    assert r['variance_lower_indicator']==r['variance_upper_indicator']==0


def test_noncensus_n1_variance_is_not_invented():
    with pytest.raises(ValueError):m.stratum_bounds(20,[0])


def test_one_class_kappa_undefined_not_one():
    r=m.agreement(['negative']*3,['negative']*3)
    assert r['agreement']==1 and r['cohen_kappa'] is None
    assert r['kappa_status']=='undefined_expected_agreement_one'


def test_weighted_agreement_separate_from_raw_sample():
    raw=m.agreement(['positive','negative'],['positive','positive'])
    weighted=m.agreement(['positive','negative'],['positive','positive'],[1,9])
    assert raw['agreement']==.5 and weighted['agreement']==.1
    assert weighted['correctness_inferred'] is False


def test_blank_human_forms_rejected_in_actual_frozen_packet():
    import pandas as pd
    b=BASE/'packet_probability_20261025_v1';root=BASE.parents[3]
    keypath=root/'data/derived/revision1_external_review_probability_20261025_v1/coordinator_sampling_key.csv'
    if not keypath.exists():pytest.skip('Private frozen packet not locally materialized')
    vals=[pd.read_csv(p,keep_default_na=False) for p in [keypath,b/'stratum_allocation.csv',b/'reviewer_1_blank.csv',b/'reviewer_2_blank.csv',b/'adjudication_blank.csv']]
    with pytest.raises(ValueError,match='Pending or invalid human judgments'):m.analyze_review(*vals)


def test_population_size_is_not_silently_rounded():
    with pytest.raises(ValueError):m.finite_population_domain([(2.9,[0,1])])
    with pytest.raises(ValueError):m.finite_population_domain([(True,[0])])
    with pytest.raises(ValueError):m.finite_population_domain([(2,[0,1])],simultaneous_strata=True)


def test_all_unknown_preserves_full_identification_range():
    r=m.finite_population_domain([(20,[None]*4)])
    assert r['point_rate'] is None
    assert r['identification_rate_lower']==0 and r['identification_rate_upper']==1
    assert r['sampling_confidence_envelope_lower']==0 and r['sampling_confidence_envelope_upper']==1


def test_missing_selected_case_cannot_be_dropped_as_nonresponse():
    import pandas as pd
    key=pd.DataFrame({'case_id':['a','b']})
    with pytest.raises(ValueError,match='incomplete or unexpected'):
        m.analyze_review(key,None,pd.DataFrame({'case_id':['a']}),None,None)


def synthetic_complete_review():
    """Two fictional cases used only inside unit tests; never write to packet."""
    import pandas as pd
    key=pd.DataFrame({'case_id':['a','b'],'path':['a.sol','b.sol'],'class':['unchecked']*2,'source_id':['toy']*2,'label_status':[m.POS]*2,'N_h':[4]*2,'n_h':[2]*2,'inclusion_probability':[.5]*2,'design_weight':[2]*2})
    alloc=pd.DataFrame({'source_id':['toy'],'class':['unchecked'],'label_status':[m.POS],'N_h':[4],'n_h':[2]})
    first=pd.DataFrame({'case_id':['a','b'],'class':['unchecked']*2,'judgment_positive_negative_unknown':['positive','negative'],'reviewer_id':['toy_first']*2,'reviewed_utc':['fictional_test']*2,'reason':['synthetic unit test']*2})
    second=first.copy();second['reviewer_id']='toy_second'
    adj=pd.DataFrame({'case_id':['a','b'],'class':['unchecked']*2,'reviewer_1_judgment':['positive','negative'],'reviewer_2_judgment':['positive','negative'],'adjudicated_judgment':['positive','negative'],'adjudicator_id':['toy_first']*2,'adjudication_reason':['synthetic unit test']*2,'adjudicated_utc':['fictional_test']*2})
    return key,alloc,first,second,adj


def test_complete_synthetic_review_and_independent_reviewer_guard():
    args=synthetic_complete_review();r=m.analyze_review(*args)
    assert r['sample_cases']==2 and r['population_cases']==4
    assert r['domains'][0]['assessment']['point_rate']==.5
    args[3]['reviewer_id']='toy_first'
    with pytest.raises(ValueError,match='Two distinct'):m.analyze_review(*args)


def test_fractional_allocation_rejected_before_integer_conversion():
    args=synthetic_complete_review();args[1]['N_h']=4.9
    with pytest.raises(ValueError,match='positive integer'):m.analyze_review(*args)


def test_initial_judgments_cannot_be_overwritten_by_adjudication():
    args=synthetic_complete_review();args[4].loc[0,'reviewer_1_judgment']='negative'
    with pytest.raises(ValueError,match='preserve initial'):m.analyze_review(*args)
