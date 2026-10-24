#!/usr/bin/env python3
"""Inspect existing C1/C2 outputs without training or changing any split.

Uses only the standard library. This is a readiness audit of historical
results, not a fixed-test experiment or a causal estimate of leakage.
"""
import argparse
import csv
import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


SOURCE_COMMIT = "2c2c7723cb9fa42ff46fb6f252652056a74f9223"
REQUIRED = ("dataset", "cls", "protocol", "seed", "fold", "n_train",
            "n_test", "pos_train", "pos_test")
COUNTS = ("seed", "fold", "n_train", "n_test", "pos_train", "pos_test")


def source_info(path):
    data = path.read_bytes()
    return {"filename": path.name, "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folds", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True,
                        help="C1 corpus audit.json")
    parser.add_argument("--manifest", type=Path, required=True,
                        help="C2 run manifest.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-commit", default=SOURCE_COMMIT,
                        help="Commit from which the historical files were read")
    parser.add_argument("--handoff-date", default="2026-10-25")
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    corpus_sizes = audit["n_files"]
    with args.folds.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not set(REQUIRED).issubset(reader.fieldnames or []):
            parser.error("folds CSV lacks required columns")
        rows = [{key: int(row[key]) if key in COUNTS else row[key]
                 for key in REQUIRED} for row in reader]
    if not rows:
        parser.error("folds CSV has no data")
    identities = [(r["dataset"], r["cls"], r["protocol"], r["seed"], r["fold"])
                  for r in rows]
    if len(set(identities)) != len(identities):
        parser.error("duplicate dataset/class/protocol/seed/fold rows")
    for row in rows:
        if row["dataset"] not in corpus_sizes:
            parser.error("fold dataset missing from C1 corpus inventory")
        if any(row[key] < 0 for key in COUNTS):
            parser.error("negative count or identifier")
        if row["pos_train"] > row["n_train"] or row["pos_test"] > row["n_test"]:
            parser.error("positive count exceeds split size")
        if row["n_train"] + row["n_test"] > corpus_sizes[row["dataset"]]:
            parser.error("train plus test count exceeds source corpus size")
    rows.sort(key=lambda r: tuple(r[key] for key in REQUIRED[:5]))

    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["dataset"], row["cls"], row["protocol"])].append(row)
    protocol_rows = []
    for (dataset, cls, protocol), selected in sorted(grouped.items()):
        item = {"dataset": dataset, "cls": cls, "protocol": protocol,
                "n_rows": len(selected),
                "n_seeds": len({r["seed"] for r in selected}),
                "fold_ids": ",".join(map(str, sorted({r["fold"] for r in selected})))}
        for key in ("n_train", "n_test", "pos_train", "pos_test"):
            values = [r[key] for r in selected]
            item[key + "_min"] = min(values)
            item[key + "_median"] = statistics.median(values)
            item[key + "_max"] = max(values)
        protocol_rows.append(item)

    protocols = sorted({r["protocol"] for r in rows})
    dapp_safe = [r for r in rows if r["dataset"] == "dappscan" and r["protocol"] == "safe"]
    giant = None
    if dapp_safe:
        maximum = max(r["n_test"] for r in dapp_safe)
        affected = [r for r in dapp_safe if r["n_test"] == maximum]
        giant = {
            "corpus_n_files": corpus_sizes["dappscan"],
            "largest_test_n": maximum,
            "largest_test_fraction": maximum / corpus_sizes["dappscan"],
            "corresponding_train_sizes": sorted({r["n_train"] for r in affected}),
            "affected_class_seed_fold_rows": len(affected),
            "affected_rows": affected,
            "all_safe_train_sizes": sorted({r["n_train"] for r in dapp_safe}),
            "interpretation": "The joint project/clone protocol has a dominant test fold and a much smaller training pool. Counts alone do not establish pairwise cloning or identify a causal leakage effect."
        }

    # Compare multisets of training sizes, not arbitrary fold numbers. Matching
    # sizes does not give matching exposure: a small-training fold can account
    # for different proportions of the out-of-fold test population.
    matched_pairs = []
    comparison_keys = sorted({(r["dataset"], r["cls"], r["seed"]) for r in rows})
    for dataset, cls, seed in comparison_keys:
        pair = {p: [r for r in rows if (r["dataset"], r["cls"], r["seed"], r["protocol"])
                   == (dataset, cls, seed, p)] for p in ("random_matched", "safe")}
        if not all(pair.values()):
            continue
        item = {"dataset": dataset, "cls": cls, "seed": seed}
        size_sets = {}
        for protocol, selected in pair.items():
            sizes = sorted(r["n_train"] for r in selected)
            size_sets[protocol] = sizes
            minimum = min(sizes)
            total = sum(r["n_test"] for r in selected)
            affected = sum(r["n_test"] for r in selected if r["n_train"] == minimum)
            item[protocol + "_training_sizes"] = json.dumps(sizes)
            item[protocol + "_minimum_train_n"] = minimum
            item[protocol + "_test_n_from_minimum_train"] = affected
            item[protocol + "_total_test_n"] = total
            item[protocol + "_test_fraction_from_minimum_train"] = affected / total
        item["training_size_multisets_equal"] = size_sets["random_matched"] == size_sets["safe"]
        matched_pairs.append(item)

    summary = {
        "schema": "existing_contract_split_readiness_v1",
        "audit_kind": "read_only_reanalysis_of_existing_metadata",
        "new_models_trained": False,
        "new_fixed_test_experiment": False,
        "external_corpus_audited": False,
        "handoff_date": args.handoff_date,
        "handoff_timezone": "Europe/Rome",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_repository": "KuznetsovKarazin/blockchain-detector-eval",
        "source_snapshot_commit": args.source_commit,
        "inputs": {"folds": source_info(args.folds), "corpus_audit": source_info(args.audit),
                   "run_manifest": source_info(args.manifest)},
        "historical_run_provenance": {
            key: manifest.get(key) for key in ("script", "created_utc", "git_commit", "git_dirty",
                                               "dirty_files", "diff_sha256", "lex_rows_copied_from")},
        "corpus_n_files": corpus_sizes,
        "fold_rows": len(rows),
        "datasets_in_folds": sorted({r["dataset"] for r in rows}),
        "classes": sorted({r["cls"] for r in rows}),
        "seeds": sorted({r["seed"] for r in rows}),
        "protocols": protocols,
        "giant_joint_fold": giant,
        "controls": {
            "random_matched_present": "random_matched" in protocols,
            "project_present": "project" in protocols,
            "local_random_and_local_safe_present": {"local_random", "local_safe"}.issubset(protocols),
            "clone_only_named_protocol_present": any(p in protocols for p in ("clone", "clone_only", "clone-only")),
            "fixed_test_membership_verified": False,
            "four_size_and_positive_matched_pools_verified": False,
            "count_comparison_dataset_class_seed_groups": len(matched_pairs),
            "training_size_multisets_equal_groups": sum(p["training_size_multisets_equal"] for p in matched_pairs),
            "interpretation": "random_matched is an existing partial training-size control. These files do not demonstrate a common fixed test or four matched training pools. Fold IDs and matching counts do not prove membership equality."
        },
        "limitations": [
            "No file-level memberships, code, new labels, model scores, external corpus, or dependency graph were analysed by this script.",
            "No AP, treatment effect, model ranking, external validity, or leakage magnitude is estimated.",
            "DAppSCAN no-finding labels remain proxy labels, not verified negatives.",
            "All counts describe the historical selected runs; the source snapshot commit differs from the original run's recorded commit and dirty-diff provenance."
        ],
        "fixed_test_inputs_next": {
            "groups": "results/contracts/c2_20261024_004314/groups.parquet",
            "assignments": "results/contracts/c2_20261024_004314/assignments.parquet",
            "corpus_sources": "docs/DATA.md at source_snapshot_commit; obtain raw files at pinned source commits",
            "labels": "Load labels locally from pinned original sources; never treat missing labels as verified negatives.",
            "group_fields": ["file_id", "dataset", "path", "group", "comp", "safe_group", "local"],
            "warning": "Verify the actual Parquet schema before use; the schema fields here follow the C2 exporter. Create new fixed-T manifests from file identities and grouping constraints rather than recycling fold numbers."
        }
    }
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "fold_inventory.csv", rows, REQUIRED)
    write_csv(args.out / "protocol_summary.csv", protocol_rows, list(protocol_rows[0]))
    if matched_pairs:
        write_csv(args.out / "matched_size_comparison.csv", matched_pairs, list(matched_pairs[0]))
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "fold_rows": len(rows), "protocols": protocols,
                      "largest_dappscan_safe_test": giant["largest_test_n"] if giant else None,
                      "corresponding_train_sizes": giant["corresponding_train_sizes"] if giant else [],
                      "external_corpus_audited": False, "new_fixed_test_experiment": False}))


if __name__ == "__main__":
    main()
