"""
TV round 2 / X6b  The label-shift estimate on Elliptic: population, positive
control and its assumption (docs/PROTOCOLS_TV.md, "Round 2").

(a) EM estimate of the illicit share per test step on all transactions of the
    step and on the labelled ones (LightGBM seed 0, window all, Platt on the
    validation steps; as in tv2_rolling_elliptic.py).
(b) Positive control, cut-offs 25 and 30: the labelled transactions of each
    test step are resampled to an illicit share of 1, 2, 5, 10, 20 %
    (p(x|y) unchanged; 50 draws per step and share); absolute error of EM.
(c) Assumption check: LightGBM, 5-fold, separates illicit 35-42 from illicit
    43-49; controls licit 35-42 vs 43-49 and illicit 35-38 vs 39-42.

    python scripts/tv8_monitors_elliptic.py --data data/raw/elliptic
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bal.data.elliptic import load_elliptic                       # noqa: E402
from bal.eval.labelshift import em_prior, fit_platt               # noqa: E402
from bal.models.gnn import neighbour_features                     # noqa: E402
from bal.models.tabular import MODELS                             # noqa: E402
from bal.utils.repro import atomic_to_csv, dump_json, set_seed, write_manifest   # noqa: E402

_spec = importlib.util.spec_from_file_location("tv2", ROOT / "scripts" / "tv2_rolling_elliptic.py")
TV2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TV2)

SHARES = (0.01, 0.02, 0.05, 0.10, 0.20)
CONTROL_CUTS = (25, 30)


def domain_auc(Xa, Xb, seed=0, cap=5000):
    rng = np.random.default_rng(seed)
    if len(Xa) > cap:
        Xa = Xa[rng.choice(len(Xa), cap, replace=False)]
    if len(Xb) > cap:
        Xb = Xb[rng.choice(len(Xb), cap, replace=False)]
    X = np.vstack([Xa, Xb])
    z = np.r_[np.zeros(len(Xa)), np.ones(len(Xb))].astype(int)
    s = np.zeros(len(z))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(X, z):
        m = MODELS["lgbm"](seed=seed)
        m.fit(X[tr], z[tr])
        s[te] = m.predict_score(X[te])
    return float(roc_auc_score(z, s)), int(len(Xa)), int(len(Xb))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/elliptic")
    ap.add_argument("--draws", type=int, default=50)
    ap.add_argument("--out", default="results/transactions")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("tv8_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    d = load_elliptic(a.data)
    X = np.hstack([d.X, neighbour_features(d.X, d.edges)]).astype(np.float32)
    y, step = d.y, d.step
    lab = y >= 0
    rng = np.random.default_rng(0)
    em_rows, ctl_rows = [], []
    for c in TV2.CUTOFFS:
        tr_steps, va_steps, te_steps = TV2.periods(c)
        tr = np.isin(step, list(tr_steps)) & lab
        va = np.isin(step, list(va_steps)) & lab
        set_seed(0)
        m = MODELS["lgbm"](seed=0)
        m.fit(X[tr], y[tr])
        s = m.predict_score(X).astype(np.float64)
        cal = fit_platt(np.clip(s[va], 1e-6, 1 - 1e-6), y[va])
        p = cal(np.clip(s, 1e-6, 1 - 1e-6))
        pi_s = float(y[va].mean())
        for t in te_steps:
            mall, ms = step == t, (step == t) & lab
            em_rows.append({"cutoff": c, "step": t, "em_all": em_prior(p[mall], pi_s),
                            "em_labelled": em_prior(p[ms], pi_s), "true_share_labelled": float(y[ms].mean()),
                            "labelled_fraction": float(ms.sum() / mall.sum()),
                            "mean_p_all": float(p[mall].mean()), "mean_p_labelled": float(p[ms].mean())})
            if c not in CONTROL_CUTS:
                continue
            pos, neg = np.flatnonzero(ms & (y == 1)), np.flatnonzero(ms & (y == 0))
            n = int(ms.sum())
            for sh in SHARES:
                k = max(1, int(round(sh * n)))
                for r in range(a.draws):
                    idx = np.r_[rng.choice(pos, k, replace=True), rng.choice(neg, n - k, replace=True)]
                    est = em_prior(p[idx], pi_s)
                    ctl_rows.append({"cutoff": c, "step": t, "target": k / n, "draw": r, "em": est,
                                     "abs_err": abs(est - k / n)})
        print("cut-off", c, "done", flush=True)
    em = pd.DataFrame(em_rows)
    ctl = pd.DataFrame(ctl_rows)
    atomic_to_csv(em, run / "em_population.csv", index=False)
    atomic_to_csv(ctl, run / "em_positive_control.csv", index=False)
    ctl["share"] = pd.cut(ctl.target, [0, .015, .03, .07, .15, .3], labels=[str(x) for x in SHARES])
    g = ctl.groupby("share", observed=True)
    ctl_sum = g.agg(median_abs_err=("abs_err", "median"), median_em=("em", "median")).reset_index()
    ctl_sum["share"] = ctl_sum["share"].astype(float)
    ctl_sum["works"] = ctl_sum.median_abs_err <= 0.25 * ctl_sum.share
    atomic_to_csv(ctl_sum, run / "em_positive_control_summary.csv", index=False)

    ill, lic = lab & (y == 1), lab & (y == 0)
    pre, post = np.isin(step, range(35, 43)), np.isin(step, range(43, 50))
    early, late = np.isin(step, range(35, 39)), np.isin(step, range(39, 43))
    shift = {}
    for name, (A, B) in {"illicit_35-42_vs_43-49": (ill & pre, ill & post),
                         "licit_35-42_vs_43-49": (lic & pre, lic & post),
                         "illicit_35-38_vs_39-42": (ill & early, ill & late)}.items():
        auc, na, nb = domain_auc(d.X[A], d.X[B])
        shift[name] = {"auc": round(auc, 4), "n_a": na, "n_b": nb}
    shift["px_given_y_shifted"] = bool(shift["illicit_35-42_vs_43-49"]["auc"]
                                       >= shift["illicit_35-38_vs_39-42"]["auc"] + 0.15)
    summary = {"em_population": em.round(4).to_dict("records"),
               "positive_control": ctl_sum.round(4).to_dict("records"),
               "positive_control_works_all_shares": bool(ctl_sum.works.all()),
               "assumption_check": shift}
    dump_json(summary, run / "summary.json")
    print(em.round(4).to_string())
    print(ctl_sum.round(4).to_string())
    print(shift)
    write_manifest(run, script=Path(__file__).name, config=vars(a), data_files=[])
    print("wrote", run)


if __name__ == "__main__":
    main()
