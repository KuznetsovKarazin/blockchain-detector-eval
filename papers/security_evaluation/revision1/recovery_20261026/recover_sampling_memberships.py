"""Restore only byte-identical missing sampling memberships; never import models.

Run from the repository root with Python and pandas 2.2.3. Reconstruction uses
the ordering and gzip arguments in the preserved prepare-stage source snapshot.
The expected SHA256 is taken from each frozen manifest; the independently
supplied public Git blob identity is also required before restoring a path.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "papers/security_evaluation/revision1/sampling_variance"
PUBLIC_GIT_BLOB = "e49ac7d9bdb79946ff772c4d5fe3bdd57cd53f44"
EXPECTED_SHA256 = "f6e79ecb693ced2d0a4f4b627bc919f19f84dd17b384ecfc9d0ef73e7edd4786"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def reconstruct(run, staging):
    manifest = json.loads((run / "manifest.json").read_text())
    config_bytes = (run / "config.json").read_bytes()
    if sha(config_bytes) != manifest["config_sha256"]:
        raise ValueError("Frozen config changed")
    if manifest["memberships_sha256"] != EXPECTED_SHA256:
        raise ValueError("Unexpected frozen membership identity")
    jobs = json.loads(config_bytes)["jobs"]
    test_ids = jobs[0]["test_ids"]
    if len(test_ids) != 1082 or len(set(test_ids)) != 1082 or test_ids != sorted(test_ids):
        raise ValueError("Unexpected original T")
    if any(job["test_ids"] != test_ids for job in jobs):
        raise ValueError("Jobs do not share the original fixed T")
    rows = []
    cells = set()
    for job in jobs:
        if job["panel"] == "training_draw" and job["method"] == "raw_tfidf_lr":
            if len(job["train_ids"]) != 1179 or len(set(job["train_ids"])) != 1179:
                raise ValueError("Unexpected training membership count")
            if set(job["train_ids"]) & set(test_ids):
                raise ValueError("Exact train/test overlap")
            cell = (job["draw"], job["regime"])
            if cell in cells:
                raise ValueError("Duplicate draw/regime")
            cells.add(cell)
            rows.extend({"draw": job["draw"], "regime": job["regime"],
                         "role": "train", "file_id": i} for i in job["train_ids"])
    rows.extend({"draw": -1, "regime": "common_test", "role": "test", "file_id": i}
                for i in test_ids)
    if len(cells) != 80 or len(rows) != 95402:
        raise ValueError("Incomplete 20-draw/four-regime memberships")
    # Filename contributes to the gzip header. Preserve the historical basename.
    candidate = staging / run.name / "memberships.csv.gz"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(candidate, index=False,
                              compression={"method": "gzip", "mtime": 0})
    data = candidate.read_bytes()
    record = {"run": run.name, "rows": len(rows), "training_rows": 94320,
              "test_rows": 1082, "draw_regime_cells": len(cells), "bytes": len(data),
              "sha256": sha(data), "git_blob_sha1": git_blob(data),
              "uncompressed_sha256": sha(gzip.decompress(data)),
              "frozen_config_sha256": manifest["config_sha256"],
              "byte_exact_public_match": git_blob(data) == PUBLIC_GIT_BLOB and sha(data) == EXPECTED_SHA256}
    target = run / "memberships.csv.gz"
    if not record["byte_exact_public_match"]:
        record.update(restored=False, candidate=str(candidate))
        return record
    if target.exists():
        if target.read_bytes() != data:
            raise FileExistsError("Refusing to overwrite differing existing membership file")
        record.update(restored=False, already_exact=True)
    else:
        # Exclusive creation: an existing path is never silently overwritten.
        with target.open("xb") as handle:
            handle.write(data)
        record.update(restored=True, already_exact=False)
    return record


def main():
    staging = Path(tempfile.mkdtemp(prefix="security-sampling-recovery-20261026-"))
    records = [reconstruct(BASE / f"run_20261025_v{v}", staging) for v in (1, 2)]
    output = {"schema": "sampling_membership_recovery_v1", "python": sys.version,
              "pandas": pd.__version__, "source": "frozen config job membership arrays",
              "models_refitted": 0, "predictions_changed": False, "records": records}
    Path(__file__).with_name("SAMPLING_RECOVERY.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))
    if not all(r["byte_exact_public_match"] for r in records):
        raise SystemExit("Byte mismatch: candidates preserved outside repository; no differing original path restored")


if __name__ == "__main__":
    main()
