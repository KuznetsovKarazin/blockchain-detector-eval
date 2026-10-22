"""
C4  Static analyser vs learned detectors on equal terms.

C3 reports Slither's F1 from binary flags; C2 reports AUPRC of learned
scores. The two are not comparable. On the SmartBugs files, for every class
with a Slither detector, this script compares on the SAME files:

* AUPRC of Slither's binary flags vs AUPRC of each cross-corpus model score
  (trained on SolidiFI or DAppSCAN, never on SmartBugs);
* precision / recall of the model at Slither's own alarm budget, i.e. the top-k
  files by model score where k = number of files Slither flags;
* the same with Slither's non-analysed files counted as "no finding"
  (end-to-end) — the model scores every file.

Usage
-----
    python scripts/c4_slither_vs_ml.py --c2-run results/contracts/<c2 run> --c3-run results/contracts/<c3 run>
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

from bal.data.contracts import load_smartbugs   # noqa: E402
from bal.utils.repro import write_manifest   # noqa: E402

CHECKS = {"reentrancy": ["reentrancy-eth", "reentrancy-no-eth", "reentrancy-unlimited-gas",
                         "reentrancy-benign", "reentrancy-events"],
          "timestamp": ["timestamp"], "unchecked": ["unchecked-lowlevel", "unchecked-send"]}


def at_budget(y, s, k):
    """Precision / recall of the top-k files, independent of file order.

    Files tied with the k-th score are taken at random: the expected number of
    positives among them is returned, with the worst and best case over all
    tie orders. Returns (precision, recall, tp_min, tp_max).
    """
    y = np.asarray(y)
    s = np.asarray(s, dtype=float)
    if k == 0:
        return 0.0, 0.0, 0, 0
    v = np.sort(s)[::-1][k - 1]
    above, tied = s > v, s == v
    r = k - int(above.sum())                      # files still to take from the tie block
    tp_above = int(y[above].sum())
    pos_t, n_t = int(y[tied].sum()), int(tied.sum())
    tp = tp_above + r * pos_t / n_t
    tp_min = tp_above + max(0, r - (n_t - pos_t))
    tp_max = tp_above + min(r, pos_t)
    npos = max(1, int(y.sum()))
    return tp / k, tp / npos, tp_min, tp_max


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--c2-run", required=True)
    ap.add_argument("--c3-run", required=True)
    ap.add_argument("--out", default="results/contracts")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("c4_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    g = pd.read_parquet(Path(a.c2_run) / "groups.parquet")
    cross = pd.read_parquet(Path(a.c2_run) / "cross_scores.parquet")
    sl = pd.read_csv(Path(a.c3_run) / "slither_raw.csv")
    sl = sl[sl.dataset == "smartbugs"].copy()
    sl["detectors"] = sl.detectors.fillna("")
    # labels from the local SmartBugs copy (published runs carry no third-party labels)
    lab = load_smartbugs()[["path", *CHECKS]]
    sb = (g.loc[g.dataset == "smartbugs", ["file_id", "path"]].merge(lab, on="path", how="left")
           .merge(sl[["path", "status", "detectors"]], on="path", how="left"))
    assert sb[list(CHECKS)].notna().all().all(), "SmartBugs labels missing for some files"
    rows = []
    for cls, checks in CHECKS.items():
        y = sb[cls].to_numpy()
        flag = sb.detectors.map(lambda d: any(c in d.split(";") for c in checks)).to_numpy()
        k = int(flag.sum())
        p_s, r_s = (y[flag].mean() if k else 0.0), y[flag].sum() / y.sum()
        rows.append({"cls": cls, "detector": "slither", "train": "-", "seed": 0, "auprc": average_precision_score(y, flag),
                     "precision_at_k": p_s, "recall_at_k": r_s,
                     "tp_at_k_min": int(y[flag].sum()), "tp_at_k_max": int(y[flag].sum()), "k": k, "n_pos": int(y.sum()), "n": len(y)})
        sub = cross[(cross.test == "smartbugs") & (cross.cls == cls)]
        for (tr, rep, model, seed), c in sub.groupby(["train", "rep", "model", "seed"]):
            sc = pd.Series(c.score.to_numpy(), index=c.file_id.to_numpy()).reindex(sb.file_id).to_numpy()
            assert np.isfinite(sc).all(), "missing model scores"
            p, r, tmin, tmax = at_budget(y, sc, k)
            rows.append({"cls": cls, "detector": f"{rep}/{model}", "train": tr, "seed": seed,
                         "auprc": average_precision_score(y, sc), "precision_at_k": p, "recall_at_k": r,
                         "tp_at_k_min": tmin, "tp_at_k_max": tmax,
                         "k": k, "n_pos": int(y.sum()), "n": len(y)})
    df = pd.DataFrame(rows)
    df.to_csv(run / "slither_vs_ml.csv", index=False)
    summ = (df.groupby(["cls", "detector", "train"])[["auprc", "precision_at_k", "recall_at_k",
                                                    "tp_at_k_min", "tp_at_k_max"]]
              .mean().round(3).sort_values(["cls", "auprc"], ascending=[True, False]))
    summ.to_csv(run / "slither_vs_ml_summary.csv")
    print(summ.groupby(level=0).head(4).to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(a.c2_run) / "cross_scores.parquet", Path(a.c2_run) / "groups.parquet",
                               Path(a.c3_run) / "slither_raw.csv",
                               Path("data/raw/smartbugs-curated/vulnerabilities.json")])
    print("wrote", run)


if __name__ == "__main__":
    main()
