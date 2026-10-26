"""Synthetic production tests; no real scores, references, source files or keys."""
import importlib.util
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("performance_v2_tested", HERE / "performance.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
spec = importlib.util.spec_from_file_location("fictional_inputs_v1", HERE.parent / "performance_v1/synthetic_inputs.py")
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)


def inputs(N=8, n=4, census=False):
    data = list(fixture_module.fixture(N, n, census=census))
    a, b = data[-1].copy(), data[-1].copy()
    a["method"], b["method"] = "A", "B"
    b["score"] = b.score.iloc[::-1].to_numpy()
    data[-1] = pd.concat([a, b], ignore_index=True)
    return data


def evaluate(data, **kwargs):
    return p.evaluate_methods(*data, "reentrancy", methods=("A", "B"), expected_files=data[0].path.nunique(),
        expected_sample_cases=len(data[1]), classes=("reentrancy",), replicates=30, **kwargs)


def fail(data, method, file_index, status="tool_error"):
    mask = (data[-1].method == method) & (data[-1].path == f"synthetic://file_{file_index:04d}")
    data[-1].loc[mask, ["status", "score"]] = [status, np.nan]


def test_census_ap_recall_yield_and_paired_truth():
    data = inputs(census=True)
    out = evaluate(data, review_fractions=(.5,))
    y = np.asarray([i % 3 == 0 for i in range(8)])
    domain = out["domains"]["full_frame_pipeline"]
    for method in ("A", "B"):
        s = data[-1].query("method == @method").score.to_numpy()
        q, _ = p.v1.queue_probabilities(s, 4)
        actual = domain["methods"][method]
        assert actual["ap"]["point"] == pytest.approx(average_precision_score(y, s))
        assert actual["workload"][0]["yield"]["point"] == pytest.approx(q @ y)
        assert actual["workload"][0]["recall"]["point"] == pytest.approx(q @ y / y.sum())
        assert actual["workload"][0]["recall"]["interval"] == [q @ y / y.sum()] * 2
    pair = domain["paired_differences"][0]
    assert pair["workload_differences"][0]["yield"]["point"] == pytest.approx(1.)
    assert pair["workload_differences"][0]["yield"]["paired_linear_design_estimate"]["design_variance_estimate"] == 0


def test_failed_positive_retained_in_pipeline_recall_denominator():
    data = inputs(census=True)
    fail(data, "A", 0)
    out = evaluate(data, review_fractions=(1.,))
    a = out["domains"]["full_frame_pipeline"]["methods"]["A"]
    assert a["ap"]["point"] is None
    q = a["workload"][0]
    assert (q["review_count_requested"], q["review_count_filled"], q["unfilled_budget"]) == (8, 7, 1)
    assert q["recall"]["denominator_HT"] == 3
    assert q["recall"]["point"] == pytest.approx(2 / 3)
    common = out["domains"]["common_success"]
    assert common["population_n"] == 7
    assert common["selected_outside_domain_retained_n"] == 1
    assert common["methods"]["A"]["workload"][0]["recall"]["point"] == 1
    assert common["methods"]["A"]["workload"][0]["review_count_requested"] == 7
    assert out["coverage_by_method"]["A"]["status_counts"]["tool_error"] == 1


def test_unknown_failed_case_blocks_full_recall_but_not_common_domain():
    data = inputs(census=True)
    fail(data, "A", 0)
    data[5].loc[0, "adjudicated_judgment"] = "unknown"
    out = evaluate(data, review_fractions=(.5,))
    full = out["domains"]["full_frame_pipeline"]
    common = out["domains"]["common_success"]
    assert full["methods"]["B"]["ap"]["point"] is None
    for method in ("A", "B"):
        assert full["methods"][method]["workload"][0]["recall"]["point"] is None
        assert common["methods"][method]["ap"]["point"] is not None
        assert common["methods"][method]["workload"][0]["recall"]["point"] is not None
    assert full["paired_differences"][0]["workload_differences"][0]["recall"]["point"] is None
    assert common["unknown_sample_outside_domain_n"] == 1


