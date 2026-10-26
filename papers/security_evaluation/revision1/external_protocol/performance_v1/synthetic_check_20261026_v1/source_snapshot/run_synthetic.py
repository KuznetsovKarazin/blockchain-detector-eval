"""Synthetic-only engineering receipt; no arguments for real sources or keys."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

import performance
from synthetic_inputs import fixture

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CODE = ("performance.py", "synthetic_inputs.py", "run_synthetic.py", "test_performance.py", "README.md", "REFERENCES.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Preserve prior engineering receipts")
    args.out.mkdir(parents=True)
    config = {"purpose": "synthetic_only_probability_metric_engineering", "fictional_files": 1998,
              "fictional_cases": 3996, "fictional_selected_cases": 180, "classes": list(performance.CLASSES),
              "replicates": 2000, "seed": 20261026, "review_fractions": [.05, .1, .2],
              "actual_external_scores_read_or_created": False, "actual_human_key_opened": False,
              "models_fitted": 0, "created_utc": datetime.now(timezone.utc).isoformat()}
    dump(args.out / "config.json", config)
    snapshots = {}
    for filename in CODE:
        target = args.out / "source_snapshot" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / filename, target)
        snapshots[filename] = sha(target)
    shutil.copy2(HERE.parent / "review_estimators.py", args.out / "source_snapshot/review_estimators.py")
    snapshots["review_estimators.py"] = sha(HERE.parent / "review_estimators.py")
    protected = {filename: sha(HERE.parent / filename) for filename in ("protocol_B_draft.json", "PROTOCOL_B.md", "validate_gate.py")}
    receipt = {"schema": "synthetic_performance_engineering_receipt_v1", "status": "prepared_before_synthetic_estimation",
               "config_sha256": sha(args.out / "config.json"), "source_hashes": snapshots,
               "protected_protocol_hashes": protected, "python": sys.version,
               "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scipy", "scikit-learn")}}
    dump(args.out / "receipt.json", receipt)
    inputs = list(fixture(1998, 90, classes=performance.CLASSES))
    results = {}
    for cls in performance.CLASSES:
        inputs[-1]["class"] = cls
        results[cls] = performance.evaluate(*inputs, cls, replicates=2000)
    # Unknown-reference smoke check, still entirely fabricated in memory.
    inputs[-1]["class"] = "reentrancy"
    inputs[5].loc[0, "adjudicated_judgment"] = "unknown"
    unknown = performance.evaluate(*inputs, "reentrancy", replicates=2000)
    assert unknown["ap"]["point"] is None and unknown["ap"]["interval"] is None
    assert [row["review_count"] for row in unknown["workload"]] == [99, 199, 399]
    dump(args.out / "fictional_complete_reference_results.json", results)
    dump(args.out / "fictional_unknown_reference_results.json", unknown)
    for name, expected in protected.items():
        if sha(HERE.parent / name) != expected:
            raise ValueError("Protected protocol changed during synthetic check")
    for name in CODE:
        if sha(HERE / name) != snapshots[name]:
            raise ValueError("Source changed during synthetic check")
    receipt.update(status="complete_synthetic_only", actual_external_scores_read_or_created=False,
                   actual_human_key_opened=False, models_fitted=0,
                   output_hashes={p.name: sha(p) for p in args.out.glob("fictional_*.json")})
    dump(args.out / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "source_sha256": snapshots["performance.py"], "models_fitted": 0}))


if __name__ == "__main__":
    main()
