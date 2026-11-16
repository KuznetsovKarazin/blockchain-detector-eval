"""
TV / X2, X3, X4, X6, A2, A3 on K4  Which part of a DeFi exploit detector
survives the next year: ranking, alarm threshold or monitor?

Data: the K4 feature table (`results/kan/k4_20261024_204829/features.parquet`,
40 attack transactions on 49 incident days) and the quiet days of
`tv3_quiet_days.py` (no DeFiHackLabs mainnet incident within +-3 days; only
negatives, flash stratum complete, background sample with weights).

Splits (by calendar year of the day)
------------------------------------
  t2024   train <= 2022, validation 2023, test 2024
  t2025   train <= 2023, validation 2024, test 2025-2026   (the K4 split)
  t2026   train <= 2024, validation 2025, test 2026
A2: the same splits with only the last two training years.
Models as in K4: rule, logistic regression (1 seed), RF, LightGBM, MLP, KAN
(5 seeds); MLP / KAN input normalisation chosen on validation AP.

Per split and model
-------------------
* ranking: test AP on incident days (sample and weighted), median day rank;
* thresholds (X3 / X4), budgets 1 and 10 alarms per day:
    fixed_incident  threshold on the validation incident days (as in K4);
    fixed_quiet     threshold on the validation-year quiet days;
    topk            the k highest-scoring transactions of each day (weighted);
  for each: recall on test attacks, alarms per day on test incident days and
  on test quiet days (the deployment-like estimate);
* monitors (X6, LightGBM seed 0): per test day, weighted mean score, weighted
  share above the fixed_incident threshold, median PSI of the features
  against the training background rows; compared with the attack's rank.
A3 (t2025 only): LightGBM and RF without the set-up features or without the
mechanism features (groups fixed in docs/PROTOCOLS_TV.md).

Usage
-----
    python scripts/tv4_k4_temporal.py --seeds 5
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bal.features.defi_features import FEATURES, day_features     # noqa: E402
from bal.models.kan import kan_param_count                        # noqa: E402
from bal.utils.repro import atomic_to_csv, dump_json, set_seed, write_manifest   # noqa: E402

_spec = importlib.util.spec_from_file_location("k4", ROOT / "scripts" / "k4_defi_kan.py")
K4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(K4)
_spec = importlib.util.spec_from_file_location("t4", ROOT / "scripts" / "t4_drift_monitor.py")
T4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T4)

K4_RUN = Path("results/kan/k4_20261024_204829")
QUIET = Path("data/derived/k4_quiet")
SPLITS = {"t2024": ("2022", "2023", ("2024",)),
          "t2025": ("2023", "2024", ("2025", "2026")),
          "t2026": ("2024", "2025", ("2026",))}
BUDGETS = (1, 10)
SETUP = ["nonce", "gas_used", "to_created_today", "n_contracts"]
MECHANISM = ["has_flash", "n_flash", "flash_to_pool", "max_price_move", "net_price_move", "n_pools"]


def load(k4_run: Path, quiet: Path) -> pd.DataFrame:
    inc = pd.read_parquet(k4_run / "features.parquet")
    inc["quiet"] = False
    parts = [inc]
    for p in sorted(quiet.glob("*/done.json")):
        f = day_features(p.parent)
        f = f[f.receipt_status == 1]
        f["day"], f["y"], f["quiet"] = p.parent.name, 0, True
        parts.append(f[["day", "hash", "stratum", "weight", "y", "quiet", *FEATURES]])
    return pd.concat(parts, ignore_index=True)


def topk_alarms(df, s, k):
    """Per day, the share of each row's weight that falls inside the k highest-scoring transactions.

    A background row of weight w stands for w transactions with its score, so the row that crosses
    the budget is counted only in part; attacks and flash rows have weight 1 (0 or 1).
    """
    w = df.weight.to_numpy()
    frac = np.zeros(len(df))
    for _, idx in df.groupby("day").indices.items():
        o = idx[np.argsort(-s[idx], kind="stable")]
        before = np.cumsum(w[o]) - w[o]
        frac[o] = np.clip((k - before) / w[o], 0, 1)
    return frac


def per_day_alarms(df, al):
    m = al * (df.y.to_numpy() == 0)
    return float((df.weight.to_numpy() * m).sum() / max(1, df.day.nunique()))


def evaluate(df, s, tr, va, te, name, seed, split, window, monitor=False, Xraw=None):
    y, w = df.y.to_numpy(), df.weight.to_numpy()
    q = df.quiet.to_numpy()
    va_i, va_q, te_i, te_q = va & ~q, va & q, te & ~q, te & q
    r = {"split": split, "window": window, "model": name, "seed": seed,
         "val_ap": K4.ap(y[va_i], s[va_i]), "test_ap": K4.ap(y[te_i], s[te_i]),
         "test_ap_weighted": K4.ap(y[te_i], s[te_i], w[te_i]),
         "test_attacks": int(y[te_i].sum()), "test_incident_days": int(df.day[te_i].nunique()),
         "test_quiet_days": int(df.day[te_q].nunique())}
    rk = K4.day_ranks(df[te_i], s[te_i])
    r["median_day_rank"] = float(rk["rank"].median()) if len(rk) else np.nan
    thr_rows = []
    for b in BUDGETS:
        for sname, mask in (("fixed_incident", va_i), ("fixed_quiet", va_q)):
            neg = mask & (y == 0)
            if not neg.any():
                continue
            t, achieved = K4.budget_threshold(s[neg], w[neg], df.day[mask].nunique(), b)
            al = s >= t
            thr_rows.append({**{k: r[k] for k in ("split", "window", "model", "seed")}, "budget": b,
                             "strategy": sname, "threshold": t, "achieved_val": achieved,
                             "recall": float(al[te_i & (y == 1)].mean()),
                             "alarms_per_day_incident": per_day_alarms(df[te_i], al[te_i]),
                             "alarms_per_day_quiet": per_day_alarms(df[te_q], al[te_q]) if te_q.any() else np.nan})
        al = topk_alarms(df, s, b)
        thr_rows.append({**{k: r[k] for k in ("split", "window", "model", "seed")}, "budget": b,
                         "strategy": "topk", "threshold": np.nan, "achieved_val": np.nan,
                         "recall": float(al[te_i & (y == 1)].mean()),          # attack rows: 0 or 1
                         "alarms_per_day_incident": per_day_alarms(df[te_i], al[te_i]),
                         "alarms_per_day_quiet": per_day_alarms(df[te_q], al[te_q]) if te_q.any() else np.nan})
    mon = []
    if monitor:
        neg = va_i & (y == 0)
        t1, _ = K4.budget_threshold(s[neg], w[neg], df.day[va_i].nunique(), 1)
        ref = tr & (df.stratum.to_numpy() == "background")
        for day, idx in df[te].groupby("day").indices.items():
            idx = np.flatnonzero(te)[idx]
            ww = w[idx]
            mon.append({"split": split, "day": day, "quiet": bool(q[idx[0]]),
                        "mean_score": float((s[idx] * ww).sum() / ww.sum()),
                        "share_above_t1": float((ww * (s[idx] >= t1)).sum() / ww.sum()),
                        "psi_median": float(np.median([T4.psi(Xraw[ref, j], Xraw[idx, j])
                                                       for j in range(Xraw.shape[1])])),
                        "attack_rank": float(rk[rk.day == day]["rank"].min()) if (rk.day == day).any() else np.nan})
    return r, thr_rows, mon


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--k4-run", default=str(K4_RUN))
    ap.add_argument("--quiet", default=str(QUIET))
    ap.add_argument("--models", default="rule,logreg,rf,lgbm,mlp,kan")
    ap.add_argument("--out", default="results/kan")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("tv4_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    df = load(Path(a.k4_run), Path(a.quiet))
    X = K4.transform(df)
    y = df.y.to_numpy()
    year = df.day.str[:4].to_numpy()
    d = X.shape[1]
    h = max(1, round((kan_param_count([d, 8, 1], 5) - 1) / (d + 2)))
    info = {"rows": int(len(df)), "incident_days": int(df.day[~df.quiet].nunique()),
            "quiet_days": sorted(df.day[df.quiet].unique().tolist()), "attacks": int(y.sum()), "mlp_hidden": h}
    dump_json(info, run / "data_summary.json")
    print(info, flush=True)

    rows, thr_rows, mon_rows, abl_rows = [], [], [], []
    for split, (tr_end, va_year, te_years) in SPLITS.items():
        for window in ("all", "last2"):
            lo = str(int(tr_end) - 1) if window == "last2" else "0000"
            tr = (year <= tr_end) & (year >= lo) & ~df.quiet.to_numpy()
            va = year == va_year
            te = np.isin(year, te_years)
            if y[tr].sum() == 0:
                continue
            prep = {}
            for m in ("mlp", "kan"):
                if m in a.models:
                    res = {}
                    for p in ("quantile", "robust"):
                        set_seed(0)
                        mdl = K4.make(m, 0, h, p).fit(X[tr], y[tr])
                        res[p] = K4.ap(y[va & ~df.quiet.to_numpy()], mdl.predict_score(X[va & ~df.quiet.to_numpy()]))
                    prep[m] = max(res, key=lambda k: (np.nan_to_num(res[k], nan=-1), k == "quantile"))
            for name in a.models.split(","):
                seeds = [0] if name in ("rule", "logreg") else range(a.seeds)
                for seed in seeds:
                    t0 = time.time()
                    if name == "rule":
                        s = (df.has_flash * df.max_price_move).to_numpy(float)
                    else:
                        set_seed(seed)
                        s = K4.make(name, seed, h, prep.get(name, "quantile")).fit(X[tr], y[tr]).predict_score(X)
                        s = np.asarray(s, float)
                    mon = name == "lgbm" and seed == 0 and window == "all"
                    r, th, mo = evaluate(df, s, tr, va, te, name, seed, split, window, mon, X)
                    r["prep"] = prep.get(name, "")
                    rows.append(r)
                    thr_rows += th
                    mon_rows += mo
                    print(split, window, name, seed, "test AP", round(r["test_ap"], 3),
                          round(time.time() - t0), "s", flush=True)
                    if split == "t2025" and window == "all" and name in ("rf", "lgbm"):
                        for gname, drop in (("no_setup", SETUP), ("no_mechanism", MECHANISM)):
                            keep = [i for i, f in enumerate(FEATURES) if f not in drop]
                            set_seed(seed)
                            s2 = np.asarray(K4.make(name, seed, h).fit(X[tr][:, keep], y[tr])
                                            .predict_score(X[:, keep]), float)
                            r2, _, _ = evaluate(df, s2, tr, va, te, name, seed, split, window)
                            abl_rows.append({"model": name, "seed": seed, "features": gname,
                                             "test_ap": r2["test_ap"], "full_test_ap": r["test_ap"],
                                             "median_day_rank": r2["median_day_rank"]})
            atomic_to_csv(pd.DataFrame(rows), run / "ranking.csv", index=False)
            atomic_to_csv(pd.DataFrame(thr_rows), run / "thresholds.csv", index=False)
            atomic_to_csv(pd.DataFrame(mon_rows), run / "monitors_by_day.csv", index=False)
            atomic_to_csv(pd.DataFrame(abl_rows), run / "ablation_a3.csv", index=False)
    R = pd.DataFrame(rows)
    print(R.groupby(["split", "window", "model"])[["test_ap", "val_ap", "median_day_rank"]].mean().round(3).to_string())
    T = pd.DataFrame(thr_rows)
    print(T.groupby(["split", "window", "model", "budget", "strategy"])[
        ["recall", "alarms_per_day_incident", "alarms_per_day_quiet"]].mean().round(2).to_string())
    if abl_rows:
        print(pd.DataFrame(abl_rows).groupby(["model", "features"])[["test_ap", "full_test_ap"]].mean().round(3))
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(a.k4_run) / "features.parquet"],
                   extra={"splits": SPLITS, "setup": SETUP, "mechanism": MECHANISM,
                          "quiet_dates": json.loads((Path(a.quiet) / "dates.json").read_text())})
    print("wrote", run)


if __name__ == "__main__":
    main()
