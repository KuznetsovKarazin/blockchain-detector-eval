"""
TV round 2 / A3b, X4b on K4 (t2025: train <= 2023, validation 2024, test
2025-26); docs/PROTOCOLS_TV.md, "Round 2".

A3b  LightGBM and RF, 5 seeds, retrained without the preparation features
     (nonce, to_created_today) or without the execution features (gas_used,
     n_contracts). Frozen check: the full model scores the test attacks with
     nonce and to_created_today taken from a random background row of the
     same day (20 draws); median within-day rank and per-day top-k recall.
X4b  Alarms per day of the fixed thresholds by stratum (flash, protocol,
     background) on the test quiet and incident days, and 90 % intervals from
     2,000 resamples of the background rows within each day, in the
     validation year (threshold re-fitted) and the test years together
     (logistic regression, RF, LightGBM; seed 0).

    python scripts/tv9_k4_round2.py
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bal.features.defi_features import FEATURES                   # noqa: E402
from bal.models.kan import kan_param_count                        # noqa: E402
from bal.utils.repro import atomic_to_csv, dump_json, set_seed, write_manifest   # noqa: E402

_spec = importlib.util.spec_from_file_location("tv4", ROOT / "scripts" / "tv4_k4_temporal.py")
TV4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TV4)
K4 = TV4.K4

PREP = ["nonce", "to_created_today"]
EXEC = ["gas_used", "n_contracts"]
BUDGETS = (1, 10)


def rank_and_topk(df, s, te_i, budgets=BUDGETS):
    rk = K4.day_ranks(df[te_i], s[te_i])
    out = {"median_day_rank": float(rk["rank"].median())}
    al = {b: TV4.topk_alarms(df, s, b) for b in budgets}
    att = te_i & (df.y.to_numpy() == 1)
    for b in budgets:
        out[f"topk{b}_recall"] = float(al[b][att].mean())
    return out


def alarms_by_stratum(df, al, mask):
    """Alarms per day on the rows of mask (negatives only), by stratum."""
    y, w, st = df.y.to_numpy(), df.weight.to_numpy(), df.stratum.to_numpy()
    nd = max(1, df.day[mask].nunique())
    m = mask & (y == 0) & al
    out = {k: float(w[m & (st == k)].sum() / nd) for k in ("flash", "protocol", "background")}
    out["total"] = sum(out.values())
    # the bootstrap cannot bound background rows that the sample never drew: Clopper-Pearson 90 %
    # interval of the share of background transactions over the threshold, times background per day
    k, nb = int((m & (st == "background")).sum()), int((mask & (y == 0) & (st == "background")).sum())
    per_day = float(w[mask & (y == 0) & (st == "background")].sum() / nd)
    lo = beta.ppf(0.05, k, nb - k + 1) if k > 0 else 0.0
    hi = beta.ppf(0.95, k + 1, nb - k)
    out.update({"background_rows_over": k, "background_rows": nb, "background_per_day": per_day,
                "background_cp_lo": float(lo * per_day), "background_cp_hi": float(hi * per_day)})
    return out


def boot_alarms(df, s, va_mask, te_q, te_i, b, n_boot, rng):
    """Resample background rows within each day (validation and test); refit the threshold."""
    y, w, st, day = df.y.to_numpy(), df.weight.to_numpy(), df.stratum.to_numpy(), df.day.to_numpy()
    bg = st == "background"
    groups = {}
    for name, mask in (("va", va_mask & (y == 0)), ("q", te_q & (y == 0)), ("i", te_i & (y == 0))):
        fixed = np.flatnonzero(mask & ~bg)
        per_day = [np.flatnonzero(mask & bg & (day == d)) for d in np.unique(day[mask])]
        groups[name] = (fixed, per_day, max(1, len(np.unique(day[mask]))))
    res = []
    for _ in range(n_boot):
        pick = {}
        for name, (fixed, per_day, nd) in groups.items():
            pick[name] = np.r_[fixed, *[rng.choice(ix, len(ix), replace=True) for ix in per_day if len(ix)]]
        va = pick["va"]
        t, _ = K4.budget_threshold(s[va], w[va], groups["va"][2], b)
        res.append({k: float(w[pick[k]][s[pick[k]] >= t].sum() / groups[k][2]) for k in ("q", "i")})
    r = pd.DataFrame(res)
    return {f"{k}_{q}": float(r[k].quantile(q)) for k in ("q", "i") for q in (0.05, 0.5, 0.95)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--draws", type=int, default=20)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--k4-run", default=str(TV4.K4_RUN))
    ap.add_argument("--quiet", default=str(TV4.QUIET))
    ap.add_argument("--out", default="results/kan")
    ap.add_argument("--run", help="existing run folder: finished (model, seed) parts are skipped")
    a = ap.parse_args()
    run = Path(a.run) if a.run else Path(a.out) / time.strftime("tv9_%Y%m%d_%H%M%S")
    (run / "parts").mkdir(parents=True, exist_ok=True)
    kinds = ("ablation_a3b", "frozen_swap", "alarms_by_stratum", "alarms_bootstrap")
    df = TV4.load(Path(a.k4_run), Path(a.quiet))
    X = K4.transform(df)
    y, q = df.y.to_numpy(), df.quiet.to_numpy()
    year = df.day.str[:4].to_numpy()
    tr_end, va_year, te_years = TV4.SPLITS["t2025"]
    tr = (year <= tr_end) & ~q
    va = year == va_year
    te = np.isin(year, te_years)
    va_i, va_q, te_i, te_q = va & ~q, va & q, te & ~q, te & q
    h = max(1, round((kan_param_count([X.shape[1], 8, 1], 5) - 1) / (X.shape[1] + 2)))
    bg_te = {d: np.flatnonzero(te & (df.stratum.to_numpy() == "background") & (df.day.to_numpy() == d))
             for d in df.day[te].unique()}
    att = np.flatnonzero(te_i & (y == 1))
    cols = [FEATURES.index(c) for c in PREP]

    for name in ("logreg", "rf", "lgbm"):
        seeds = [0] if name == "logreg" else range(a.seeds)
        for seed in seeds:
            if (run / "parts" / f"{name}_s{seed}.done").exists():
                continue
            abl, frozen, strat, boot = [], [], [], []
            rng = np.random.default_rng([seed, ("logreg", "rf", "lgbm").index(name)])   # same draws on resume
            t0 = time.time()
            set_seed(seed)
            mdl = K4.make(name, seed, h).fit(X[tr], y[tr])
            s = np.asarray(mdl.predict_score(X), float)
            full = {"test_ap": K4.ap(y[te_i], s[te_i]), **rank_and_topk(df, s, te_i)}
            if name != "logreg":
                abl.append({"model": name, "seed": seed, "features": "full", **full})
                for gname, drop in (("no_preparation", PREP), ("no_execution", EXEC)):
                    keep = [i for i, f in enumerate(FEATURES) if f not in drop]
                    set_seed(seed)
                    s2 = np.asarray(K4.make(name, seed, h).fit(X[tr][:, keep], y[tr])
                                    .predict_score(X[:, keep]), float)
                    abl.append({"model": name, "seed": seed, "features": gname,
                                "test_ap": K4.ap(y[te_i], s2[te_i]), **rank_and_topk(df, s2, te_i)})
                for r in range(a.draws):
                    Xa = X[att].copy()
                    for k, i in enumerate(att):
                        j = rng.choice(bg_te[df.day.iat[i]])
                        Xa[k, cols] = X[j, cols]
                    s3 = s.copy()
                    s3[att] = np.asarray(mdl.predict_score(Xa), float)
                    frozen.append({"model": name, "seed": seed, "draw": r, "full_test_ap": full["test_ap"],
                                   "full_median_day_rank": full["median_day_rank"],
                                   "test_ap": K4.ap(y[te_i], s3[te_i]), **rank_and_topk(df, s3, te_i)})
            if seed == 0:
                for b in BUDGETS:
                    for sname, mask in (("fixed_incident", va_i), ("fixed_quiet", va_q)):
                        neg = mask & (y == 0)
                        t, _ = K4.budget_threshold(s[neg], df.weight.to_numpy()[neg], df.day[mask].nunique(), b)
                        al = s >= t
                        for tname, tm in (("quiet", te_q), ("incident", te_i)):
                            strat.append({"model": name, "budget": b, "strategy": sname, "test_days": tname,
                                          **alarms_by_stratum(df, al, tm)})
                        boot.append({"model": name, "budget": b, "strategy": sname,
                                     **boot_alarms(df, s, mask, te_q, te_i, b, a.boot, rng)})
            print(name, seed, "AP", round(full["test_ap"], 3), round(time.time() - t0), "s", flush=True)
            for kind, rows in zip(kinds, (abl, frozen, strat, boot)):
                if rows:
                    atomic_to_csv(pd.DataFrame(rows), run / "parts" / f"{kind}__{name}_s{seed}.csv", index=False)
            (run / "parts" / f"{name}_s{seed}.done").touch()
    tabs = {k: pd.concat([pd.read_csv(p) for p in sorted((run / "parts").glob(f"{k}__*.csv"))], ignore_index=True)
            for k in kinds}
    for k, t in tabs.items():
        atomic_to_csv(t, run / f"{k}.csv", index=False)
    abl, frozen, strat, boot = (tabs[k] for k in kinds)
    A = pd.DataFrame(abl).groupby(["model", "features"]).mean(numeric_only=True).drop(columns="seed").round(3)
    F = pd.DataFrame(frozen).groupby("model").mean(numeric_only=True).drop(columns=["seed", "draw"]).round(3)
    print(A.to_string(), F.to_string(), pd.DataFrame(strat).round(2).to_string(),
          pd.DataFrame(boot).round(2).to_string(), sep="\n\n")
    dump_json({"ablation": A.reset_index().to_dict("records"), "frozen": F.reset_index().to_dict("records"),
               "preparation": PREP, "execution": EXEC}, run / "summary.json")
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(a.k4_run) / "features.parquet"], extra={"split": "t2025"})
    print("wrote", run)


if __name__ == "__main__":
    main()
