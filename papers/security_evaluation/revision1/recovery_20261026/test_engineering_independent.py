"""Independent adversarial tests using fictional sources/reviews/scores only.

No frozen source, actual annotation, feature fit on project data, or model output
is opened here. Tiny exhaustive oracles are separate from estimator code.
"""
import importlib.util
import itertools
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).parents[1] / 'external_protocol'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


p = module('independent_performance', BASE / 'performance_v1/performance.py')
a = module('independent_adapters', BASE / 'adapters_v1/adapters.py')


def design(N, n, source='toy'):
    common = dict(source_id=source, **{'class': 'unchecked'}, label_status=p.review.POS,
                  N_h=N, n_h=n)
    sample = pd.DataFrame([dict(common, case_id=f'{source}{i}', path=f'{source}{i}.sol',
                               design_weight=N/n, inclusion_probability=n/N)
                           for i in range(n)])
    return sample, pd.DataFrame([common])


def fixture(y=('positive', 'negative', 'negative')):
    sample, alloc = design(6, 3)
    frame = pd.DataFrame([dict(path=f'toy{i}.sol', source_id='toy',
                              **{'class': 'unchecked'}, label_status=p.review.POS)
                          for i in range(6)])
    first = sample[['case_id', 'class']].copy()
    first['judgment_positive_negative_unknown'] = y
    first['reviewer_id'] = 'Fictional reviewer A'
    first['reviewed_utc'] = 'synthetic fixture, never a real review'
    first['reason'] = 'Fictional test only'
    second = first.copy(); second['reviewer_id'] = 'Fictional reviewer B'
    adj = sample[['case_id', 'class']].copy()
    for column in ('reviewer_1_judgment', 'reviewer_2_judgment', 'adjudicated_judgment'):
        adj[column] = y
    adj['adjudicator_id'] = 'Fictional adjudicator'
    adj['adjudication_reason'] = 'Fictional test only'
    adj['adjudicated_utc'] = 'synthetic fixture, never a real review'
    scores = frame[['path', 'class']].copy()
    scores['score'] = [3., 2., 1., 6., 5., 4.]
    scores['status'] = 'ok'
    return [frame, sample, alloc, first, second, adj, scores]


def evaluate(args, **kwargs):
    return p.evaluate(*args, target_class='unchecked', expected_files=6,
                      expected_sample_cases=3, classes=('unchecked',),
                      review_fractions=(.5,), replicates=18, **kwargs)


def test_ht_truth_and_variance_across_every_stratified_sample():
    # Exhaustive actual sampling distribution: 10 * 6 = 60 possible samples.
    populations = (np.array([0., .25, .75, 1., 1.]), np.array([0., .2, .8, 1.]))
    s1, a1 = design(5, 3, 'A'); s2, a2 = design(4, 2, 'B')
    sample = pd.concat([s1, s2], ignore_index=True)
    alloc = pd.concat([a1, a2], ignore_index=True)
    estimates, variance_estimates = [], []
    for ids1 in itertools.combinations(range(5), 3):
        for ids2 in itertools.combinations(range(4), 2):
            z = np.r_[populations[0][list(ids1)], populations[1][list(ids2)]]
            r = p.ht_total(z, sample, alloc)
            estimates.append(r['estimate']); variance_estimates.append(r['design_variance_estimate'])
    assert len(estimates) == 60
    assert np.mean(estimates) == pytest.approx(sum(x.sum() for x in populations), abs=1e-12)
    assert np.mean(variance_estimates) == pytest.approx(np.var(estimates), abs=1e-12)


