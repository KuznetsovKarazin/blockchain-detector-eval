"""
K1  Kolmogorov-Arnold Networks for blockchain security: accuracy at matched
size, interpretability, behaviour under temporal shift, and LUT deployment
(uses the Elliptic protocol of T1).

Research questions and hypotheses
---------------------------------
RQK.1  Accuracy at matched parameter count.
        HK.1  Under the temporal protocol a KAN is not more accurate than an
               MLP with the same number of parameters; neither reaches RF
               (T1).  Reported: test / pre / post F1 and AUPRC, 3 seeds.
RQK.2  Do KAN input relevances agree with model-agnostic importances?
        HK.2  The spline-range relevance of the first layer ranks features
               similarly to the KAN's own permutation importance (Spearman >
               0.5), i.e. it is a faithful explanation of THIS model; its
               agreement with RF impurity importance is lower.
RQK.3  Shift diagnostic.
        HK.3  The share of inputs that fall outside the training range (and
               are clipped before reaching the splines) rises after the
               dark-market shutdown, and steps with more clipping have lower
               F1 for all neural models (negative Spearman across steps).
RQK.4  LUT deployment.
        HK.4  With >= 8 points per knot interval the LUT model reproduces the
               float model's decisions (> 99.9% agreement at the validation
               threshold) and runs faster than float PyTorch at batch size 1.

Protocol: train steps 1-30, validation 31-34 (threshold = max F1), test 35-49.
Matched size: MLP with one hidden layer of width h = round((P_kan - 1)/(d + 2)).

Usage
-----
    python scripts/k1_kan_analysis.py --data data/raw/elliptic --seeds 3
    python scripts/k1_kan_analysis.py --synthetic --seeds 1        # smoke test
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import f1_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.elliptic import (POST_SHUTDOWN, PRE_SHUTDOWN, TEST_STEPS, TRAIN_STEPS,  # noqa: E402
                               VAL_STEPS, load_elliptic, make_synthetic)
from bal.eval.metrics import binary_report, safe_ap, threshold_at_val_f1          # noqa: E402
from bal.models.kan import kan_param_count                                        # noqa: E402
from bal.models.tabular import TorchClassifier, random_forest                     # noqa: E402
from bal.utils.repro import dump_json, set_seed, write_manifest                   # noqa: E402

KAN_CONFIGS = [((4,), 3), ((8,), 5), ((16,), 5), ((8,), 8)]
PPI = [2, 4, 8, 16, 32]


def scores_report(y, s, step, thr):
    out = {}
    for part, steps in [("test", TEST_STEPS), ("pre", PRE_SHUTDOWN), ("post", POST_SHUTDOWN)]:
        m = np.isin(step, list(steps))
        r = binary_report(y[m], s[m], thr)
        out[f"{part}_f1"], out[f"{part}_auprc"] = r.f1, r.auprc
    return out


def per_step_f1(y, s, step, thr):
    return {int(t): f1_score(y[step == t], (s[step == t] >= thr).astype(int), zero_division=0)
            for t in TEST_STEPS if (step == t).any()}


def clipped_fraction(model: TorchClassifier, X, step):
    model._prep(X)
    over = np.abs(model._raw_z) > model.clip
    return {int(t): float(over[step == t].mean()) for t in np.unique(step)}


def permutation_importance(model, X, y, n_rep=3, seed=0):
    rng = np.random.default_rng(seed)
    base = safe_ap(y, model.predict_score(X))
    imp = np.zeros(X.shape[1])
    for j in range(X.shape[1]):
        drops = []
        for _ in range(n_rep):
            Xp = X.copy()
            Xp[:, j] = Xp[rng.permutation(len(Xp)), j]
            drops.append(base - safe_ap(y, model.predict_score(Xp)))
        imp[j] = np.mean(drops)
    return imp


def latency(fn, x, reps=200):
    fn(x)
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn(x)
        ts.append(time.perf_counter() - t0)
    return float(np.median(ts) * 1e6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/elliptic")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--out", default="results/kan")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--prep", default="robust", choices=["robust", "quantile"],
                    help="input normalisation for both KAN and MLP (HT.5 / T3)")
    ap.add_argument("--perm-features", type=int, default=40,
                    help="permutation importance on the top-N features by KAN relevance + RF importance")
    a = ap.parse_args()
    run = Path(a.out) / ("smoke" if a.synthetic else time.strftime(f"k1_{a.prep}_%Y%m%d_%H%M%S"))
    run.mkdir(parents=True, exist_ok=True)
    d = make_synthetic() if a.synthetic else load_elliptic(a.data)
    X, y, step = d.features("AF"), d.y, d.step
    tr, va = d.mask(TRAIN_STEPS), d.mask(VAL_STEPS)
    lab = y >= 0
    dim = X.shape[1]

    # ---- RQK.1 matched-size accuracy -------------------------------------
    rows, steprows, keep = [], [], {}
    for hidden, grid in KAN_CONFIGS:
        P = kan_param_count([dim, *hidden, 1], grid)
        h_mlp = max(1, round((P - 1) / (dim + 2)))
        for kind, kw in [("kan", dict(hidden=hidden, grid=grid)), ("mlp", dict(hidden=(h_mlp,)))]:
            for seed in range(a.seeds):
                set_seed(seed)
                m = TorchClassifier(kind, seed=seed, prep=a.prep, **kw).fit(X[tr], y[tr])
                s = m.predict_score(X)
                thr = threshold_at_val_f1(y[va], s[va])
                cfg = f"kan{hidden[0]}g{grid}"
                rows.append({"config": cfg, "model": kind, "seed": seed, "params": m.n_params(),
                             "epochs": m.epochs_run, "threshold": thr,
                             **scores_report(y[lab], s[lab], step[lab], thr)})
                for t, f in per_step_f1(y[lab], s[lab], step[lab], thr).items():
                    steprows.append({"config": cfg, "model": kind, "seed": seed, "step": t, "f1": f})
                if cfg == "kan8g5" and seed == 0:
                    keep[kind] = (m, s, thr)
                print(f"{cfg} {kind} seed={seed} params={m.n_params()} "
                      f"test F1={rows[-1]['test_f1']:.3f} post={rows[-1]['post_f1']:.3f}", flush=True)
    rf = random_forest(seed=0).fit(X[tr], y[tr])
    s_rf = rf.predict_score(X)
    thr_rf = threshold_at_val_f1(y[va], s_rf[va])
    rows.append({"config": "rf", "model": "rf", "seed": 0, "params": np.nan, "epochs": np.nan,
                 "threshold": thr_rf, **scores_report(y[lab], s_rf[lab], step[lab], thr_rf)})
    for t, f in per_step_f1(y[lab], s_rf[lab], step[lab], thr_rf).items():
        steprows.append({"config": "rf", "model": "rf", "seed": 0, "step": t, "f1": f})
    acc = pd.DataFrame(rows)
    acc.to_csv(run / "matched_accuracy.csv", index=False)
    pd.DataFrame(steprows).to_csv(run / "per_step_f1.csv", index=False)

    # ---- RQK.2 interpretability ------------------------------------------
    kan_m, s_kan, thr_kan = keep["kan"]
    rel = kan_m.net.input_relevance()
    rf_imp = rf.est.feature_importances_
    cand = np.unique(np.r_[np.argsort(-rel)[:a.perm_features // 2], np.argsort(-rf_imp)[:a.perm_features // 2]])
    perm_full = np.full(dim, np.nan)
    vlab = va
    Xv = X[vlab]
    for j, v in zip(cand, permutation_importance(_Subset(kan_m, cand, Xv), Xv[:, cand], y[vlab])):
        perm_full[j] = v
    imp = pd.DataFrame({"feature": d.feature_names, "kan_relevance": rel, "rf_importance": rf_imp,
                        "kan_permutation": perm_full})
    imp.to_csv(run / "importances.csv", index=False)
    sub = imp.dropna()

    def top_overlap(a_, b_, k=10):
        return len(set(np.argsort(-a_)[:k]) & set(np.argsort(-b_)[:k])) / k
    interp = {"spearman_rel_vs_perm_on_candidates": float(spearmanr(sub.kan_relevance, sub.kan_permutation)[0]),
              "spearman_rel_vs_rf_all": float(spearmanr(rel, rf_imp)[0]),
              "spearman_perm_vs_rf_on_candidates": float(spearmanr(sub.kan_permutation, sub.rf_importance)[0]),
              "top10_overlap_rel_rf": top_overlap(rel, rf_imp),
              "top10_overlap_rel_perm_candidates": top_overlap(sub.kan_relevance.to_numpy(), sub.kan_permutation.to_numpy()),
              "n_candidates": int(len(cand))}
    xs, phi = kan_m.net.edge_functions(0)
    top = np.argsort(-rel)[:6]
    ef = pd.DataFrame({"x": xs, **{d.feature_names[j]: phi[:, j, :].sum(axis=0) for j in top}})
    ef.to_csv(run / "edge_functions_top6.csv", index=False)

    # ---- RQK.3 shift diagnostic ------------------------------------------
    cf = clipped_fraction(kan_m, X, step)
    ps = pd.DataFrame(steprows)
    shift = []
    for (cfg, model), g in ps[ps.seed == 0].groupby(["config", "model"]):
        f = g.set_index("step").f1
        c = pd.Series({t: cf[t] for t in f.index})
        shift.append({"config": cfg, "model": model, "spearman_clip_vs_f1": float(spearmanr(c, f)[0])})
    clip_df = pd.DataFrame({"step": list(cf), "clipped_fraction": list(cf.values())})
    clip_df.to_csv(run / "clipped_fraction_by_step.csv", index=False)
    pd.DataFrame(shift).to_csv(run / "shift_correlation.csv", index=False)
    pre_c = np.mean([cf[t] for t in PRE_SHUTDOWN if t in cf])
    post_c = np.mean([cf[t] for t in POST_SHUTDOWN if t in cf])
    train_c = np.mean([cf[t] for t in TRAIN_STEPS if t in cf])

    # ---- RQK.4 LUT deployment ---------------------------------------------
    import torch
    Zte = kan_m._prep(X[lab])
    with torch.no_grad():
        logit_f = kan_m.net(torch.tensor(Zte)).squeeze(-1).numpy()
    dec_f = 1 / (1 + np.exp(-logit_f)) >= thr_kan
    lut_rows = []
    torch.set_num_threads(1)
    x1 = torch.tensor(Zte[:1])
    xb = torch.tensor(Zte[:1024])
    t_float1 = latency(lambda z: kan_m.net(z), x1)
    t_floatb = latency(lambda z: kan_m.net(z), xb, reps=30)
    for ppi in PPI:
        L = kan_m.net.to_lut(ppi)
        lg = L.forward(Zte).squeeze(-1)
        dec = 1 / (1 + np.exp(-lg)) >= thr_kan
        lut_rows.append({"ppi": ppi, "bytes": L.nbytes(), "max_abs_logit_err": float(np.abs(lg - logit_f).max()),
                         "decision_agreement": float((dec == dec_f).mean()),
                         "test_auprc_lut": safe_ap(y[lab][np.isin(step[lab], list(TEST_STEPS))],
                                                   lg[np.isin(step[lab], list(TEST_STEPS))]),
                         "latency_us_b1": latency(L.forward, Zte[:1]),
                         "latency_us_b1024": latency(L.forward, Zte[:1024], reps=30)})
    lut = pd.DataFrame(lut_rows)
    lut["float_latency_us_b1"] = t_float1
    lut["float_latency_us_b1024"] = t_floatb
    lut["float_bytes"] = sum(p.numel() * 4 for p in kan_m.net.parameters())
    lut.to_csv(run / "lut.csv", index=False)

    summ = acc.groupby(["config", "model"])[["params", "test_f1", "pre_f1", "post_f1", "test_auprc"]].agg(["mean", "std"]).round(4)
    summ.to_csv(run / "matched_accuracy_summary.csv")
    summary = {"interpretability": interp,
               "clipped_fraction": {"train": train_c, "pre": pre_c, "post": post_c},
               "shift_correlation": shift}
    dump_json(summary, run / "summary.json")
    print(summ.to_string())
    print(summary)
    print(lut.to_string())
    _figures(run, ef, clip_df, ps)
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[] if a.synthetic else [Path(a.data) / f for f in
                               ("elliptic_txs_features.csv", "elliptic_txs_classes.csv", "elliptic_txs_edgelist.csv")],
                   extra={"kan_configs": [list(h) + [g] for h, g in KAN_CONFIGS], "ppi": PPI})
    print("wrote", run)


class _Subset:
    """Model wrapper that only lets the candidate columns vary (others fixed at their values)."""

    def __init__(self, model, cols, X_full):
        self.model, self.cols, self.X_full = model, cols, X_full

    def predict_score(self, Xc):
        X = self.X_full.copy()
        X[:, self.cols] = Xc
        return self.model.predict_score(X)


def _figures(run, ef, clip_df, ps):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    for c in ef.columns[1:]:
        ax[0].plot(ef.x, ef[c], label=c)
    ax[0].set_xlabel("scaled input")
    ax[0].set_ylabel(r"$\sum_j \phi_{j,i}(x)$")
    ax[0].set_title("Top-6 first-layer KAN functions")
    ax[0].legend(fontsize=7)
    f = ps[(ps.seed == 0)].pivot_table(index="step", columns="model", values="f1", aggfunc="mean")
    ax2 = ax[1].twinx()
    for c in f.columns:
        ax[1].plot(f.index, f[c], marker="o", ms=3, label=c)
    c = clip_df.set_index("step").clipped_fraction.reindex(f.index)
    ax2.bar(f.index, c, alpha=0.2, color="grey")
    ax2.set_ylabel("share of clipped inputs")
    ax[1].axvline(42.5, ls="--", c="k", lw=0.8)
    ax[1].set_xlabel("time step")
    ax[1].set_ylabel("illicit F1")
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(run / "fig_e17_kan.png", dpi=160)


if __name__ == "__main__":
    main()
