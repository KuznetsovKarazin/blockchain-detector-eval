"""
TV / X1  Elliptic++ wallets with causal features: how much of the wallet
score depends on features that see the address's future?

T5 found that all 55 Elliptic++ wallet features are constant within an
address (lifetime aggregates) and that the score falls from F1 0.95 (random
rows) to 0.27-0.39 (temporal, address-disjoint). This script rebuilds wallet
features from the transactions of the address up to and including the row's
step, so that a row at step t uses nothing from steps > t.

Causal features of (address a, step t)
--------------------------------------
From the address-transaction edge lists (AddrTx: a is an input of the
transaction, "sent"; TxAddr: a is an output, "received") joined with the
Elliptic++ transaction table:
* n_sent_cum, n_recv_cum, n_sent_t, n_recv_t, active_steps, steps_since_first;
* for each role (sent / received) and each of TX_COLS: min, mean and max over
  the role's transactions of the address at steps <= t.
A transaction counts once per (address, role) even if the address appears in
it several times.

Hypothesis HV1 and the decision rule are in docs/PROTOCOLS_TV.md.

Protocols (rows and seeds as in T5; RF and LightGBM, 3 seeds; threshold =
max-F1 on validation)
------------------------------------------------------------------------
P1  random rows 70/15/15            P1b  one row per address (first step), random
P2  temporal rows (<=30 / 31-34 / >=35)
P3  temporal, one row per address at its first step (address-disjoint)
P5  temporal rows; test = rows >= 35 of addresses with no row <= 34
    (address-disjoint, but later rows of an address carry its accumulated
    history)
Feature sets: lifetime (55), lifetime_no_time (T5's P4 set), causal,
causal+lifetime. Labels: Elliptic++ wallet class (1 illicit, 2 licit). The
causal label (any illicit transaction of the address up to t) is computed
and compared with the wallet class (audit.json) and used as a sensitivity
label in the P3/P5 rows (`label=causal`).

Usage
-----
    python scripts/tv1_wallet_causal.py --data data/raw/ellipticpp
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

TX_COLS = ["total_BTC", "fees", "size", "num_input_addresses", "num_output_addresses",
           "in_BTC_total", "out_BTC_total", "in_txs_degree", "out_txs_degree"]
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


def causal_features(data: Path) -> pd.DataFrame:
    tx = pd.read_csv(data / "txs_features.csv", usecols=["txId", "Time step", *TX_COLS])
    tx = tx.rename(columns={"Time step": "step"})
    cls = pd.read_csv(data / "txs_classes.csv")
    tx = tx.merge(cls, on="txId", how="left")
    tx["illicit"] = (tx["class"] == 1).astype(np.int8)
    sent = pd.read_csv(data / "AddrTx_edgelist.csv").rename(columns={"input_address": "address"})
    recv = pd.read_csv(data / "TxAddr_edgelist.csv").rename(columns={"output_address": "address"})
    parts, per_step = [], []
    for role, e in (("sent", sent), ("recv", recv)):
        e = e.drop_duplicates(["address", "txId"]).merge(tx, on="txId", how="inner")
        g = e.groupby(["address", "step"])
        agg = g[TX_COLS].agg(["min", "max", "sum"])
        agg.columns = [f"{c}_{s}" for c, s in agg.columns]
        agg["n"] = g.size()
        agg["ill"] = g["illicit"].max()
        agg = agg.reset_index().sort_values(["address", "step"])
        a = agg.groupby("address")
        out = agg[["address", "step"]].copy()
        out[f"n_{role}_t"] = agg["n"].to_numpy()
        out[f"n_{role}_cum"] = a["n"].cumsum().to_numpy()
        out[f"ill_{role}_cum"] = a["ill"].cummax().to_numpy()
        for c in TX_COLS:
            out[f"{role}_{c}_min"] = a[f"{c}_min"].cummin().to_numpy()
            out[f"{role}_{c}_max"] = a[f"{c}_max"].cummax().to_numpy()
            out[f"{role}_{c}_mean"] = (a[f"{c}_sum"].cumsum() / out[f"n_{role}_cum"]).to_numpy()
        parts.append(out)
        per_step.append(agg[["address", "step"]])
    steps = pd.concat(per_step).drop_duplicates().sort_values(["address", "step"])
    f = steps
    for p in parts:
        f = f.merge(p, on=["address", "step"], how="left")
    # carry each role's cumulative values forward to steps where only the other role is active
    f = f.sort_values(["address", "step"]).reset_index(drop=True)
    cum_cols = [c for c in f.columns if c not in ("address", "step") and not c.endswith("_t")]
    f[cum_cols] = f.groupby("address")[cum_cols].ffill()
    for r in ("sent", "recv"):
        f[f"n_{r}_t"] = f[f"n_{r}_t"].fillna(0)
        f[f"n_{r}_cum"] = f[f"n_{r}_cum"].fillna(0)
        f[f"ill_{r}_cum"] = f[f"ill_{r}_cum"].fillna(0)
    a = f.groupby("address")
    f["active_steps"] = a.cumcount() + 1
    f["steps_since_first"] = f.step - a.step.transform("min")
    f["y_causal"] = np.maximum(f.pop("ill_sent_cum"), f.pop("ill_recv_cum")).astype(int)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/ellipticpp")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--out", default="results/transactions")
    ap.add_argument("--protocols", default="all")
    ap.add_argument("--run", help="existing run folder: finished parts are skipped")
    ap.add_argument("--aggregate", action="store_true", help="only merge the parts of --run")
    a = ap.parse_args()
    run = Path(a.run) if a.run else Path(a.out) / time.strftime("tv1_%Y%m%d_%H%M%S")
    (run / "parts").mkdir(parents=True, exist_ok=True)
    data = Path(a.data)
    if a.aggregate:
        return aggregate(run, a, data)
    t0 = time.time()
    cache = run / "causal_features.parquet"      # local cache, not committed
    if cache.exists():
        cf = pd.read_parquet(cache)
    else:
        cf = causal_features(data)
        cf.to_parquet(cache, index=False)
    causal = [c for c in cf.columns if c not in ("address", "step", "y_causal")]
    print("causal features", cf.shape, round(time.time() - t0), "s", flush=True)

    life = pd.read_csv(data / "wallets_features_classes_combined.csv").rename(columns={"Time step": "step"})
    lifetime = [c for c in life.columns if c not in ("address", "step", "class")]
    d = life.merge(cf, on=["address", "step"], how="left", indicator=True)
    audit = {"wallet_rows": int(len(life)), "causal_rows": int(len(cf)),
             "wallet_rows_without_causal_row": int((d._merge == "left_only").sum())}
    d = d[d._merge == "both"].drop(columns="_merge")
    lab = d[d["class"] != 3].copy().reset_index(drop=True)
    lab["y"] = (lab["class"] == 1).astype(int)
    first = lab.groupby("address").step.transform("min")
    # causal label vs wallet class
    last = lab.sort_values("step").groupby("address").tail(1)
    audit.update({
        "labelled_rows": int(len(lab)), "labelled_addresses": int(lab.address.nunique()),
        "causal_label_at_last_row_vs_class": pd.crosstab(last.y, last.y_causal).to_dict(),
        "causal_label_at_first_row_vs_class": pd.crosstab(lab[lab.step == first].y,
                                                          lab[lab.step == first].y_causal).to_dict(),
        "illicit_wallets_with_no_illicit_tx_by_first_row": int(
            ((lab.step == first) & (lab.y == 1) & (lab.y_causal == 0)).sum()),
    })
    dump_json(audit, run / "audit.json")
    print(audit, flush=True)

    ent = lab[lab.step == first].drop_duplicates("address").reset_index(drop=True)
    rng_rows = np.random.default_rng(0).random(len(lab))
    rng_ent = np.random.default_rng(0).random(len(ent))
    seen_early = set(lab.address[lab.step <= 34])
    p5_test = (lab.step >= 35) & ~lab.address.isin(seen_early)
    fsets = {"lifetime": lifetime,
             "lifetime_no_time": [c for c in lifetime if c not in TIME_FEATURES],
             "causal": causal,
             "causal+lifetime": causal + lifetime,
             # post-hoc check: tx-graph degrees are complete only once the step has closed
             "causal_no_degree": [c for c in causal if "txs_degree" not in c]}
    protocols = {
        "P1_random_rows": (lab, rng_rows < 0.70, (rng_rows >= 0.70) & (rng_rows < 0.85), rng_rows >= 0.85),
        "P1b_random_entity": (ent, rng_ent < 0.70, (rng_ent >= 0.70) & (rng_ent < 0.85), rng_ent >= 0.85),
        "P2_temporal_rows": (lab, lab.step <= 30, lab.step.between(31, 34), lab.step >= 35),
        "P3_temporal_entity": (ent, ent.step <= 30, ent.step.between(31, 34), ent.step >= 35),
        "P5_temporal_rows_new_addresses": (lab, lab.step <= 30, lab.step.between(31, 34), p5_test),
    }
    if a.protocols != "all":
        keep = tuple(a.protocols.split(","))
        protocols = {k: v for k, v in protocols.items() if k.startswith(keep)}
    for pname, (D, tr, va, te) in protocols.items():
        tr, va, te = np.asarray(tr), np.asarray(va), np.asarray(te)
        labels = {"wallet": D.y.to_numpy()}
        if pname.startswith(("P3", "P5")):
            labels["causal"] = D.y_causal.to_numpy()
        for lname, y in labels.items():
            for fname, cols in fsets.items():
                if fname == "causal_no_degree" and (lname != "wallet" or pname.startswith("P1")):
                    continue
                if lname == "causal" and fname not in ("lifetime", "causal"):
                    continue
                part = run / "parts" / f"{pname}__{lname}__{fname}.csv"
                if part.exists():
                    continue
                rows = []
                X = D[cols].to_numpy(np.float32)
                for seed in range(a.seeds):
                    set_seed(seed)
                    for mname, m in models(seed).items():
                        m.fit(X[tr], y[tr])
                        s = m.predict_proba(X)[:, 1]
                        thr = threshold_at_val_f1(y[va], s[va])
                        r = binary_report(y[te], s[te], thr)
                        rows.append({"protocol": pname, "label": lname, "features": fname, "model": mname,
                                     "seed": seed, "n_features": len(cols), "n_train": int(tr.sum()),
                                     "n_test": int(te.sum()), "test_base_rate": float(y[te].mean()),
                                     "f1": r.f1, "precision": r.precision, "recall": r.recall,
                                     "auprc": r.auprc, "roc_auc": r.roc_auc})
                        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rows[-1].items()},
                              flush=True)
                pd.DataFrame(rows).to_csv(part, index=False)
    aggregate(run, a, data, causal)


def aggregate(run, a, data, causal=None):
    df = pd.concat([pd.read_csv(p) for p in sorted((run / "parts").glob("*.csv"))], ignore_index=True)
    df.to_csv(run / "metrics.csv", index=False)
    summ = df.groupby(["protocol", "label", "features", "model"])[
        ["auprc", "f1", "roc_auc", "test_base_rate", "n_test"]].agg(["mean", "std"]).round(4)
    summ.to_csv(run / "metrics_summary.csv")
    print(summ.to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[data / f for f in ("txs_features.csv", "txs_classes.csv", "AddrTx_edgelist.csv",
                                                  "TxAddr_edgelist.csv",
                                                  "wallets_features_classes_combined.csv")],
                   extra={"tx_cols": TX_COLS, "time_features": TIME_FEATURES,
                          "causal_features": causal,
                          "parts": sorted(p.name for p in (run / "parts").glob("*.csv"))})
    print("wrote", run)


if __name__ == "__main__":
    main()