def test_actual_rao_wu_code_matches_exhaustive_conditional_variance():
    # Every ordered pair from three sample elements is equally likely for m=2.
    multiplicities = np.array([np.bincount(ids, minlength=3)
                              for ids in itertools.product(range(3), repeat=2)])
    class ExhaustiveRandom:
        def multinomial(self, n, probabilities, size):
            assert n == 2 and size == 9
            np.testing.assert_allclose(probabilities, np.ones(3)/3)
            return multiplicities
    sample, alloc = design(8, 3)
    z = np.array([0., .4, 1.])
    with patch.object(p.np.random, 'default_rng', return_value=ExhaustiveRandom()):
        weights = p.rao_wu_weights(sample, alloc, replicates=9)
    total = p.ht_total(z, sample, alloc)
    np.testing.assert_allclose(weights.sum(axis=1), 8)
    assert np.mean(weights @ z) == pytest.approx(total['estimate'], abs=1e-12)
    assert np.var(weights @ z) == pytest.approx(total['design_variance_estimate'], abs=1e-12)


def test_singleton_census_and_noncensus_are_distinguished():
    sample, alloc = design(1, 1)
    np.testing.assert_array_equal(p.rao_wu_weights(sample, alloc, 3), np.ones((3, 1)))
    assert p.ht_total([1], sample, alloc)['design_variance_estimate'] == 0
    sample, alloc = design(3, 1)
    with pytest.raises(ValueError, match='n_h=1'):
        p.rao_wu_weights(sample, alloc, 3)


def test_seeded_replicates_follow_case_id_not_input_row_order():
    sample, alloc = design(8, 3)
    order = [2, 0, 1]
    one = p.rao_wu_weights(sample, alloc, 31, 88)
    two = p.rao_wu_weights(sample.iloc[order].reset_index(drop=True), alloc, 31, 88)
    np.testing.assert_array_equal(one[:, order], two)


def test_weighted_ap_against_manual_tied_group_oracle():
    # Top tied group: positive mass 2, negative mass 6; second positive mass 3;
    # final negative mass 4. AP=(2/5)*(2/8)+(3/5)*(5/11), independent of sklearn.
    expected = (2/5)*(2/8) + (3/5)*(5/11)
    assert p.weighted_ap([1, 0, 1, 0], [4, 4, 2, 1], [2, 6, 3, 4]) == pytest.approx(expected)
    assert p.weighted_ap([1, 0, 1, 0], [4, 4, 2, 1], [2, 6, 3, 4]) != pytest.approx(p.weighted_ap([1, 0, 1, 0], [4, 4, 2, 1], [1]*4))


def test_tie_probabilities_equal_enumerated_uniform_boundary_choices():
    scores = np.array([9., 7., 7., 7., 1.])
    q, tie = p.queue_probabilities(scores, 3)
    indicators = []
    for chosen in itertools.combinations((1, 2, 3), 2):
        row = np.zeros(5); row[0] = 1; row[list(chosen)] = 1; indicators.append(row)
    np.testing.assert_allclose(q, np.mean(indicators, axis=0))
    assert tie == {'boundary_score': 7., 'tie_count': 3, 'slots_from_tie': 2}


def test_every_unknown_and_unsampled_completion_inside_workload_hard_bounds():
    sample, alloc = design(5, 3)
    q = np.array([1., .5, .5, .5, .5])
    y = [1, np.nan, 0]
    result = p.workload(q, [f'toy{i}.sol' for i in range(5)], sample, alloc, y)
    possible = [float(q @ np.array([1, u, 0, x, z]))
                for u, x, z in itertools.product((0, 1), repeat=3)]
    assert result['finite_population_logical_bounds'] == pytest.approx([min(possible), max(possible)])
    assert result['point_HT_total_unclipped'] is None
    assert not result['unknown_cases_dropped']


def test_ht_above_queue_budget_is_reported_not_silently_clipped():
    sample, alloc = design(10, 2)
    result = p.workload([1]+[0]*9, [f'toy{i}.sol' for i in range(10)], sample, alloc, [1, 0])
    assert result['point_HT_total_unclipped'] == 5
    assert result['review_count'] == 1 and result['point_outside_finite_support']
    assert result['finite_population_logical_bounds'] == [1, 1]


