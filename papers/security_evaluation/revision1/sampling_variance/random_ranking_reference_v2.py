"""Version 2: decimal-safe workload budgets for descriptive random rankings.

This general-use revision was added after the completed historical experiment.
The experiment keeps its original helper, tests and executed snapshots unchanged.
For its N=1082 and fractions .05/.10/.20 both versions give 54/108/216.
No inferential p-values are computed.

For N fixed objects, K positive proxy labels and a uniformly random strict
ordering, AP = (1/K) * sum_i I_i * C_i / i. Here I_i indicates that rank i is
positive and C_i counts positives through i. Since

    E[I_i] = K/N,
    E[I_i * sum_{j<i} I_j] = (i-1)*K*(K-1)/(N*(N-1)),

E[AP] = H_N/N + (K-1)*(N-H_N)/(N*(N-1)) for N>1, K>0.
For N=K=1 it is 1; with K=0 AP is undefined, not zero.

The reference randomizes positions of positive labels; it has no fitted model,
observed score or observed AP input. Quantiles describe this stipulated random
ranking distribution. They are NOT confidence intervals for detector quality,
project generalization, or a causal leakage effect. A fixed test consisting of
one dependency component does not justify file-wise exchangeability for those
inferential questions. Workload budgets use floor(q*N), with complete scoring
and known binary proxy targets assumed; this helper cannot handle tool failures
or unknown labels and must not replace the main workload evaluator.
"""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_FLOOR
from numbers import Integral, Real
from typing import Iterable

import numpy as np


def _integer(name: str, value: int, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _population(n: int, k: int) -> tuple[int, int]:
    n, k = _integer("n", n, 1), _integer("k", k, 0)
    if k > n:
        raise ValueError("k must not exceed n")
    return n, k


def expected_ap_uniform_ranking(n: int, k: int) -> float | None:
    """Exact finite-population mean, evaluated in floating-point arithmetic."""
    n, k = _population(n, k)
    if k == 0:
        return None
    if k == n:
        return 1.0
    harmonic = math.fsum(1.0 / i for i in range(1, n + 1))
    return harmonic / n + (k - 1) * (n - harmonic) / (n * (n - 1))


def _summary(values: np.ndarray) -> dict:
    q = np.quantile(values, [0.025, 0.5, 0.975], method="linear")
    return {
        "mean": float(np.mean(values)),
        "sd": float(np.std(values, ddof=1)) if len(values) > 1 else None,
        "minimum": float(np.min(values)),
        "q025": float(q[0]),
        "median": float(q[1]),
        "q975": float(q[2]),
        "maximum": float(np.max(values)),
        "quantile_interpretation": "descriptive random-ranking quantiles; not a confidence interval",
    }


def random_ranking_reference(
    n: int,
    k: int,
    n_draws: int = 10000,
    seed: int = 20261025,
    review_fractions: Iterable[float] = (0.05, 0.10, 0.20),
    include_draws: bool = True,
) -> dict:
    """Return a JSON-friendly descriptive reference under uniform strict ranks.

    Each draw uniformly samples K distinct positive positions from 1,...,N.
    This is equivalent to permuting a fixed binary label vector, without
    materializing N! object orderings. The generator and seed are recorded.
    No tests of an observed method, empirical p-values, or significance claims
    are produced. Freeze n/k, draw count and seed before calling in an analysis.
    """
    n, k = _population(n, k)
    n_draws, seed = _integer("n_draws", n_draws, 1), _integer("seed", seed, 0)
    if not isinstance(include_draws, bool):
        raise ValueError("include_draws must be boolean")
    fractions = tuple(review_fractions)
    if any(isinstance(q, bool) or not isinstance(q, Real) or not math.isfinite(q) or not 0 <= q <= 1
           for q in fractions):
        raise ValueError("review fractions must be finite numbers in [0,1]")
    fractions = tuple(float(q) for q in fractions)
    if len(set(fractions)) != len(fractions):
        raise ValueError("review fractions must be unique")
    budgets = np.asarray([int((Decimal(str(q)) * n).to_integral_value(rounding=ROUND_FLOOR)) for q in fractions], dtype=np.int64)
    rng = np.random.default_rng(seed)
    aps = np.empty(n_draws, dtype=np.float64) if k else None
    workload = np.zeros((n_draws, len(budgets)), dtype=np.int64)
    positive_index = np.arange(1, k + 1, dtype=np.float64)
    for draw in range(n_draws):
        positions = np.sort(rng.choice(n, size=k, replace=False)) + 1
        if k:
            aps[draw] = float(np.mean(positive_index / positions))
        workload[draw] = np.searchsorted(positions, budgets, side="right")
    result = {
        "schema": "descriptive_uniform_random_ranking_v2",
        "n_files": n,
        "positive_proxy_count": k,
        "prevalence_proxy": k / n,
        "exact_ap_mean": expected_ap_uniform_ranking(n, k),
        "ap_defined": k > 0,
        "n_draws": n_draws,
        "seed": seed,
        "generator": type(rng.bit_generator).__name__,
        "numpy_version": np.__version__,
        "ranking_rule": "uniform strict ordering; no ties",
        "budget_rule": "floor(Decimal(str(float(fraction))) * n_files)",
        "scoring_assumption": "all files scored; all labels known binary proxies",
        "inferential_p_values_computed": False,
        "observed_model_scores_used": False,
        "ap_summary": _summary(aps) if k else None,
        "workload": [],
        "limitations": [
            "Conditional descriptive random-ranking reference, not a fitted baseline",
            "No exchangeability claim for dependent source files",
            "Quantiles are not confidence intervals for model or project performance",
            "Proxy-label agreement is not adjudicated vulnerability accuracy",
        ],
    }
    for j, (fraction, budget) in enumerate(zip(fractions, budgets)):
        counts = workload[:, j]
        row = {
            "review_fraction": fraction,
            "review_count": int(budget),
            "expected_positive_yield_exact": float(int(budget) * k / n),
            "positive_yield_summary": _summary(counts),
            "proxy_recall_summary": _summary(counts / k) if k else None,
            "proxy_precision_summary": _summary(counts / budget) if budget else None,
        }
        if include_draws:
            row["positive_yield_draws"] = counts.tolist()
        result["workload"].append(row)
    if include_draws:
        result["ap_draws"] = aps.tolist() if k else None
    return result
