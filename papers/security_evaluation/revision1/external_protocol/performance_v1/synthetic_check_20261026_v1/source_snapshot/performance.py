"""Survey performance engineering for a fixed stratified SRSWOR frame.

Pure in-memory API: no paths, data/key loading, model fitting or external scoring.
AP is a nonlinear weighted plug-in. Intervals are design-approximate conditional
on the fixed frame, scores and reference process; never new-family intervals.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR
import importlib.util
import math
from numbers import Integral
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import average_precision_score

_spec = importlib.util.spec_from_file_location("existing_review_estimators", Path(__file__).parents[1] / "review_estimators.py")
review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(review)
STRATA = review.STRATA
CLASSES = ("reentrancy", "unchecked")


def _integer(value, name, minimum=1):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _alpha(alpha):
    if isinstance(alpha, bool) or not np.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be in (0,1)")


def _strata(sample, allocation):
    """Validate every stratum and its unaltered fixed-design weights."""
    if sample.empty or allocation.empty or allocation[STRATA].duplicated().any():
        raise ValueError("Nonempty sample and unique allocation strata required")
    if not sample.case_id.is_unique or sample.case_id.isna().any() or sample.case_id.astype(str).str.strip().eq("").any():
        raise ValueError("Duplicate or missing sample case IDs")
    if any(isinstance(x, (bool, np.bool_)) for x in allocation[["N_h", "n_h"]].to_numpy().ravel()):
        raise ValueError("Boolean allocation counts are not integers")
    counts = allocation[["N_h", "n_h"]].to_numpy(dtype=float)
    if not np.isfinite(counts).all() or (counts < 1).any() or (counts != np.floor(counts)).any() or (counts[:, 1] > counts[:, 0]).any():
        raise ValueError("Finite positive integer N_h,n_h with n_h<=N_h required")
    if ((counts[:, 1] == 1) & (counts[:, 0] > 1)).any():
        raise ValueError("Noncensus n_h=1 cannot estimate design variance")
    groups = sample.groupby(STRATA, sort=True, dropna=False).indices
    indexed = allocation.set_index(STRATA)
    if set(groups) != set(indexed.index):
        raise ValueError("Missing or unexpected sampling stratum")
    result = []
    for group, positions in groups.items():
        row = indexed.loc[group]
        N, n = int(row.N_h), int(row.n_h)
        part = sample.iloc[positions]
        if len(part) != n:
            raise ValueError("Selected cases were removed or added")
        for column, expected in (("N_h", N), ("n_h", n), ("design_weight", N / n), ("inclusion_probability", n / N)):
            if not np.allclose(part[column].to_numpy(dtype=float), expected, atol=1e-12, rtol=1e-12):
                raise ValueError("Wrong " + column)
        # Stable case order makes seeded replicates invariant to input row order.
        positions = np.asarray(sorted(positions, key=lambda i: str(sample.iloc[i].case_id)))
        result.append((group, positions, N, n))
    return result


def rao_wu_weights(sample, allocation, replicates=2000, seed=20261026):
    """Finite-correction Rao–Wu rescaling, m_h=n_h−1, for single-stage SRSWOR.

    w* = w [1-sqrt(1-f) + sqrt(1-f)*n/(n-1)*M], M~Multinomial(n-1,1/n).
    Census strata stay fixed. No stratum collapsing or implicit FPC omission.
    """
    B, seed = _integer(replicates, "replicates", 2), _integer(seed, "seed", 0)
    rng = np.random.default_rng(seed)
    result = np.empty((B, len(sample)), dtype=float)
    for _, ids, N, n in _strata(sample, allocation):
        if n == N:
            result[:, ids] = 1.0
            continue
        fraction = n / N
        scale = math.sqrt(1.0 - fraction)
        # Algebraically 1-scale; stable when a positive fraction is very small.
        baseline = fraction / (1.0 + scale)
        multiplicity = rng.multinomial(n - 1, np.full(n, 1.0 / n), size=B)
        result[:, ids] = (N / n) * (baseline + scale * n / (n - 1) * multiplicity)
        if not np.allclose(result[:, ids].sum(axis=1), N, rtol=1e-12, atol=1e-12):
            raise ArithmeticError("Replicate stratum weights do not sum to N_h")
    return result


def ht_total(values, sample, allocation):
    """Unclipped HT total and standard SRSWOR variance estimator for a fixed z."""
    z = np.asarray(values, dtype=float)
    if z.shape != (len(sample),) or not np.isfinite(z).all():
        raise ValueError("Aligned finite sample values required; unknowns need explicit endpoint analysis")
    estimate, variance = 0.0, 0.0
    for _, ids, N, n in _strata(sample, allocation):
        estimate += N * float(z[ids].mean())
        if n < N:
            variance += N * N * (1 - n / N) * float(np.var(z[ids], ddof=1)) / n
    return {"estimate": estimate, "design_variance_estimate": variance,
            "standard_error_estimate": math.sqrt(variance)}


def queue_probabilities(scores, k):
    """Label-independent selection probabilities on the COMPLETE ranked queue."""
    s = np.asarray(scores, dtype=float)
    if s.ndim != 1 or len(s) == 0 or not np.isfinite(s).all():
        raise ValueError("Full finite score vector required")
    k = _integer(k, "k", 0)
    if k > len(s):
        raise ValueError("Budget exceeds full queue")
    if k == 0:
        return np.zeros(len(s)), {"boundary_score": None, "tie_count": 0, "slots_from_tie": 0}
    cutoff = np.sort(s)[-k]
    above, tie = s > cutoff, s == cutoff
    slots = k - int(above.sum())
    q = above.astype(float)
    q[tie] = slots / int(tie.sum())
    return q, {"boundary_score": float(cutoff), "tie_count": int(tie.sum()), "slots_from_tie": slots}


def weighted_ap(y, scores, weights):
    """Complete-reference nonlinear plug-in; None means undefined/suppressed."""
    y, s, w = np.asarray(y, dtype=float), np.asarray(scores, dtype=float), np.asarray(weights, dtype=float)
    if y.ndim != 1 or y.size == 0 or s.shape != y.shape or w.shape != y.shape:
        raise ValueError("Nonempty aligned vectors required")
    if np.isinf(y).any() or not np.isin(y[np.isfinite(y)], [0, 1]).all():
        raise ValueError("Outcomes must be binary or explicit NaN unknowns")
    if not np.isfinite(s).all() or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError("Finite scores and nonnegative positive-total weights required")
    if np.isnan(y).any() or float(w @ y) <= 0:
        return None
    return float(average_precision_score(y.astype(int), s, sample_weight=w))


def ap_interval(y, scores, weights, replicate_weights, alpha=.05, census=False):
    _alpha(alpha)
    y = np.asarray(y, dtype=float)
    reps = np.asarray(replicate_weights, dtype=float)
    if reps.ndim != 2 or reps.shape[1] != len(y) or reps.shape[0] < 2:
        raise ValueError("At least two aligned bootstrap replicates required")
    if not np.isfinite(reps).all() or (reps < 0).any():
        raise ValueError("Invalid replicate weights")
    point = weighted_ap(y, scores, weights)
    result = {"point": point, "estimator": "nonlinear_survey_weighted_AP_plugin_not_unbiased",
              "unknown_sample_outcomes": int(np.isnan(y).sum()), "interval": None,
              "safe_AP_bound_if_population_has_positive": [0.0, 1.0],
              "coverage_scope": "design_approximate_fixed_finite_frame_scores_and_reference_process_not_family_generalization",
              "invalid_replicates": 0, "no_positive_replicates": 0, "replicates_requested": len(reps),
              "replicate_values": [], "bootstrap_coverage_guaranteed": False}
    if np.isnan(y).any():
        result["status"] = "suppressed_unknown_outcomes_no_complete_case_deletion"
        return result
    if point is None:
        result["status"] = "undefined_no_sample_positive"
        result["no_positive_replicates"] = len(reps)
        result["invalid_replicates"] = len(reps)
        if census:
            result["safe_AP_bound_if_population_has_positive"] = None
            result["status"] = "undefined_no_population_positive_census"
        return result
    values = []
    for w in reps:
        if w.sum() <= 0 or float(w @ y) <= 0:
            values.append(None)
            result["invalid_replicates"] += 1
            result["no_positive_replicates"] += int(float(w @ y) <= 0)
        else:
            values.append(weighted_ap(y, scores, w))
    result["replicate_values"] = values
    if result["invalid_replicates"]:
        result["status"] = "CI_blocked_invalid_replicates_none_silently_dropped"
        return result
    result["status"] = "census_exact" if census else "complete_reference_design_approximation"
    result["interval"] = [point, point] if census else list(map(float, np.quantile(values, [alpha / 2, 1 - alpha / 2])))
    result["interval_method"] = "census_no_sampling_error" if census else "Rao_Wu_FPC_percentile_design_approximate"
    result["nominal_level"] = 1 - alpha
    result["bootstrap_variance"] = float(np.var(values, ddof=1))
    result["rare_positive_caution"] = "Positive FPC baseline can retain every observed positive in every replicate; valid replicates or zero spread do not prove coverage."
    return result


def _normal_interval(center, variance, alpha):
    half = float(norm.ppf(1 - alpha / 2)) * math.sqrt(variance)
    return [center - half, center + half]


def workload(q_full, paths_full, sampled, allocation, y, alpha=.05):
    """HT-estimate tie-averaged findings; unknown endpoints and hard bounds separate."""
    _alpha(alpha)
    q_full, y = np.asarray(q_full, dtype=float), np.asarray(y, dtype=float)
    if q_full.shape != (len(paths_full),) or len(set(paths_full)) != len(paths_full):
        raise ValueError("Full unique path/probability alignment required")
    if not np.isfinite(q_full).all() or ((q_full < 0) | (q_full > 1)).any():
        raise ValueError("Review probabilities must be finite in [0,1]")
    if y.shape != (len(sampled),) or np.isinf(y).any() or not np.isin(y[np.isfinite(y)], [0, 1]).all():
        raise ValueError("Aligned binary/unknown reference outcomes required")
    if not sampled.path.is_unique or not set(sampled.path).issubset(set(paths_full)):
        raise ValueError("Sample is not a unique subset of the full queue")
    mapping = dict(zip(paths_full, q_full))
    q = np.asarray([mapping[p] for p in sampled.path])
    lower = q * np.where(np.isnan(y), 0, y)
    upper = q * np.where(np.isnan(y), 1, y)
    lo, hi = ht_total(lower, sampled, allocation), ht_total(upper, sampled, allocation)
    complete = not np.isnan(y).any()
    k = float(q_full.sum())
    if not math.isclose(k, round(k), rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("Fixed review probabilities must sum to an integer budget")
    # These unweighted bounds are logically valid even for all unsampled labels.
    finite_low = float(q[y == 1].sum())
    finite_high = float(k - q[y == 0].sum())
    envelope = [_normal_interval(lo["estimate"], lo["design_variance_estimate"], alpha)[0],
                _normal_interval(hi["estimate"], hi["design_variance_estimate"], alpha)[1]]
    clipped = [max(0.0, envelope[0]), min(k, envelope[1])]
    intersection = clipped if clipped[0] <= clipped[1] else None
    return {"estimand": "expected_recovered_reference_positive_count_under_uniform_boundary_tie",
            "queue_n": len(paths_full), "review_count": int(round(k)),
            "point_HT_total_unclipped": lo["estimate"] if complete else None,
            "point_design_variance": lo["design_variance_estimate"] if complete else None,
            "point_outside_finite_support": bool(complete and not 0 <= lo["estimate"] <= k),
            "unknown_sample_n": int(np.isnan(y).sum()), "unknown_cases_dropped": False,
            "HT_estimated_unknown_lower_endpoint": lo, "HT_estimated_unknown_upper_endpoint": hi,
            "endpoint_estimates_are_not_hard_population_bounds": True,
            "finite_population_logical_bounds": [finite_low, finite_high],
            "logical_bounds_include_unsampled_and_unknown_reference_outcomes": True,
            "approximate_normal_interval_or_unknown_envelope_raw": envelope,
            "approximate_interval_support_intersection": intersection,
            "point_estimate_clipped": False, "nominal_level": 1 - alpha,
            "noncensus_zero_estimated_variance": bool((allocation.N_h > allocation.n_h).any() and
                lo["design_variance_estimate"] == 0 and hi["design_variance_estimate"] == 0),
            "interval_coverage_guaranteed": False,
            "interval_caveat": "Design-normal approximation can under-cover with rare/zero observed findings; zero sample variance is not evidence of absent unsampled findings. Logical bounds remain separate.",
            "variance_scope": "annotation_sampling_for_tie_averaged_yield; excludes realized_tie_randomization_variance_and_model_training_variability",
            "new_family_inference": False}


def validate_inputs(frame, sample, allocation, first, second, adjudication, scores,
                    target_class, expected_files=1998, expected_sample_cases=180, classes=CLASSES):
    """Full frame + all selected cases/provenance; no score or reference deletion."""
    expected_files = _integer(expected_files, "expected_files")
    expected_sample_cases = _integer(expected_sample_cases, "expected_sample_cases")
    if not classes or len(set(classes)) != len(classes) or set(classes) - set(CLASSES) or target_class not in classes:
        raise ValueError("Unexpected classes or target class")
    required = ["path", *STRATA]
    if any(c not in frame for c in required) or frame[required].isna().any().any():
        raise ValueError("Complete frame identifiers and strata required")
    if frame[required].astype(str).apply(lambda c: c.str.strip().eq("")).any().any():
        raise ValueError("Blank frame identifiers")
    if frame[["path", "class"]].duplicated().any() or set(frame["class"]) != set(classes):
        raise ValueError("Invalid or duplicated complete frame units")
    full_paths = set(frame.path)
    if len(full_paths) != expected_files or len(frame) != expected_files * len(classes):
        raise ValueError("Complete file-by-class frame required")
    if any(set(g.path) != full_paths for _, g in frame.groupby("class")):
        raise ValueError("Each class must cover the same full file queue")
    if len(sample) != expected_sample_cases:
        raise ValueError("All preselected cases must be retained")
    _strata(sample, allocation)
    counts = frame.groupby(STRATA, sort=True).size()
    alloc = allocation.set_index(STRATA)
    if set(counts.index) != set(alloc.index) or any(int(counts.loc[s]) != int(alloc.loc[s].N_h) for s in counts.index):
        raise ValueError("Allocation does not match complete frame population counts")
    joined = sample.merge(frame[required], on=["path", "class"], how="left", validate="one_to_one", suffixes=("", "_frame"), indicator=True)
    if not joined._merge.eq("both").all():
        raise ValueError("Selected case outside frame")
    if any(not joined[c].equals(joined[c + "_frame"]) for c in ("source_id", "label_status")):
        raise ValueError("Selected case stratum metadata changed")
    # Existing validator enforces every case, weights, class, distinct named
    # initial reviewers, provenance fields and preserved initial judgments.
    review.analyze_review(sample, allocation, first, second, adjudication)
    for data, label in ((sample, "sample"), (scores, "scores")):
        if any(c not in data for c in ("path", "class")) or data[["path", "class"]].isna().any().any():
            raise ValueError("Missing " + label + " identities")
    if scores[["path", "class"]].duplicated().any() or set(scores["class"]) != {target_class}:
        raise ValueError("Scores must identify one target class and each path exactly once")
    if set(scores.path) != full_paths or len(scores) != expected_files:
        raise ValueError("Full queue score coverage required, never sample-only ranking")
    if "score" not in scores or "status" not in scores or not scores.status.eq("ok").all():
        raise ValueError("Any failed or missing score blocks this complete-score estimator")
    if not np.isfinite(scores.score.to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite score; failure is not a safe score")
    sample = sample.sort_values("case_id").reset_index(drop=True)
    selected = sample[sample["class"] == target_class].reset_index(drop=True)
    alloc_class = allocation[allocation["class"] == target_class].copy()
    scores = scores.sort_values("path").reset_index(drop=True)
    outcomes = adjudication.set_index("case_id").loc[selected.case_id, "adjudicated_judgment"]
    y = np.asarray([np.nan if x == "unknown" else int(x == "positive") for x in outcomes])
    return selected, alloc_class, scores, y


def evaluate(frame, sample, allocation, first, second, adjudication, scores, target_class,
             *, expected_files=1998, expected_sample_cases=180, classes=CLASSES,
             review_fractions=(.05, .1, .2), replicates=2000, seed=20261026, alpha=.05):
    """One method/class. Caller must separately satisfy prospective execution gates."""
    _alpha(alpha)
    selected, alloc, queue, y = validate_inputs(frame, sample, allocation, first, second, adjudication,
        scores, target_class, expected_files, expected_sample_cases, classes)
    weights = selected.design_weight.to_numpy(dtype=float)
    sample_scores = queue.set_index("path").loc[selected.path, "score"].to_numpy(dtype=float)
    rep_weights = rao_wu_weights(selected, alloc, replicates, seed)
    ap = ap_interval(y, sample_scores, weights, rep_weights, alpha, census=bool((alloc.N_h == alloc.n_h).all()))
    budgets = []
    fractions = tuple(review_fractions)
    if not fractions or len(set(fractions)) != len(fractions):
        raise ValueError("Unique nonempty review fractions required")
    for fraction in fractions:
        if isinstance(fraction, bool) or not np.isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("Review fraction outside [0,1]")
        k = int((Decimal(str(fraction)) * len(queue)).to_integral_value(rounding=ROUND_FLOOR))
        q, tie = queue_probabilities(queue.score, k)  # before joining sample
        budgets.append({"review_fraction": float(fraction), "review_count_requested": k, **tie,
                        **workload(q, queue.path.tolist(), selected, alloc, y, alpha)})
    return {"schema": "fixed_frame_probability_performance_engineering_v1", "class": target_class,
            "score_coverage": 1.0, "full_queue_files": len(queue), "all_selected_cases": len(sample),
            "selected_class_cases": len(selected), "sampling_design": "independent_stratified_SRSWOR_file_by_class",
            "reference": "named_expert_adjudication_conditional_not_infallible_truth", "ap": ap, "workload": budgets,
            "bootstrap": {"method": "Rao_Wu_single_stage_SRSWOR_FPC", "replicates": replicates, "seed": seed,
                          "census_strata_fixed": True, "noncensus_n1_rejected": True},
            "model_fits_performed": 0, "execution_gate_override": False,
            "limitations": ["Nonlinear AP plug-in is not unbiased", "AP percentile and workload normal intervals are design approximations without established rare-positive coverage",
                            "Unknown reference outcomes never deleted or treated as known negatives", "No new-project/family confidence interval or model-training uncertainty",
                            "No cross-class paired inference: file-by-class sample overlaps need separate covariance treatment",
                            "Complete successful full-queue scores required; failed-score fallback is not implemented"]}
