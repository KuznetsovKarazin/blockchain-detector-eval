"""
K4: effect of the causal pool metadata on the real feature table.

Compares the feature table of an earlier run (whole-day token map of each V2
pool, runs up to v0.5.1) with the features recomputed from the current day
extracts (`causal_pairs`, pool known only from events up to the end of each
transaction). Also checks that the re-extracted day files are byte-identical
to the inputs recorded in the earlier run's manifest, so that any difference
comes from the feature code and not from the data.

    python scripts/tools/k4_feature_diff.py results/kan/k4_20261024_080035 --out <dir>

Output in <dir>: feature_diff_summary.json, feature_diff_rows.csv (one row per
changed transaction and feature, old and new value).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bal.features.defi_features import FEATURES   # noqa: E402
from k4_defi_kan import DERIVED, load_days        # noqa: E402


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(2**20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old_run")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rtol", type=float, default=1e-9)
    a = ap.parse_args()
    old_run, out = Path(a.old_run), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    # 1. inputs: re-extracted files vs the earlier manifest
    man = json.loads((old_run / "manifest.json").read_text())
    same, differ, missing = 0, [], []
    for rel, digest in man["data"].items():
        p = Path(rel)
        if not p.exists():
            missing.append(rel)
        elif sha256(p) == digest:
            same += 1
        else:
            differ.append(rel)

    # 2. features: old table vs recomputed
    old = pd.read_parquet(old_run / "features.parquet").set_index(["day", "hash"])
    new = load_days().set_index(["day", "hash"])
    keys_old, keys_new = set(old.index), set(new.index)
    common = old.index.intersection(new.index)
    o, n = old.loc[common, FEATURES].astype(float), new.loc[common, FEATURES].astype(float)
    close = np.isclose(o.to_numpy(), n.to_numpy(), rtol=a.rtol, atol=0, equal_nan=True)
    changed = pd.DataFrame(~close, index=common, columns=FEATURES)
    rows = changed.any(axis=1)
    y = old.loc[common, "y"]
    long = []
    for (day, h), r in changed[rows].iterrows():
        for c in FEATURES:
            if r[c]:
                long.append({"day": day, "hash": h, "y": int(y.loc[(day, h)]),
                             "stratum": old.loc[(day, h), "stratum"], "feature": c,
                             "old": float(o.loc[(day, h), c]), "new": float(n.loc[(day, h), c])})
    pd.DataFrame(long).to_csv(out / "feature_diff_rows.csv", index=False)
    summary = {
        "old_run": str(old_run), "derived": str(DERIVED),
        "inputs_identical_to_old_manifest": same, "inputs_different": differ, "inputs_missing": missing,
        "rows_old": len(old), "rows_new": len(new), "rows_only_old": len(keys_old - keys_new),
        "rows_only_new": len(keys_new - keys_old), "rows_compared": int(len(common)),
        "rows_changed": int(rows.sum()), "share_rows_changed": float(rows.mean()),
        "positives_changed": int((rows & (y == 1)).sum()), "positives": int((y == 1).sum()),
        "days_with_changes": int(changed[rows].index.get_level_values("day").nunique()),
        "changed_by_feature": {c: int(changed[c].sum()) for c in FEATURES},
        "changed_by_stratum": old.loc[common][rows].stratum.value_counts().to_dict(),
    }
    (out / "feature_diff_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
