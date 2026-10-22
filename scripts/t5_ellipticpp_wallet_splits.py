"""
T5  Actor-level detection on Elliptic++ wallets: how much of the score is
look-ahead and entity leakage?

Observation that motivates the experiment (audit in this script)
----------------------------------------------------------------
`wallets_features_classes_combined.csv` has one row per (address, time step),
but every one of its 55 features is constant across the rows of an address:
they are lifetime aggregates over all 49 steps (e.g. last_block_appeared_in,
lifetime_in_blocks, num_timesteps_appeared_in). A row at step 10 therefore
carries information from step 49, and the same address with the same
features and label appears in both training and test steps.

Hypothesis
----------
HT.6  The usual row-level random split overstates wallet-level illicit F1;
       a temporal split that is also entity-disjoint (test wallets first appear
       after the training period) gives a markedly lower F1, and removing the
       explicitly future-revealing features lowers it further.

Protocols (RF and LightGBM, 3 seeds; threshold = max-F1 on a validation split)
-----------------------------------------------------------------------------
P1 random_rows       rows split 70/15/15 at random (as in most papers using the file)
P1b random_entity   one row per address (first step), addresses split 70/15/15 at random
P2 temporal_rows     rows by step: train <= 30, val 31-34, test >= 35 (address overlap allowed)
P3 temporal_entity   one row per address at its FIRST step; train first step <= 30,
                     val 31-34, test >= 35 (no address in two parts)
P4 P3 minus time     P3 without first/last block, lifetime, num_timesteps_appeared_in,
                     first_sent_block, first_received_block

Even P4 keeps lifetime aggregates of test wallets that extend over later test
steps; it is the least leaky protocol available without recomputing wallet
features from raw transactions, not a fully causal one.

Usage
-----
    python scripts/t5_ellipticpp_wallet_splits.py --data data/raw/ellipticpp
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.eval.metrics import binary_report, threshold_at_val_f1   # noqa: E402
from bal.utils.repro import dump_json, set_seed, write_manifest   # noqa: E402

TIME_FEATURES = ["first_block_appeared_in", "last_block_appeared_in", "lifetime_in_blocks",
                 "num_timesteps_appeared_in", "first_sent_block", "first_received_block"]


def models(seed):
    import lightgbm as lgb
    from sklearn.ensemble import RandomForestClassifier
    return {"rf": RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample",
                                         n_jobs=4, random_state=seed, min_samples_leaf=2),
            "lgbm": lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=63,
                                       subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                       class_weight="balanced", random_state=seed, verbose=-1, n_jobs=4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/ellipticpp")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--out", default="results/transactions")
    ap.add_argument("--protocols", default="all", help="comma list of protocol name prefixes, or all")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("t5_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    src = Path(a.data) / "wallets_features_classes_combined.csv"
    d = pd.read_csv(src)
    d = d.rename(columns={"Time step": "step"})
    feats = [c for c in d.columns if c not in ("address", "step", "class")]

    # ---- audit -------------------------------------------------------------
    n_rows = d.groupby("address").size()
    multi = d[d.address.isin(n_rows[n_rows > 1].index)]
    const_share = multi.groupby("address")[feats].nunique().eq(1).mean()
    lab = d[d["class"] != 3].copy()
    lab["y"] = (lab["class"] == 1).astype(int)
    first = lab.groupby("address").step.transform("min")
    audit = {"rows": int(len(d)), "addresses": int(d.address.nunique()),
             "labelled_rows": int(len(lab)), "labelled_addresses": int(lab.address.nunique()),
             "features": len(feats),
             "features_constant_within_address_share_min": float(const_share.min()),
             "labelled_rows_in_test_steps_whose_address_also_in_train_steps": float(
                 lab[lab.step >= 35].address.isin(lab[lab.step <= 30].address).mean()),
             "P1_test_rows_whose_address_has_a_train_row": None,
             "labelled_addresses_first_seen_ge35": int((lab.groupby("address").step.min() >= 35).sum())}
    rng_rows = np.random.default_rng(0).random(len(lab))
    ent = lab[lab.step == first].drop_duplicates("address")
    rng_ent = np.random.default_rng(0).random(len(ent))
    audit["P1_test_rows_whose_address_has_a_train_row"] = float(
        lab.address[rng_rows >= 0.85].isin(lab.address[rng_rows < 0.70]).mean())
    dump_json(audit, run / "audit.json")
    print(audit, flush=True)

    protocols = {
        "P1_random_rows": (lab, rng_rows < 0.70, (rng_rows >= 0.70) & (rng_rows < 0.85), rng_rows >= 0.85, feats),
        "P1b_random_entity": (ent, rng_ent < 0.70, (rng_ent >= 0.70) & (rng_ent < 0.85), rng_ent >= 0.85, feats),
        "P2_temporal_rows": (lab, lab.step <= 30, lab.step.between(31, 34), lab.step >= 35, feats),
        "P3_temporal_entity": (ent, ent.step <= 30, ent.step.between(31, 34), ent.step >= 35, feats),
        "P4_temporal_entity_no_time": (ent, ent.step <= 30, ent.step.between(31, 34), ent.step >= 35,
                                       [f for f in feats if f not in TIME_FEATURES]),
    }
    if a.protocols != "all":
        keep = tuple(a.protocols.split(","))
        protocols = {k: v for k, v in protocols.items() if k.startswith(keep)}
    rows = []
    for pname, (D, tr, va, te, cols) in protocols.items():
        tr, va, te = np.asarray(tr), np.asarray(va), np.asarray(te)
        X, y = D[cols].to_numpy(np.float32), D.y.to_numpy()
        for seed in range(a.seeds):
            set_seed(seed)
            for mname, m in models(seed).items():
                m.fit(X[tr], y[tr])
                s = m.predict_proba(X)[:, 1]
                thr = threshold_at_val_f1(y[va], s[va])
                r = binary_report(y[te], s[te], thr)
                rows.append({"protocol": pname, "model": mname, "seed": seed, "n_train": int(tr.sum()),
                             "n_test": int(te.sum()), "test_base_rate": float(y[te].mean()),
                             "f1": r.f1, "precision": r.precision, "recall": r.recall,
                             "auprc": r.auprc, "roc_auc": r.roc_auc})
                print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(run / "metrics.csv", index=False)
    summ = df.groupby(["protocol", "model"])[["f1", "auprc", "roc_auc", "test_base_rate", "n_test"]].agg(
        ["mean", "std"]).round(4)
    summ.to_csv(run / "metrics_summary.csv")
    print(summ.to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a), data_files=[src],
                   extra={"time_features": TIME_FEATURES})
    print("wrote", run)


if __name__ == "__main__":
    main()
