"""The day bootstrap of K4 weights a day drawn k times by k instead of copying
its rows; the resampled AP must equal sklearn's AP of the concatenated rows."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

_p = Path(__file__).resolve().parents[1] / "scripts" / "k4_defi_kan.py"
_spec = importlib.util.spec_from_file_location("k4", _p)
k4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(k4)


def _direct(df, ss, n, weighted):
    rng = np.random.default_rng(0)
    days = df.day.unique()
    idx = {d: np.flatnonzero(df.day.to_numpy() == d) for d in days}
    y, w = df.y.to_numpy(), df.weight.to_numpy()
    vals = []
    for _ in range(n):
        ii = np.concatenate([idx[d] for d in rng.choice(days, len(days))])
        vals.append(np.mean([average_precision_score(y[ii], s[ii], sample_weight=w[ii] if weighted else None)
                             if y[ii].sum() else np.nan for s in ss]))
    return [float(np.nanpercentile(vals, 5)), float(np.nanpercentile(vals, 95))]


def test_boot_ci_matches_concatenated_resample():
    rng = np.random.default_rng(1)
    n = 3000
    df = pd.DataFrame({"day": rng.choice([f"2025-01-{d:02d}" for d in range(1, 9)], n),
                       "y": (rng.random(n) < 0.01).astype(int),
                       "weight": rng.choice([1.0, 7.5, 40.0], n)})
    # ties on purpose: rounded scores
    ss = [np.round(rng.random(n) + df.y.to_numpy() * rng.random(), 2) for _ in range(3)]
    for weighted in (False, True):
        a = k4.boot_ci(df, ss, n=200, weighted=weighted)
        b = _direct(df, ss, 200, weighted)
        assert np.allclose(a, b, rtol=0, atol=1e-12), (weighted, a, b)
