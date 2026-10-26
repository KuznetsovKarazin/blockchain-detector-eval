"""Analytic AP mean and descriptive-reference checks independent of model fits."""
import importlib.util
import itertools
import json
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location(
    "security_random_ranking_reference",
    Path(__file__).parents[1] / "papers/security_evaluation/revision1/sampling_variance/random_ranking_reference.py",
)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)


def test_exact_mean_matches_all_positive_position_subsets_for_small_populations():
    # Enumerate every binary ranking, using precision-at-positive positions
    # directly. This neither uses the closed form nor simulates its expectation.
    for n in range(1, 8):
        for k in range(1, n + 1):
            aps = []
            for positive in itertools.combinations(range(n), k):
                labels = np.zeros(n, dtype=int)
                labels[list(positive)] = 1
                precision = np.cumsum(labels) / np.arange(1, n + 1)
                aps.append(float((precision * labels).sum() / k))
            assert reference.expected_ap_uniform_ranking(n, k) == pytest.approx(np.mean(aps), abs=2e-15)


def test_finite_random_ranking_mean_differs_from_prevalence():
    assert reference.expected_ap_uniform_ranking(2, 1) == 0.75
    assert reference.expected_ap_uniform_ranking(1082, 21) > 21 / 1082
    assert reference.expected_ap_uniform_ranking(1082, 21) == pytest.approx(0.02536, abs=0.00001)


def test_reference_reproducible_and_workload_counts_respect_fixed_budgets():
    a = reference.random_ranking_reference(20, 4, n_draws=100, seed=7, review_fractions=(0, 0.10, 1))
    b = reference.random_ranking_reference(20, 4, n_draws=100, seed=7, review_fractions=(0, 0.10, 1))
    assert a == b
    assert a["inferential_p_values_computed"] is False
    assert a["observed_model_scores_used"] is False
    assert a["workload"][0]["positive_yield_draws"] == [0] * 100
    assert a["workload"][0]["proxy_precision_summary"] is None
    assert a["workload"][1]["review_count"] == 2
    assert max(a["workload"][1]["positive_yield_draws"]) <= 2
    assert a["workload"][2]["positive_yield_draws"] == [4] * 100
    assert a["workload"][2]["proxy_recall_summary"]["mean"] == 1
    json.dumps(a, allow_nan=False)


def test_zero_positive_is_undefined_and_all_positive_is_one():
    zero = reference.random_ranking_reference(8, 0, n_draws=3, review_fractions=(0.5,))
    assert zero["exact_ap_mean"] is None and zero["ap_summary"] is None and zero["ap_draws"] is None
    assert zero["workload"][0]["proxy_recall_summary"] is None
    assert zero["workload"][0]["positive_yield_draws"] == [0, 0, 0]
    full = reference.random_ranking_reference(8, 8, n_draws=3, review_fractions=(0.5,))
    assert full["exact_ap_mean"] == 1 and full["ap_draws"] == [1, 1, 1]
    assert full["workload"][0]["positive_yield_draws"] == [4, 4, 4]
    json.dumps(zero, allow_nan=False)


@pytest.mark.parametrize("n,k", [(0, 0), (3, -1), (3, 4), (True, 1), (3, 1.2)])
def test_invalid_population_rejected(n, k):
    with pytest.raises(ValueError):
        reference.expected_ap_uniform_ranking(n, k)


def test_fraction_validation_and_optional_draw_omission():
    for q in [(float("nan"),), (-0.1,), (1.1,), (True,), (0.5, 0.5)]:
        with pytest.raises(ValueError):
            reference.random_ranking_reference(10, 2, n_draws=1, review_fractions=q)
    result = reference.random_ranking_reference(10, 2, n_draws=1, include_draws=False)
    assert "ap_draws" not in result
    assert all("positive_yield_draws" not in x for x in result["workload"])
    assert result["ap_summary"]["sd"] is None
