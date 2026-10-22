"""
B1  Learned vs rule-based detection of cross-chain bridge attacks.

Research question
-----------------
Can a detector that never sees an attack label flag the Ronin and Nomad
exploits from bridge outflow events, how early, and how does it compare with
the cross-chain consistency rule ("an outflow must have a source-chain
request") that XChainWatcher encodes in Datalog?

Hypotheses
----------
HB.1  With the destination-chain view only (D), one-class detectors rank the
       attack outflows above almost all normal outflows (ROC-AUC > 0.95), but at
       a fixed alarm budget they fire only after part of the funds has left.
HB.2  Adding the cross-chain view (X: matched / latency) is what makes
       detection immediate; the learned model then adds value mainly by
       ranking the noisy "unmatched" population.
HB.3  Detectors trained on one bridge transfer to the other with a moderate
       loss, because the features are relative (ratios, novelty), not absolute.

Protocol
--------
* Train: normal outflows strictly before (attack_day - 7 days).
  The last 14 days of that period are the calibration window used ONLY to set
  thresholds for nominal false-positive budgets of 0.1% and 1%
  (bal.eval.alarm.threshold_at_budget: achieved rate <= budget, ties kept
  whole; the ACHIEVED calibration rate is reported next to every result).
* Test: all outflows from (attack_day - 7 days) to the end of the data.
* Seeds: 5 for stochastic detectors (IForest, autoencoders).
* Losses (bal.eval.alarm.alarm_accounting): value released before the alarm
  event, through the alarm event, through its block (same timestamp), and the
  value released after alarm + d seconds. Releases are already executed when
  they are observed, so none of these is a measured prevented loss.
* USD: features and rules value EVERY release with the close price of the
  last daily candle closed at or before it (bal.data.prices), whether or not
  the release was matched; every run asserts price_time <= release time row
  by row and checks prefix invariance of raw -> features. Loss shares use the
  reference value (attacks.csv). `--usd-mode matched_dataset` / `legacy` rerun
  the previous / first version.
* Outputs: results/bridges/<run>/metrics.csv, first_alarm.csv, thresholds.csv,
  manifest.json.

Usage
-----
    python scripts/b1_bridge_detection.py --root data/raw/XChainWatcher/cross-chain-rules-validator
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.prices import used_files                               # noqa: E402
from bal.data.xchain import BRIDGES, BRIDGES as _B, causal_usd, load_bridge, summary  # noqa: E402
from bal.eval.alarm import alarm_accounting, threshold_at_budget     # noqa: E402
from bal.eval.metrics import safe_ap, safe_auc, tie_ranks            # noqa: E402
from bal.features.xchain_features import D_FEATURES, X_FEATURES, REPLAY_SPECIFIC, build_features  # noqa: E402
from bal.models.anomaly import DETECTORS                             # noqa: E402
from bal.utils.repro import dump_json, set_seed, write_manifest      # noqa: E402

VIEWS = {
    "D": D_FEATURES,
    "D_noreplay": [f for f in D_FEATURES if f not in REPLAY_SPECIFIC],
    "X": X_FEATURES,
}
FPR_BUDGETS = [0.001, 0.01]
STOCHASTIC = {"iforest", "ae_mlp", "ae_kan"}


def split(F: pd.DataFrame, attack_day: pd.Timestamp):
    t = pd.to_datetime(F.ts, unit="s")
    test_start = attack_day - pd.Timedelta(days=7)
    cal_start = test_start - pd.Timedelta(days=14)
    tr = (t < cal_start) & (F.label == 0)
    cal = (t >= cal_start) & (t < test_start) & (F.label == 0)
    te = t >= test_start
    return tr.to_numpy(), cal.to_numpy(), te.to_numpy()


def prefix_invariance(ev: pd.DataFrame, F: pd.DataFrame, fractions=(0.25, 0.5, 0.75),
                      usd_mode: str = "asof") -> float:
    """Max abs difference between features of a prefix computed alone and inside the full stream.

    This checks dependence on LATER ROWS only; whether the values inside a row
    were available at its time is checked separately (price_time_s <= ts).
    """
    worst = 0.0
    for f in fractions:
        k = int(len(ev) * f)
        pre = ev.iloc[:k].copy()
        if usd_mode == "matched_dataset":
            v, _ = causal_usd(pre)
            pre["value_usd"] = np.clip(v, 0, None)
        Fp = build_features(pre)
        worst = max(worst, float(np.abs(Fp[X_FEATURES].to_numpy() - F[X_FEATURES].iloc[:k].to_numpy()).max()))
    return worst


def input_files(root: str, usd_mode: str) -> list[Path]:
    """Every raw file the loader reads, for the manifest."""
    root = Path(root)
    out = []
    for b, cfg in _B.items():
        out += [root / "analysis" / cfg["dir"] / "data" / "cctxs_withdrawals.csv",
                root / "analysis" / cfg["dir"] / "data" / "attacks.csv",
                root / "datalog" / cfg["dir"] / "results" / "SC_WithdrawalsWithoutMatch.csv"]
        if usd_mode == "asof":
            out += used_files(b, root.parent / "token-price-data")
    missing = [p for p in out if not p.exists()]
    assert not missing, f"missing input files: {missing}"
    return out


def first_alarm(F_te: pd.DataFrame, s_te: np.ndarray, thr: float) -> dict:
    return alarm_accounting(F_te.ts.to_numpy(), F_te.label.to_numpy(),
                            F_te.value_usd_ref.to_numpy(), s_te >= thr)


def evaluate(name, det_name, view, seed, s_cal, s_te, F_te, rows, alarms, domain="in", thr_rows=None):
    y = F_te.label.to_numpy()
    neg_pre = (y == 0)
    days = max(1.0, (F_te.ts.max() - F_te.ts.min()) / 86400)
    base = {"bridge": name, "detector": det_name, "view": view, "seed": seed, "domain": domain}
    rows.append({**base, "metric": "auprc", "value": safe_ap(y, s_te)})
    rows.append({**base, "metric": "roc_auc", "value": safe_auc(y, s_te)})
    # rank of attacks among test events (1 = top). Tied scores get the
    # midrank; min/max give the range over all orderings of the ties.
    mid, lo, hi = tie_ranks(s_te)
    b = np.flatnonzero(y == 1)[np.argmin(mid[y == 1])]
    rows.append({**base, "metric": "best_attack_rank", "value": float(mid[b])})
    rows.append({**base, "metric": "best_attack_rank_min", "value": float(lo[b])})
    rows.append({**base, "metric": "best_attack_rank_max", "value": float(hi[b])})
    rows.append({**base, "metric": "median_attack_rank", "value": float(np.median(mid[y == 1]))})
    rows.append({**base, "metric": "median_attack_rank_min", "value": float(np.median(lo[y == 1]))})
    rows.append({**base, "metric": "median_attack_rank_max", "value": float(np.median(hi[y == 1]))})
    for fpr in FPR_BUDGETS:
        thr, achieved = threshold_at_budget(s_cal, fpr)
        # what the old quantile rule (alarm if score >= quantile) would have achieved
        q = float(np.quantile(s_cal, 1.0 - fpr))
        if thr_rows is not None:
            thr_rows.append({**base, "fpr_budget": fpr, "n_cal": len(s_cal), "resolution": 1 / len(s_cal),
                             "threshold": thr, "achieved_cal_rate": achieved,
                             "quantile_rule_cal_rate": float((s_cal >= q).mean()),
                             "cal_ties_at_max": int((s_cal == s_cal.max()).sum())})
        fa = first_alarm(F_te, s_te, thr)
        false_alarms = int(((s_te >= thr) & neg_pre).sum())
        rows.append({**base, "metric": f"achieved_cal_rate@fpr{fpr}", "value": achieved})
        rows.append({**base, "metric": f"recall@fpr{fpr}", "value": fa.get("attack_recall", np.nan)})
        rows.append({**base, "metric": f"usd_recall@fpr{fpr}", "value": fa.get("usd_recall", np.nan)})
        rows.append({**base, "metric": f"usd_before_alarm@fpr{fpr}", "value": fa.get("usd_share_before_alarm", np.nan)})
        rows.append({**base, "metric": f"usd_through_alarm_block@fpr{fpr}",
                     "value": fa.get("usd_share_through_alarm_block", np.nan)})
        rows.append({**base, "metric": f"false_alarms_per_day@fpr{fpr}", "value": false_alarms / days})
        alarms.append({**base, "fpr_budget": fpr, **fa})


def rule_baselines(name, F_tr, F_te, rows, alarms):
    """Transparent rules, no learning.

    R1 consistency (XChainWatcher-style, simplified): flag every outflow without
       a matching source-chain request. NOTE: XChainWatcher's full rule set uses
       more facts than the matched flag reproduced here.
    R2 unprecedented value: flag outflows larger than the largest single
       outflow seen in the training period.
    R3 = R1 AND value above the training 99th percentile.
    """
    y = F_te.label.to_numpy()
    v = F_te.value_usd.to_numpy()          # observable value, not the attacks.csv reference
    unm = F_te.unmatched.to_numpy() > 0.5
    vmax = F_tr.value_usd.max()
    v99 = F_tr.value_usd.quantile(0.99)
    rules = {"R1_unmatched": unm, "R2_unprecedented_value": v > vmax,
             "R3_unmatched_and_large": unm & (v > v99)}
    days = max(1.0, (F_te.ts.max() - F_te.ts.min()) / 86400)
    for rn, flag in rules.items():
        tp = int((flag & (y == 1)).sum())
        fp = int((flag & (y == 0)).sum())
        base = {"bridge": name, "detector": rn, "view": "rule", "seed": 0, "domain": "in"}
        rows.append({**base, "metric": "recall", "value": tp / max(1, y.sum())})
        rows.append({**base, "metric": "precision", "value": tp / max(1, tp + fp)})
        rows.append({**base, "metric": "false_alarms_per_day", "value": fp / days})
        fa = first_alarm(F_te, flag.astype(float), 0.5)
        rows.append({**base, "metric": "usd_recall", "value": fa.get("usd_recall", np.nan)})
        rows.append({**base, "metric": "usd_before_alarm", "value": fa.get("usd_share_before_alarm", np.nan)})
        rows.append({**base, "metric": "usd_through_alarm_block",
                     "value": fa.get("usd_share_through_alarm_block", np.nan)})
        alarms.append({**base, "fpr_budget": np.nan, **fa})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/raw/XChainWatcher/cross-chain-rules-validator")
    ap.add_argument("--out", default="results/bridges")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--detectors", default="robust_z,ecod,ecod_max,ecod_max_lex,iforest,ae_mlp,ae_kan")
    ap.add_argument("--usd-mode", default="asof", choices=["asof", "matched_dataset", "legacy"])
    args = ap.parse_args()

    run = Path(args.out) / time.strftime("b1_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    dets = args.detectors.split(",")

    feats, splits, summaries = {}, {}, []
    for b in BRIDGES:
        st = load_bridge(b, args.root, usd_mode=args.usd_mode)
        summaries.append(summary(st))
        F = build_features(st.events)
        if args.usd_mode != "legacy":
            summaries[-1]["prefix_invariance_max_abs_diff"] = prefix_invariance(st.events, F, usd_mode=args.usd_mode)
            assert summaries[-1]["prefix_invariance_max_abs_diff"] < 1e-9, "raw->features pipeline is not causal"
        if args.usd_mode == "asof":
            e = st.events
            priced = e.price_time_s >= 0
            summaries[-1]["price_after_release_rows"] = int((e.price_time_s[priced] > e.ts[priced]).sum())
            assert summaries[-1]["price_after_release_rows"] == 0, "a price was used before it was available"
        F.to_parquet(run / f"features_{b}.parquet") if _has_pyarrow() else F.to_csv(run / f"features_{b}.csv", index=False)
        feats[b] = F
        splits[b] = split(F, st.attack_day)
    dump_json(summaries, run / "data_summary.json")

    rows, alarms, thr_rows = [], [], []
    for b, F in feats.items():
        tr, cal, te = splits[b]
        F_te = F[te].reset_index(drop=True)
        rule_baselines(b, F[tr], F_te, rows, alarms)
        for view, cols in VIEWS.items():
            Xtr, Xcal, Xte = F.loc[tr, cols].to_numpy(), F.loc[cal, cols].to_numpy(), F_te[cols].to_numpy()
            for d in dets:
                for seed in (range(args.seeds) if d in STOCHASTIC else [0]):
                    set_seed(seed)
                    m = DETECTORS[d](seed).fit(Xtr)
                    evaluate(b, d, view, seed, m.score(Xcal), m.score(Xte), F_te, rows, alarms, thr_rows=thr_rows)
                    print(f"[{b}] {view:10s} {d:9s} seed={seed} done", flush=True)

    # HB.3 transfer: fit on source bridge train, threshold on source calibration, test on target
    for src, tgt in [("ronin", "nomad"), ("nomad", "ronin")]:
        trs, cals, _ = splits[src]
        _, _, tet = splits[tgt]
        Fs, Ft = feats[src], feats[tgt]
        Ft_te = Ft[tet].reset_index(drop=True)
        for view in ["D", "X"]:
            cols = VIEWS[view]
            for d in dets:
                for seed in (range(args.seeds) if d in STOCHASTIC else [0]):
                    set_seed(seed)
                    m = DETECTORS[d](seed).fit(Fs.loc[trs, cols].to_numpy())
                    evaluate(tgt, d, view, seed, m.score(Fs.loc[cals, cols].to_numpy()),
                             m.score(Ft_te[cols].to_numpy()), Ft_te, rows, alarms,
                             domain=f"transfer_from_{src}", thr_rows=thr_rows)
                    print(f"[{src}->{tgt}] {view} {d} seed={seed} done", flush=True)

    met = pd.DataFrame(rows)
    met.to_csv(run / "metrics.csv", index=False)
    pd.DataFrame(alarms).to_csv(run / "first_alarm.csv", index=False)
    pd.DataFrame(thr_rows).to_csv(run / "thresholds.csv", index=False)
    agg = (met.groupby(["bridge", "domain", "view", "detector", "metric"])["value"]
              .agg(["mean", "std", "count"]).reset_index())
    agg.to_csv(run / "metrics_summary.csv", index=False)
    write_manifest(run, script=Path(__file__).name, config=vars(args),
                   data_files=input_files(args.root, args.usd_mode),
                   extra={"views": VIEWS, "fpr_budgets": FPR_BUDGETS})
    print("wrote", run)


def _has_pyarrow():
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
