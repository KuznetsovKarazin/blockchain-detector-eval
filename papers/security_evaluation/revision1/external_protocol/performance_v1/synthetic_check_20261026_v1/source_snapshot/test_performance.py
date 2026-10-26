"""Production implementation tests on fictional populations; no external data."""
import importlib.util
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

HERE = Path(__file__).parent
def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
m, toy = load("performance"), load("synthetic_inputs")


def evaluate(args, **kwargs):
    return m.evaluate(*args, "reentrancy", expected_files=args[0].path.nunique(),
                      expected_sample_cases=len(args[1]), classes=("reentrancy",), replicates=40, **kwargs)


def design(N, chosen):
    n = len(chosen)
    key = pd.DataFrame({"case_id": [f"c{i}" for i in chosen], "source_id": "s", "class": "reentrancy",
                        "label_status": toy.POS, "N_h": N, "n_h": n,
                        "design_weight": N / n, "inclusion_probability": n / N})
    alloc = key[[*m.STRATA, "N_h", "n_h"]].drop_duplicates().reset_index(drop=True)
    return key, alloc


def test_ht_mean_and_variance_exhaustive_finite_populations():
    for values in ([0., 1., 0., 0.], [0., .25, 1., .75, 0.], [-2., 1., 3., .5]):
        N = len(values)
        for n in range(2, N + 1):
            results = []
            for ids in itertools.combinations(range(N), n):
                key, alloc = design(N, ids)
                results.append(m.ht_total(np.asarray(values)[list(ids)], key, alloc))
            points = [r["estimate"] for r in results]
            assert np.mean(points) == pytest.approx(sum(values), abs=1e-12)
            assert np.mean([r["design_variance_estimate"] for r in results]) == pytest.approx(np.var(points), abs=1e-12)


def test_production_bootstrap_weights_exact_multinomial_variance(monkeypatch):
    for N in range(3, 8):
        for n in range(2, min(N, 4) + 1):
            sequences = list(itertools.product(range(n), repeat=n - 1))
            counts = np.array([[seq.count(i) for i in range(n)] for seq in sequences])
            class ExhaustiveRNG:
                def multinomial(self, count, probability, size):
                    assert count == n - 1 and size == len(counts)
                    return counts.copy()
            monkeypatch.setattr(m.np.random, "default_rng", lambda seed: ExhaustiveRNG())
            key, alloc = design(N, list(range(n)))
            weights = m.rao_wu_weights(key, alloc, len(counts))
            z = np.array([0., .25, 1., -.5])[:n]
            total = weights @ z
            expected = m.ht_total(z, key, alloc)
            assert np.allclose(weights.sum(axis=1), N)
            assert np.mean(total) == pytest.approx(expected["estimate"], abs=1e-12)
            assert np.var(total) == pytest.approx(expected["design_variance_estimate"], abs=1e-12)


def test_census_exact_sklearn_AP_and_workload():
    args = toy.fixture(census=True)
    result = evaluate(args, review_fractions=(.25, .5, 1.))
    y = np.array([int(i % 3 == 0) for i in range(8)])
    assert result["ap"]["point"] == average_precision_score(y, args[-1].score)
    assert result["ap"]["interval"] == [result["ap"]["point"]] * 2
    for r, k in zip(result["workload"], (2, 4, 8)):
        assert r["point_HT_total_unclipped"] == y[:k].sum()
        assert r["point_design_variance"] == 0
        assert r["finite_population_logical_bounds"] == [float(y[:k].sum())] * 2


def test_weighted_AP_is_not_unweighted_sample_AP():
    y, scores, weights = [1, 0, 1], [.9, .8, .1], [1, 10, 1]
    assert m.weighted_ap(y, scores, weights) == average_precision_score(y, scores, sample_weight=weights)
    assert m.weighted_ap(y, scores, weights) != average_precision_score(y, scores)


def test_full_queue_cutoff_before_join_and_unknown_endpoint_bounds():
    args = list(toy.fixture())
    # Sample paths0,3,4,7; full top2 are0,1, not sampled top2 paths0,3.
    r = evaluate(args, review_fractions=(.25,))["workload"][0]
    assert r["point_HT_total_unclipped"] == 2.0
    args[5].loc[0, "adjudicated_judgment"] = "unknown"
    result = evaluate(args, review_fractions=(.25,))
    assert result["ap"]["point"] is None and result["ap"]["interval"] is None
    assert result["ap"]["safe_AP_bound_if_population_has_positive"] == [0, 1]
    w = result["workload"][0]
    assert w["point_HT_total_unclipped"] is None and w["unknown_sample_n"] == 1
    assert w["HT_estimated_unknown_lower_endpoint"]["estimate"] == 0
    assert w["HT_estimated_unknown_upper_endpoint"]["estimate"] == 2
    assert w["finite_population_logical_bounds"] == [0, 2]


