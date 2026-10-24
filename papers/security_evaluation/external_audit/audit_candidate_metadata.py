#!/usr/bin/env python3
"""Inventory candidate metadata without parsing vulnerability annotations.

Inputs: a complete GitHub recursive Git-tree JSON and a compact CSV manifest.
Only the CSV's source (`label`) and object identifier (`contract`) are used.
This script does not analyze the `tag` annotation column or evaluate models.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


SOURCE_DIRECTORIES = {
    "smartbugs_results": "sb_results_contracts",
    "smartbugs_curated": "smartbugs_curated",
    "zeus_safe": "zeus_safe_contracts",
    "zeus_vulnerable": "zeus_vulnerable_contracts",
}


def file_counts(entries: list[dict]) -> dict:
    counts = {}
    for entry in entries:
        directory = "/".join(entry["path"].split("/")[:2])
        item = counts.setdefault(directory, {"file_count": 0, "total_bytes": 0})
        item["file_count"] += 1
        item["total_bytes"] += entry["size"]
    return dict(sorted(counts.items()))


def audit(tree_path: Path, manifest_path: Path) -> dict:
    tree_bytes = tree_path.read_bytes()
    tree = json.loads(tree_bytes)
    if not isinstance(tree, dict) or not isinstance(tree.get("tree"), list):
        raise ValueError("Expected a GitHub-style JSON object with a tree array.")
    if tree.get("truncated") is not False:
        raise ValueError("The input must explicitly state truncated=false.")
    entries = tree["tree"]
    blobs = [entry for entry in entries if entry.get("type") == "blob"]
    for entry in blobs:
        if not isinstance(entry.get("path"), str) or not entry.get("sha"):
            raise ValueError("A blob is missing its path or Git object ID.")
        if not isinstance(entry.get("size"), int) or entry["size"] < 0:
            raise ValueError("A blob is missing its nonnegative byte size.")

    sources = [entry for entry in blobs
               if entry["path"].startswith("contracts/")
               and entry["path"].endswith(".sol")]
    bytecodes = [entry for entry in blobs
                 if entry["path"].startswith("bytecode/")
                 and entry["path"].endswith(".hex")]
    if not sources:
        raise ValueError("No contracts/**/*.sol entries found in the tree.")

    manifest_bytes = manifest_path.read_bytes()
    reader = csv.DictReader(io.StringIO(manifest_bytes.decode("utf-8-sig"), newline=""))
    if not {"label", "contract"}.issubset(reader.fieldnames or []):
        raise ValueError("Manifest requires label and contract columns.")
    # Deliberately keep only identity metadata. Never parse the `tag` column.
    identities = []
    for line_number, row in enumerate(reader, start=2):
        source, identifier = row["label"], row["contract"]
        if not source or not identifier:
            raise ValueError(f"Empty source/contract identifier at row {line_number}.")
        identities.append((source, identifier))
    if not identities:
        raise ValueError("The manifest has no data rows.")

    pair_counts = collections.Counter(identities)
    identifier_sources = collections.defaultdict(set)
    for source, identifier in identities:
        identifier_sources[identifier.lower()].add(source)
    source_counts = dict(sorted(collections.Counter(s for s, _ in identities).items()))

    sha_paths = collections.defaultdict(list)
    for entry in sources:
        sha_paths[entry["sha"]].append(entry["path"])
    duplicate_blobs = [
        {"git_blob_sha": sha, "paths": sorted(paths)}
        for sha, paths in sorted(sha_paths.items()) if len(paths) > 1
    ]

    reconciliation = []
    for source, directory in SOURCE_DIRECTORIES.items():
        file_stems = {
            PurePosixPath(entry["path"]).stem.lower()
            for entry in sources if entry["path"].split("/")[1] == directory
        }
        manifest_ids = {
            identifier.lower().removesuffix(".sol")
            for label, identifier in identities if label == source
        }
        reconciliation.append({
            "source": source,
            "source_directory": "contracts/" + directory,
            "unique_manifest_identifiers": len(manifest_ids),
            "unique_source_file_stems": len(file_stems),
            "manifest_identifiers_without_file_stem": sorted(manifest_ids - file_stems),
            "source_file_stems_without_manifest_identifier": sorted(file_stems - manifest_ids),
        })

    # Check exact manifest bytes when its repository path is represented in tree.
    manifest_repo_path = "csvs/" + manifest_path.name
    matching_entry = next((e for e in blobs if e["path"] == manifest_repo_path), None)
    git_blob_sha = hashlib.sha1(
        b"blob " + str(len(manifest_bytes)).encode("ascii") + b"\0" + manifest_bytes
    ).hexdigest()
    if matching_entry is not None:
        verified = (matching_entry["sha"] == git_blob_sha
                    and matching_entry["size"] == len(manifest_bytes))
        if not verified:
            raise ValueError("Manifest bytes do not match the pinned tree's Git blob.")
    else:
        verified = None

    return {
        "schema": "p1_external_candidate_metadata_recount_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "Within-candidate identity metadata only; no model or annotation evaluation.",
        "status": "CANDIDATE_ONLY_NOT_INDEPENDENCE_VERIFIED",
        "input_metadata": {
            "tree_sha": tree.get("sha"),
            "tree_entries": len(entries),
            "tree_truncated": False,
            "tree_json_sha256": hashlib.sha256(tree_bytes).hexdigest(),
            "manifest_filename": manifest_path.name,
            "manifest_bytes": len(manifest_bytes),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "manifest_git_blob_sha": git_blob_sha,
            "manifest_matches_git_tree": verified,
        },
        "source_file_count": len(sources),
        "unique_source_git_blobs": len(sha_paths),
        "source_file_counts": file_counts(sources),
        "bytecode_file_count": len(bytecodes),
        "bytecode_file_counts": file_counts(bytecodes),
        "manifest_rows": len(identities),
        "manifest_rows_by_source": source_counts,
        "unique_source_contract_pairs_case_sensitive": len(pair_counts),
        "unique_lowercase_contract_identifiers": len(identifier_sources),
        "duplicate_source_contract_keys": [
            {"source": s, "contract": c, "count": n}
            for (s, c), n in sorted(pair_counts.items()) if n > 1
        ],
        "cross_source_lowercase_identifier_count": sum(
            len(sources_) > 1 for sources_ in identifier_sources.values()
        ),
        "cross_source_lowercase_identifiers": [
            {"contract": identifier, "sources": sorted(sources_)}
            for identifier, sources_ in sorted(identifier_sources.items())
            if len(sources_) > 1
        ],
        "exact_git_blob_duplicate_groups": duplicate_blobs,
        "manifest_source_file_reconciliation": reconciliation,
        "unmapped_manifest_source_labels": sorted(set(source_counts) - set(SOURCE_DIRECTORIES)),
        "limitations": [
            "Git blob equality identifies byte-identical files; no source normalization or clone detection is performed.",
            "Identifier checks use lowercase strings, without Ethereum address validation or zero-padding.",
            "File reconciliation additionally removes a trailing .sol from manifest identifiers.",
            "No comparison is made against the current study's training, validation or test pools.",
            "No vulnerability tag is parsed; no class labels or detector metrics are generated.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree-json", type=Path, required=True)
    parser.add_argument("--manifest-csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Output JSON file")
    args = parser.parse_args()
    try:
        summary = audit(args.tree_json, args.manifest_csv)
    except (ValueError, OSError, KeyError, csv.Error) as error:
        parser.exit(2, f"Audit failed: {error}\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(args.out),
        "manifest_rows": summary["manifest_rows"],
        "source_files": summary["source_file_count"],
        "unique_source_git_blobs": summary["unique_source_git_blobs"],
        "manifest_matches_git_tree": summary["input_metadata"]["manifest_matches_git_tree"],
    }))


if __name__ == "__main__":
    main()
