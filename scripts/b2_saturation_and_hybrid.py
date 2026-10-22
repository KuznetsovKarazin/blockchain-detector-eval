"""
B2  Why a 0.99-AUROC detector can still miss the largest bridge withdrawal,
and what a rule + detector hybrid buys.

Motivation (from B1)
------------------------
On Ronin, ECOD and Isolation Forest rank the attack outflows highly (ROC-AUC
0.99 / 0.98), yet at a 0.1% false-positive budget they alarm on the SECOND
attack transaction (25.5 M USDC) and miss the first one (173,600 ETH,
~540 M USD): ~95% of the stolen value was released before the alarm event.
The transparent rule R2 ("larger than any training outflow") flags it.

Hypotheses
----------
HB.4  Sum-aggregated tail scores (ECOD) dilute a single extreme feature: the
       largest Ronin withdrawal is extreme on value features only, and its
       ECOD score is bounded by d * log(n+1) like any other point that is
       moderately unusual on many features. Max-aggregation (ECOD-max) removes
       the dilution.
HB.5  OR-combining a magnitude/consistency rule with a learned detector keeps
       the rule's first-release alarm (an alarm on an executed release, not a
       prevented loss) and adds the detector's coverage of
       attacks that are not large, at the cost of the union of false alarms.

Protocol: identical splits, thresholds and features to B1 (features are
read from an B1 run directory so both scripts see the same numbers).

Usage
-----
    python scripts/b2_saturation_and_hybrid.py --b1-run results/bridges/<b1 run>
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bal.data.xchain import BRIDGES                                  # noqa: E402
from bal.eval.alarm import threshold_at_budget                       # noqa: E402
from bal.eval.metrics import safe_auc                                # noqa: E402
from bal.models.anomaly import DETECTORS, ECOD                       # noqa: E402
from bal.utils.repro import set_seed, write_manifest                 # noqa: E402

_spec = importlib.util.spec_from_file_location("b1", ROOT / "scripts" / "b1_bridge_detection.py")
b1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b1)

DETS = ["ecod", "ecod_max", "ecod_max_lex", "iforest", "ae_mlp", "ae_kan"]
FPR = 0.001


def rules(F_tr, F_te):
    v = F_te.value_usd.to_numpy()
    unm = F_te.unmatched.to_numpy() > 0.5
    return {"R2": v > F_tr.value_usd.max(),
            "R3": unm & (v > F_tr.value_usd.quantile(0.99))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--b1-run", required=True)
    ap.add_argument("--out", default="results/bridges")
    ap.add_argument("--seeds", type=int, default=5)
    a = ap.parse_args()
    src = Path(a.b1_run)
    run = Path(a.out) / time.strftime("b2_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)

    rows, contrib = [], []
    for b, meta in BRIDGES.items():
        F = pd.read_parquet(src / f"features_{b}.parquet")
        tr, cal, te = b1.split(F, pd.Timestamp(meta["attack_day"]))
        F_tr, F_te = F[tr], F[te].reset_index(drop=True)
        y = F_te.label.to_numpy()
        days = max(1.0, (F_te.ts.max() - F_te.ts.min()) / 86400)
        R = rules(F_tr, F_te)
        for view in ["D", "X"]:
            cols = b1.VIEWS[view]
            Xtr, Xcal, Xte = F.loc[tr, cols].to_numpy(), F.loc[cal, cols].to_numpy(), F_te[cols].to_numpy()

            # HB.4: per-feature tail scores of every attack event under ECOD
            ec = ECOD().fit(Xtr)
            T = ec.tail_scores(Xte)
            cap = np.log(len(Xtr) + 1)
            for i in np.where(y == 1)[0][:5]:
                order = np.argsort(-T[i])
                contrib.append({"bridge": b, "view": view, "tx_hash": F_te.tx_hash[i],
                                "value_usd": F_te.value_usd[i], "ecod_sum": T[i].sum(),
                                "ecod_rank": int((T.sum(1) > T[i].sum()).sum()) + 1,
                                "max_tail": T[i].max(), "cap_log_n1": cap,
                                "top_features": ";".join(f"{cols[j]}={T[i, j]:.1f}" for j in order[:4])})

            for d in DETS:
                for seed in (range(a.seeds) if d in b1.STOCHASTIC else [0]):
                    set_seed(seed)
                    m = DETECTORS[d](seed).fit(Xtr)
                    s_cal, s_te = m.score(Xcal), m.score(Xte)
                    thr, achieved = threshold_at_budget(s_cal, FPR)
                    flags = {d: s_te >= thr}
                    for rn, rf in R.items():
                        flags[f"{rn}|{d}"] = rf | (s_te >= thr)
                    for name, fl in flags.items():
                        fa = b1.first_alarm(F_te, fl.astype(float), 0.5)
                        rows.append({"bridge": b, "view": view, "detector": name, "seed": seed,
                                     "roc_auc": safe_auc(y, s_te) if name == d else np.nan,
                                     "achieved_cal_rate": achieved,
                                     "recall": fa["attack_recall"], "usd_recall": fa["usd_recall"],
                                     "usd_before_alarm": fa["usd_share_before_alarm"],
                                     "usd_through_alarm_block": fa["usd_share_through_alarm_block"],
                                     "seconds_to_alarm": fa["seconds_to_alarm"],
                                     "false_alarms_per_day": float((fl & (y == 0)).sum() / days)})
                    print(f"[{b}] {view} {d} seed={seed}", flush=True)
        for rn, rf in R.items():
            fa = b1.first_alarm(F_te, rf.astype(float), 0.5)
            rows.append({"bridge": b, "view": "rule", "detector": rn, "seed": 0, "roc_auc": np.nan,
                         "achieved_cal_rate": np.nan,
                         "recall": fa["attack_recall"], "usd_recall": fa["usd_recall"],
                         "usd_before_alarm": fa["usd_share_before_alarm"],
                         "usd_through_alarm_block": fa["usd_share_through_alarm_block"],
                         "seconds_to_alarm": fa["seconds_to_alarm"],
                         "false_alarms_per_day": float((rf & (y == 0)).sum() / days)})

    df = pd.DataFrame(rows)
    df.to_csv(run / "hybrid_metrics.csv", index=False)
    pd.DataFrame(contrib).to_csv(run / "ecod_attack_contributions.csv", index=False)
    summ = df.groupby(["bridge", "view", "detector"]).mean(numeric_only=True).drop(columns="seed").round(4)
    summ.to_csv(run / "hybrid_summary.csv")
    print(summ.to_string())
    print(pd.DataFrame(contrib).to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[src / f"features_{b}.parquet" for b in BRIDGES],
                   extra={"fpr_budget": FPR, "source_run": str(src)})
    print("wrote", run)


if __name__ == "__main__":
    main()
