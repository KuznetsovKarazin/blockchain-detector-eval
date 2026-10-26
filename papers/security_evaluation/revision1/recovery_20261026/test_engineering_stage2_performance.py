"""Independent fictional finite-frame checks for failure-aware paired metrics."""
import copy
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).parents[1] / 'external_protocol'
spec = importlib.util.spec_from_file_location('independent_performance_v2', BASE/'performance_v2/performance.py')
p = importlib.util.module_from_spec(spec); sys.modules[spec.name] = p; spec.loader.exec_module(p)


def fixture(N=6, chosen=None, labels=None, scores_by_method=None, sources=None):
    chosen = list(range(N)) if chosen is None else list(chosen)
    labels = [1, 1, 0, 0, 1, 0] if labels is None else list(labels)
    sources = ['toy']*N if sources is None else list(sources)
    frame = pd.DataFrame([dict(path=f'f{i}.sol', source_id=sources[i],
        **{'class': 'unchecked'}, label_status=p.v1.review.POS) for i in range(N)])
    rows, alloc = [], []
    for source in sorted(set(sources)):
        pop = [i for i, s in enumerate(sources) if s == source]
        sample = [i for i in chosen if sources[i] == source]
        n, total = len(sample), len(pop)
        alloc.append(dict(source_id=source, **{'class': 'unchecked'}, label_status=p.v1.review.POS, N_h=total, n_h=n))
        rows += [dict(frame.iloc[i], case_id=f'fictional_{i}', N_h=total, n_h=n,
                      design_weight=total/n, inclusion_probability=n/total) for i in sample]
    sample = pd.DataFrame(rows)
    y = [('unknown' if labels[int(path[1:-4])] is None else
          'positive' if labels[int(path[1:-4])] else 'negative') for path in sample.path]
    first = sample[['case_id', 'class']].copy(); first['judgment_positive_negative_unknown'] = y
    first['reviewer_id'] = 'Fictional independent first'; first['reason'] = 'Synthetic test only'
    first['reviewed_utc'] = 'Fictional test, no actual human review'
    second = first.copy(); second['reviewer_id'] = 'Fictional independent second'
    adj = sample[['case_id', 'class']].copy()
    for col in ('reviewer_1_judgment', 'reviewer_2_judgment', 'adjudicated_judgment'): adj[col] = y
    adj['adjudicator_id'] = 'Fictional adjudicator'; adj['adjudication_reason'] = 'Synthetic test only'
    adj['adjudicated_utc'] = 'Fictional test, no actual adjudication'
    scores_by_method = scores_by_method or {'A': [6, 5, 4, 3, None, 1], 'B': [5, None, 6, 3, 2, 1]}
    scores = pd.DataFrame([dict(method=method, path=f'f{i}.sol', **{'class': 'unchecked'},
        status='tool_error' if value is None else 'ok', score=np.nan if value is None else value)
        for method, values in scores_by_method.items() for i, value in enumerate(values)])
    return [frame, sample, pd.DataFrame(alloc), first, second, adj, scores]


def evaluate(args, fractions=(.5,), **kwargs):
    return p.evaluate_methods(*args, 'unchecked', methods=tuple(sorted(args[-1].method.unique())),
        expected_files=len(args[0]), expected_sample_cases=len(args[1]), classes=('unchecked',),
        review_fractions=fractions, replicates=37, **kwargs)


def metric(result, domain, method, name='recall'):
    return result['domains'][domain]['methods'][method]['workload'][0][name]


def test_census_pipeline_recall_keeps_failed_positives_and_common_target_changes():
    r = evaluate(fixture())
    # Three true positives, with one unavailable to A and a different one to B.
    assert metric(r, 'full_frame_pipeline', 'A')['point'] == pytest.approx(2/3)
    assert metric(r, 'full_frame_pipeline', 'B')['point'] == pytest.approx(1/3)
    assert metric(r, 'full_frame_pipeline', 'A')['denominator_HT'] == 3
    common = r['domains']['common_success']
    assert common['population_n'] == 4 and common['selected_outside_domain_retained_n'] == 2
    assert common['target_population_changed_from_full_frame']
    assert metric(r, 'common_success', 'A')['point'] == metric(r, 'common_success', 'B')['point'] == 1
    assert common['methods']['A']['ap']['point'] == 1
    assert common['methods']['B']['ap']['point'] == .5
    assert r['domains']['full_frame_pipeline']['methods']['A']['ap']['point'] is None
    pair = r['domains']['full_frame_pipeline']['paired_differences'][0]['workload_differences'][0]
    assert pair['yield']['point'] == 1 and pair['recall']['point'] == pytest.approx(1/3)
    assert pair['recall']['interval'] == pytest.approx([1/3, 1/3])


