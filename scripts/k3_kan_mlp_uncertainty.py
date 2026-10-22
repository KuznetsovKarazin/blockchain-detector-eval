"""
K3  Is the matched-size KAN better than, or equivalent to, the MLP?
A pre-declared follow-up analysis for the best K1 configuration (fixed before
it ran, but after K1 had looked at the same test period; seeds 0-2 repeat K1),
not a confirmatory preregistration.

K1 compared KAN (width 8, grid 5, quantile inputs) with a parameter-matched
MLP on 3 seeds and called the result a tie, although the F1 difference was
positive for all 3 seeds. Three seeds cannot support either claim. This script
fixes the analysis before running it.

Pre-declared protocol (written before any of these runs)
--------------------------------------------------------
* Models: KAN [d, 8, 1], grid 5, quantile prep; MLP [d, h, 1] with
  h = round((P_kan - 1) / (d + 2)), quantile prep; AF features; strict temporal
  split (train 1-30, val 31-34, test 35-49); threshold = max-F1 on validation.
* Seeds 0..9, paired (same seed for both models).
* Primary metric: test AUPRC. Secondary: test F1 at the validation threshold.
* Equivalence margin: |delta AUPRC| < 0.02 and |delta F1| < 0.03.
* Two uncertainty units are reported, because they answer different questions:
  (a) seed: paired t-interval over 10 seeds (training randomness only);
  (b) time: cluster bootstrap over the 15 observed test time steps of the
      seed-averaged difference (2,000 resamples). It keeps the objects of a
      step together, but not the dependence between neighbouring steps, and it
      does not create new histories: it is not an estimate of variability
      over future periods.
* Decision rule: "KAN better" if the 90 % interval of delta lies above 0 for
  both units; "equivalent" if both 90 % intervals lie inside the margin
  (two one-sided tests at 5 %); otherwise "inconclusive".

Usage
-----
    python scripts/k3_kan_mlp_uncertainty.py --data data/raw/elliptic --seeds 10
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import average_precision_score, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.elliptic import TEST_STEPS, TRAIN_STEPS, VAL_STEPS, load_elliptic  # noqa: E402
from bal.eval.metrics import threshold_at_val_f1                                # noqa: E402
from bal.models.kan import kan_param_count                                      # noqa: E402
from bal.models.tabular import TorchClassifier                                  # noqa: E402
from bal.utils.repro import dump_json, set_seed, write_manifest                 # noqa: E402

MARGIN = {"auprc": 0.02, "f1": 0.03}


def step_metrics(y, s, yhat, step):
    """Per test step: (n, positives, AP contribution parts) for block bootstrap."""
    return {t: (y[step == t], s[step == t], yhat[step == t]) for t in TEST_STEPS}


def pooled(parts, steps, metric):
    y = np.concatenate([parts[t][0] for t in steps])
    if metric == "auprc":
        return average_precision_score(y, np.concatenate([parts[t][1] for t in steps])) if y.sum() else np.nan
    return f1_score(y, np.concatenate([parts[t][2] for t in steps]), zero_division=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/elliptic")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--out", default="results/kan")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("k3_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    d = load_elliptic(a.data)
    X, y = d.features("AF"), d.y
    tr, va, te = d.mask(TRAIN_STEPS), d.mask(VAL_STEPS), d.mask(TEST_STEPS)
    dim = X.shape[1]
    h = max(1, round((kan_param_count([dim, 8, 1], 5) - 1) / (dim + 2)))
    yt, stp = y[te], d.step[te]

    rows, parts, saved = [], {}, {}
    for seed in range(a.seeds):
        for kind, kw in [("kan", dict(hidden=(8,), grid=5)), ("mlp", dict(hidden=(h,)))]:
            set_seed(seed)
            m = TorchClassifier(kind, seed=seed, prep="quantile", **kw).fit(X[tr], y[tr])
            s_va, s_te = m.predict_score(X[va]), m.predict_score(X[te])
            thr = threshold_at_val_f1(y[va], s_va)
            yhat = (s_te >= thr).astype(int)
            parts[(kind, seed)] = step_metrics(yt, s_te, yhat, stp)
            saved[f"{kind}_{seed}_val"], saved[f"{kind}_{seed}_test"] = s_va, s_te
            saved[f"{kind}_{seed}_thr"] = np.array(thr)
            rows.append({"model": kind, "seed": seed, "params": m.n_params(),
                         "test_auprc": average_precision_score(yt, s_te),
                         "test_f1": f1_score(yt, yhat, zero_division=0)})
            print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(run / "per_seed.csv", index=False)
    # scores and validation thresholds, no labels: rows follow the labelled
    # validation / test nodes of the dataset in file order
    lab = np.stack([np.r_[y[va], yt], np.r_[d.step[va], stp]]).astype(np.int64)
    np.savez_compressed(run / "scores.npz", **saved,
                        val_txid=d.tx_ids[va], test_txid=d.tx_ids[te],
                        labels_sha256=np.array(hashlib.sha256(lab.tobytes()).hexdigest()))

    piv = df.pivot(index="seed", columns="model")
    res = {"mlp_hidden": h, "margin": MARGIN, "seeds": a.seeds}
    rng = np.random.default_rng(0)
    steps = np.array(TEST_STEPS)
    for metric in ["auprc", "f1"]:
        diff = piv[f"test_{metric}"]["kan"] - piv[f"test_{metric}"]["mlp"]
        n = len(diff)
        tq = stats.t.ppf(0.95, n - 1)
        seed_ci = (float(diff.mean() - tq * diff.std(ddof=1) / np.sqrt(n)),
                   float(diff.mean() + tq * diff.std(ddof=1) / np.sqrt(n)))
        boots = []
        for _ in range(a.boot):
            bs = rng.choice(steps, len(steps), replace=True)
            boots.append(np.nanmean([pooled(parts[("kan", s)], bs, metric) - pooled(parts[("mlp", s)], bs, metric)
                                     for s in range(a.seeds)]))
        time_ci = (float(np.nanpercentile(boots, 5)), float(np.nanpercentile(boots, 95)))
        mg = MARGIN[metric]
        better = seed_ci[0] > 0 and time_ci[0] > 0
        equiv = all(-mg < lo and hi < mg for lo, hi in (seed_ci, time_ci))
        res[metric] = {"kan_mean": float(piv[f"test_{metric}"]["kan"].mean()),
                       "mlp_mean": float(piv[f"test_{metric}"]["mlp"].mean()),
                       "delta_mean": float(diff.mean()), "delta_by_seed": diff.round(4).tolist(),
                       "kan_wins": int((diff > 0).sum()),
                       "ci90_seed": seed_ci, "ci90_time_block_bootstrap": time_ci,
                       "decision": "KAN better" if better else ("equivalent" if equiv else "inconclusive")}
    dump_json(res, run / "decision.json")
    print(res)
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(a.data) / f for f in ("elliptic_txs_features.csv", "elliptic_txs_classes.csv")],
                   extra={"margin": MARGIN})
    print("wrote", run)


if __name__ == "__main__":
    main()