def test_shared_replicates_cancel_identical_methods_exactly():
    data = inputs()
    data[-1].loc[data[-1].method == "B", "score"] = data[-1].query("method == 'A'").score.to_numpy()
    out = evaluate(data, review_fractions=(.5,))
    pair = out["domains"]["full_frame_pipeline"]["paired_differences"][0]
    for result in (pair["ap_difference"], pair["workload_differences"][0]["yield"], pair["workload_differences"][0]["recall"]):
        assert result["point"] == 0
        assert result["interval"] == [0, 0]
        assert result["replicate_values"] == [0] * 30
    assert out["bootstrap"]["shared_across_all_methods_and_domains"]


def test_common_domain_retains_original_design_and_shared_matrix():
    data = inputs()
    fail(data, "B", 0)
    out = evaluate(data, review_fractions=(.5,))
    common = out["domains"]["common_success"]
    assert common["selected_in_domain_n"] == 3
    assert common["selected_outside_domain_retained_n"] == 1
    assert out["selected_class_cases_retained"] == 4
    assert not common["sample_design_redefined"]
    # Direct original-sample calculation, not reweighted domain sample.
    selected = data[1].sort_values("case_id")
    reps = p.v1.rao_wu_weights(selected.reset_index(drop=True), data[2], 30, 20261026)
    y = np.array([1., 1., 0., 0.])  # fixture sample indices 0,3,4,7
    d = np.array([False, True, True, True])
    q = np.array([0., 1., 0., 0.])  # A: common top3 indices1,2,3
    direct = p.recall_interval(y, q, d, selected.design_weight, reps)
    assert common["methods"]["A"]["workload"][0]["recall"]["replicate_values"] == direct["replicate_values"]


def test_queue_uses_unsampled_leaders_and_full_budget_before_reference():
    data = inputs()
    # Selected0,3,4,7; unsampled1,2 occupy both slots.
    data[-1].loc[data[-1].method == "A", "score"] = [0, 9, 8, 0, 0, 0, 0, 0]
    plan = p.plan_score_domains(data[0], data[-1], "reentrancy", methods=("A", "B"), expected_files=8,
                               classes=("reentrancy",), review_fractions=(.25,))
    assert plan["domains"]["full_frame_pipeline"]["methods"]["A"]["queues"][0]["q"].tolist() == [0, 1, 1, 0, 0, 0, 0, 0]
    out = evaluate(data, review_fractions=(.25,))
    assert out["domains"]["full_frame_pipeline"]["methods"]["A"]["workload"][0]["yield"]["point"] == 0


def test_zero_denominator_replicate_blocks_whole_ratio_interval():
    result = p.recall_interval([1, 0], [1, 0], np.array([True, True]), [2, 2], [[0, 4], [4, 0]])
    assert result["point"] == 1
    assert result["interval"] is None
    assert result["replicate_values"] == [None, 1]
    assert result["zero_denominator_replicates"] == 1
    assert result["invalid_replicates"] == 1


def test_no_positive_and_empty_common_are_undefined():
    data = inputs(census=True)
    data[5]["adjudicated_judgment"] = "negative"
    out = evaluate(data, review_fractions=(0.,))
    metric = out["domains"]["full_frame_pipeline"]["methods"]["A"]["workload"][0]
    assert metric["yield"]["point"] == 0
    assert metric["recall"]["point"] is None
    assert metric["recall"]["zero_denominator_replicates"] == 30
    data = inputs()
    for i in range(8):
        fail(data, "A", i)
    out = evaluate(data)
    common = out["domains"]["common_success"]
    assert common["population_n"] == 0
    assert common["methods"]["A"]["ap"]["point"] is None
    assert all(q["review_count_requested"] == 0 for q in common["methods"]["A"]["workload"])


def test_ratio_is_ratio_of_totals_not_mean_of_individual_ratios():
    y, q, d, w = np.array([1, 1, 0]), np.array([1., .5, 0]), np.ones(3, dtype=bool), np.array([1., 9., 5.])
    result = p.recall_interval(y, q, d, w, np.array([w, w]))
    assert result["point"] == .55
    assert result["numerator_HT"] == 5.5
    assert result["denominator_HT"] == 10