def test_zero_score_is_success_and_unfilled_budget_is_explicit():
    args = fixture(scores_by_method={'A': [0, None, None, None, None, None]})
    r = evaluate(args)
    assert r['coverage_by_method']['A']['success_n'] == 1
    q = r['domains']['full_frame_pipeline']['methods']['A']['workload'][0]
    assert (q['review_count_requested'], q['review_count_filled'], q['unfilled_budget']) == (3, 1, 2)
    assert q['yield']['point'] == 1 and q['recall']['point'] == pytest.approx(1/3)


def test_common_domain_preserves_original_weights_and_strata():
    # Unequal inclusion: stratum A 2/4 => weight2; B 2/8 => weight4.
    # Common-success observed positives at0(A) and4(B). Top half of all four
    # common files selects0 and1: recoveredHT=2, domainHTpositives=2+4=6.
    N = 12; labels = [0]*N; labels[0] = labels[4] = 1
    scores = [None]*N
    for i, score in ((0, 9), (1, 8), (4, 7), (5, 6)): scores[i] = score
    args = fixture(N, [0, 1, 4, 5], labels, {'A': scores, 'B': scores}, ['A']*4+['B']*8)
    r = evaluate(args)
    common = r['domains']['common_success']
    assert common['sample_design_redefined'] is False
    v = metric(r, 'common_success', 'A')
    assert v['numerator_HT'] == 2 and v['denominator_HT'] == 6
    assert v['point'] == pytest.approx(1/3) and v['point'] != .5
    assert r['bootstrap']['original_strata_and_sampling_fractions_preserved']


def test_identical_methods_have_exact_zero_paired_spread_with_nonzero_marginal_spread():
    args = fixture(6, [0, 1, 2], [1, 0, 1, 0, 0, 0],
                   {'A': [6, 5, 4, 3, 2, 1], 'B': [6, 5, 4, 3, 2, 1]})
    r = evaluate(args, fractions=(.2,))
    full = r['domains']['full_frame_pipeline']
    assert np.ptp(full['methods']['A']['ap']['replicate_values']) > 0
    assert np.ptp(metric(r, 'full_frame_pipeline', 'A')['replicate_values']) > 0
    pair = full['paired_differences'][0]
    for delta in [pair['ap_difference'], pair['workload_differences'][0]['recall'], pair['workload_differences'][0]['yield']]:
        assert delta['point'] == 0 and delta['interval'] == [0, 0]
        assert set(delta['replicate_values']) == {0.}


def test_unknown_outside_common_is_irrelevant_there_but_blocks_full_recall():
    args = fixture(labels=[1, None, 0, 0, None, 0])
    r = evaluate(args)
    assert metric(r, 'full_frame_pipeline', 'A')['point'] is None
    common = r['domains']['common_success']
    assert common['unknown_sample_outside_domain_n'] == 2 and common['unknown_sample_in_domain_n'] == 0
    assert metric(r, 'common_success', 'A')['point'] == 1
    assert metric(r, 'common_success', 'A')['unknown_outside_domain_sample_n'] == 2


def test_unknown_inside_common_suppresses_point_without_complete_case_deletion():
    r = evaluate(fixture(labels=[None, 1, 0, 0, 1, 0]))
    common = r['domains']['common_success']
    assert common['selected_in_domain_n'] == 4
    for method in ('A', 'B'):
        assert metric(r, 'common_success', method)['point'] is None
        assert common['methods'][method]['ap']['point'] is None
    assert common['paired_differences'][0]['ap_difference']['point'] is None


