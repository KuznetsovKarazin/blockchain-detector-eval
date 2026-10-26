"""Synthetic-only v2 receipt; no real input-file arguments or model operations."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd
import performance

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE.parent
DEPENDENCIES = ("performance_v2/performance.py", "performance_v2/run_synthetic.py",
                "performance_v2/test_performance.py", "performance_v2/README.md", "performance_v2/REFERENCES.json",
                "performance_v1/performance.py", "performance_v1/synthetic_inputs.py",
                "performance_v1/REFERENCES.json", "review_estimators.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def fictional_inputs(target_class, failures=False):
    spec = importlib.util.spec_from_file_location("fictional_fixture", PROTOCOL / "performance_v1/synthetic_inputs.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    data = list(fixture.fixture(1998, 90, classes=performance.CLASSES))
    base = data[-1]
    base["class"] = target_class
    scores = []
    for method in ("SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_C"):
        part = base.copy()
        part["method"] = method
        if method == "SYNTHETIC_B": part["score"] = part.score.iloc[::-1].to_numpy()
        if method == "SYNTHETIC_C":
            part["score"] = np.floor(np.arange(1998) / 30)
            if failures:
                rows = np.arange(1998)
                part.loc[rows % 4 == 0, "status"] = "timeout"
                part.loc[(rows % 4 != 0) & (rows % 11 == 0), "status"] = "compile_error"
                part.loc[~part.status.eq("ok"), "score"] = np.nan
        scores.append(part)
    data[-1] = pd.concat(scores, ignore_index=True)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Preserve completed engineering receipts; use a new output path")
    args.out.mkdir(parents=True)
    config = {"schema": "synthetic_paired_metrics_config_v2", "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "fictional_in_memory_engineering_only", "fictional_files": 1998, "fictional_cases": 3996,
        "fictional_selected_cases": 180, "classes": list(performance.CLASSES),
        "methods": ["SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_C"], "replicates": 2000, "seed": 20261026,
        "review_fractions": [.05, .1, .2], "alpha": .05, "failure_status_inventory": list(performance.FAILURE_STATUSES),
        "scenarios": ["complete_scores_both_classes", "mixed_failures_both_classes", "unknown_outside_common", "unknown_inside_common"],
        "actual_external_scores_read_or_created": False, "actual_human_keys_or_judgments_opened": False,
        "model_fits": 0, "prospective_study_freeze": False, "execution_gate_override": False}
    dump(args.out / "config.json", config)
    source_hashes = {}
    for rel in DEPENDENCIES:
        target = args.out / "source_snapshot" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROTOCOL / rel, target)
        source_hashes[rel] = sha(target)
    protected = {str(p.relative_to(PROTOCOL)): sha(p) for p in (PROTOCOL / "performance_v1").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts}
    protected.update({name: sha(PROTOCOL / name) for name in ("PROTOCOL_B.md", "protocol_B_draft.json", "validate_gate.py", "review_estimators.py")})
    receipt = {"schema": "synthetic_paired_metrics_receipt_v2", "status": "prepared_before_synthetic_estimation",
        "prepared_utc": datetime.now(timezone.utc).isoformat(), "config_sha256": sha(args.out / "config.json"),
        "source_hashes": source_hashes, "protected_hashes": protected, "python": sys.version,
        "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scipy", "scikit-learn")}}
    dump(args.out / "receipt.json", receipt)
    kwargs = {k: config[k] for k in ("methods", "replicates", "seed", "review_fractions", "alpha")}
    results = {}
    for failures in (False, True):
        scenario = "mixed_failures" if failures else "complete_scores"
        results[scenario] = {}
        for cls in performance.CLASSES:
            results[scenario][cls] = performance.evaluate_methods(*fictional_inputs(cls, failures), cls, **kwargs)
    for outside in (True, False):
        data = fictional_inputs("reentrancy", True)
        plan = performance.plan_score_domains(data[0], data[-1], "reentrancy", methods=config["methods"])
        domain_paths = {p for p, d in zip(plan["paths"], plan["domains"]["common_success"]["mask"]) if bool(d) != outside}
        case = data[1][data[1]["class"].eq("reentrancy") & data[1].path.isin(domain_paths)].case_id.iloc[0]
        data[5].loc[data[5].case_id.eq(case), "adjudicated_judgment"] = "unknown"
        name = "unknown_outside_common" if outside else "unknown_inside_common"
        results[name] = performance.evaluate_methods(*data, "reentrancy", **kwargs)
        common_ap = results[name]["domains"]["common_success"]["methods"]["SYNTHETIC_A"]["ap"]["point"]
        assert (common_ap is not None) == outside
        assert results[name]["domains"]["full_frame_pipeline"]["methods"]["SYNTHETIC_A"]["workload"][0]["recall"]["point"] is None
    for name, result in results.items():
        dump(args.out / ("fictional_" + name + ".json"), result)
    for name, expected in {**source_hashes, **protected}.items():
        if sha(PROTOCOL / name) != expected:
            raise RuntimeError("Source or protected artifact changed during synthetic estimation: " + name)
    receipt.update(status="complete_synthetic_only", completed_utc=datetime.now(timezone.utc).isoformat(),
        actual_external_scores_read_or_created=False, actual_human_keys_or_judgments_opened=False,
        model_fits=0, protected_artifacts_unchanged=True, prospective_study_freeze=False, execution_gate_override=False,
        output_hashes={p.name: sha(p) for p in args.out.glob("fictional_*.json")})
    dump(args.out / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "performance_sha256": source_hashes["performance_v2/performance.py"], "models_fitted": 0}))


if __name__ == "__main__":
    main()
