"""Workload semantics tested against exact small-population enumeration."""

import importlib.util
import itertools
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import average_precision_score


_SPEC = importlib.util.spec_from_file_location(
    "security_metrics", Path(__file__).parents[1] / "papers/security_evaluation/evaluation_metrics.py"
)
metrics = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(metrics)


@pytest.mark.parametrize("k", range(7))
def test_tie_counts_match_exhaustive_orderings(k):
    labels = np.array([1.0, 1.0, 0.0, np.nan, 0.0, 1.0])
    scores = [0.9, 0.5, 0.5, 0.5, 0.5, 0.1]
    r = metrics.review_at_k(labels, scores, k)
    orderings = [[0, *order, 5] for order in itertools.permutations([1, 2, 3, 4])]
    for name, mask in {
        "known_positive": labels == 1,
        "known_negative": labels == 0,
        "unknown_label": np.isnan(labels),
        "known_label": ~np.isnan(labels),
    }.items():
        counts = [int(mask[order[:k]].sum()) for order in orderings]
        assert r[f"{name}_reviewed_expected"] == pytest.approx(np.mean(counts))
        assert r[f"{name}_reviewed_min"] == min(counts)
        assert r[f"{name}_reviewed_max"] == max(counts)


def test_unknown_consumes_budget_and_failed_positive_stays_in_recall_denominator():
    r = metrics.evaluate_workload(
        [1, None, 0, 1], [0.8, 0.9, 0.1, 1.0],
        statuses=["ok", "ok", "ok", "compile_error"],
        label_regime="source_reported", label_provenance="fixture_source",
        review_fractions=[0.5, 1.0],
    )
    first, full = r["budgets"]
    assert r["ranking_ap"] == 1.0
    assert r["ranking_n"] == 2 and r["ranking_coverage_of_known_labels"] == pytest.approx(2/3)
    assert r["n_finite_scores_discarded_for_failure_status"] == 1
    assert r["n_unscorable_known_positive"] == 1
    assert first["unknown_label_reviewed_expected"] == 1
    assert first["known_negative_reviewed_expected"] == 0
    assert first["known_positive_recall_expected"] == 0.5
    assert first["judged_precision_ratio_of_expected_counts"] == 1.0
    assert first["known_positive_yield_per_review"] == 0.5
    assert full["review_count_requested"] == 4
    assert full["review_count_achieved"] == 3 and full["unused_review_slots"] == 1
    assert full["known_positive_recall_expected"] == 0.5


def test_ratio_of_expected_counts_is_not_claimed_as_expected_precision():
    # Always review one positive, then one of a tied negative and unknown.
    # Expected judged precision is (1/2 + 1)/2 = 3/4; ratio of counts is 1/1.5.
    r = metrics.review_at_k([1, 0, None], [1.0, 0.5, 0.5], 2)
    assert r["judged_precision_ratio_of_expected_counts"] == pytest.approx(2/3)
    assert r["judged_precision_ratio_of_expected_counts"] != pytest.approx(3/4)


def test_row_permutation_changes_no_reported_metric():
    y = np.array([1, 0, np.nan, 1, 0])
    s = np.array([0.9, 0.5, 0.5, np.nan, 0.1])
    st = np.array(["ok", "ok", "ok", "timeout", "ok"])
    p = np.array([4, 2, 1, 3, 0])
    a = metrics.evaluate_workload(y, s, statuses=st, label_regime="proxy", review_fractions=[0.6])
    b = metrics.evaluate_workload(y[p], s[p], statuses=st[p], label_regime="proxy", review_fractions=[0.6])
    assert a == b
    assert "proxy" in a["interpretation"]


def test_ap_and_trapezoidal_area_are_distinct_and_unknowns_excluded():
    r = metrics.evaluate_workload([1, 0, 1, None], [0.2, 0.8, 0.5, 1.0], label_regime="confirmed")
    assert r["ranking_ap"] == pytest.approx(average_precision_score([1, 0, 1], [0.2, 0.8, 0.5]))
    assert r["ranking_ap"] != pytest.approx(r["ranking_trapezoidal_pr_area"])
    assert r["ranking_prevalence"] == pytest.approx(2/3)


def test_no_positive_and_zero_budget_metrics_are_undefined_where_needed():
    r = metrics.evaluate_workload([0, None], [0.2, 0.8], label_regime="confirmed")
    assert r["ranking_ap"] is None and r["ranking_trapezoidal_pr_area"] is None
    for budget in r["budgets"]:
        assert budget["review_count_achieved"] == 0
        assert budget["known_positive_recall_expected"] is None
        assert budget["judged_precision_ratio_of_expected_counts"] is None
        assert budget["known_positive_yield_per_review"] is None
        assert budget["known_positive_reviewed_expected"] == 0


def test_empty_and_all_unscorable_populations_are_explicit():
    empty = metrics.evaluate_workload([], [], label_regime="confirmed")
    assert empty["scoring_coverage"] is None and empty["ranking_ap"] is None
    r = metrics.evaluate_workload([1, 0], [np.nan, np.nan], statuses=["ok", "timeout"],
                                  label_regime="confirmed", review_fractions=[1])
    assert r["n_status_ok_without_score"] == 1
    assert r["scoring_coverage"] == 0
    assert r["ranking_ap"] is None
    assert r["budgets"][0]["known_positive_recall_expected"] == 0
    assert r["budgets"][0]["unused_review_slots"] == 2


def test_decimal_budget_floor_and_explicit_regime_validation():
    r = metrics.evaluate_workload([0]*100, [0.0]*100, label_regime="proxy", review_fractions=[0.58])
    assert r["budgets"][0]["review_count_requested"] == 58
    with pytest.raises(TypeError):
        metrics.evaluate_workload([1], [0.2])
    with pytest.raises(ValueError, match="label_regime"):
        metrics.evaluate_workload([1], [0.2], label_regime="guessed")


@pytest.mark.parametrize("labels,scores,statuses", [
    ([-1], [0.1], None), ([2], [0.1], None), ([1], [float("inf")], None),
    ([1], [0.1, 0.2], None), ([1], [0.1], [None]),
])
def test_invalid_inputs_do_not_silently_become_negatives(labels, scores, statuses):
    with pytest.raises(ValueError):
        metrics.evaluate_workload(labels, scores, statuses=statuses, label_regime="confirmed")


@pytest.mark.parametrize("k", [-1, 1.5, True, 3])
def test_invalid_budget_counts_are_rejected(k):
    with pytest.raises(ValueError):
        metrics.review_at_k([0, 1], [0.1, 0.9], k)