def test_queue_is_selected_before_human_sample_join():
    result = evaluate(fixture())
    work = result['workload'][0]
    # All three highest-scoring full-frame files are unsampled. A sample-only
    # cutoff would find the sampled positive and produce a nonzero estimate.
    assert work['review_count'] == 3 and work['point_HT_total_unclipped'] == 0
    assert work['finite_population_logical_bounds'] == [0, 3]
    assert result['full_queue_files'] == 6 and result['selected_class_cases'] == 3


@pytest.mark.parametrize('bad', ('missing_score', 'failed_score', 'missing_case', 'same_reviewer', 'changed_class', 'changed_stratum'))
def test_full_api_rejects_adversarial_design_or_provenance_changes(bad):
    args = fixture()
    if bad == 'missing_score': args[6] = args[6].iloc[:-1]
    elif bad == 'failed_score': args[6].loc[0, 'status'] = 'failed'
    elif bad == 'missing_case': args[4] = args[4].iloc[:-1]
    elif bad == 'same_reviewer': args[4]['reviewer_id'] = 'Fictional reviewer A'
    elif bad == 'changed_class': args[6].loc[0, 'class'] = 'reentrancy'
    elif bad == 'changed_stratum': args[1].loc[0, 'source_id'] = 'fabricated'
    with pytest.raises(ValueError): evaluate(args)


def test_all_unknown_cannot_become_binary_ap_or_complete_case_metric():
    result = evaluate(fixture(('unknown',)*3))
    assert result['ap']['point'] is None and result['ap']['interval'] is None
    assert result['ap']['safe_AP_bound_if_population_has_positive'] == [0., 1.]
    assert result['ap']['unknown_sample_outcomes'] == 3
    assert result['workload'][0]['point_HT_total_unclipped'] is None


def test_absent_sample_positives_do_not_create_precise_ap():
    result = evaluate(fixture(('negative',)*3))
    assert result['ap']['point'] is None and result['ap']['interval'] is None
    assert result['ap']['safe_AP_bound_if_population_has_positive'] == [0., 1.]


def test_pattern_training_cannot_drop_an_invalid_member():
    records = [a.SourceRecord('one', 'train', 'contract C {}'),
               a.SourceRecord('two', 'train', b'\xff')]
    with pytest.raises(a.TrainingInputError): a.Pattern43().fit_transform_training(records)


def test_fitted_training_identity_cannot_be_rebound_to_different_bytes():
    adapter = a.TrainOnlyTfidf('raw')
    records = [a.SourceRecord('one', 'train', 'shared'), a.SourceRecord('two', 'train', 'shared')]
    adapter.fit_transform_training(records)
    with pytest.raises(ValueError):
        adapter.transform([a.SourceRecord('one', 'train', 'shared plus substituted bytes')])


def test_external_rare_terms_do_not_change_training_idf_scale_or_vocabulary():
    adapter = a.TrainOnlyTfidf('raw')
    train = [a.SourceRecord('one', 'train', 'alpha beta'),
             a.SourceRecord('two', 'train', 'alpha beta'),
             a.SourceRecord('three', 'train', 'alpha gamma')]
    adapter.fit_transform_training(train)
    before = adapter.state_sha256()
    # gamma appears once in training and is below min_df=2 even if common later.
    assert 'gamma' not in adapter._vectorizer.vocabulary_
    result = adapter.transform([a.SourceRecord(f'ext{i}', 'external', 'gamma gamma') for i in range(20)])
    assert before == adapter.state_sha256()
    assert result.matrix.nnz == 0 and all(not c['feature_ready'] for c in result.coverage)
    assert 'gamma' not in adapter._vectorizer.vocabulary_


def test_corrected_scanner_removes_actual_comment_without_erasing_literal_neighbor():
    source = 'contract C { string s="/* quoted // marker */"; /* actual */ function f() public { payee.send(1); } }'
    output = a.Pattern43().transform([a.SourceRecord('fictional', 'external', source)])
    assert output.matrix.shape == (1, 43)
    assert output.matrix[0, a.PATTERN_NAMES.index('send')] > 0
    assert output.coverage[0]['string_literals'] == 1 and output.coverage[0]['block_comments'] == 1