def test_empty_common_domain_is_not_an_available_perfect_ranking():
    args = fixture(scores_by_method={'A': [6, 5, 4, None, None, None], 'B': [None, None, None, 3, 2, 1]})
    common = evaluate(args)['domains']['common_success']
    assert common['population_n'] == 0 and common['selected_outside_domain_retained_n'] == 6
    for method in ('A', 'B'):
        assert common['methods'][method]['ap']['point'] is None
        assert common['methods'][method]['workload'][0]['recall']['point'] is None


def test_nonempty_but_unsampled_common_domain_not_recast_as_census():
    args = fixture(6, [0, 1, 2], [1, 0, 0, 1, 0, 0],
        {'A': [None, None, None, 3, 2, 1], 'B': [None, None, None, 3, 2, 1]})
    common = evaluate(args)['domains']['common_success']
    assert common['population_n'] == 3 and common['selected_in_domain_n'] == 0
    assert common['methods']['A']['ap']['point'] is None
    assert common['methods']['A']['workload'][0]['recall']['point'] is None
    bounds = common['methods']['A']['workload'][0]['yield_bounds_and_design_variance']
    assert bounds['finite_population_logical_bounds'] == [0, 1]
    assert bounds['noncensus_zero_estimated_variance']


@pytest.mark.parametrize('corruption', ('failure_with_zero', 'failure_with_infinity', 'success_with_nan', 'missing_file', 'unregistered_method', 'unknown_status'))
def test_status_inventory_rejects_imputation_and_silent_frame_deletion(corruption):
    args = fixture(); s = args[-1]
    fail = s.index[s.status.ne('ok')][0]; ok = s.index[s.status.eq('ok')][0]
    if corruption == 'failure_with_zero': s.loc[fail, 'score'] = 0
    elif corruption == 'failure_with_infinity': s.loc[fail, 'score'] = np.inf
    elif corruption == 'success_with_nan': s.loc[ok, 'score'] = np.nan
    elif corruption == 'missing_file': args[-1] = s.iloc[1:]
    elif corruption == 'unregistered_method': s.loc[ok, 'method'] = 'UNREGISTERED'
    elif corruption == 'unknown_status': s.loc[fail, 'status'] = 'some_unrecorded_fallback'
    with pytest.raises(ValueError):
        p.plan_score_domains(args[0], args[-1], 'unchecked', methods=('A', 'B'), expected_files=6, classes=('unchecked',))


@pytest.mark.parametrize('tag', ('replicate_id', 'metric', 'domain_id', 'review_count_requested'))
def test_paired_metrics_reject_mismatched_comparison_targets(tag):
    r = evaluate(fixture())
    left = metric(r, 'full_frame_pipeline', 'A')
    right = copy.deepcopy(metric(r, 'full_frame_pipeline', 'B'))
    right[tag] = 'different_target'
    with pytest.raises(ValueError): p.paired_difference(left, right)


def test_unknown_reference_changes_neither_score_domain_nor_cutoff():
    args = fixture()
    plan = p.plan_score_domains(args[0], args[-1], 'unchecked', methods=('A', 'B'), expected_files=6,
                               classes=('unchecked',), review_fractions=(.5,))
    unknown = fixture(labels=[None]*6)
    other = p.plan_score_domains(unknown[0], unknown[-1], 'unchecked', methods=('A', 'B'), expected_files=6,
                                classes=('unchecked',), review_fractions=(.5,))
    for domain in plan['domains']:
        assert plan['domains'][domain]['domain_id'] == other['domains'][domain]['domain_id']
        for method in ('A', 'B'):
            np.testing.assert_array_equal(plan['domains'][domain]['methods'][method]['queues'][0]['q'],
                                          other['domains'][domain]['methods'][method]['queues'][0]['q'])


def test_paired_ratio_invalid_replicate_cannot_be_dropped():
    r = p.recall_interval([1, 0], [.5, 1.], np.array([True, True]), [2., 2.], [[0., 4.], [2., 2.]])
    assert r['point'] == .5 and r['interval'] is None
    assert r['invalid_replicates'] == r['zero_denominator_replicates'] == 1
    assert len(r['replicate_values']) == 2 and r['replicate_values'][0] is None
