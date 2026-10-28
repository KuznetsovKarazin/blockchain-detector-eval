"""Independent synthetic tests of the inactive finite-frame reporting adapter.

All references, cases, files and scores below are fictional. No project source,
actual reference key, fitted model or external prediction is read.
"""
import copy
import importlib.util
import itertools
from fractions import Fraction
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

B = Path(__file__).parents[1] / 'external_protocol'
spec = importlib.util.spec_from_file_location('independent_reporting', B/'reporting_v1/reporting.py')
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def fixture(n=6, chosen=None, labels=None, strata=None, score_changes=None, broad=False):
    chosen = list(range(n)) if chosen is None else list(chosen)
    labels = [1, 0, 1, 0, 0, 0] if labels is None else list(labels)
    strata = ['fictional']*n if strata is None else list(strata)
    frame = pd.DataFrame([dict(path=f'fictional_{i:02d}.sol', source_id=strata[i],
        **{'class': cls}, label_status=r.review.POS)
        for cls in r.CLASSES for i in range(n)])
    rows, allocation = [], []
    for cls in r.CLASSES:
        for source in sorted(set(strata)):
            population = [i for i in range(n) if strata[i] == source]
            selected = [i for i in chosen if strata[i] == source]
            N, k = len(population), len(selected)
            allocation.append(dict(source_id=source, **{'class': cls}, label_status=r.review.POS, N_h=N, n_h=k))
            for i in selected:
                rows.append(dict(path=f'fictional_{i:02d}.sol', case_id=f'case_{cls}_{i:02d}',
                    source_id=source, **{'class': cls}, label_status=r.review.POS,
                    N_h=N, n_h=k, design_weight=N/k, inclusion_probability=k/N))
    sample = pd.DataFrame(rows)
    judgments = [('unknown' if labels[int(x[-6:-4])] is None else
                  'positive' if labels[int(x[-6:-4])] else 'negative') for x in sample.path]
    first = sample[['case_id', 'class']].copy()
    first['judgment_positive_negative_unknown'] = judgments
    first['reviewer_id'] = 'Fictional first reader'; first['reason'] = 'Synthetic only'
    first['reviewed_utc'] = 'Fictional metadata, not a human response'
    second = first.copy(); second['reviewer_id'] = 'Fictional second reader'
    adjudication = sample[['case_id', 'class']].copy()
    for field in ('reviewer_1_judgment', 'reviewer_2_judgment', 'adjudicated_judgment'):
        adjudication[field] = judgments
    adjudication['adjudicator_id'] = 'Fictional adjudicator'
    adjudication['adjudication_reason'] = 'Synthetic only'
    adjudication['adjudicated_utc'] = 'Fictional metadata, not actual adjudication'
    score_rows = []
    inventory = r.primary_inventory('unchecked')
    if broad:
        inventory += [dict(job_id='slither_broad:unchecked:0', method='slither',
                           **{'class': 'unchecked'}, seed=0, variant='broad_secondary')]
    for job in inventory:
        values = ([1 if i < 2 else 0 for i in range(n)] if job['method']=='slither' else list(range(n,0,-1)))
        values = (score_changes or {}).get(job['job_id'], values)
        for i, value in enumerate(values):
            score_rows.append(dict(job, path=f'fictional_{i:02d}.sol', execution_status='tool_error' if value is None else 'ok',
                status='tool_error' if value is None else 'ok', score=np.nan if value is None else value))
    return [frame, sample, pd.DataFrame(allocation), first, second, adjudication, pd.DataFrame(score_rows)]


def report(args, **kwargs):
    return r.report_class(*args, 'unchecked', case_manifest=args[1].copy(),
        expected_files=args[0].path.nunique(), expected_sample_cases=len(args[1]),
        review_fractions=(.5,), synthetic_fixture=True, **kwargs)


def domain(result, name='full_frame_pipeline'):
    return result['primary']['domains'][name]


def yield_summary(result, job='raw_tfidf_lr:unchecked:0', name='full_frame_pipeline'):
    return domain(result, name)['vectors'][job]['workload'][0]['positive_yield']


