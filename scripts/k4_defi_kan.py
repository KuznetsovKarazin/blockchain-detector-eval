"""
K4  Can a KAN flag flash-loan price-manipulation exploits among the
transactions of the same day, at an alarm budget per day, and do its edge
functions say why?

Data: incident days from `k4_extract_days.py` (DeFiHackLabs @23c7bd8 incidents,
AWS Ethereum transactions / logs / token transfers). Positives are the linked
attack transactions; negatives are all other flash-loan transactions of those
days (hard), transactions touching the same contracts (sampled) and a uniform
background sample, each with its sampling weight.

Hypotheses
----------
HK4.1  On transaction-level causal features, learned models rank the attack
       transaction near the top of its day, and a two-condition rule (flash
       loan AND large in-transaction pool price move) is a strong baseline.
HK4.2  A KAN is not better than a same-size MLP or a tree ensemble (K1-K3
       found no stable KAN advantage on Elliptic).
HK4.3  The KAN's edge functions for the key features agree with the model's
       measured response to perturbing those features (partial dependence) and
       with permutation importance.

Protocol (fixed before the run)
-------------------------------
* Temporal split by incident date: train <= 2023-12-31, validation 2024,
  test 2025-2026. Features are transformed by log1p (signed for profit);
  MLP / KAN input normalisation (quantile or robust) is chosen on validation
  AP, per model.
* Leave-protocol-out: 8 folds grouped by incident day (no incident in train
  and test), out-of-fold scores, threshold-free metrics only.
* Models: logistic regression, random forest, LightGBM, MLP [d, h, 1] with the
  parameter count of the KAN [d, 8, 1] (grid 5), the rule score
  `has_flash * max_price_move`. Neural models and trees: 5 seeds.
* AP = sklearn `average_precision_score` (non-interpolated). Reported on the
  kept sample (hard negatives at full weight) and population-weighted with
  the sampling weights, each with its base rate. Point estimate: mean over
  seeds of the per-seed AP; 90 % interval: bootstrap over test incident days
  (2,000 resamples), recomputing the same seed mean in every resample. The
  AP of the seed-averaged score is reported separately.
* Alarm budget: 1 and 10 alarms per day. The threshold is a conservative value
  among the observed validation scores whose weighted alarms per day on the
  validation days do not exceed the budget; the achieved rate is reported.
* Within-day rank of each attack: 1 + weighted number of that day's negatives
  that score higher (ties count half).
* Edge functions: first-layer functions of the KAN (seed 0) for the three
  features with the largest relevance, combined over hidden units with the
  mean slope of the second-layer function of each unit (linearised path to
  the logit; the plain sum is reported too, it ignores the sign set by the
  second layer); checked
  against partial dependence of the KAN logit on the validation rows (the
  feature swept over the same grid, other inputs unchanged) and permutation
  importance (AP drop on validation).

What this does NOT show: detection before execution (features are computed
from the mined transaction), native-ETH profit (no traces), Uniswap V4 flash
accounting, other chains, or a deployment-level false-alarm rate (the day set
is the set of incident days).

Usage
-----
    python scripts/k4_extract_days.py --workers 3
    python scripts/k4_defi_kan.py --seeds 5
    # models only, from the committed feature table (no AWS access needed):
    python scripts/k4_defi_kan.py --seeds 5 --features results/kan/k4_20261024_080035/features.parquet
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bal.data.defi import load_incidents                                   # noqa: E402
from bal.features.defi_features import FEATURES, day_features            # noqa: E402
from bal.models.kan import kan_param_count                                # noqa: E402
from bal.models.tabular import TorchClassifier, lightgbm, logreg, random_forest  # noqa: E402
from bal.utils.repro import dump_json, set_seed, write_manifest          # noqa: E402

DERIVED = Path("data/derived/k4")
TRAIN_END, VAL_END = "2023-12-31", "2024-12-31"
BUDGETS = (1, 10)
N_PERM = 20
LOG_COLS = ["n_flash", "flash_to_pool", "n_pools", "n_contracts", "n_logs", "n_tokens", "gas_used",
            "nonce", "value_eth", "max_price_move", "net_price_move"]


def load_days(only=None) -> pd.DataFrame:
    parts = []
    for d in sorted(DERIVED.glob("*/done.json")):
        if only and d.parent.name not in only:
            continue
        f = day_features(d.parent)
        f["day"] = d.parent.name
        parts.append(f)
    df = pd.concat(parts, ignore_index=True)
    df = df[df.receipt_status == 1].reset_index(drop=True)
    df["y"] = (df.stratum == "attack").astype(int)
    return df


def transform(df: pd.DataFrame) -> np.ndarray:
    X = df[FEATURES].astype(float).copy()
    for c in LOG_COLS:
        X[c] = np.log1p(X[c].clip(lower=0))
    X["profit_usd"] = np.sign(X.profit_usd) * np.log1p(np.abs(X.profit_usd))
    return X.to_numpy(np.float32)


def ap(y, s, w=None):
    return float(average_precision_score(y, s, sample_weight=w)) if y.sum() else np.nan


def budget_threshold(s_neg, w_neg, n_days, budget):
    """Lowest observed score t (conservative) with weighted alarms/day of s >= t within budget."""
    o = np.argsort(-s_neg, kind="stable")
    s, cw = s_neg[o], np.cumsum(w_neg[o]) / n_days
    u, first = np.unique(-s, return_index=True)          # distinct scores, descending
    last = np.r_[first[1:], len(s)] - 1
    ok = cw[last] <= budget
    if not ok[0]:
        return float(np.nextafter(s[0], np.inf)), 0.0
    k = np.flatnonzero(ok)[-1] if ok.all() else np.flatnonzero(~ok)[0] - 1
    return float(-u[k]), float(cw[last[k]])


def day_ranks(df, s):
    out = []
    for day, g in df.assign(s=s).groupby("day"):
        neg = g[g.y == 0]
        for r in g[g.y == 1].itertuples():
            higher = neg.weight[neg.s > r.s].sum() + 0.5 * neg.weight[neg.s == r.s].sum()
            out.append({"day": day, "hash": r.hash, "rank": 1 + float(higher), "n_day": float(g.weight.sum())})
    return pd.DataFrame(out)


def make(name, seed, h, prep="quantile"):
    if name == "logreg":
        return logreg(seed)
    if name == "rf":
        return random_forest(seed)
    if name == "lgbm":
        return lightgbm(seed)
    if name == "kan":
        return TorchClassifier("kan", hidden=(8,), grid=5, seed=seed, prep=prep)
    return TorchClassifier("mlp", hidden=(h,), seed=seed, prep=prep)


def boot_ci(df, ss, n=2000, seed=0, weighted=False):
    """90 % interval of the seed-mean AP, resampling days (the same days for every seed).

    `ss` is one score vector or a list of per-seed score vectors; the statistic
    is the mean over seeds of the AP, i.e. the same quantity as the point
    estimate `mean of per-seed AP`.
    """
    ss = [ss] if isinstance(ss, np.ndarray) and ss.ndim == 1 else list(ss)
    rng = np.random.default_rng(seed)
    days = df.day.unique()
    idx = {d: np.flatnonzero(df.day.to_numpy() == d) for d in days}
    y, w = df.y.to_numpy(), df.weight.to_numpy()
    vals = []
    for _ in range(n):
        ii = np.concatenate([idx[d] for d in rng.choice(days, len(days))])
        vals.append(np.mean([ap(y[ii], s[ii], w[ii] if weighted else None) for s in ss]))
    return [float(np.nanpercentile(vals, 5)), float(np.nanpercentile(vals, 95))]


def base_rate(df, weighted=False):
    """AP of a random ranking: the (weighted) share of attacks."""
    w = df.weight.to_numpy() if weighted else np.ones(len(df))
    return float((w * df.y.to_numpy()).sum() / w.sum())


def main():
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--seeds", type=int, default=5)
    ap_.add_argument("--folds", type=int, default=8)
    ap_.add_argument("--boot", type=int, default=2000)
    ap_.add_argument("--out", default="results/kan")
    ap_.add_argument("--days", nargs="*", help="smoke tests only: restrict to these days")
    ap_.add_argument("--features", help="features.parquet of an earlier run (skips the AWS extraction)")
    a = ap_.parse_args()
    run = Path(a.out) / time.strftime("k4_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)

    incs = load_incidents()
    df = pd.read_parquet(a.features) if a.features else load_days(a.days)
    X = transform(df)
    y = df.y.to_numpy()
    w = df.weight.to_numpy()
    tr = (df.day <= TRAIN_END).to_numpy()
    va = ((df.day > TRAIN_END) & (df.day <= VAL_END)).to_numpy()
    te = (df.day > VAL_END).to_numpy()
    d = X.shape[1]
    h = max(1, round((kan_param_count([d, 8, 1], 5) - 1) / (d + 2)))
    summary = {"n_rows": int(len(df)), "n_days": int(df.day.nunique()), "n_incidents": len(incs),
               "positives": {"train": int(y[tr].sum()), "val": int(y[va].sum()), "test": int(y[te].sum())},
               "days": {"train": int(df.day[tr].nunique()), "val": int(df.day[va].nunique()),
                        "test": int(df.day[te].nunique())},
               "strata": df.stratum.value_counts().to_dict(), "mlp_hidden": h}
    print(summary, flush=True)
    df[["day", "hash", "stratum", "weight", "y", *FEATURES]].to_parquet(run / "features.parquet", index=False)

    # ---- choose input normalisation for the neural models on validation ----
    prep = {}
    for m in ("mlp", "kan"):
        res = {}
        for p in ("quantile", "robust"):
            set_seed(0)
            mdl = make(m, 0, h, p).fit(X[tr], y[tr])
            res[p] = ap(y[va], mdl.predict_score(X[va]))
        prep[m] = max(res, key=lambda k: (np.nan_to_num(res[k], nan=-1), k == "quantile"))
        summary[f"prep_val_ap_{m}"] = res
    summary["prep"] = prep

    # ---- temporal split -----------------------------------------------------
    rows, scores, thr_rows, rank_rows = [], {}, [], []
    names = ["rule", "logreg", "rf", "lgbm", "mlp", "kan"]
    fit_tr = tr                                    # thresholds use validation days
    nd_va, nd_te = df.day[va].nunique(), df.day[te].nunique()
    for name in names:
        seeds = [0] if name in ("rule", "logreg") else range(a.seeds)
        for seed in seeds:
            if name == "rule":
                s = (df.has_flash * df.max_price_move).to_numpy(float)
            else:
                set_seed(seed)
                mdl = make(name, seed, h, prep.get(name, "quantile")).fit(X[fit_tr], y[fit_tr])
                s = mdl.predict_score(X).astype(float)
            scores[f"{name}_{seed}"] = s
            r = {"model": name, "seed": seed,
                 "val_ap": ap(y[va], s[va]), "test_ap": ap(y[te], s[te]),
                 "test_ap_weighted": ap(y[te], s[te], w[te]),
                 "test_roc_auc": float(roc_auc_score(y[te], s[te], sample_weight=w[te]))}
            for b in BUDGETS:
                t, achieved = budget_threshold(s[va & (y == 0)], w[va & (y == 0)], nd_va, b)
                al = s[te] >= t
                r[f"recall@{b}/day"] = float(al[y[te] == 1].mean())
                r[f"alarms_per_day@{b}/day"] = float(w[te][al & (y[te] == 0)].sum() / nd_te)
                thr_rows.append({"model": name, "seed": seed, "budget_per_day": b, "threshold": t,
                                 "achieved_val_alarms_per_day": achieved})
            rows.append(r)
            rk = day_ranks(df[te], s[te])
            rank_rows.append(rk.assign(model=name, seed=seed))
            print(r, flush=True)
    M = pd.DataFrame(rows)
    M.to_csv(run / "temporal_metrics.csv", index=False)
    pd.DataFrame(thr_rows).to_csv(run / "thresholds.csv", index=False)
    R = pd.concat(rank_rows)
    R.to_csv(run / "test_attack_ranks.csv", index=False)

    agg = M.groupby("model").agg(["mean", "std"]).drop(columns="seed", level=0)
    agg.columns = [f"{a_}_{b_}" for a_, b_ in agg.columns]
    ci = {}
    tdf = df[te].reset_index(drop=True)
    for name in names:
        per_seed = [v[te] for k, v in scores.items() if k.rsplit("_", 1)[0] == name]
        s_mean = np.mean(per_seed, axis=0)
        ci[name] = {"test_ap_ci90": boot_ci(tdf, per_seed, a.boot),
                    "test_ap_weighted_ci90": boot_ci(tdf, per_seed, a.boot, weighted=True),
                    "test_base_rate": base_rate(tdf), "test_base_rate_weighted": base_rate(tdf, weighted=True),
                    "seed_mean_score_test_ap": ap(tdf.y.to_numpy(), s_mean),
                    "median_day_rank": float(R[R.model == name].groupby("hash")["rank"].mean().median())}
    agg = agg.join(pd.DataFrame(ci).T)
    agg.to_csv(run / "temporal_summary.csv")
    print(agg.round(3).to_string(), flush=True)

    # ---- leave-protocol-out --------------------------------------------------
    g = df.day.to_numpy()
    lpo = []
    oof = {n: np.zeros(len(df)) for n in names}
    for name in names:
        seeds = [0] if name in ("rule", "logreg") else range(min(3, a.seeds))
        per_seed = []
        for seed in seeds:
            s_oof = np.zeros(len(df))
            if name == "rule":
                s_oof = (df.has_flash * df.max_price_move).to_numpy(float)
            else:
                for k, (i_tr, i_te) in enumerate(GroupKFold(a.folds).split(X, y, g)):
                    set_seed(seed)
                    mdl = make(name, seed, h, prep.get(name, "quantile")).fit(X[i_tr], y[i_tr])
                    s_oof[i_te] = mdl.predict_score(X[i_te])
            per_seed.append(s_oof)
        oof[name] = np.mean(per_seed, axis=0)
        rk = day_ranks(df, oof[name])
        # out-of-fold AP per seed, averaged over seeds (point and interval);
        # the AP of the seed-averaged OOF score is reported as `ensemble_ap`
        lpo.append({"model": name, "seeds": len(seeds),
                    "ap": float(np.mean([ap(y, s_) for s_ in per_seed])),
                    "ap_ci90": boot_ci(df, per_seed, a.boot),
                    "ap_weighted": float(np.mean([ap(y, s_, w) for s_ in per_seed])),
                    "ap_weighted_ci90": boot_ci(df, per_seed, a.boot, weighted=True),
                    "base_rate": base_rate(df), "base_rate_weighted": base_rate(df, weighted=True),
                    "ensemble_ap": ap(y, oof[name]),
                    "median_day_rank": float(rk["rank"].median()),
                    "share_rank_le_10": float((rk["rank"] <= 10).mean())})
        print(lpo[-1], flush=True)
    pd.DataFrame(lpo).to_csv(run / "leave_protocol_out.csv", index=False)

    # ---- KAN edge functions vs perturbation ----------------------------------
    import torch
    set_seed(0)
    km = make("kan", 0, h, prep["kan"]).fit(X[tr], y[tr])
    rel = km.net.input_relevance()
    top = list(np.argsort(-rel)[:3])
    xs, phi = km.net.edge_functions(0)
    Zv = km._prep(X[va])
    base_ap = ap(y[va], km.predict_score(X[va]))
    rng = np.random.default_rng(0)
    # permutation importance: one computation for every feature, N_PERM
    # permutations each (with 9 validation attacks one permutation is noisy)
    perm = np.zeros((N_PERM, d))
    for r_ in range(N_PERM):
        for j in range(d):
            Xp = X[va].copy()
            Xp[:, j] = Xp[rng.permutation(len(Xp)), j]
            perm[r_, j] = base_ap - ap(y[va], km.predict_score(Xp))
    perm_mean, perm_sd = perm.mean(0), perm.std(0, ddof=1)
    ef_rows, chk = [], []
    # second-layer slopes at the validation hidden activations: the sign and
    # weight with which each hidden unit passes a first-layer edge to the logit
    with torch.no_grad():
        hv = km.net.layers[0](torch.tensor(Zv, dtype=torch.float32))
        L2 = km.net.layers[1]
        slope = ((L2.edge_values(hv + 1e-3) - L2.edge_values(hv)) / 1e-3).mean(0)[0].numpy()   # (hidden,)
    for j in top:
        edge_raw = phi[:, j, :].sum(axis=0)
        edge = (slope[:, None] * phi[:, j, :]).sum(axis=0)   # linearised path to the logit
        pdp = []
        sub = Zv[rng.choice(len(Zv), min(5000, len(Zv)), replace=False)]
        for x in xs:
            Zs = sub.copy()
            Zs[:, j] = x
            with torch.no_grad():
                pdp.append(float(km.net(torch.tensor(Zs, dtype=torch.float32)).squeeze(-1).mean()))
        # raw feature value at each grid point (validation rows with the nearest transformed value)
        order = np.argsort(Zv[:, j])
        raw_at = df[FEATURES[j]].to_numpy()[va][order][np.clip(np.searchsorted(Zv[order, j], xs), 0, len(order) - 1)]
        chk.append({"feature": FEATURES[j], "relevance": float(rel[j]),
                    "spearman_edge_vs_partial_dependence": float(spearmanr(edge, pdp)[0]),
                    "spearman_unweighted_edge_sum_vs_pd": float(spearmanr(edge_raw, pdp)[0]),
                    "permutation_ap_drop_val": float(perm_mean[j]),
                    "permutation_ap_drop_val_sd": float(perm_sd[j])})
        ef_rows += [{"feature": FEATURES[j], "z": float(x), "raw_value": float(rv), "edge_path": float(e),
                     "edge_sum_unweighted": float(er), "partial_dependence_logit": p}
                    for x, rv, e, er, p in zip(xs, raw_at, edge, edge_raw, pdp)]
    summary["kan_relevance_vs_permutation_spearman"] = float(spearmanr(rel, perm_mean)[0])
    summary["kan_relevance"] = dict(zip(FEATURES, map(float, rel)))
    summary["kan_permutation_ap_drop_val"] = dict(zip(FEATURES, map(float, perm_mean)))
    summary["kan_permutation_ap_drop_val_sd"] = dict(zip(FEATURES, map(float, perm_sd)))
    summary["n_permutations"] = N_PERM
    pd.DataFrame(ef_rows).to_csv(run / "kan_edge_functions.csv", index=False)
    pd.DataFrame(chk).to_csv(run / "kan_edge_checks.csv", index=False)
    summary["edge_checks"] = chk

    np.savez_compressed(run / "scores.npz", **{k: v.astype(np.float32) for k, v in scores.items()},
                        **{f"lpo_{k}": v.astype(np.float32) for k, v in oof.items()})
    dump_json(summary, run / "summary.json")
    inc = pd.DataFrame([{"date": i.date, "name": i.name, "heading": i.heading, "poc": i.sol, "txs": ";".join(i.txs)}
                        for i in incs])
    found = df[df.y == 1][["day", "hash"]]
    inc["found"] = inc.txs.map(lambda t: sum(h in set(found.hash) for h in t.split(";")))
    inc.to_csv(run / "incidents.csv", index=False)
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(a.features)] if a.features else sorted(DERIVED.glob("*/*.parquet")),
                   extra={"defihacklabs_commit": "23c7bd83ccb4524972a9493617fcc8764ab6269b",
                          "aws": "s3://aws-public-blockchain/v1.0/eth/{transactions,logs,token_transfers}",
                          "split": {"train_end": TRAIN_END, "val_end": VAL_END}, "budgets_per_day": BUDGETS})
    print("wrote", run)


if __name__ == "__main__":
    main()