def test_tie_probabilities_match_exhaustive_uniform_boundary_choices():
    scores, y = [9, 8, 8, 8, 0], np.array([0, 1, 0, 1, 1])
    q, detail = m.queue_probabilities(scores, 2)
    assert np.allclose(q, [1, 1/3, 1/3, 1/3, 0])
    actual = [y[0] + y[i] for i in (1, 2, 3)]
    assert q @ y == pytest.approx(np.mean(actual))
    assert detail["tie_count"] == 3


def test_HT_outside_support_kept_unclipped():
    key, alloc = design(4, [0, 1]); key["path"] = ["a", "b"]
    r = m.workload([1, 0, 0, 0], ["a", "b", "c", "d"], key, alloc, [1, 0])
    assert r["point_HT_total_unclipped"] == 2 > r["review_count"]
    assert r["point_outside_finite_support"] and not r["point_estimate_clipped"]
    assert r["finite_population_logical_bounds"] == [1, 1]


def test_no_positive_replicate_blocks_interval_without_dropping():
    r = m.ap_interval([1, 0], [.9, .1], [1, 1], [[0, 2], [1, 1]])
    assert r["point"] == 1 and r["interval"] is None
    assert r["invalid_replicates"] == r["no_positive_replicates"] == 1
    assert r["replicate_values"] == [None, 1.0]
    absent = m.ap_interval([0, 0], [.9, .1], [1, 1], [[1, 1], [1, 1]])
    assert absent["point"] is None and absent["invalid_replicates"] == 2


def test_non_census_singleton_fails_and_census_singleton_fixed():
    with pytest.raises(ValueError, match="n_h=1"):
        m.rao_wu_weights(*design(4, [0]), 4)
    assert np.array_equal(m.rao_wu_weights(*design(1, [0]), 4), np.ones((4, 1)))


@pytest.mark.parametrize("change", ["frame", "case", "weights", "class", "scores", "failure", "reviewer", "provenance", "initial", "stratum", "fractional"])
def test_adversarial_input_guards(change):
    args = list(toy.fixture())
    if change == "frame": args[0] = args[0].iloc[:-1]
    elif change == "case": args[1] = args[1].iloc[:-1]
    elif change == "weights": args[1].loc[0, "design_weight"] = 1
    elif change == "class": args[4].loc[0, "class"] = "unchecked"
    elif change == "scores": args[-1] = args[-1].iloc[:-1]
    elif change == "failure": args[-1].loc[0, "status"] = "timeout"
    elif change == "reviewer": args[4]["reviewer_id"] = "SYNTHETIC_REVIEWER_A"
    elif change == "provenance": args[3].loc[0, "reason"] = ""
    elif change == "initial": args[5].loc[0, "reviewer_1_judgment"] = "negative"
    elif change == "stratum": args[1].loc[0, "source_id"] = "other"
    else:
        args[2]["N_h"] = args[2]["N_h"].astype(float)
        args[2].loc[0, "N_h"] = 4.5
    with pytest.raises(ValueError):
        m.evaluate(*args, "reentrancy", expected_files=8, expected_sample_cases=4, classes=("reentrancy",), replicates=10)


def test_row_order_invariance_and_fixed_seed():
    args = toy.fixture()
    first = evaluate(args, review_fractions=(.25,))
    shuffled = [frame.sample(frac=1, random_state=i).reset_index(drop=True) for i, frame in enumerate(args)]
    assert evaluate(shuffled, review_fractions=(.25,)) == first


def test_unknown_hard_bounds_cover_all_completions():
    key, alloc = design(5, [0, 1]); key["path"] = ["a", "b"]
    q, _ = m.queue_probabilities([3, 2, 2, 2, 0], 2)
    r = m.workload(q, list("abcde"), key, alloc, [1, np.nan])
    lo, hi = r["finite_population_logical_bounds"]
    for rest in itertools.product([0, 1], repeat=4):
        actual = q @ np.array([1, *rest])
        assert lo - 1e-12 <= actual <= hi + 1e-12


def test_decimal_budget_and_empty_review_queue():
    result = evaluate(toy.fixture(N=100), review_fractions=(.29, 0))
    assert [r["review_count_requested"] for r in result["workload"]] == [29, 0]
    empty = result["workload"][1]
    assert empty["point_HT_total_unclipped"] == 0 and empty["finite_population_logical_bounds"] == [0, 0]


def test_full_size_fictional_frame_keeps_1998_queue_and_180_cases():
    args = toy.fixture(N=1998, n_per_class=90, classes=m.CLASSES)
    result = m.evaluate(*args, "reentrancy", replicates=10)
    assert result["full_queue_files"] == 1998 and result["all_selected_cases"] == 180
    assert result["selected_class_cases"] == 90
    assert [r["review_count_requested"] for r in result["workload"]] == [99, 199, 399]
