"""Decimal budget regression and equivalence for the frozen experiment inputs."""
import importlib.util
import json
from pathlib import Path

import pytest


def module(name):
    path = Path(__file__).parents[1] / 'papers/security_evaluation/revision1/sampling_variance' / (name+'.py')
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


v1 = module('random_ranking_reference')
v2 = module('random_ranking_reference_v2')


@pytest.mark.parametrize('fraction,expected', [(0.29,29),(0.57,57),(0.58,58),(0.0,0),(1.0,100)])
def test_decimal_budget_does_not_lose_one_review_at_integer_boundary(fraction, expected):
    result = v2.random_ranking_reference(100,20,n_draws=30,review_fractions=(fraction,))
    assert result['workload'][0]['review_count'] == expected
    assert result['workload'][0]['expected_positive_yield_exact'] == expected * 20 / 100
    json.dumps(result, allow_nan=False)


def test_frozen_population_random_draws_and_budgets_remain_identical():
    original = v1.random_ranking_reference(1082,21,n_draws=10000,seed=20261025)
    corrected = v2.random_ranking_reference(1082,21,n_draws=10000,seed=20261025)
    assert corrected['schema'].endswith('_v2')
    for key in original:
        if key not in {'schema','budget_rule'}:
            assert corrected[key] == original[key]
    assert [b['review_count'] for b in corrected['workload']] == [54,108,216]