def rational(record):
    return None if record is None else Fraction(int(record['numerator']), int(record['denominator']))


def scalar_ap(scores, labels):
    """Independent exact definition; no estimator, sklearn or DP imports."""
    positives = sum(labels)
    if not positives:
        return None
    value = Fraction(0); cumulative_n = cumulative_positive = 0
    for score in sorted(set(scores), reverse=True):
        ids = [i for i, x in enumerate(scores) if x == score]
        group_positive = sum(labels[i] for i in ids)
        cumulative_n += len(ids); cumulative_positive += group_positive
        value += Fraction(group_positive*cumulative_positive, positives*cumulative_n)
    return value


def test_all_stratified_samples_unbiased_total_and_variance_with_signed_contributions():
    truth = np.array([1,0,1,0,1,0,1])
    coeff = np.array([1.,-.5,-1.,.5,0.,1.,-1.])
    estimates, variances = [], []
    for left in itertools.combinations(range(4), 2):
        for right in itertools.combinations(range(4,7), 2):
            selected = list(left+right)
            args = fixture(7, selected, list(truth), ['A']*4+['B']*3)
            sample = args[1][args[1]['class'].eq('unchecked')].reset_index(drop=True)
            allocation = args[2][args[2]['class'].eq('unchecked')]
            ids = np.array([int(x[-6:-4]) for x in sample.path])
            summary = r.fixed_queue_ht(coeff, np.ones(7,dtype=bool), truth, sample, allocation, truth[ids], ids)
            estimates.append(summary['point']['estimate'])
            variances.append(summary['point']['design_variance_estimate'])
            assert summary['point']['standard_error_estimate']**2 == pytest.approx(variances[-1])
    assert len(estimates) == 18
    assert np.mean(estimates) == pytest.approx(float(truth@coeff))
    assert np.mean(variances) == pytest.approx(np.var(estimates, ddof=0))


def test_signed_unknown_endpoint_estimates_are_distinct_from_population_bounds():
    args = fixture(6, [0,1,2], [None,None,1,0,0,0])
    sample = args[1][args[1]['class'].eq('unchecked')].reset_index(drop=True)
    allocation = args[2][args[2]['class'].eq('unchecked')]
    labels = np.array([np.nan,np.nan,1,np.nan,np.nan,np.nan])
    summary = r.fixed_queue_ht([1,-.5,0,.25,-1,.75], np.ones(6,dtype=bool), labels,
                              sample, allocation, labels[:3], np.array([0,1,2]))
    assert summary['point'] is None
    assert summary['endpoint_estimates']['lower']['estimate'] == -1
    assert summary['endpoint_estimates']['upper']['estimate'] == 2
    assert summary['logical_population_bounds']['lower'] == -1.5
    assert summary['logical_population_bounds']['upper'] == 2
    assert summary['confidence_interval'] is None


def test_HT_total_stays_unclipped_even_above_physical_queue_size():
    args = fixture(10, [0,1], [1]+[0]*9)
    sample = args[1][args[1]['class'].eq('unchecked')].reset_index(drop=True)
    allocation = args[2][args[2]['class'].eq('unchecked')]
    labels = np.array([1,0]+[np.nan]*8)
    summary = r.fixed_queue_ht([1]+[0]*9, np.ones(10,dtype=bool), labels,
                              sample, allocation, labels[:2], np.array([0,1]))
    assert summary['point']['estimate'] == 5
    assert summary['logical_population_bounds']['lower'] == summary['logical_population_bounds']['upper'] == 1
    assert summary['variance_zero_means_certainty'] is False


def test_common_domain_keeps_outside_rows_original_weights_and_FPC():
    labels = [1,0,0,0,1,0,0,0,0,0,0,0]
    # Only files0,1,4,5 are in common; both strata still contribute original n2.
    values = [12,11,None,None,8,7,None,None,None,None,None,None]
    args = fixture(12,[0,1,4,5],labels,['A']*4+['B']*8,
                   {'pattern_rf:unchecked:4': values})
    result = report(args); common = domain(result,'common_success')
    assert common['population_n'] == 4 and common['sample_design_redefined'] is False
    summary = yield_summary(result,name='common_success')
    # Budget2 selects0,1. Original stratum A sample (1,0): HT2, V=4²*.5*.5/2=2.
    assert summary['point']['estimate'] == 2
    assert summary['point']['design_variance_estimate'] == 2
    positive = common['reference_positive_total']['point']
    assert positive['estimate'] == 6
    assert positive['design_variance_estimate'] == 14


