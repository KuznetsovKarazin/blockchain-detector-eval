"""
T2  Is the post-shutdown collapse on Elliptic a threshold / prior-shift
problem?  (hypothesis HT.3)

Setting
-------
Scores come from an T1 run (scores_labelled.npz: one score vector per
model|features|seed over the labelled nodes, plus y and step). For every test
time step t the illicit prior pi_t is estimated WITHOUT labels from the score
distribution of that step's labelled nodes (their labels are never read), the
calibrated posterior is re-weighted to pi_t, and the validation threshold is
applied to the re-weighted posterior.

Variants
--------
none     validation threshold on the uncorrected score (= T1)
em       Saerens-Latinne-Decaestecker EM prior per step
bbse     black-box shift estimation per step (Lipton et al. 2018)
oracle   true per-step prior (uses labels; NOT a method). With the validation
         F1 threshold kept fixed this is NOT an upper bound on F1: the
         F1-optimal threshold itself depends on the prior, so prior correction
         can fail even under exact label shift (see tests/test_eval.py).

Diagnostics (shift_diagnostics.csv; labels used only to describe the shift)
--------------------------------------------------------------------------
per test step and model:
* roc_auc             prevalence-free ranking quality (AUPRC moves with the prior)
* ks_pos / ks_neg     two-sample KS distance between the score distribution of
                      illicit (licit) nodes in the step and in validation, with
                      p-values; under pure label shift P(score | y) is unchanged,
                      so both should be small up to sampling noise
* f1_step_optimal     F1 at the threshold chosen on that step's own labels: an
                      upper bound for ANY threshold or prior-correction policy
                      applied to this score

Calibration: Platt scaling fitted on validation steps 31-34 only.
The evaluated population is the labelled nodes of each step, as in every
Elliptic paper; using unlabelled nodes to estimate the prior would change the
population, so it is not done here.

Usage
-----
    python scripts/t2_label_shift.py --t1-run results/transactions/<t1 run>
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.metrics import f1_score, precision_recall_curve, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.elliptic import POST_SHUTDOWN, PRE_SHUTDOWN, TEST_STEPS, VAL_STEPS, load_scores  # noqa: E402
from bal.eval.labelshift import adjust_posterior, bbse_prior, em_prior, fit_platt  # noqa: E402
from bal.eval.metrics import threshold_at_val_f1                                   # noqa: E402
from bal.utils.repro import write_manifest                                         # noqa: E402

VARIANTS = ["none", "em", "bbse", "oracle"]


def run_one(s, y, step):
    va = np.isin(step, list(VAL_STEPS))
    s = np.clip(s, 1e-6, 1 - 1e-6) if (s.min() >= 0 and s.max() <= 1) else 1 / (1 + np.exp(-s))
    cal = fit_platt(s[va], y[va])
    p = cal(s)
    pi_s = float(y[va].mean())
    thr_raw = threshold_at_val_f1(y[va], s[va])
    thr = threshold_at_val_f1(y[va], p[va])
    yhat_val = (p[va] >= thr).astype(int)
    preds = {v: np.zeros(len(y), dtype=int) for v in VARIANTS}
    priors = []
    for t in TEST_STEPS:
        m = step == t
        if not m.any():
            continue
        pt = p[m]
        preds["none"][m] = s[m] >= thr_raw
        est = {"em": em_prior(pt, pi_s),
               "bbse": bbse_prior((pt >= thr).astype(int), y[va], yhat_val),
               "oracle": float(np.clip(y[m].mean(), 1e-6, 1 - 1e-6))}
        for v, pi_t in est.items():
            if not np.isfinite(pi_t):
                pi_t = pi_s
            preds[v][m] = adjust_posterior(pt, pi_s, pi_t) >= thr
        priors.append({"step": int(t), "true": float(y[m].mean()), "em": est["em"], "bbse": est["bbse"],
                       "source": pi_s})
    return preds, priors


def best_f1(y, s) -> float:
    if y.sum() == 0:
        return np.nan
    p, r, _ = precision_recall_curve(y, s)
    return float(np.max(2 * p * r / np.clip(p + r, 1e-12, None)))


def diagnostics(key, s, y, step):
    va = np.isin(step, list(VAL_STEPS))
    rows = []
    for t in TEST_STEPS:
        m = step == t
        yt, st = y[m], s[m]
        npos = int(yt.sum())
        r = {"key": key, "step": int(t), "n": int(m.sum()), "n_pos": npos, "prior": float(yt.mean()),
             "roc_auc": float(roc_auc_score(yt, st)) if 0 < npos < len(yt) else np.nan,
             "f1_step_optimal": best_f1(yt, st)}
        for cls, name in [(1, "pos"), (0, "neg")]:
            a, b = s[va & (y == cls)], st[yt == cls]
            if len(b) >= 5:
                k = ks_2samp(a, b)
                r[f"ks_{name}"], r[f"ks_{name}_p"] = float(k.statistic), float(k.pvalue)
                r[f"median_score_{name}"] = float(np.median(b))
            else:
                r[f"ks_{name}"] = r[f"ks_{name}_p"] = r[f"median_score_{name}"] = np.nan
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--t1-run", required=True)
    ap.add_argument("--data", default="data/raw/elliptic", help="labels, if the score file has none")
    ap.add_argument("--out", default="results/transactions")
    a = ap.parse_args()
    src = Path(a.t1_run)
    run = Path(a.out) / (time.strftime("t2_%Y%m%d_%H%M%S") if "smoke" not in src.name else "smoke_t2")
    run.mkdir(parents=True, exist_ok=True)
    Z, y, step = load_scores(src, a.data)
    rows, prior_rows, diag = [], [], []
    for key in Z:
        model, fset, seed = key.split("|")
        preds, priors = run_one(Z[key].astype(float), y, step)
        diag += diagnostics(key, Z[key].astype(float), y, step)
        for v, yh in preds.items():
            for part, steps in [("test", TEST_STEPS), ("pre", PRE_SHUTDOWN), ("post", POST_SHUTDOWN)]:
                m = np.isin(step, list(steps))
                rows.append({"model": model, "features": fset, "seed": int(seed), "variant": v,
                             "part": part, "f1": f1_score(y[m], yh[m], zero_division=0),
                             "precision": float(yh[m][y[m] == 1].sum() / max(1, yh[m].sum())),
                             "recall": float(yh[m][y[m] == 1].mean())})
        for r in priors:
            prior_rows.append({"model": model, "features": fset, "seed": int(seed), **r})
    df = pd.DataFrame(rows)
    df.to_csv(run / "label_shift_metrics.csv", index=False)
    pd.DataFrame(prior_rows).to_csv(run / "estimated_priors.csv", index=False)
    summ = (df.pivot_table(index=["model", "features", "variant"], columns="part", values="f1", aggfunc="mean")
              .round(4))
    summ.to_csv(run / "label_shift_summary.csv")
    D = pd.DataFrame(diag)
    D.to_csv(run / "shift_diagnostics.csv", index=False)
    D["model"] = D.key.str.split("|").str[0] + "|" + D.key.str.split("|").str[1]
    Ds = D.groupby(["model", "step"])[["prior", "n_pos", "roc_auc", "f1_step_optimal", "ks_pos", "ks_neg"]].mean()
    Ds.round(3).to_csv(run / "shift_diagnostics_by_step.csv")
    print(Ds.loc[[k for k in ["rf|AF+NB", "lgbm|AF+NB"] if k in Ds.index.get_level_values(0)]].round(3).to_string())
    print(summ.to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[src / "scores_labelled.npz"], extra={"variants": VARIANTS})
    print("wrote", run)


if __name__ == "__main__":
    main()
