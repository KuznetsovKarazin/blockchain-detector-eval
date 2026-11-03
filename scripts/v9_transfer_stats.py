"""V9  Random-ranking control and cluster bootstrap for the frozen transfer of V3.

Prompted by an external review (protocol amendment 5). For every (class, source,
target) of V3 and for the frozen candidate and the target-best (oracle) candidate:

* point estimate: mean over seeds of the per-seed AP (as in V3);
* random-ranking control: the AP of a uniformly random order has expectation
  E[AP_rand] > prevalence for finite n; it is estimated from label permutations.
  The permutation p-value is P(AP_perm >= AP_obs), with the same permutation
  applied to every seed so that the statistic (seed-mean AP) is the same as the
  point estimate. Two nulls: files exchangeable (`p_perm`), and labels permuted
  only within groups (`p_perm_within`; DAppSCAN projects, SolidiFI base
  contracts; SmartBugs files are their own groups, so no within-group test);
* 95% interval: cluster bootstrap over groups (DAppSCAN projects, SolidiFI base
  contracts, SmartBugs files), recomputing the seed-mean AP in every resample, so
  that interval and point estimate refer to the same quantity.

Usage
-----
    python scripts/v9_transfer_stats.py --v3 results/contracts/v3_20261030_182906
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bal.data.contracts import load_all                     # noqa: E402
from bal.utils.repro import atomic_to_csv, write_manifest   # noqa: E402


def seed_mean_ap(y: np.ndarray, S: np.ndarray) -> float:
    """y: (n,), S: (seeds, n)."""
    return float(np.mean([average_precision_score(y, s) for s in S]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v3", required=True)
    ap.add_argument("--out", default="results/contracts")
    ap.add_argument("--perms", type=int, default=5000)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("v9_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)

    sel = pd.read_csv(Path(a.v3) / "v3_selection.csv")
    sc = pd.read_parquet(Path(a.v3) / "target_scores.parquet")
    groups = load_all().group.to_numpy()
    rows = []
    for r in sel.itertuples():
        for role, cand in (("frozen", r.candidate), ("oracle", r.oracle)):
            m = sc[(sc.cls == r.cls) & (sc.source == r.source) & (sc.target == r.target) & (sc.candidate == cand)]
            W = m.pivot(index="file_id", columns="seed", values="score")
            y = m.groupby("file_id").y.first().loc[W.index].to_numpy().astype(int)
            S = W.to_numpy().T.astype(float)
            g = groups[W.index.to_numpy()]
            rng = np.random.default_rng(a.seed)
            obs = seed_mean_ap(y, S)
            # nulls
            null, null_w = np.empty(a.perms), np.empty(a.perms)
            gi = pd.factorize(g)[0]
            order = np.argsort(gi, kind="stable")
            bounds = np.flatnonzero(np.diff(gi[order])) + 1
            blocks = np.split(order, bounds)
            within = any(len(b) > 1 for b in blocks)
            for k in range(a.perms):
                null[k] = seed_mean_ap(rng.permutation(y), S)
                if within:
                    yw = y.copy()
                    for b in blocks:
                        if len(b) > 1:
                            yw[b] = y[rng.permutation(b)]
                    null_w[k] = seed_mean_ap(yw, S)
            # cluster bootstrap
            ug = np.unique(gi)
            members = {u: np.flatnonzero(gi == u) for u in ug}
            bs = []
            for _ in range(a.boot):
                pick = rng.choice(ug, len(ug), replace=True)
                i = np.concatenate([members[u] for u in pick])
                if y[i].min() != y[i].max():
                    bs.append(seed_mean_ap(y[i], S[:, i]))
            rows.append({"cls": r.cls, "source": r.source, "target": r.target, "role": role, "candidate": cand,
                         "n": len(y), "n_pos": int(y.sum()), "n_groups": len(ug), "seeds": S.shape[0],
                         "prevalence": y.mean(), "auprc": obs, "e_ap_random": null.mean(),
                         "random_q95": float(np.quantile(null, 0.95)), "lift": obs / null.mean(),
                         "p_perm": (1 + (null >= obs).sum()) / (1 + a.perms),
                         "p_perm_within": (1 + (null_w >= obs).sum()) / (1 + a.perms) if within else np.nan,
                         "ci_lo_cluster": float(np.quantile(bs, 0.025)), "ci_hi_cluster": float(np.quantile(bs, 0.975))})
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rows[-1].items()}, flush=True)
    R = pd.DataFrame(rows)
    atomic_to_csv(R, run / "v9_transfer_stats.csv", index=False)
    write_manifest(run, script=Path(__file__).name, config=vars(a), data_sets={}, extra={"v3": a.v3})
    print(f"wrote {run}")


if __name__ == "__main__":
    main()
