"""Label-aware workload metrics for the security evaluation study.

The review population is every input file, including unknown labels and tool
failures. Only files with status ``ok`` and a finite score can enter its ranked
review queue. There is no implicit manual fallback for failures and no synthetic
"safe" score. An unknown label must be None/NaN, never a numeric zero.

AP and trapezoidal PR area are conditional on successfully scored, known-label
files. Workload recall instead divides by all known positives in the input,
including failed files. Precision on known labels is the ratio of expected
positive and known-label review counts; with unknowns in a boundary tie this is
NOT generally the expectation of the random precision ratio.

Scores are tied by exact equality, without post-hoc rounding. A partially
selected boundary tie is a uniform subset, independent of labels. The reported
count ranges are marginal feasible ranges, not jointly attainable intervals.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_FLOOR
from numbers import Integral

import numpy as np
from sklearn.metrics import auc, average_precision_score, precision_recall_curve


LABEL_REGIMES = {"confirmed", "source_reported", "proxy"}


def _inputs(labels, scores, statuses=None):
    y = np.asarray(labels, dtype=float)
    s = np.asarray(scores, dtype=float)
    if y.ndim != 1 or s.ndim != 1 or len(y) != len(s):
        raise ValueError("labels and scores must be one-dimensional and equally sized")
    known = ~np.isnan(y)
    if not np.isin(y[known], [0.0, 1.0]).all():
        raise ValueError("labels must be 0, 1, or None/NaN for unknown")
    if np.isinf(s).any():
        raise ValueError("scores may be finite or NaN, not infinite")
    if statuses is None:
        status = np.where(np.isfinite(s), "ok", "unscored")
    else:
        status = np.asarray(statuses, dtype=object)
        if status.ndim != 1 or len(status) != len(y):
            raise ValueError("statuses must have one entry per file")
        if any(not isinstance(x, str) or not x.strip() for x in status):
            raise ValueError("each status must be a nonempty string")
    scorable = (status == "ok") & np.isfinite(s)
    return y, s, status, known, scorable


def _ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else None


def _count_expectation_and_range(mask, above, tied, slots):
    fixed = int(np.count_nonzero(mask & above))
    n_tied = int(tied.sum())
    n_matching = int(np.count_nonzero(mask & tied))
    expected = fixed + slots * n_matching / n_tied if n_tied else float(fixed)
    minimum = fixed + max(0, slots - (n_tied - n_matching))
    maximum = fixed + min(slots, n_matching)
    return float(expected), int(minimum), int(maximum)


def _at_k(y, s, known, scorable, requested_count):
    if not isinstance(requested_count, Integral) or isinstance(requested_count, bool) or requested_count < 0:
        raise ValueError("requested_count must be a nonnegative integer")
    n = len(y)
    if requested_count > n:
        raise ValueError("requested_count cannot exceed the full file population")
    k = min(int(requested_count), int(scorable.sum()))
    if k:
        threshold = float(np.sort(s[scorable])[-k])
        above = scorable & (s > threshold)
        tied = scorable & (s == threshold)
        slots = k - int(above.sum())
    else:
        threshold = None
        above = tied = np.zeros(n, dtype=bool)
        slots = 0
    positive = known & (y == 1)
    negative = known & (y == 0)
    masks = {"known_positive": positive, "known_negative": negative,
             "known_label": known, "unknown_label": ~known}
    counts = {}
    for name, mask in masks.items():
        expected, minimum, maximum = _count_expectation_and_range(mask, above, tied, slots)
        counts[f"{name}_reviewed_expected"] = expected
        counts[f"{name}_reviewed_min"] = minimum
        counts[f"{name}_reviewed_max"] = maximum
    tp = counts["known_positive_reviewed_expected"]
    return {
        "review_count_requested": int(requested_count),
        "review_count_achieved": k,
        "review_fraction_achieved": _ratio(k, n),
        "unused_review_slots": int(requested_count) - k,
        "boundary_score": threshold,
        "above_boundary_count": int(above.sum()),
        "boundary_tie_count": int(tied.sum()),
        "boundary_tie_slots": slots,
        **counts,
        "known_positive_yield_per_review": _ratio(tp, k),
        "judged_precision_ratio_of_expected_counts": _ratio(tp, counts["known_label_reviewed_expected"]),
        "known_positive_recall_expected": _ratio(tp, int(positive.sum())),
        "known_positive_recall_min": _ratio(counts["known_positive_reviewed_min"], int(positive.sum())),
        "known_positive_recall_max": _ratio(counts["known_positive_reviewed_max"], int(positive.sum())),
    }


def review_at_k(labels, scores, requested_count, *, statuses=None):
    """Return tie-aware counts for an explicit budget on the full population.

    This low-level function computes arithmetic only; use ``evaluate_workload``
    to attach the mandatory label-regime interpretation and ranking coverage.
    """
    y, s, _, known, scorable = _inputs(labels, scores, statuses)
    return _at_k(y, s, known, scorable, requested_count)


def evaluate_workload(labels, scores, *, label_regime, statuses=None,
                      label_provenance=None, review_fractions=(0.05, 0.10, 0.20)):
    """Evaluate one class and one method on one common ordered file population.

    ``label_regime`` is required: ``confirmed``, ``source_reported``, or ``proxy``.
    Passing proxy zeros does not establish confirmed negatives. Provenance may
    be one source string or an aligned sequence and is reported as counts. The
    function does not verify any annotation or infer a regime from its values.

    Review budgets use floor(fraction * total files), including failures and
    unknown labels in the denominator. Each budget is independently evaluated;
    failed/unscored files cannot be ranked and leave unused slots if necessary.
    Empty/no-positive ranking populations have undefined AP and PR area (None).
    """
    if label_regime not in LABEL_REGIMES:
        raise ValueError(f"label_regime must be one of {sorted(LABEL_REGIMES)}")
    y, s, status, known, scorable = _inputs(labels, scores, statuses)
    n = len(y)
    positive = known & (y == 1)
    ranked_known = scorable & known
    n_ranked_known = int(ranked_known.sum())
    n_ranked_positive = int((ranked_known & positive).sum())
    ap = pr_area = None
    if n_ranked_positive:
        yy, ss = y[ranked_known].astype(int), s[ranked_known]
        ap = float(average_precision_score(yy, ss))
        precision, recall, _ = precision_recall_curve(yy, ss)
        pr_area = float(auc(recall, precision))
    if label_provenance is None:
        provenance = ["unspecified"] * n
    elif isinstance(label_provenance, str):
        provenance = [label_provenance] * n
    else:
        provenance = list(label_provenance)
        if len(provenance) != n:
            raise ValueError("label_provenance must have one entry per file")
    if any(not isinstance(x, str) or not x.strip() for x in provenance):
        raise ValueError("label provenance entries must be nonempty strings")
    budget_rows = []
    for fraction in review_fractions:
        q = Decimal(str(fraction))
        if not q.is_finite() or not Decimal(0) <= q <= Decimal(1):
            raise ValueError("review fractions must be finite numbers between 0 and 1")
        requested = int((q * n).to_integral_value(rounding=ROUND_FLOOR))
        budget_rows.append({"review_fraction_requested": float(q),
                            **_at_k(y, s, known, scorable, requested)})
    return {
        "schema": "security_workload_metrics_v1",
        "label_regime": label_regime,
        "interpretation": {
            "confirmed": "Metrics relative to supplied confirmed labels; unknowns remain unknown.",
            "source_reported": "Metrics relative to source annotations; no independent confirmation is implied.",
            "proxy": "Agreement with proxy labels, not confirmed vulnerability precision or recall.",
        }[label_regime],
        "label_provenance_counts": dict(sorted(Counter(provenance).items())),
        "status_counts": dict(sorted(Counter(status.tolist()).items())),
        "n_files": n,
        "n_known_labels": int(known.sum()),
        "n_unknown_labels": int((~known).sum()),
        "n_known_positive": int(positive.sum()),
        "n_scorable": int(scorable.sum()),
        "scoring_coverage": _ratio(int(scorable.sum()), n),
        "n_status_ok_without_score": int(((status == "ok") & ~np.isfinite(s)).sum()),
        "n_finite_scores_discarded_for_failure_status": int(((status != "ok") & np.isfinite(s)).sum()),
        "n_unscorable_known_positive": int((positive & ~scorable).sum()),
        "ranking_population": "status_ok_finite_score_and_known_label_only",
        "ranking_n": n_ranked_known,
        "ranking_n_positive": n_ranked_positive,
        "ranking_coverage_of_known_labels": _ratio(n_ranked_known, int(known.sum())),
        "ranking_prevalence": _ratio(n_ranked_positive, n_ranked_known),
        "ranking_ap": ap,
        "ranking_trapezoidal_pr_area": pr_area,
        "review_policy": "rank_scorable_only_no_failure_fallback_uniform_boundary_tie",
        "budget_rounding": "floor_fraction_times_all_input_files",
        "precision_definition": "ratio_of_expected_positive_and_known_review_counts_not_expected_random_ratio",
        "budgets": budget_rows,
    }
