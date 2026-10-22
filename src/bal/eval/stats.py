"""
Statistical summaries: multi-seed aggregation, bootstrap CIs, paired tests.

A difference between two models is reported as "supported" only if the paired
bootstrap 95% CI of the difference excludes zero. Seeds are paired by index.
"""

from __future__ import annotations

import numpy as np


def mean_ci(values, alpha: float = 0.05, n_boot: int = 5000, seed: int = 0):
    v = np.asarray([x for x in values if np.isfinite(x)], dtype=float)
    if len(v) == 0:
        return float("nan"), float("nan"), float("nan")
    if len(v) == 1:
        return float(v[0]), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    boots = rng.choice(v, size=(n_boot, len(v)), replace=True).mean(axis=1)
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    return float(v.mean()), float(lo), float(hi)


def paired_diff_ci(a, b, alpha: float = 0.05, n_boot: int = 5000, seed: int = 0):
    """CI for mean(a - b) over paired runs (e.g. same seeds)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = a - b
    d = d[np.isfinite(d)]
    return mean_ci(d, alpha=alpha, n_boot=n_boot, seed=seed)


def bootstrap_metric(y, s, metric, n_boot: int = 1000, seed: int = 0, alpha: float = 0.05):
    """Sample-level bootstrap CI of a metric(y, s) on a single test set."""
    y = np.asarray(y)
    s = np.asarray(s)
    rng = np.random.default_rng(seed)
    n = len(y)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if y[idx].min() == y[idx].max():
            continue
        vals.append(metric(y[idx], s[idx]))
    vals = np.asarray(vals)
    return float(metric(y, s)), float(np.quantile(vals, alpha / 2)), float(np.quantile(vals, 1 - alpha / 2))