def test_unknown_outside_common_has_zero_domain_contribution_but_blocks_full_summary():
    result = report(fixture(labels=[1,0,1,0,0,None], score_changes={
        'pattern_rf:unchecked:4': [6,5,4,3,2,None]}))
    assert yield_summary(result)['point'] is None
    summary = yield_summary(result,name='common_success')
    assert summary['point']['estimate'] == 1
    assert summary['unknown_sample_outside_domain_n'] == 1
    assert summary['unknown_sample_in_domain_n'] == 0


def test_unknown_zero_queue_contribution_still_suppresses_declared_domain_point():
    result = report(fixture(labels=[1,0,1,0,0,None]))
    assert yield_summary(result)['point'] is None
    assert yield_summary(result)['unknown_sample_in_domain_n'] == 1


def test_each_seed_retained_once_and_exactly_twelve_reference_contrasts():
    result = report(fixture(score_changes={'pattern_rf:unchecked:4':[1,2,3,4,5,6]}))
    for data in result['primary']['domains'].values():
        assert len(data['vectors']) == 13
        pairs = data['raw_LR_reference_contrasts']
        assert len(pairs) == 12 and len({p['left'] for p in pairs}) == 12
        assert {p['right'] for p in pairs} == {'raw_tfidf_lr:unchecked:0'}
        delta = next(p for p in pairs if p['left']=='pattern_rf:unchecked:4')
        assert delta['workload'][0]['positive_yield_difference']['point']['estimate'] == -2


def test_broad_vector_does_not_enter_primary_common_domain_planning(monkeypatch):
    calls=[]; original=r.v2.plan_score_domains
    def watched(*args,**kwargs):
        calls.append(tuple(kwargs['methods'])); return original(*args,**kwargs)
    monkeypatch.setattr(r.v2,'plan_score_domains',watched)
    result=report(fixture(broad=True))
    assert len(calls[0]) == 13
    assert 'slither_broad:unchecked:0' not in calls[0]
    assert calls[1] == ('slither_broad:unchecked:0',)
    assert result['secondary_broad_slither']['excluded_from_primary_common_domain']


def test_AP_joins_assessed_by_file_and_keeps_all_unsampled_and_unknown_labels():
    args=fixture(6,[0,1,2],[1,None,0,0,0,0])
    result=report(args)
    ap=domain(result)['vectors']['raw_tfidf_lr:unchecked:0']['ap_completion']
    values=[]
    for completion in itertools.product((0,1),repeat=4):
        labels=[1,completion[0],0,*completion[1:]]
        values.append(scalar_ap([6,5,4,3,2,1],labels))
    assert ap['unknown_count'] == 4 and ap['n'] == 6 and ap['known_positives'] == 1
    assert rational(ap['lower_ap']) == min(values)
    assert rational(ap['upper_ap']) == max(values)
    assert not ap['undefined_possible']


def test_missing_score_blocks_full_AP_without_shrinking_population():
    result=report(fixture(score_changes={'normalized_tfidf_lr:unchecked:0':[6,5,4,3,2,None]}))
    full=domain(result)
    ap=full['vectors']['normalized_tfidf_lr:unchecked:0']['ap_completion']
    assert ap['lower_ap'] is None and ap['status']=='suppressed_missing_scores_no_complete_queue'
    pair=full['raw_LR_reference_contrasts'][0]['ap_difference_envelope']
    assert pair['lower'] is None and pair['undefined_possible'] is None
    assert domain(result,'common_success')['population_n'] == 5


