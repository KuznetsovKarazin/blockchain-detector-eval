"""
T1  Model families for illicit-transaction detection under a strict
temporal protocol (KAN rows are analysed further in K).

Research question
-----------------
Which model families detect illicit Bitcoin transactions best when trained on
the past and tested on the future, and what happens after the dark-market
shutdown (time step 43)?

Hypotheses
----------
HT.1  Under the temporal protocol, gradient-boosted trees / RF on node
       features match or beat GCN, GraphSAGE and GAT (Maganti 2026, arXiv:2604.19514,
       reports RF 0.821 vs GraphSAGE 0.689 ± 0.017 illicit F1).
HT.2  Cheap neighbour aggregates (mean/max of neighbour features + degree)
       capture most of what message passing adds.
HT.3  The post-shutdown collapse is largely a threshold problem caused by
       prior shift; label-shift correction without target labels (EM, BBSE)
       recovers part of the lost F1.  (scripts/t2_label_shift.py)

Protocol (bal.data.elliptic): train steps 1-30, validation 31-34, test 35-49.
Thresholds = max-F1 on validation. Seeds 0..S-1 for every stochastic model.
Feature sets: LF (93 local), AF (all 165), AF+NB (AF + neighbour aggregates).
Headline rule (fixed in code, `select_by_validation`): for every model the
feature set with the highest mean validation AUPRC is reported; the test-best
set is shown next to it only for transparency.

Early stopping differs by family and is part of each model's definition:
MLP/KAN hold out a stratified random 15 % of the labelled TRAIN nodes (rows,
not time steps), GNNs use the temporal
validation steps, trees and logistic regression use no early stopping.

Each invocation writes its parts to RUN/parts/<tag>/; --aggregate reads only
those parts, so it is idempotent and never reads its own outputs.

Usage
-----
    python scripts/t1_temporal_benchmark.py --data data/raw/elliptic --seeds 5
    python scripts/t1_temporal_benchmark.py --synthetic --seeds 1     # smoke test
    # parallel model groups sharing one run, then merge:
    python scripts/t1_temporal_benchmark.py --run results/transactions/R --models logreg,rf,lgbm
    python scripts/t1_temporal_benchmark.py --run results/transactions/R --models gcn,sage,gat
    python scripts/t1_temporal_benchmark.py --run results/transactions/R --aggregate
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.elliptic import (POST_SHUTDOWN, PRE_SHUTDOWN, TEST_STEPS, TRAIN_STEPS,  # noqa: E402
                               VAL_STEPS, load_elliptic, make_synthetic)
from bal.eval.metrics import binary_report, safe_ap, threshold_at_val_f1          # noqa: E402
from bal.models.gnn import GraphClassifier, neighbour_features                    # noqa: E402
from bal.models.tabular import MODELS                                             # noqa: E402
from bal.utils.repro import atomic_to_csv, set_seed, write_manifest               # noqa: E402

TAB_MODELS = ["logreg", "rf", "lgbm", "mlp", "kan"]
GNN_MODELS = ["gcn", "sage", "gat"]


def per_step_f1(y, s, step, thr, steps):
    from sklearn.metrics import f1_score
    out = {}
    for t in steps:
        m = step == t
        if m.sum() == 0:
            continue
        out[int(t)] = float(f1_score(y[m], (s[m] >= thr).astype(int), zero_division=0))
    return out


def evaluate(name, fset, seed, s_all, d, rows, steprows, scores_out):
    va, te = d.mask(VAL_STEPS), d.mask(TEST_STEPS)
    thr = threshold_at_val_f1(d.y[va], s_all[va])
    rep = binary_report(d.y[te], s_all[te], thr)
    pre, post = d.mask(PRE_SHUTDOWN), d.mask(POST_SHUTDOWN)
    rp = binary_report(d.y[pre], s_all[pre], thr)
    rq = binary_report(d.y[post], s_all[post], thr)
    rows.append({"model": name, "features": fset, "seed": seed, "threshold": thr,
                 "val_auprc": safe_ap(d.y[va], s_all[va]),
                 "test_f1": rep.f1, "test_precision": rep.precision, "test_recall": rep.recall,
                 "test_auprc": rep.auprc, "test_roc_auc": rep.roc_auc,
                 "pre_f1": rp.f1, "post_f1": rq.f1, "pre_auprc": rp.auprc, "post_auprc": rq.auprc})
    for t, f in per_step_f1(d.y[te], s_all[te], d.step[te], thr, TEST_STEPS).items():
        steprows.append({"model": name, "features": fset, "seed": seed, "step": t, "f1": f})
    labelled = d.y >= 0
    scores_out[f"{name}|{fset}|{seed}"] = s_all[labelled].astype(np.float32)
    print(f"{name:7s} {fset:6s} seed={seed} test F1={rep.f1:.3f} AUPRC={rep.auprc:.3f} "
          f"pre={rp.f1:.3f} post={rq.f1:.3f}", flush=True)


def _part_dirs(run: Path) -> list[Path]:
    parts = sorted(p for p in (run / "parts").glob("*") if p.is_dir())
    if not parts:
        raise SystemExit(f"no parts under {run / 'parts'}")
    return parts


def select_by_validation(met: pd.DataFrame) -> pd.DataFrame:
    """Per model: feature set chosen by mean validation AUPRC (headline) vs test-best."""
    g = met.groupby(["model", "features"])[["val_auprc", "test_f1", "test_auprc", "post_f1"]].mean()
    rows = []
    for model, sub in g.groupby(level=0):
        sub = sub.droplevel(0)
        v, t = sub.val_auprc.idxmax(), sub.test_f1.idxmax()
        rows.append({"model": model, "features_by_val": v, "val_auprc": sub.loc[v, "val_auprc"],
                     "test_f1": sub.loc[v, "test_f1"], "test_auprc": sub.loc[v, "test_auprc"],
                     "post_f1": sub.loc[v, "post_f1"], "features_by_test": t,
                     "test_f1_if_test_selected": sub.loc[t, "test_f1"]})
    return pd.DataFrame(rows).sort_values("test_f1", ascending=False).round(4)


def aggregate(run: Path):
    """Merge RUN/parts/<tag>/{metrics,per_step_f1}.csv and scores.npz (idempotent)."""
    parts = _part_dirs(run)
    met = pd.concat([pd.read_csv(p / "metrics.csv") for p in parts], ignore_index=True)
    key = ["model", "features", "seed"]
    if met.duplicated(key).any():
        raise SystemExit(f"duplicate rows across parts: {met[met.duplicated(key)][key].values[:5]}")
    steps = pd.concat([pd.read_csv(p / "per_step_f1.csv") for p in parts], ignore_index=True)
    scores = {}
    for p in parts:
        Z = np.load(p / "scores.npz")
        scores.update({k: Z[k] for k in Z.files})
    atomic_to_csv(met, run / "metrics.csv", index=False)
    atomic_to_csv(steps, run / "per_step_f1.csv", index=False)
    import hashlib
    if "y" in scores:   # fingerprint of the labels, so a label-free copy can be checked against local data
        scores["labels_sha256"] = np.array(hashlib.sha256(
            np.stack([scores["y"], scores["step"]]).astype(np.int64).tobytes()).hexdigest())
    tmp = run / "scores_labelled.tmp.npz"
    np.savez_compressed(tmp, **scores)
    tmp.replace(run / "scores_labelled.npz")
    summ = (met.groupby(["model", "features"])
            [["test_f1", "test_auprc", "pre_f1", "post_f1", "val_auprc"]].agg(["mean", "std"]).round(4))
    atomic_to_csv(summ, run / "metrics_summary.csv")
    sel = select_by_validation(met)
    atomic_to_csv(sel, run / "headline_by_validation.csv", index=False)
    print(summ)
    print(sel.to_string(index=False))
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/elliptic")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--out", default="results/transactions")
    ap.add_argument("--run", default=None,
                    help="existing/new run directory; lets several invocations (one per model "
                         "group) share one run, merged afterwards with --aggregate")
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--models", default=",".join(TAB_MODELS + GNN_MODELS))
    a = ap.parse_args()
    if a.run:
        run = Path(a.run)
    else:
        run = Path(a.out) / ("smoke" if a.synthetic else time.strftime("t1_%Y%m%d_%H%M%S"))
    run.mkdir(parents=True, exist_ok=True)
    if a.aggregate:
        aggregate(run)
        return
    d = make_synthetic() if a.synthetic else load_elliptic(a.data)
    models = a.models.split(",")
    tag = "-".join(models)
    part = run / "parts" / tag
    part.mkdir(parents=True, exist_ok=True)

    NB = neighbour_features(d.X, d.edges)
    fsets = {"LF": d.features("LF"), "AF": d.features("AF"), "AF+NB": np.hstack([d.X, NB])}
    tr, va = d.mask(TRAIN_STEPS), d.mask(VAL_STEPS)
    rows, steprows, scores = [], [], {}

    def checkpoint():
        # written after every model so a crash loses at most one fit
        atomic_to_csv(pd.DataFrame(rows), part / "metrics.csv", index=False)
        atomic_to_csv(pd.DataFrame(steprows), part / "per_step_f1.csv", index=False)
        np.savez_compressed(part / "scores.tmp.npz", **scores, y=d.y[d.y >= 0], step=d.step[d.y >= 0])
        (part / "scores.tmp.npz").replace(part / "scores.npz")

    for name in [m for m in models if m in TAB_MODELS]:
        for fset, X in fsets.items():
            for seed in range(a.seeds if name != "logreg" else 1):
                set_seed(seed)
                # neural models do their own internal validation split for early
                # stopping, taken from the TRAIN steps only
                m = MODELS[name](seed=seed).fit(X[tr], d.y[tr])
                s = m.predict_score(X)
                evaluate(name, fset, seed, s, d, rows, steprows, scores)
                checkpoint()

    for name in [m for m in models if m in GNN_MODELS]:
        for seed in range(a.seeds):
            set_seed(seed)
            g = GraphClassifier(kind=name, seed=seed).fit(d.X, d.edges, d.y, tr, va)
            evaluate(name, "AF+graph", seed, g.scores_, d, rows, steprows, scores)
            checkpoint()

    write_manifest(part, script=Path(__file__).name, config=vars(a),
                   data_files=[] if a.synthetic else [Path(a.data) / f for f in
                               ("elliptic_txs_features.csv", "elliptic_txs_classes.csv", "elliptic_txs_edgelist.csv")],
                   extra={"splits": {"train": [1, 30], "val": [31, 34], "test": [35, 49],
                                     "pre": [35, 42], "post": [43, 49]}})
    print("wrote", run)


if __name__ == "__main__":
    main()
