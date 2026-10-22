"""
Evaluation metrics shared by all experiments.

Conventions
-----------
* The positive class (1) is always the anomalous / illicit / vulnerable class.
* Threshold-free metrics (AUPRC, ROC-AUC) are the primary metrics: the base rate
  differs between datasets and periods, so a fixed 0.5 threshold is not a
  meaningful operating point.
* Thresholded metrics are reported at a threshold chosen on validation data
  only (never on test), see `threshold_at_val_f1` and `threshold_at_fpr`.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    precision_recall_curve,
    brier_score_loss,
)


def safe_auc(y, s) -> float:
    y = np.asarray(y)
    if y.min() == y.max():
        return float("nan")
    return float(roc_auc_score(y, s))


def safe_ap(y, s) -> float:
    y = np.asarray(y)
    if y.sum() == 0:
        return float("nan")
    return float(average_precision_score(y, s))


def threshold_at_val_f1(y_val, s_val) -> float:
    """Threshold maximising F1 on validation scores."""
    p, r, t = precision_recall_curve(y_val, s_val)
    f1 = 2 * p * r / np.clip(p + r, 1e-12, None)
    # precision_recall_curve returns len(t) = len(p) - 1
    i = int(np.nanargmax(f1[:-1])) if len(t) else 0
    return float(t[i]) if len(t) else 0.5


def threshold_at_fpr(s_neg, fpr: float) -> float:
    """Threshold such that a fraction `fpr` of reference negatives exceed it."""
    s_neg = np.asarray(s_neg)
    return float(np.quantile(s_neg, 1.0 - fpr))


def expected_calibration_error(y, p, n_bins: int = 15) -> float:
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 0, 1)
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, bins) - 1, 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            ece += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(ece)


@dataclass
class BinaryReport:
    n: int
    n_pos: int
    auprc: float
    roc_auc: float
    f1: float
    precision: float
    recall: float
    threshold: float
    brier: float | None = None
    ece: float | None = None

    def to_dict(self):
        return asdict(self)


def binary_report(y, scores, threshold: float, probabilities: bool = False) -> BinaryReport:
    y = np.asarray(y).astype(int)
    s = np.asarray(scores, dtype=float)
    yhat = (s >= threshold).astype(int)
    rep = BinaryReport(
        n=int(len(y)),
        n_pos=int(y.sum()),
        auprc=safe_ap(y, s),
        roc_auc=safe_auc(y, s),
        f1=float(f1_score(y, yhat, zero_division=0)),
        precision=float(precision_score(y, yhat, zero_division=0)),
        recall=float(recall_score(y, yhat, zero_division=0)),
        threshold=float(threshold),
    )
    if probabilities:
        rep.brier = float(brier_score_loss(y, np.clip(s, 0, 1)))
        rep.ece = expected_calibration_error(y, s)
    return rep


def tie_ranks(scores):
    """Ranks under descending score (1 = top) that do not depend on tie order.

    Returns (mid, lo, hi): the average rank of each tie group and the best and
    worst rank a member of that group could get under any ordering of ties.
    """
    s = -np.asarray(scores, dtype=float)
    srt = np.sort(s)
    lo = np.searchsorted(srt, s, side="left") + 1
    hi = np.searchsorted(srt, s, side="right")
    return (lo + hi) / 2.0, lo, hi