def test_paired_recall_values_use_same_replicates_not_difference_of_quantiles():
    out = evaluate(inputs(), review_fractions=(.5,))
    domain = out["domains"]["full_frame_pipeline"]
    a, b = [domain["methods"][m]["workload"][0]["recall"] for m in ("A", "B")]
    pair = domain["paired_differences"][0]["workload_differences"][0]["recall"]
    expected = np.array(a["replicate_values"]) - b["replicate_values"]
    assert pair["replicate_values"] == pytest.approx(expected)
    assert pair["interval"] == pytest.approx(np.quantile(expected, [.025, .975]))


@pytest.mark.parametrize("key", ["replicate_id", "metric", "domain_id", "review_count_requested"])
def test_pairing_rejects_unshared_inputs(key):
    result = evaluate(inputs(), review_fractions=(.5,))["domains"]["full_frame_pipeline"]["methods"]["A"]["workload"][0]["recall"]
    changed = {**result, key: "different"}
    with pytest.raises(ValueError, match="same shared"):
        p.paired_difference(result, changed)


@pytest.mark.parametrize("mutation", ["missing_row", "finite_failure", "nan_success", "infinite_failure", "unknown_status", "wrong_class", "duplicate", "extra_method", "wrong_weight", "missing_review", "same_reviewer"])
def test_fail_closed_inputs(mutation):
    data = inputs()
    if mutation == "missing_row": data[-1] = data[-1].iloc[1:].copy()
    if mutation == "finite_failure": data[-1].loc[0, "status"] = "tool_error"
    if mutation == "nan_success": data[-1].loc[0, "score"] = np.nan
    if mutation == "infinite_failure": data[-1].loc[0, ["status", "score"]] = ["tool_error", np.inf]
    if mutation == "unknown_status": data[-1].loc[0, "status"] = "okay"
    if mutation == "wrong_class": data[-1].loc[0, "class"] = "unchecked"
    if mutation == "duplicate": data[-1] = pd.concat([data[-1], data[-1].iloc[:1]], ignore_index=True)
    if mutation == "extra_method": data[-1].loc[0, "method"] = "C"
    if mutation == "wrong_weight": data[1].loc[0, "design_weight"] = 1
    if mutation == "missing_review": data[3] = data[3].iloc[1:].copy()
    if mutation == "same_reviewer": data[4]["reviewer_id"] = data[3].reviewer_id.iloc[0]
    with pytest.raises(ValueError): evaluate(data)


def test_row_permutation_invariance_and_zero_score_is_success():
    data = inputs()
    data[-1].loc[0, "score"] = 0
    a = evaluate(data)
    b = evaluate([x.sample(frac=1, random_state=3).reset_index(drop=True) for x in data])
    assert a == b
    assert a["coverage_by_method"]["A"]["success_n"] == 8


def test_tied_common_queue_uniform_exact_enumeration():
    data = inputs(census=True)
    fail(data, "A", 0)
    data[-1].loc[(data[-1].method == "A") & data[-1].status.eq("ok"), "score"] = 0
    out = evaluate(data, review_fractions=(.5,))
    a = out["domains"]["common_success"]["methods"]["A"]["workload"][0]
    assert a["review_count_requested"] == 3
    yields = [sum(i in (3, 6) for i in combo) for combo in itertools.combinations(range(1, 8), 3)]
    assert a["yield"]["point"] == pytest.approx(np.mean(yields))
    assert a["recall"]["point"] == pytest.approx(np.mean(yields) / 2)


def test_unknown_domain_suppresses_paired_points_but_preserves_bounds():
    data = inputs()
    data[5].loc[0, "adjudicated_judgment"] = "unknown"
    out = evaluate(data, review_fractions=(.5,))
    d = out["domains"]["full_frame_pipeline"]
    assert d["paired_differences"][0]["ap_difference"]["point"] is None
    assert d["paired_differences"][0]["workload_differences"][0]["recall"]["point"] is None
    bounds = d["methods"]["A"]["workload"][0]["yield_bounds_and_design_variance"]
    assert bounds["unknown_sample_n"] == 1
    assert bounds["finite_population_logical_bounds"][1] >= bounds["finite_population_logical_bounds"][0]


def test_decimal_budget_and_small_domain_zero_budget():
    assert p._budget(.29, 100) == 29
    out = evaluate(inputs(), review_fractions=(.05,))
    a = out["domains"]["full_frame_pipeline"]["methods"]["A"]["workload"][0]
    assert a["review_count_requested"] == 0
    assert a["yield"]["point"] == a["recall"]["point"] == 0
