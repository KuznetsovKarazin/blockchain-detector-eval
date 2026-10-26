"""Fixed-frame survey comparisons; pure in-memory engineering, no execution gate.

The unchanged v1 supplies SRSWOR weights, weighted AP and HT workload bounds.
All methods and domains share ONE replicate matrix from the original sample.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location("performance_v1_dependency", Path(__file__).parents[1] / "performance_v1/performance.py")
v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v1)
STRATA, CLASSES = v1.STRATA, v1.CLASSES
FAILURE_STATUSES = ("compile_error", "tool_error", "timeout", "missing_dependency", "unsupported_pragma",
                    "missing_score", "preprocessing_error", "unavailable_binary", "model_error")
SCOPE = "design_approximate_fixed_finite_frame_scores_and_reference_process_not_family_generalization"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _fractions(fractions):
    values = tuple(fractions)
    if not values or len(set(values)) != len(values):
        raise ValueError("Unique nonempty review fractions required")
    for x in values:
        if isinstance(x, (bool, np.bool_)) or not np.isfinite(x) or not 0 <= x <= 1:
            raise ValueError("Review fractions must lie in [0,1]")
    return values


def _budget(fraction, size):
    return int((Decimal(str(fraction)) * size).to_integral_value(rounding=ROUND_FLOOR))


def _frame(frame, target_class, expected_files, classes):
    v1._integer(expected_files, "expected_files")
    if not classes or len(set(classes)) != len(classes) or set(classes) - set(CLASSES) or target_class not in classes:
        raise ValueError("Unexpected target class or class inventory")
    columns = ["path", *STRATA]
    if any(c not in frame for c in columns) or frame[columns].isna().any().any():
        raise ValueError("Complete frame identifiers and strata required")
    if any(not isinstance(x, str) or not x.strip() for x in frame[columns].to_numpy().ravel()):
        raise ValueError("Frame identifiers must be nonblank strings")
    paths = sorted(set(frame.path))
    if frame[["path", "class"]].duplicated().any() or set(frame["class"]) != set(classes):
        raise ValueError("Duplicate frame units or wrong class inventory")
    if len(paths) != expected_files or len(frame) != expected_files * len(classes):
        raise ValueError("Complete file-by-class frame required")
    if any(set(g.path) != set(paths) for _, g in frame.groupby("class")):
        raise ValueError("Classes must have the same fixed full file population")
    return paths


def plan_score_domains(frame, scores, target_class, *, methods, expected_files=1998,
                       classes=CLASSES, review_fractions=(.05, .1, .2)):
    """Build queues using statuses/scores only, BEFORE any reference join.

    Returns computational arrays aligned to sorted full-frame paths. No outcomes
    are accepted. A failed row must remain present, with an explicit reason and
    NaN score. Zero is a valid successful score; it is not a failure sentinel.
    """
    paths = _frame(frame, target_class, expected_files, classes)
    fractions = _fractions(review_fractions)
    methods = tuple(methods)
    if not methods or len(set(methods)) != len(methods) or any(not isinstance(x, str) or not x.strip() for x in methods):
        raise ValueError("Explicit unique nonblank method inventory required")
    required = ["method", "path", "class", "status", "score"]
    if any(c not in scores for c in required):
        raise ValueError("Scores require method,path,class,status,score")
    if scores[["method", "path", "class", "status"]].isna().any().any():
        raise ValueError("Missing score identity/status")
    if set(scores.method) != set(methods) or set(scores["class"]) != {target_class} or scores[["method", "path"]].duplicated().any():
        raise ValueError("Scores do not match declared one-class method inventory")
    if set(scores.status) - {"ok", *FAILURE_STATUSES}:
        raise ValueError("Unrecognized score status; amend the engineering policy explicitly")
    method_data = {}
    for method in methods:
        rows = scores[scores.method == method]
        if len(rows) != expected_files or set(rows.path) != set(paths):
            raise ValueError("Every method needs one explicit status for every full-frame file")
        rows = rows.set_index("path").loc[paths]
        success = rows.status.eq("ok").to_numpy()
        s = rows.score.to_numpy(dtype=float)
        if not np.isfinite(s[success]).all() or not np.isnan(s[~success]).all():
            raise ValueError("Successful scores must be finite; failures must have missing scores")
        method_data[method] = {"success": success, "scores": s,
            "status_counts": {status: int(rows.status.eq(status).sum()) for status in ("ok", *FAILURE_STATUSES)}}
    common = np.logical_and.reduce([method_data[m]["success"] for m in methods])
    domains = {}
    for name, domain in (("full_frame_pipeline", np.ones(len(paths), dtype=bool)), ("common_success", common)):
        n = int(domain.sum())
        entry = {"mask": domain, "population_n": n, "domain_id": _digest([p for p, d in zip(paths, domain) if d]), "methods": {}}
        for method in methods:
            data = method_data[method]
            available = data["success"] & domain
            queues = []
            for fraction in fractions:
                requested = _budget(fraction, n)
                filled = min(requested, int(available.sum()))
                q = np.zeros(len(paths))
                tie = {"boundary_score": None, "tie_count": 0, "slots_from_tie": 0}
                if available.any():
                    q[available], tie = v1.queue_probabilities(data["scores"][available], filled)
                queues.append({"review_fraction": float(fraction), "review_count_requested": requested,
                    "review_count_filled": filled, "unfilled_budget": requested - filled, "q": q, **tie})
            entry["methods"][method] = {"queues": queues, "AP_total_ranking_available": bool(np.all(data["success"][domain]))}
        domains[name] = entry
    return {"paths": paths, "class": target_class, "methods": method_data, "domains": domains,
            "selection_uses_reference_outcomes": False}


def _references(frame, sample, allocation, first, second, adjudication, target_class, expected_sample_cases):
    v1._integer(expected_sample_cases, "expected_sample_cases")
    if len(sample) != expected_sample_cases:
        raise ValueError("Every originally selected case must remain present")
    v1._strata(sample, allocation)
    counts, alloc = frame.groupby(STRATA, sort=True).size(), allocation.set_index(STRATA)
    if set(counts.index) != set(alloc.index) or any(int(counts.loc[g]) != int(alloc.loc[g].N_h) for g in counts.index):
        raise ValueError("Allocation differs from complete frame")
    joined = sample.merge(frame[["path", *STRATA]], on=["path", "class"], how="left", validate="one_to_one", suffixes=("", "_frame"), indicator=True)
    if not joined._merge.eq("both").all() or any(not joined[c].equals(joined[c + "_frame"]) for c in ("source_id", "label_status")):
        raise ValueError("Selected unit or stratum differs from complete frame")
    v1.review.analyze_review(sample, allocation, first, second, adjudication)
    selected = sample[sample["class"] == target_class].sort_values("case_id").reset_index(drop=True)
    alloc_class = allocation[allocation["class"] == target_class].copy()
    outcomes = adjudication.set_index("case_id").loc[selected.case_id, "adjudicated_judgment"]
    y = np.asarray([np.nan if x == "unknown" else int(x == "positive") for x in outcomes])
    return selected, alloc_class, y


def _vectors(y, q, domain, weights, replicate_weights):
    y, q, d, w, reps = map(np.asarray, (y, q, domain, weights, replicate_weights))
    y, q, w, reps = (x.astype(float) for x in (y, q, w, reps))
    if y.ndim != 1 or not len(y) or q.shape != y.shape or d.shape != y.shape or w.shape != y.shape:
        raise ValueError("Nonempty aligned sample vectors required")
    if d.dtype != np.bool_:
        raise ValueError("Domain must be an explicit boolean vector")
    if np.isinf(y).any() or not np.isin(y[np.isfinite(y)], [0, 1]).all():
        raise ValueError("Binary outcomes or explicit NaN unknowns required")
    if not np.isfinite(q).all() or ((q < 0) | (q > d)).any():
        raise ValueError("Queue probabilities must be in [0,domain indicator]")
    if not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError("Original positive design weights required")
    if reps.ndim != 2 or reps.shape[1] != len(y) or reps.shape[0] < 2 or not np.isfinite(reps).all() or (reps < 0).any():
        raise ValueError("At least two aligned finite nonnegative replicate weights required")
    return y, q, d, w, reps


def _result(point, values, alpha, census, *, estimator, status=None):
    v1._alpha(alpha)
    values = [None if x is None else float(x) for x in values]
    invalid = sum(x is None for x in values)
    interval = None
    if point is not None and not invalid:
        interval = [float(point), float(point)] if census else list(map(float, np.quantile(values, [alpha / 2, 1 - alpha / 2])))
    return {"point": None if point is None else float(point), "interval": interval,
        "replicate_values": values, "invalid_replicates": invalid, "replicates_requested": len(values),
        "status": status or ("CI_blocked_invalid_replicates_none_dropped" if invalid else "census_exact" if census else "design_approximation"),
        "estimator": estimator, "interval_method": "census_no_sampling_error" if census else "Rao_Wu_FPC_percentile_design_approximate",
        "nominal_level": 1 - alpha, "interval_coverage_guaranteed": False, "coverage_scope": SCOPE,
        "noncensus_zero_replicate_spread": bool(not census and not invalid and np.ptp(values) == 0),
        "uncertainty_excludes": ["realized_boundary_tie_randomization", "model_training_variation", "reference_errors", "new_family_variation"]}


def recall_interval(y, q, domain, weights, replicate_weights, alpha=.05, census=False):
    """Ratio of HT tie-averaged findings to HT reference positives in domain.

    A nonlinear generally biased ratio; not the expectation of a random ratio.
    Full-frame domain includes failed-score positives in its denominator.
    Outside-domain rows remain in every replicate with zero domain contribution.
    """
    y, q, d, w, reps = _vectors(y, q, domain, weights, replicate_weights)
    unknown = int(np.isnan(y[d]).sum())
    if unknown:
        result = _result(None, [None] * len(reps), alpha, census, estimator="ratio_of_HT_totals_not_unbiased",
                         status="suppressed_unknown_domain_outcomes")
        result.update(zero_denominator_replicates=0, invalid_replicates_reason="unknown_domain_outcomes_not_zero_denominator")
    else:
        positive = np.where(d, y, 0.0)  # domain indicator, NOT a negative reference label
        recovered = q * positive
        denominator, numerator = float(w @ positive), float(w @ recovered)
        denominators, numerators = reps @ positive, reps @ recovered
        values = [float(a / b) if b > 0 else None for a, b in zip(numerators, denominators)]
        result = _result(numerator / denominator if denominator > 0 else None, values, alpha, census,
            estimator="ratio_of_HT_totals_not_unbiased", status="undefined_no_estimated_domain_positive" if denominator <= 0 else None)
        result.update(numerator_HT=numerator, denominator_HT=denominator,
                      zero_denominator_replicates=int((denominators <= 0).sum()))
    result.update(unknown_domain_sample_n=unknown, unknown_outside_domain_sample_n=int(np.isnan(y[~d]).sum()),
                  safe_recall_bound_if_domain_has_positive=[0.0, 1.0], unknowns_dropped=False,
                  ratio_bias_caveat="Finite-sample nonlinear ratio bias; zero or rare observed positives can yield undefined or unreliable intervals.")
    return result


def yield_interval(y, q, domain, weights, replicate_weights, alpha=.05, census=False):
    """HT tie-averaged count, with shared replicates for paired comparisons."""
    y, q, d, w, reps = _vectors(y, q, domain, weights, replicate_weights)
    if np.isnan(y[d]).any():
        return _result(None, [None] * len(reps), alpha, census, estimator="HT_total_unclipped",
                       status="suppressed_unknown_domain_outcomes")
    z = q * np.where(d, y, 0.0)
    return _result(w @ z, reps @ z, alpha, census, estimator="HT_total_unclipped")


def paired_difference(left, right, *, alpha=.05, census=False):
    """Left minus right within the SAME target/budget and shared resampling.

    Metric records must be tagged by evaluate_methods with shared matrix digest,
    metric, domain ID and requested budget. This forbids cross-domain contrasts.
    """
    keys = ("replicate_id", "metric", "domain_id", "review_count_requested")
    if any(k not in left or k not in right or left[k] != right[k] for k in keys):
        raise ValueError("Paired comparison requires same shared replicates, metric, domain and budget")
    lv, rv = left["replicate_values"], right["replicate_values"]
    if len(lv) != len(rv) or len(lv) < 2:
        raise ValueError("Aligned replicate records required")
    point = None if left["point"] is None or right["point"] is None else left["point"] - right["point"]
    values = [None if a is None or b is None else a - b for a, b in zip(lv, rv)]
    result = _result(point, values, alpha, census, estimator="paired_difference_of_" + left["metric"],
                     status="suppressed_or_undefined_component" if point is None else None)
    result.update({k: left[k] for k in keys})
    result["direction"] = "left_minus_right"
    result["independent_bootstrap_for_each_method"] = False
    result["multiplicity_adjusted"] = False
    return result


def _tag(result, replicate_id, metric, domain_id, budget=None):
    return {**result, "replicate_id": replicate_id, "metric": metric,
            "domain_id": domain_id, "review_count_requested": budget}


def evaluate_methods(frame, sample, allocation, first, second, adjudication, scores, target_class,
                     *, methods, expected_files=1998, expected_sample_cases=180, classes=CLASSES,
                     review_fractions=(.05, .1, .2), replicates=2000, seed=20261026, alpha=.05):
    """One class, declared methods, unchanged complete survey sample. No I/O."""
    v1._alpha(alpha)
    plan = plan_score_domains(frame, scores, target_class, methods=methods, expected_files=expected_files,
                             classes=classes, review_fractions=review_fractions)
    selected, alloc, y = _references(frame, sample, allocation, first, second, adjudication, target_class, expected_sample_cases)
    weights = selected.design_weight.to_numpy(dtype=float)
    reps = v1.rao_wu_weights(selected, alloc, replicates, seed)  # ONE shared matrix, original design
    replicate_id = _digest({"cases": selected.case_id.tolist(), "weights": reps.tolist()})
    positions = {p: i for i, p in enumerate(plan["paths"])}
    ids = np.asarray([positions[p] for p in selected.path])
    census = bool((alloc.N_h == alloc.n_h).all())
    domains = {}
    for name, domain in plan["domains"].items():
        d = domain["mask"][ids]
        domain_id = domain["domain_id"]
        results = {}
        for method, method_plan in domain["methods"].items():
            s = plan["methods"][method]["scores"][ids]
            if domain["population_n"] == 0 or not d.any():
                ap = _result(None, [None] * len(reps), alpha, census, estimator="nonlinear_domain_weighted_AP_plugin_not_unbiased",
                             status="undefined_empty_population_or_unsampled_domain")
            elif not method_plan["AP_total_ranking_available"]:
                ap = _result(None, [None] * len(reps), alpha, census, estimator="nonlinear_domain_weighted_AP_plugin_not_unbiased",
                             status="suppressed_no_total_ranking_failed_scores")
            else:
                ap = v1.ap_interval(y[d], s[d], weights[d], reps[:, d], alpha, census)
                # v1 suppressed cases return no draws; paired alignment stays explicit.
                if not ap["replicate_values"]:
                    ap["replicate_values"] = [None] * len(reps)
                    ap["invalid_replicates"] = len(reps)
            ap = _tag(ap, replicate_id, "AP", domain_id)
            budgets = []
            for queue in method_plan["queues"]:
                q_full, q = queue["q"], queue["q"][ids]
                record = {k: v for k, v in queue.items() if k != "q"}
                k = queue["review_count_requested"]
                record["yield"] = _tag(yield_interval(y, q, d, weights, reps, alpha, census), replicate_id, "yield", domain_id, k)
                record["recall"] = _tag(recall_interval(y, q, d, weights, reps, alpha, census), replicate_id, "recall", domain_id, k)
                # v1 retains original sample/strata; y_D is a domain indicator
                # contribution. Unknowns outside D are irrelevant, not relabelled.
                record["yield_bounds_and_design_variance"] = v1.workload(q_full, plan["paths"], selected, alloc, np.where(d, y, 0.0), alpha)
                record["yield_bounds_and_design_variance"]["domain_zero_contribution_outside_target"] = True
                budgets.append(record)
            results[method] = {"ap": ap, "workload": budgets}
        pairs = []
        for left, right in itertools.combinations(sorted(results), 2):
            a, b = results[left], results[right]
            pair = {"left": left, "right": right,
                    "ap_difference": paired_difference(a["ap"], b["ap"], alpha=alpha, census=census), "workload_differences": []}
            for qa, qb in zip(a["workload"], b["workload"]):
                differences = {"review_fraction": qa["review_fraction"], "review_count_requested": qa["review_count_requested"]}
                for metric in ("yield", "recall"):
                    differences[metric] = paired_difference(qa[metric], qb[metric], alpha=alpha, census=census)
                # Exact standard design variance estimator for the linear paired yield.
                if not np.isnan(y[d]).any():
                    index = len(pair["workload_differences"])
                    delta = (domain["methods"][left]["queues"][index]["q"][ids] - domain["methods"][right]["queues"][index]["q"][ids]) * np.where(d, y, 0.0)
                    differences["yield"]["paired_linear_design_estimate"] = v1.ht_total(delta, selected, alloc)
                pair["workload_differences"].append(differences)
            pairs.append(pair)
        domains[name] = {"population_n": domain["population_n"], "domain_id": domain_id,
            "selected_in_domain_n": int(d.sum()), "selected_outside_domain_retained_n": int((~d).sum()),
            "unknown_sample_in_domain_n": int(np.isnan(y[d]).sum()), "unknown_sample_outside_domain_n": int(np.isnan(y[~d]).sum()),
            "target_population_changed_from_full_frame": bool(name == "common_success" and domain["population_n"] != len(plan["paths"])),
            "budget_denominator": domain["population_n"], "sample_design_redefined": False,
            "methods": results, "paired_differences": pairs}
    coverage = {method: {"class": target_class, "full_frame_n": len(plan["paths"]),
        "success_n": int(data["success"].sum()), "failure_n": int((~data["success"]).sum()),
        "success_fraction": float(data["success"].mean()), "status_counts": data["status_counts"]}
        for method, data in plan["methods"].items()}
    return {"schema": "fixed_frame_probability_performance_engineering_v2", "class": target_class,
        "declared_methods": list(methods), "coverage_by_method": coverage, "domains": domains,
        "all_selected_cases": len(sample), "selected_class_cases_retained": len(selected),
        "bootstrap": {"method": "Rao_Wu_single_stage_SRSWOR_FPC", "replicates": replicates, "seed": seed,
                      "replicate_id": replicate_id, "shared_across_all_methods_and_domains": True, "original_strata_and_sampling_fractions_preserved": True},
        "policy": {"full_frame_budget": "floor(f*N_full); rank successful files; failed files receive no score and no automated review; unused slots remain unfilled",
                   "common_success_budget": "floor(f*N_common); intersection across ALL declared methods from statuses before reference join",
                   "pipeline_recall_denominator": "all full-frame reference positives including failed-score positives",
                   "common_recall_denominator": "reference positives in common-success domain",
                   "paired_targets": "within the same domain and planned budget only; cross-domain contrasts are not method comparisons",
                   "failure_triage": "No manual failure triage or fallback is included; such a policy needs a separate prespecified budget",
                   "unknowns": "Never dropped or called negative; suppress AP/ratio/difference in affected domain; workload endpoint bounds remain available"},
        "coverage_scope": SCOPE, "model_fits_performed": 0, "execution_gate_override": False,
        "limitations": ["AP and recall ratios are nonlinear generally biased plug-ins", "Percentile and normal intervals are design approximations; rare-positive coverage is not guaranteed",
                        "Shared replicates retain paired covariance but do not prove interval coverage", "No multiplicity correction or cross-class covariance inference",
                        "No new-family interval, model-training uncertainty or validation of human-reference correctness",
                        "Common-success selection is score-status dependent and changes target population; no extrapolation to failed files"]}
