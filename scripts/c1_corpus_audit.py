"""
C1  Corpus audit: duplication and label-revealing artefacts.

Research question
-----------------
How much of a typical smart-contract vulnerability benchmark can be "solved"
without learning vulnerability semantics, i.e. by memorising near-duplicate
code or label-revealing identifiers?

Measured
--------
* exact duplicates after comment stripping + identifier normalisation;
* near-duplicate components (Jaccard >= 0.8 on normalised 5-gram sets), within
  and across corpora, and how many cross the SolidiFI base-contract groups;
* SolidiFI identifier artefacts: share of buggy files whose injected identifiers
  contain the bug-type stem (re_ent, tmstmp, unchk, txorigin, TOD, ...).

Outputs: results/contracts/<run>/audit.json, near_dup_components.csv, manifest.json
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bal.data.contracts import CLASSES, label_files, load_all                                # noqa: E402
from bal.features.contract_features import exact_hash, near_duplicate_groups, normalised_text  # noqa: E402
from bal.utils.repro import dump_json, write_manifest                             # noqa: E402

# identifier stems used by SolidiFI's snippet templates (inspected manually in
# buggy_contracts/*; see docs/FINDINGS_CONTRACTS.md)
ARTEFACT_STEMS = {
    "reentrancy": r"re_?ent", "timestamp": r"tmstmp", "unchecked": r"unchk|bug_unchk|callnotchecked",
    "tx_origin": r"txorigin", "arithmetic": r"intou|vundflw", "tod": r"TOD\d|_tod",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/contracts")
    ap.add_argument("--jaccard", type=float, default=0.8)
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("c1_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)

    df = load_all()
    df["norm"] = df.source.map(normalised_text)
    df["exact"] = df.source.map(exact_hash)
    comp = near_duplicate_groups(df.norm.tolist(), threshold=a.jaccard)
    df["near_comp"] = comp

    res = {"n_files": {k: int(v) for k, v in df.dataset.value_counts().items()}}
    for ds, g in df.groupby("dataset"):
        res[f"{ds}_exact_dup_share"] = float(g.exact.duplicated(keep=False).mean())
        sizes = g.near_comp.map(g.near_comp.value_counts())
        res[f"{ds}_near_dup_share"] = float((sizes > 1).mean())
        res[f"{ds}_n_near_components"] = int(g.near_comp.nunique())
    # cross-corpus near duplicates
    cross = df.groupby("near_comp").dataset.nunique()
    multi = cross[cross > 1].index
    res["cross_corpus_components"] = int(len(multi))
    res["cross_corpus_files"] = {k: int(v) for k, v in df[df.near_comp.isin(multi)].dataset.value_counts().items()}
    # SolidiFI: do near-duplicate components span different base contracts?
    s = df[df.dataset == "solidifi"]
    span = s.groupby("near_comp").group.nunique()
    res["solidifi_components_spanning_groups"] = int((span > 1).sum())
    # labels within a near-dup component that disagree (label noise / regime conflict)
    conflicts = {}
    for c in CLASSES:
        lab = df.groupby("near_comp")[c].agg(["min", "max", "size"])
        conflicts[c] = int(((lab["min"] != lab["max"]) & (lab["size"] > 1)).sum())
    res["components_with_conflicting_labels"] = conflicts

    art = {}
    for c, stem in ARTEFACT_STEMS.items():
        pos = s[s[c] == 1]
        neg = s[s[c] == 0]
        rx = re.compile(stem, re.I)
        art[c] = {"pos_with_stem": float(pos.source.map(lambda t: bool(rx.search(t))).mean()) if len(pos) else None,
                  "neg_with_stem": float(neg.source.map(lambda t: bool(rx.search(t))).mean()) if len(neg) else None}
    res["solidifi_identifier_artefacts"] = art

    df[["dataset", "path", "group", "near_comp", "exact", *CLASSES]].to_csv(run / "near_dup_components.csv", index=False)
    dump_json(res, run / "audit.json")
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_sets={f"sources_{ds}": g.path for ds, g in df.groupby("dataset")}
                   | {"label_files": label_files()})
    print(pd.Series({k: v for k, v in res.items() if not isinstance(v, dict)}))
    print(art)
    print("wrote", run)


if __name__ == "__main__":
    main()
