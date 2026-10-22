"""
T4  Can a label-free monitor tell that the Elliptic model has stopped working?
(follows from T2)

Motivation
----------
T2 showed that after the dark-market shutdown (step 43) the model's
ranking collapses (AUPRC ~ base rate), and that in steps 48-49 the illicit
share returns to 8-12 % while every label-free prior estimate (EM, BBSE) stays
near 0: an output monitor reports "no illicit activity" exactly when the model
is blind. Here we ask whether monitoring the INPUTS would have raised a flag.

Monitors (all computed per test step, no labels)
------------------------------------------------
* em_prior          EM prior estimate from the model's scores (output monitor; from T2 logic)
* domain_auc        ROC-AUC of a classifier separating training-step nodes (1-30)
                    from step-t nodes (3-fold CV, LightGBM); 0.5 = no drift
* domain_auc_labelled   same, restricted to labelled nodes of step t vs labelled training nodes
* psi_median        median over features of the population stability index vs training

Ground truth to compare against (labels used ONLY to evaluate the monitors):
per-step AUPRC / F1 of the T1 RF (AF+NB, seed 0) and the true illicit share.

Usage
-----
    python scripts/t4_drift_monitor.py --t1-run results/transactions/<t1 run>
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.elliptic import TEST_STEPS, TRAIN_STEPS, VAL_STEPS, load_elliptic, load_scores  # noqa: E402
from bal.eval.labelshift import em_prior, fit_platt                             # noqa: E402
from bal.utils.repro import write_manifest                                      # noqa: E402


def psi(ref, cur, bins=10):
    q = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(q) < 3:
        return 0.0
    a = np.histogram(np.clip(ref, q[0], q[-1]), q)[0] / len(ref) + 1e-4
    b = np.histogram(np.clip(cur, q[0], q[-1]), q)[0] / len(cur) + 1e-4
    return float(((b - a) * np.log(b / a)).sum())


def domain_auc(Xa, Xb, seed=0, max_ref=8000):
    import lightgbm as lgb
    rng = np.random.default_rng(seed)
    if len(Xa) > max_ref:
        Xa = Xa[rng.choice(len(Xa), max_ref, replace=False)]
    X = np.vstack([Xa, Xb])
    y = np.r_[np.zeros(len(Xa)), np.ones(len(Xb))]
    s = np.zeros(len(y))
    for tr, te in StratifiedKFold(3, shuffle=True, random_state=seed).split(X, y):
        m = lgb.LGBMClassifier(n_estimators=200, num_leaves=31, learning_rate=0.05, verbose=-1,
                               n_jobs=2, random_state=seed).fit(X[tr], y[tr])
        s[te] = m.predict_proba(X[te])[:, 1]
    return float(roc_auc_score(y, s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/elliptic")
    ap.add_argument("--t1-run", required=True)
    ap.add_argument("--model-key", default="rf|AF+NB|0")
    ap.add_argument("--out", default="results/transactions")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("t4_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    d = load_elliptic(a.data)
    X = d.features("AF")
    Z, y, step = load_scores(a.t1_run, a.data)
    s = Z[a.model_key].astype(float)
    va = np.isin(step, list(VAL_STEPS))
    cal = fit_platt(np.clip(s[va], 1e-6, 1 - 1e-6), y[va])
    p = cal(np.clip(s, 1e-6, 1 - 1e-6))
    pi_s = float(y[va].mean())

    tr_all = np.isin(d.step, list(TRAIN_STEPS))
    tr_lab = tr_all & (d.y >= 0)
    rows = []
    for t in TEST_STEPS:
        m_all = d.step == t
        m_lab = m_all & (d.y >= 0)
        ms = step == t
        rows.append({
            "step": int(t),
            "true_prior": float(y[ms].mean()),
            "model_auprc": float(average_precision_score(y[ms], s[ms])) if y[ms].sum() else np.nan,
            "em_prior": em_prior(p[ms], pi_s),
            "domain_auc": domain_auc(X[tr_all], X[m_all], seed=0),
            "domain_auc_labelled": domain_auc(X[tr_lab], X[m_lab], seed=0),
            "psi_median": float(np.median([psi(X[tr_all, j], X[m_all, j]) for j in range(X.shape[1])])),
        })
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(run / "drift_by_step.csv", index=False)
    corr = {c: float(spearmanr(df[c], df.model_auprc, nan_policy="omit")[0])
            for c in ["em_prior", "domain_auc", "domain_auc_labelled", "psi_median"]}
    pd.Series(corr).to_csv(run / "monitor_vs_auprc_spearman.csv")
    print(df.round(3).to_string())
    print(corr)
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(a.t1_run) / "scores_labelled.npz"]
                   + [Path(a.data) / f"elliptic_txs_{f}.csv" for f in ("features", "classes", "edgelist")])
    print("wrote", run)


if __name__ == "__main__":
    main()
