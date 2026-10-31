"""
TV  Decision rules HV1-HV5 of docs/PROTOCOLS_TV.md on the finished runs.

Reads the result folders only (no data, no labels) and writes the tables of
docs/FINDINGS_TEMPORAL_VALIDITY.md to <out>/: hv1.csv ... hv5.csv and
hv_summary.json. Bootstrap: 90 % intervals over test steps (Elliptic) with
the seed mean recomputed in each of 2,000 resamples.

Usage
-----
    python scripts/tv6_analysis.py --x1 results/transactions/tv1_20261030_x1 \
        --x2 results/transactions/tv2_20261030_x2 \
        --k4 results/kan/tv4_20261030_194723,results/kan/tv4_20261030_195926
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bal.utils.repro import write_manifest   # noqa: E402

SETUP = "nonce, gas_used, to_created_today, n_contracts"
MECH = "has_flash, n_flash, flash_to_pool, max_price_move, net_price_move, n_pools"


def boot_mean(per_step: pd.DataFrame, n=2000, seed=0):
    """per_step: rows = steps, columns = seeds; 90 % interval of the seed-mean step-mean."""
    rng = np.random.default_rng(seed)
    v = per_step.to_numpy()
    idx = rng.integers(0, len(v), (n, len(v)))
    m = np.nanmean(np.nanmean(v[idx], axis=2), axis=1)
    return float(np.nanmean(v)), float(np.quantile(m, 0.05)), float(np.quantile(m, 0.95))


def hv1(x1: Path):
    d = pd.read_csv(x1 / "metrics.csv")
    d = d[d.label == "wallet"]
    t = d.groupby(["protocol", "features", "model"]).auprc.agg(["mean", "std"]).round(4).reset_index()
    ap = d.groupby(["protocol", "features", "model"]).auprc.mean()
    out = {}
    for m in ("lgbm", "rf"):
        p3 = ap["P3_temporal_entity", "causal", m] - ap["P3_temporal_entity", "lifetime", m]
        p1 = ap["P1_random_rows", "causal", m] - ap["P1_random_rows", "lifetime", m]
        out[m] = {"P3_causal_minus_lifetime": round(p3, 4), "P1_causal_minus_lifetime": round(p1, 4),
                  "part1_P3": bool(p3 >= -0.02), "part2_P1_drop": bool(p1 < -0.02)}
    out["supported"] = out["lgbm"]["part1_P3"] and out["lgbm"]["part2_P1_drop"]
    return t, out


def hv2(x2: Path, k4: list[Path]):
    d = pd.read_csv(x2 / "rolling_long.csv")
    a = d[(d.kind == "ap") & (d.window == "all")]
    rows = []
    for (c, m), g in a.groupby(["cutoff", "model"]):
        mean, lo, hi = boot_mean(g.pivot(index="step", columns="seed", values="ap"))
        per = d[(d.kind == "ap_period") & (d.window == "all") & (d.cutoff == c) & (d.model == m)].ap.mean()
        rows.append({"domain": "elliptic", "period": f"c{c}", "model": m, "period_ap": round(per, 4),
                     "step_ap_mean": round(mean, 4), "step_ap_lo90": round(lo, 4), "step_ap_hi90": round(hi, 4)})
    for r in k4:
        k = pd.read_csv(r / "ranking.csv")
        k = k[k.window == "all"].groupby(["split", "model"]).test_ap.mean()
        for (s, m), v in k.items():
            rows.append({"domain": "k4", "period": s, "model": m, "period_ap": round(v, 4)})
    t = pd.DataFrame(rows)
    out = {}
    for dom, g in t.groupby("domain"):
        piv = g.pivot(index="period", columns="model", values="period_ap")
        taus = [kendalltau(piv.loc[p], piv.loc[q]).statistic for p, q in itertools.combinations(piv.index, 2)]
        best = piv.max(axis=1)
        trees_first = [piv.loc[p].idxmax() in ("lgbm", "rf") for p in piv.index]
        out[dom] = {"order_by_period": {p: list(piv.loc[p].sort_values(ascending=False).index) for p in piv.index},
                    "kendall_tau_mean": round(float(np.mean(taus)), 3), "kendall_tau_min": round(float(np.min(taus)), 3),
                    "trees_first_every_period": bool(all(trees_first)),
                    "best_ap_max_over_min": round(float(best.max() / best.min()), 2),
                    "supported": bool(all(trees_first) and np.mean(taus) >= 0.6 and best.max() / best.min() > 1.5)}
    return t, out


def hv3(x2: Path, k4: list[Path]):
    d = pd.read_csv(x2 / "rolling_long.csv")
    a = d[(d.kind == "alarm") & (d.window == "all")]
    e = a.groupby(["model", "budget", "strategy"])[["alarm_share", "recall"]].mean().reset_index()
    e["achieved_over_planned"] = e.alarm_share / e.budget
    e["domain"] = "elliptic"
    # the share of test steps where the fixed threshold overshoots by > 2x or raises (almost) nothing
    f = a[a.strategy == "fixed"].assign(r=lambda x: x.alarm_share / x.budget)
    over = f.groupby(["model", "budget"]).r.apply(lambda r: float((r > 2).mean())).rename("steps_over_2x")
    under = f.groupby(["model", "budget"]).r.apply(lambda r: float((r < 0.5).mean())).rename("steps_under_half")
    e = e.merge(over.reset_index(), on=["model", "budget"], how="left").merge(under.reset_index(), on=["model", "budget"], how="left")
    ks = pd.concat([pd.read_csv(r / "thresholds.csv") for r in k4])
    ks = ks[(ks.window == "all") & (ks.split == "t2025")]
    k = ks.groupby(["model", "budget", "strategy"])[["recall", "alarms_per_day_incident", "alarms_per_day_quiet"]].mean().reset_index()
    k["achieved_over_planned"] = k.alarms_per_day_quiet / k.budget
    k["domain"] = "k4_t2025"
    t = pd.concat([e, k], ignore_index=True).round(4)
    out = {}
    for dom, fixed_name in (("elliptic", "fixed"), ("k4_t2025", "fixed_incident")):
        g = t[t.domain == dom]
        fx = g[g.strategy == fixed_name].set_index(["model", "budget"])
        tk = g[g.strategy == "topk"].set_index(["model", "budget"])
        over2 = fx.achieved_over_planned > 2
        by_model_both = over2.groupby(level="model").all()
        ratio = (tk.recall / fx.recall).dropna()
        out[dom] = {"models_over_2x_at_both_budgets": int(by_model_both.sum()), "models": int(len(by_model_both)),
                    "part1": bool(by_model_both.mean() >= 0.5),
                    "topk_over_fixed_recall_min": round(float(ratio.min()), 3),
                    "topk_over_fixed_recall_median": round(float(ratio.median()), 3),
                    "part2": bool((ratio >= 0.5).all())}
    return t, out


def hv4(x2: Path, k4: list[Path]):
    d = pd.read_csv(x2 / "rolling_long.csv")
    m = d[d.kind == "monitor"][["cutoff", "step", "em_prior", "true_prior", "mean_score", "psi_median", "domain_auc"]]
    ap = d[(d.kind == "ap") & (d.model == "lgbm") & (d.seed == 0) & (d.window == "all")][["cutoff", "step", "ap"]]
    m = m.merge(ap, on=["cutoff", "step"])
    rows, out = [], {"elliptic": {}, "k4": {}}
    for c in ("psi_median", "domain_auc", "mean_score", "em_prior"):
        rho = spearmanr(m[c], m.ap).statistic
        rows.append({"domain": "elliptic", "monitor": c, "target": "step AP (lgbm s0)", "spearman": round(float(rho), 3)})
        out["elliptic"][c] = round(float(rho), 3) if np.isfinite(rho) else None
    # output monitor misreading: AP at the step at most half the validation AP while the estimated share
    # falls against the previous step (test steps 25-49 do not overlap between cut-offs)
    va = d[(d.kind == "ap_period") & (d.model == "lgbm") & (d.seed == 0) & (d.window == "all")][["cutoff", "val_ap"]]
    m = m.merge(va, on="cutoff").sort_values("step").reset_index(drop=True)
    mis = m[(m.ap <= 0.5 * m.val_ap) & (m.em_prior < m.em_prior.shift(1))]
    out["elliptic"]["steps_em_below_half_true"] = m.loc[m.em_prior < 0.5 * m.true_prior, "step"].tolist()
    out["elliptic"]["misread_steps"] = mis[["cutoff", "step", "ap", "val_ap", "em_prior", "true_prior"]].round(4).to_dict("records")
    out["elliptic"]["em_vs_true_spearman"] = round(float(spearmanr(m.em_prior, m.true_prior).statistic), 3)
    k = pd.read_csv(k4[0] / "monitors_by_day.csv")
    ki = k[~k.quiet].dropna(subset=["attack_rank"])
    for c in ("psi_median", "mean_score", "share_above_t1"):
        rho = spearmanr(ki[c], -ki.attack_rank).statistic
        rows.append({"domain": "k4", "monitor": c, "target": "minus attack rank (lgbm)", "spearman": round(float(rho), 3)})
        out["k4"][c] = round(float(rho), 3) if np.isfinite(rho) else None
    q = k.groupby("quiet")[["psi_median", "mean_score", "share_above_t1"]].mean().round(6)
    out["k4"]["quiet_vs_incident_means"] = {str(i): r.to_dict() for i, r in q.iterrows()}
    inp = [abs(v) for c, v in out["elliptic"].items() if c in ("psi_median", "domain_auc") and v is not None]
    out["input_uninformative"] = bool(all(v < 0.3 for v in inp)) if inp else True
    out["output_misread"] = bool(len(mis) > 0)
    return pd.DataFrame(rows), out


def hv5(k4: list[Path]):
    a = pd.read_csv(k4[0] / "ablation_a3.csv")
    t = a.groupby(["model", "features"])[["test_ap", "full_test_ap", "median_day_rank"]].mean().round(4).reset_index()
    out = {}
    for m, g in t.groupby("model"):
        g = g.set_index("features")
        full = float(g.full_test_ap.iloc[0])
        out[m] = {"full": round(full, 4), "drop_no_setup": round(full - g.loc["no_setup", "test_ap"], 4),
                  "drop_no_mechanism": round(full - g.loc["no_mechanism", "test_ap"], 4)}
    out["supported"] = out["lgbm"]["drop_no_setup"] > out["lgbm"]["drop_no_mechanism"]
    out["setup"], out["mechanism"] = SETUP, MECH
    return t, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--x1", required=True)
    ap.add_argument("--x2", required=True)
    ap.add_argument("--k4", required=True, help="comma-separated tv4 run folders, the first one with A3 and monitors")
    ap.add_argument("--out", default="results/tv_analysis")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    k4 = [Path(p) for p in a.k4.split(",")]
    summary = {}
    for name, (t, s) in {"hv1": hv1(Path(a.x1)), "hv2": hv2(Path(a.x2), k4), "hv3": hv3(Path(a.x2), k4),
                         "hv4": hv4(Path(a.x2), k4), "hv5": hv5(k4)}.items():
        t.to_csv(out / f"{name}.csv", index=False)
        summary[name] = s
    (out / "hv_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=1, default=str))
    write_manifest(out, script=Path(__file__).name, config=vars(a), data_files=[])


if __name__ == "__main__":
    main()
