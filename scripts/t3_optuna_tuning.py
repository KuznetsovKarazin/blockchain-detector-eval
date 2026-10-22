"""
T3  Does hyper-parameter tuning change the T1 ranking?

Motivation
----------
T1 used one fixed configuration per model. A fair objection is that the
neural models (MLP, KAN) were under-tuned while LightGBM / RF defaults are known
to be strong. This script gives every model the same Optuna budget.

Hypotheses
----------
HT.4  With an equal tuning budget, tree ensembles stay ahead of MLP and KAN on
       the test steps; tuning narrows but does not close the gap.
HT.5  Rank-based input normalisation (QuantileTransformer) helps the neural
       models, and the KAN more than the MLP, because the heavy-tailed Elliptic
       features otherwise put most of the mass in a few spline intervals.

Protocol (no test information is used for any choice)
-----------------------------------------------------
* Objective: AUPRC on validation steps 31-34 of a model fitted on steps 1-30
  (neural models early-stop on a random 15% of the training steps).
* Sampler: TPE, seed 0; same number of trials for every model family.
* Feature set (LF / AF / AF+NB) is part of the search space.
* After the search the best configuration is refitted with seeds 0..S-1; the
  threshold is the validation max-F1 threshold; test 35-49 is evaluated once.

Usage
-----
    python scripts/t3_optuna_tuning.py --model kan --trials 40
    python scripts/t3_optuna_tuning.py --model lgbm --trials 40
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

from bal.data.elliptic import (POST_SHUTDOWN, PRE_SHUTDOWN, TEST_STEPS, TRAIN_STEPS,  # noqa: E402
                               VAL_STEPS, load_elliptic)
from bal.eval.metrics import binary_report, safe_ap, threshold_at_val_f1          # noqa: E402
from bal.models.gnn import neighbour_features                                     # noqa: E402
from bal.models.tabular import SkWrap, TorchClassifier                            # noqa: E402
from bal.utils.repro import dump_json, set_seed, write_manifest                   # noqa: E402


def suggest(trial, model):
    fset = trial.suggest_categorical("features", ["LF", "AF", "AF+NB"])
    if model == "lgbm":
        return fset, dict(
            n_estimators=trial.suggest_int("n_estimators", 100, 1200, step=100),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            num_leaves=trial.suggest_int("num_leaves", 8, 128, log=True),
            min_child_samples=trial.suggest_int("min_child_samples", 5, 100, log=True),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.3, 1.0),
            subsample=trial.suggest_float("subsample", 0.5, 1.0),
            reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True))
    if model == "rf":
        return fset, dict(
            n_estimators=trial.suggest_int("n_estimators", 200, 800, step=100),
            max_features=trial.suggest_categorical("max_features", ["sqrt", "log2", 0.2, 0.4]),
            min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 10))
    depth = trial.suggest_int("depth", 1, 2 if model == "kan" else 3)
    width = trial.suggest_categorical("width", [4, 8, 16, 32] if model == "kan" else [16, 32, 64, 128, 256])
    kw = dict(hidden=tuple([width] * depth),
              lr=trial.suggest_float("lr", 3e-4, 3e-2, log=True),
              weight_decay=trial.suggest_float("weight_decay", 1e-6, 1e-2, log=True),
              prep=trial.suggest_categorical("prep", ["robust", "quantile"]),
              batch=trial.suggest_categorical("batch", [256, 512, 1024]))
    if model == "kan":
        kw["grid"] = trial.suggest_categorical("grid", [3, 5, 8, 12])
        kw["l1_spline"] = trial.suggest_categorical("l1_spline", [0.0, 1e-4, 1e-3, 1e-2])
    return fset, kw


def build(model, kw, seed):
    if model == "lgbm":
        import lightgbm as lgb
        return SkWrap(lgb.LGBMClassifier(**kw, subsample_freq=1, class_weight="balanced",
                                         random_state=seed, verbose=-1, n_jobs=1), name="lgbm")
    if model == "rf":
        from sklearn.ensemble import RandomForestClassifier
        return SkWrap(RandomForestClassifier(**kw, class_weight="balanced_subsample", n_jobs=1,
                                             random_state=seed), name="rf")
    return TorchClassifier(model, seed=seed, **kw)


def main():
    import optuna
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/elliptic")
    ap.add_argument("--model", required=True, choices=["lgbm", "rf", "mlp", "kan"])
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--out", default="results/transactions")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime(f"t3_{a.model}_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)

    d = load_elliptic(a.data)
    NB = neighbour_features(d.X, d.edges)
    fsets = {"LF": d.features("LF"), "AF": d.features("AF"), "AF+NB": np.hstack([d.X, NB])}
    tr, va = d.mask(TRAIN_STEPS), d.mask(VAL_STEPS)
    lab = d.y >= 0

    def objective(trial):
        fset, kw = suggest(trial, a.model)
        X = fsets[fset]
        set_seed(0)
        m = build(a.model, kw, 0).fit(X[tr], d.y[tr])
        return safe_ap(d.y[va], m.predict_score(X[va]))

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=0))
    t0 = time.time()
    study.optimize(objective, n_trials=a.trials)
    study.trials_dataframe().to_csv(run / "trials.csv", index=False)
    best = study.best_trial
    fset, kw = suggest(optuna.trial.FixedTrial(best.params), a.model)
    print("best", best.value, best.params, flush=True)

    rows = []
    X = fsets[fset]
    for seed in range(a.seeds):
        set_seed(seed)
        m = build(a.model, kw, seed).fit(X[tr], d.y[tr])
        s = m.predict_score(X)
        thr = threshold_at_val_f1(d.y[va], s[va])
        r = {"model": a.model, "features": fset, "seed": seed, "val_auprc": safe_ap(d.y[va], s[va])}
        for part, steps in [("test", TEST_STEPS), ("pre", PRE_SHUTDOWN), ("post", POST_SHUTDOWN)]:
            mm = np.isin(d.step, list(steps)) & lab
            rep = binary_report(d.y[mm], s[mm], thr)
            r[f"{part}_f1"], r[f"{part}_auprc"] = rep.f1, rep.auprc
        rows.append(r)
        print(r, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(run / "best_refit.csv", index=False)
    summary = {"model": a.model, "best_val_auprc_seed0": best.value,
               "best_params": best.params, "trials": a.trials, "search_seconds": time.time() - t0,
               **{f"{c}_mean": float(df[c].mean()) for c in df.columns if c.endswith(("f1", "auprc"))},
               **{f"{c}_std": float(df[c].std()) for c in df.columns if c.endswith(("f1", "auprc"))}}
    dump_json(summary, run / "summary.json")
    print(json.dumps(summary, indent=1, default=str))
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(a.data) / f for f in ("elliptic_txs_features.csv",
                               "elliptic_txs_classes.csv", "elliptic_txs_edgelist.csv")])
    print("wrote", run)


if __name__ == "__main__":
    main()