@pytest.mark.parametrize('labels', [[0]*6, [None]*6])
def test_no_positive_and_possible_all_negative_propagate_to_AP_pairs(labels):
    result=report(fixture(labels=labels))
    data=domain(result); ap=data['vectors']['raw_tfidf_lr:unchecked:0']['ap_completion']
    pair=data['raw_LR_reference_contrasts'][0]['ap_difference_envelope']
    assert ap['undefined_possible'] and pair['undefined_possible']
    if labels[0] == 0:
        assert not ap['defined_completions_exist'] and pair['lower'] is None
    else:
        assert ap['defined_completions_exist'] and pair['lower'] is not None
        assert pair['conditional_on_both_APs_defined']


def test_paired_AP_envelope_rejects_changed_completion_domain():
    result=report(fixture()); ap=domain(result)['vectors']['raw_tfidf_lr:unchecked:0']['ap_completion']
    other=copy.deepcopy(ap); other['reference_completion_id']='different'
    with pytest.raises(ValueError): r.ap_difference_envelope(ap,other)


def test_primary_has_no_bootstrap_or_normal_interval_and_exploratory_is_separate():
    result=report(fixture(),include_exploratory=True,replicates=11)
    assert result['engine_audit']['label']=='UNFILTERED_FROZEN_ENGINE_AUDIT_NOT_PRIMARY_REPORT'
    raw=result['engine_audit']['raw_output']
    for name in result['primary']['domains']:
        assert len(raw['domains'][name]['paired_differences']) == 78
        clean=result['exploratory']['domains'][name]
        assert len(clean['raw_LR_reference_contrasts']) == 12
        for vector in clean['vectors'].values():
            assert vector['AP']['interval_coverage_validated'] is False
        for vector in result['primary']['domains'][name]['vectors'].values():
            summary=vector['workload'][0]['positive_yield']
            assert summary['confidence_interval'] is None
            assert 'normal_interval' not in summary and 'replicate_values' not in summary


@pytest.mark.parametrize('corruption', ['seed_alias','drop_vector','missing_score','failure_zero','case_swap','wrong_form_class'])
def test_join_seed_and_status_corruptions_fail_closed(corruption):
    args=fixture(); manifest=args[1].copy(); scores=args[-1]
    if corruption=='seed_alias':
        scores.loc[scores.job_id.eq('pattern_rf:unchecked:1'),'job_id']='pattern_rf:unchecked:0'
    elif corruption=='drop_vector': args[-1]=scores[~scores.job_id.eq('pattern_rf:unchecked:4')]
    elif corruption=='missing_score': args[-1]=scores.iloc[1:]
    elif corruption=='failure_zero': scores.loc[0,['status','execution_status']]='tool_error'
    elif corruption=='case_swap':
        ids=args[1].index[:2]; args[1].loc[ids,'path']=args[1].loc[ids,'path'].iloc[::-1].to_numpy()
    elif corruption=='wrong_form_class': args[3].loc[0,'class']='wrong'
    with pytest.raises(ValueError):
        r.report_class(*args,'unchecked',case_manifest=manifest,expected_files=6,
                       expected_sample_cases=12,review_fractions=(.5,),synthetic_fixture=True)


def test_production_admission_is_closed_before_path_or_object_access():
    class Poison:
        def __getattribute__(self,name): raise AssertionError('Input accessed: '+name)
    result=r.production_admission(Poison(),release=Poison())
    assert not result['admitted'] and result['files_opened']==0
    args=fixture()
    with pytest.raises(ValueError,match='synthetic'):
        r.report_class(*args,'unchecked',case_manifest=args[1],expected_files=6,expected_sample_cases=12)


def test_reference_row_permutation_does_not_change_primary_results():
    args=fixture(6,[0,1,2],[1,None,0,0,0,0]); original=report(args)
    shuffled=[x.sample(frac=1,random_state=14).reset_index(drop=True) for x in args]
    changed=report(shuffled)
    assert original['primary'] == changed['primary']


def test_empty_common_domain_is_explicit_and_never_perfect_AP():
    result=report(fixture(score_changes={
        'pattern_rf:unchecked:0':[6,5,4,None,None,None],
        'pattern_rf:unchecked:1':[None,None,None,3,2,1]}))
    common=domain(result,'common_success')
    assert common['population_n']==0 and not common['ranking_defined']
    for vector in common['vectors'].values():
        assert vector['ap_completion']['lower_ap'] is None
        assert not vector['ap_completion']['defined_completions_exist']


