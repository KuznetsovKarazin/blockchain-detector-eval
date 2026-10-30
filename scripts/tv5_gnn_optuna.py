"""
TV / X5  Does tuning the graph neural networks change the T1 order?

T1 trained GCN, GraphSAGE and GAT with one configuration (2 layers, 64
hidden, dropout 0.3, lr 1e-2) and reported them as a lower bound. Here
GraphSAGE and GAT get the T3 budget: 40 TPE trials (seed 0), objective =
validation AP (steps 31-34) of a model trained on steps 1-30, early stopping
on the same validation steps as in T1. Search space: hidden {32, 64, 128,
256}, layers {1, 2, 3}, dropout [0, 0.6], learning rate [1e-3, 3e-2] (log),
input LF or AF. The best configuration is refitted with seeds 0..4; F1 at the
validation max-F1 threshold and AP are reported on test 35-49, pre 35-42 and
post 43-49.

Usage
-----
    python scripts/tv5_gnn_optuna.py --model sage --trials 40
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.elliptic import POST_SHUTDOWN, PRE_SHUTDOWN, TEST_STEPS, TRAIN_STEPS, VAL_STEPS, load_elliptic  # noqa: E402
from bal.eval.metrics import binary_report, safe_ap, threshold_at_val_f1          # noqa: E402
from bal.models.gnn import GraphClassifier                                        # noqa: E402
from bal.utils.repro import dump_json, set_seed, write_manifest                   # noqa: E402


def main():
    import optuna
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/elliptic")
    ap.add_argument("--model", required=True, choices=["sage", "gat"])
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--out", default="results/transactions")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime(f"tv5_{a.model}_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    d = load_elliptic(a.data)
    fsets = {"LF": d.features("LF"), "AF": d.features("AF")}
    tr, va = d.mask(TRAIN_STEPS), d.mask(VAL_STEPS)

    def params(trial):
        return dict(features=trial.suggest_categorical("features", ["LF", "AF"]),
                    hidden=trial.suggest_categorical("hidden", [32, 64, 128, 256]),
                    layers=trial.suggest_int("layers", 1, 3),
                    dropout=trial.suggest_float("dropout", 0.0, 0.6),
                    lr=trial.suggest_float("lr", 1e-3, 3e-2, log=True))

    def objective(trial):
        p = params(trial)
        set_seed(0)
        t0 = time.time()
        g = GraphClassifier(kind=a.model, hidden=p["hidden"], layers=p["layers"], dropout=p["dropout"],
                            lr=p["lr"], seed=0).fit(fsets[p["features"]], d.edges, d.y, tr, va)
        trial.set_user_attr("epochs", g.epochs_run)
        trial.set_user_attr("seconds", round(time.time() - t0, 1))
        return safe_ap(d.y[va], g.scores_[va])

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=0))
    study.optimize(objective, n_trials=a.trials, callbacks=[
        lambda s, t: print(t.number, round(t.value, 4), t.params, t.user_attrs, flush=True)])
    study.trials_dataframe().to_csv(run / "trials.csv", index=False)
    best = study.best_params
    dump_json({"best_params": best, "best_val_ap": study.best_value}, run / "best.json")

    rows = []
    for seed in range(a.seeds):
        set_seed(seed)
        g = GraphClassifier(kind=a.model, hidden=best["hidden"], layers=best["layers"], dropout=best["dropout"],
                            lr=best["lr"], seed=seed).fit(fsets[best["features"]], d.edges, d.y, tr, va)
        s = g.scores_
        thr = threshold_at_val_f1(d.y[va], s[va])
        for pname, steps in (("test", TEST_STEPS), ("pre", PRE_SHUTDOWN), ("post", POST_SHUTDOWN)):
            m = d.mask(steps)
            r = binary_report(d.y[m], s[m], thr)
            rows.append({"model": a.model, "seed": seed, "period": pname, "f1": r.f1, "auprc": r.auprc,
                         "val_ap": safe_ap(d.y[va], s[va]), "epochs": g.epochs_run})
        print(rows[-3], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(run / "refit_metrics.csv", index=False)
    print(df.groupby("period")[["f1", "auprc"]].agg(["mean", "std"]).round(4).to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(a.data) / f"elliptic_txs_{f}.csv" for f in ("features", "classes", "edgelist")],
                   extra={"best_params": best})
    print("wrote", run)


if __name__ == "__main__":
    main()
