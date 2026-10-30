"""
TV / X2, X4, X6 on Elliptic  Rolling-origin evaluation: which part of the
detector survives the next period, the ranking, the threshold or the monitor?

Cut-offs c in {20, 25, 30, 35, 40}: train steps <= c (A2: only the last 10
steps, c-9..c), validation c+1..c+4, test c+5..c+9 (c = 40: test 45-49).
Features AF+NB (T1 headline set of the trees and the MLP). Models: logistic
regression (1 seed), RF, LightGBM, MLP (5 seeds).

Per test step
-------------
* ranking: AP (sklearn, non-interpolated) on the labelled nodes, base rate;
* thresholds (X4), budget b in {1 %, 5 %} of ALL transactions of the step
  (labelled or not, as an analyst would see them):
    fixed    score quantile 1-b over all validation transactions;
    rolling  score quantile 1-b over all transactions of the 3 previous steps
             (no labels needed);
    topk     the ceil(b * n_step) highest scores of the step;
  achieved alarm share, recall and precision on the labelled nodes;
* monitors (X6, LightGBM seed 0 only): EM prior from Platt-calibrated scores
  (calibrated on validation), mean score, median PSI over features against
  the training steps, domain-classifier ROC-AUC (training vs step).

Hypotheses HV2-HV4 and decision rules: docs/PROTOCOLS_TV.md.

Usage
-----
    python scripts/tv2_rolling_elliptic.py --data data/raw/elliptic --seeds 5
    python scripts/tv2_rolling_elliptic.py --models logreg,rf,lgbm      # without torch
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bal.data.elliptic import load_elliptic                       # noqa: E402
from bal.eval.labelshift import em_prior, fit_platt               # noqa: E402
from bal.models.gnn import neighbour_features                     # noqa: E402
from bal.models.tabular import MODELS                             # noqa: E402
from bal.utils.repro import atomic_to_csv, set_seed, write_manifest   # noqa: E402

_spec = importlib.util.spec_from_file_location("t4", ROOT / "scripts" / "t4_drift_monitor.py")
T4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T4)

CUTOFFS = (20, 25, 30, 35, 40)
BUDGETS = (0.01, 0.05)
WINDOWS = {"all": None, "last10": 10}


def periods(c):
    return (range(1, c + 1), range(c + 1, c + 5), range(c + 5, min(c + 10, 50)))


def thresholds_by_step(s, step, val_steps, test_steps, b):
    """Per test step: (fixed, rolling) thresholds; topk handled separately."""
    fixed = float(np.quantile(s[np.isin(step, list(val_steps))], 1 - b))
    out = {}
    for t in test_steps:
        prev = np.isin(step, [t - 1, t - 2, t - 3])
        out[t] = (fixed, float(np.quantile(s[prev], 1 - b)))
    return out


def alarm_stats(alarm, y, lab):
    pos = lab & (y == 1)
    return {"alarm_share": float(alarm.mean()),
            "recall": float(alarm[pos].mean()) if pos.any() else np.nan,
            "precision_labelled": float(y[alarm & lab].mean()) if (alarm & lab).any() else np.nan}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/elliptic")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--models", default="logreg,rf,lgbm,mlp")
    ap.add_argument("--cutoffs", default=",".join(map(str, CUTOFFS)))
    ap.add_argument("--out", default="results/transactions")
    ap.add_argument("--run", help="existing run folder (adds rows; finished parts are skipped)")
    a = ap.parse_args()
    run = Path(a.run) if a.run else Path(a.out) / time.strftime("tv2_%Y%m%d_%H%M%S")
    (run / "parts").mkdir(parents=True, exist_ok=True)
    d = load_elliptic(a.data)
    X = np.hstack([d.X, neighbour_features(d.X, d.edges)]).astype(np.float32)
    y, step = d.y, d.step
    lab = y >= 0
    cuts = [int(c) for c in a.cutoffs.split(",")]
    for c in cuts:
        tr_steps, va_steps, te_steps = periods(c)
        for wname, w in WINDOWS.items():
            trs = tr_steps if w is None else range(max(1, c - w + 1), c + 1)
            tr = np.isin(step, list(trs)) & lab
            va = np.isin(step, list(va_steps)) & lab
            for mname in a.models.split(","):
                seeds = [0] if mname == "logreg" else list(range(a.seeds))
                for seed in seeds:
                    tag = f"c{c}_{wname}_{mname}_s{seed}"
                    if (run / "parts" / f"{tag}.csv").exists():
                        continue
                    t0 = time.time()
                    set_seed(seed)
                    m = MODELS[mname](seed=seed)
                    m.fit(X[tr], y[tr])
                    s = m.predict_score(X).astype(np.float64)
                    rows = []
                    for t in te_steps:
                        ms = (step == t) & lab
                        rows.append({"cutoff": c, "window": wname, "model": mname, "seed": seed,
                                     "step": t, "kind": "ap", "budget": np.nan, "strategy": "",
                                     "ap": float(average_precision_score(y[ms], s[ms])) if y[ms].sum() else np.nan,
                                     "base_rate": float(y[ms].mean()), "n_labelled": int(ms.sum())})
                    period = np.isin(step, list(te_steps)) & lab
                    rows.append({"cutoff": c, "window": wname, "model": mname, "seed": seed, "step": -1,
                                 "kind": "ap_period", "ap": float(average_precision_score(y[period], s[period])),
                                 "base_rate": float(y[period].mean()), "n_labelled": int(period.sum()),
                                 "val_ap": float(average_precision_score(y[va], s[va]))})
                    for b in BUDGETS:
                        thr = thresholds_by_step(s, step, va_steps, te_steps, b)
                        for t in te_steps:
                            mall = step == t
                            k = math.ceil(b * mall.sum())
                            top = np.zeros(mall.sum(), bool)
                            top[np.argsort(-s[mall], kind="stable")[:k]] = True
                            alarms = {"fixed": s[mall] >= thr[t][0], "rolling": s[mall] >= thr[t][1], "topk": top}
                            for sname, al in alarms.items():
                                rows.append({"cutoff": c, "window": wname, "model": mname, "seed": seed,
                                             "step": t, "kind": "alarm", "budget": b, "strategy": sname,
                                             **alarm_stats(al, y[mall], lab[mall])})
                    if mname == "lgbm" and seed == 0 and wname == "all":
                        cal = fit_platt(np.clip(s[va], 1e-6, 1 - 1e-6), y[va])
                        p = cal(np.clip(s, 1e-6, 1 - 1e-6))
                        pi_s = float(y[va].mean())
                        trall = np.isin(step, list(tr_steps))
                        for t in te_steps:
                            mall, ms = step == t, (step == t) & lab
                            rows.append({"cutoff": c, "window": wname, "model": mname, "seed": seed, "step": t,
                                         "kind": "monitor", "em_prior": em_prior(p[ms], pi_s),
                                         "mean_score": float(s[mall].mean()),
                                         "psi_median": float(np.median([T4.psi(d.X[trall, j], d.X[mall, j])
                                                                        for j in range(d.X.shape[1])])),
                                         "domain_auc": T4.domain_auc(d.X[trall], d.X[mall], seed=0),
                                         "true_prior": float(y[ms].mean())})
                    atomic_to_csv(pd.DataFrame(rows), run / "parts" / f"{tag}.csv", index=False)
                    print(tag, "period AP", round(rows[len(te_steps)]["ap"], 4),
                          round(time.time() - t0), "s", flush=True)
    df = pd.concat([pd.read_csv(p) for p in sorted((run / "parts").glob("*.csv"))], ignore_index=True)
    atomic_to_csv(df, run / "rolling_long.csv", index=False)
    per = df[df.kind == "ap_period"].groupby(["cutoff", "window", "model"])[["ap", "val_ap", "base_rate"]].agg(
        ["mean", "std"]).round(4)
    per.to_csv(run / "ap_by_cutoff.csv")
    print(per.to_string())
    al = df[df.kind == "alarm"].groupby(["cutoff", "window", "model", "budget", "strategy"])[
        ["alarm_share", "recall", "precision_labelled"]].mean().round(4)
    al.to_csv(run / "alarms_by_cutoff.csv")
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(a.data) / f"elliptic_txs_{f}.csv" for f in ("features", "classes", "edgelist")],
                   extra={"cutoffs": cuts, "budgets": BUDGETS, "windows": WINDOWS})
    print("wrote", run)


if __name__ == "__main__":
    main()