@pytest.mark.parametrize('corruption',['nonbinary','broad_status','unchecked_union','noninteger_seed'])
def test_static_union_and_seed_types_reject_impossible_combinations(corruption):
    args=fixture(broad=True); scores=args[-1]
    scores['score']=scores.score.astype(float)
    ids=scores.index[scores.job_id.eq('slither_broad:unchecked:0')]
    if corruption=='nonbinary': scores.loc[ids[0],'score']=.5
    elif corruption=='broad_status':
        scores.loc[ids[0],['status','execution_status']]='tool_error'; scores.loc[ids[0],'score']=np.nan
    elif corruption=='unchecked_union': scores.loc[ids[-1],'score']=1
    elif corruption=='noninteger_seed': scores['seed']=scores.seed.astype(float)
    with pytest.raises(ValueError): report(args)


def test_zero_observed_positive_variance_does_not_collapse_unsampled_bounds():
    result=report(fixture(6,[0,1,2],[0]*6))
    total=domain(result)['reference_positive_total']
    assert total['point']['estimate']==total['point']['design_variance_estimate']==0
    assert total['logical_population_bounds']['lower']==0
    assert total['logical_population_bounds']['upper']==3
    assert total['variance_zero_means_certainty'] is False
    ap=domain(result)['vectors']['raw_tfidf_lr:unchecked:0']['ap_completion']
    assert ap['unknown_count']==3 and ap['undefined_possible']


def test_boundary_tie_yield_is_expected_over_orderings_not_realized_tie_variance():
    result=report(fixture(score_changes={'raw_tfidf_lr:unchecked:0':[1]*6}))
    total=yield_summary(result)['point']
    # Uniformly select3 of6 with2 positives; expected recovery=1. Complete census
    # has zero annotation-sampling variance even though realized tie yield varies.
    assert total['estimate']==1 and total['design_variance_estimate']==0
    actual=[sum([1,0,1,0,0,0][i] for i in subset) for subset in itertools.combinations(range(6),3)]
    assert np.mean(actual)==1 and np.var(actual)>0


def test_primary_pair_AP_envelopes_are_exact_but_marked_generally_nonsharp():
    result=report(fixture(6,[0,1,2],[1,None,0,0,0,0],score_changes={
        'normalized_tfidf_lr:unchecked:0':[1,2,3,4,5,6]}))
    full=domain(result); pair=full['raw_LR_reference_contrasts'][0]['ap_difference_envelope']
    left=full['vectors']['normalized_tfidf_lr:unchecked:0']['ap_completion']
    right=full['vectors']['raw_tfidf_lr:unchecked:0']['ap_completion']
    assert rational(pair['lower'])==rational(left['lower_ap'])-rational(right['upper_ap'])
    assert rational(pair['upper'])==rational(left['upper_ap'])-rational(right['lower_ap'])
    assert pair['separate_endpoint_completions_may_be_incompatible']
    assert pair['confidence_level'] is None and not pair['superiority_claim']


def test_reentrancy_broad_union_can_add_findings_but_cannot_remove_primary():
    args=fixture(broad=True); scores=args[-1]
    scores['class']='reentrancy'
    scores['job_id']=scores.job_id.str.replace(':unchecked:',':reentrancy:',regex=False)
    broad=scores.index[scores.job_id.eq('slither_broad:reentrancy:0')]
    paths=sorted(args[0].path.unique())
    scores.loc[broad[-1],'score']=1
    inventory,main,secondary=r._scores(scores,'reentrancy',paths)
    assert len(inventory)==13 and len(secondary)==6
    scores.loc[broad[0],'score']=0
    with pytest.raises(ValueError,match='union'):
        r._scores(scores,'reentrancy',paths)


@pytest.mark.parametrize('bad_flag', ['true', 1, None])
def test_exploratory_flag_is_explicit_boolean_not_truthiness(bad_flag):
    with pytest.raises(ValueError,match='boolean'):
        report(fixture(),include_exploratory=bad_flag)
