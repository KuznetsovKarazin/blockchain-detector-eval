"""Prepare and execute hash-frozen DEVELOPMENT campaigns on DAppSCAN proxies.

This runner cannot score an external corpus. A selected development bundle
must be explicitly marked train_allowed before preparation. It never selects
models or hyperparameters using scores. See README.md for the bundle contract.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time
import traceback
import warnings

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "papers/security_evaluation"))
from bal.features.contract_features import raw_text, normalised_text, pattern_matrix
from evaluation_metrics import evaluate_workload

DAPP_PIN = "66a56619c44770e05c2db600fa6468115ff0dcd5"
PREFIX = "data/raw/DAppSCAN/DAppSCAN-source/contracts/"
HISTORY = "results/contracts/c2_20261024_004314/groups.parquet"
REGIMES = ("other_files_unrestricted", "project_disjoint", "clone_disjoint", "joint_project_clone_disjoint")
METHODS = ("raw_tfidf_lr", "normalized_tfidf_lr", "pattern_rf", "pattern_lightgbm")
CLASSES = ("reentrancy", "unchecked")
BASE_BUNDLE = ("source_inventory.csv", "label_input_hashes.json")
CODE = ("papers/security_evaluation/campaign/run_development.py",
        "papers/security_evaluation/evaluation_metrics.py", "src/bal/features/contract_features.py")
PACKAGES = ("numpy", "pandas", "scipy", "scikit-learn", "lightgbm", "pyarrow", "threadpoolctl")
HISTORICAL_PILOT = "papers/security_evaluation/runs/dev_fixed_t_20261025_v1"
HISTORICAL_PREDICTIONS_SHA256 = "23c33c1602dea2347c1d268c6510bf0f4146ab769df8b4eacb6ac04675255d48"


class ExecutionBlocked(ValueError):
    """A scientific execution gate failed before loading model inputs or fitting."""


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def dump(path, value):
    """Atomic JSON publication; a terminated fit never looks complete."""
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()


def source_path(relative):
    """Hard source gate: neither an external path nor a symlink escape is allowed."""
    if not isinstance(relative, str) or not relative.startswith(PREFIX) or not relative.endswith(".sol"):
        raise ValueError(f"Only pinned DAppSCAN development Solidity paths are allowed: {relative}")
    path = ROOT / relative
    if not path.resolve().is_relative_to((ROOT / PREFIX).resolve()) or ".." in Path(relative).parts:
        raise ValueError("Source path escapes the permitted development corpus")
    return path


def checked_bundle_manifest(manifest):
    if manifest.get("purpose") != "development_only" or manifest.get("external_scoring_allowed") is not False:
        raise ValueError("Bundle must explicitly prohibit external scoring and be development_only")
    if manifest.get("train_allowed") is not True:
        raise ValueError("Candidate feasibility bundle is not approved for training")
    if manifest.get("data_commits", {}).get("DAppSCAN") != DAPP_PIN:
        raise ValueError("Bundle does not identify the pinned DAppSCAN development source")
    if set(bundle_files(manifest)) - set(manifest.get("hashes", {})):
        raise ValueError("Bundle lacks required input hashes")


def bundle_files(manifest):
    membership = manifest.get("membership_file", "selected_memberships.csv")
    if membership not in {"selected_memberships.csv", "selected_memberships.csv.gz"}:
        raise ValueError("Unsupported membership file; expected CSV or gzip CSV")
    return (membership, *BASE_BUNDLE)


def verify_hashes(base, hashes):
    for relative, expected in hashes.items():
        path = Path(base) / relative
        if ".." in Path(relative).parts or Path(relative).is_absolute():
            raise ValueError("Manifest artifact paths must be relative and contained")
        if not path.is_file() or sha(path) != expected:
            raise ValueError(f"Hash mismatch or missing artifact: {path}")


def verify_inventory(inventory):
    """Keep the complete historical dependency population before any restriction."""
    history = pd.read_parquet(ROOT / HISTORY)
    if inventory.file_id.duplicated().any() or len(inventory) != len(history):
        raise ValueError("Inventory must retain every original historical graph vertex exactly once")
    original, current = history.sort_values("file_id"), inventory.sort_values("file_id")
    for col in ("file_id", "dataset", "path", "group", "comp"):
        if not np.array_equal(original[col].to_numpy(), current[col].to_numpy()):
            raise ValueError(f"Full inventory differs from original graph: {col}")
    # Compare equivalence relations, allowing stable joint IDs to differ in name.
    pairs = pd.DataFrame({"old": original.safe_group.to_numpy(), "new": current.joint_id.to_numpy()})
    if not ((pairs.groupby("old").new.nunique() == 1).all() and
            (pairs.groupby("new").old.nunique() == 1).all()):
        raise ValueError("Joint components differ from the original full graph")


def proxy_labels(inventory, expected_label_hashes):
    """Read only requested development annotations; absent findings remain proxies."""
    result, used = {}, {}
    for row in inventory.itertuples():
        source_path(row.path)
        suffix = Path(row.path[len(PREFIX):]).with_suffix(".json")
        annotation = ROOT / "data/raw/DAppSCAN/DAppSCAN-source/SWCsource" / suffix
        values = {"reentrancy": 0, "unchecked": 0}
        if annotation.exists():
            relative = str(annotation.relative_to(ROOT))
            if expected_label_hashes.get(relative) != sha(annotation):
                raise ValueError(f"Annotation hash missing or changed: {relative}")
            obj = json.loads(annotation.read_text())
            if obj.get("filePath") != row.path.removeprefix("data/raw/DAppSCAN/"):
                raise ValueError(f"Annotation source mismatch: {relative}")
            codes = {x.get("category", "").split("-")[1] for x in obj.get("SWCs", [])
                     if x.get("category", "").startswith("SWC-")}
            values = {"reentrancy": int("107" in codes), "unchecked": int("104" in codes)}
            used[relative] = sha(annotation)
        result[int(row.file_id)] = values
    return result, used


def validate_memberships(members, inventory, labels, classes, seeds, test_ids):
    """Validate exact common tests, matched counts, and regime-specific exclusion.

    The inventory must have already passed verify_inventory() on the full
    population. Test rows may be common (class='*', seed=-1) or repeated by
    cell; repeated cell copies must be exactly equal, not different subsets.
    """
    fields = ("test_id", "class", "seed", "regime", "role", "file_id", "path", "group", "comp", "joint_id")
    if set(fields) - set(members.columns):
        raise ValueError("Membership columns are incomplete")
    if not set(members.role).issubset({"train", "test"}):
        raise ValueError("Unknown membership role")
    by_id = inventory.set_index("file_id")
    if not members.file_id.isin(by_id.index).all():
        raise ValueError("Membership ID missing from full inventory")
    original = by_id.loc[members.file_id]
    if not (original.dataset == "dappscan").all():
        raise ValueError("External/non-DAppSCAN scoring is forbidden")
    for field in ("path", "group", "comp", "joint_id"):
        if not np.array_equal(members[field].to_numpy(), original[field].to_numpy()):
            raise ValueError(f"Membership identity changed: {field}")
    output = []
    for test_id in test_ids:
        rows = members[members.test_id == test_id]
        tests = rows[rows.role == "test"]
        if tests.empty:
            raise ValueError(f"No fixed test for {test_id}")
        copies = list(tests.groupby(["class", "seed", "regime"], dropna=False))
        reference = None
        for _, copy in copies:
            if copy.file_id.duplicated().any():
                raise ValueError("Duplicate test file within a membership cell")
            ids = tuple(sorted(map(int, copy.file_id)))
            if reference is not None and ids != reference:
                raise ValueError("Test population changes across classes, seeds or regimes")
            reference = ids
        test = by_id.loc[list(reference)]
        for cls in classes:
            yt = np.asarray([labels[i][cls] for i in reference])
            if set(yt) != {0, 1}:
                raise ValueError(f"Test has no positive or no proxy-zero for {test_id}/{cls}")
            for seed in seeds:
                matched_counts = []
                for regime in REGIMES:
                    train_rows = rows[(rows.role == "train") & (rows["class"] == cls) &
                                      (rows.seed == seed) & (rows.regime == regime)]
                    if train_rows.empty or train_rows.file_id.duplicated().any():
                        raise ValueError(f"Missing or duplicate training cell: {test_id}/{cls}/{seed}/{regime}")
                    ids = tuple(sorted(map(int, train_rows.file_id)))
                    if set(ids) & set(reference):
                        raise ValueError("Exact test object appears in training")
                    train = by_id.loc[list(ids)]
                    for column, modes in (("group", {"project_disjoint"}),
                                          ("comp", {"clone_disjoint"}),
                                          ("joint_id", {"joint_project_clone_disjoint"})):
                        if regime in modes and set(train[column]) & set(test[column]):
                            raise ValueError(f"{column} overlaps under {regime}")
                    yy = np.asarray([labels[i][cls] for i in ids])
                    counts = (int((yy == 0).sum()), int((yy == 1).sum()))
                    if min(counts) == 0:
                        raise ValueError("Infeasible training cell lacks one proxy class")
                    matched_counts.append(counts)
                    output.append({"test_id": str(test_id), "class": cls, "seed": int(seed), "regime": regime,
                                   "train_ids": list(ids), "test_ids": list(reference),
                                   "train_n": len(ids), "train_positive_proxy": counts[1],
                                   "test_n": len(reference), "test_positive_proxy": int(yt.sum()),
                                   "test_joint_components": int(test.joint_id.nunique())})
                if len(set(matched_counts)) != 1:
                    raise ValueError("Training object/positive counts differ across the four regimes")
    return output


def model_config():
    return {
        "tfidf": {"token_pattern": r"\S+", "ngram_range": [1, 3], "min_df": 2,
                  "max_features": 50000, "sublinear_tf": True, "lowercase": False},
        "lr": {"C": 1.0, "max_iter": 3000, "class_weight": "balanced", "solver": "lbfgs", "tol": 0.0001},
        "rf": {"n_estimators": 500, "class_weight": "balanced_subsample", "min_samples_leaf": 1, "n_jobs": 4},
        "lightgbm": {"n_estimators": 400, "learning_rate": 0.05, "num_leaves": 31, "subsample": 0.8,
                     "subsample_freq": 1, "colsample_bytree": 0.8, "class_weight": "balanced", "verbose": -1, "n_jobs": 4},
        "scaler": "StandardScaler(with_mean=False) for lexical methods only",
        "threads": {"lr_native_pools": 1, "tree_openmp": 4, "tree_blas": 1, "tree_n_jobs": 4},
    }


def make_jobs(cells, methods, regimes):
    jobs, canonical = [], {}
    for cell in cells:
        if cell["regime"] not in regimes:
            continue
        for method in methods:
            spec = {**cell, "method": method}
            identity = {k: spec[k] for k in ("test_id", "class", "seed", "regime", "method")}
            spec["job_id"] = fingerprint(identity)[:24]
            spec["training_membership_sha256"] = fingerprint(spec["train_ids"])
            # lbfgs is deterministic: repeated sampling seeds add no computation
            # when the ordered training set and test are identical.
            reuse_key = fingerprint({"class": cell["class"], "method": method,
                                     "train_ids": cell["train_ids"], "test_ids": cell["test_ids"]})
            if method.endswith("tfidf_lr") and reuse_key in canonical:
                spec["reuse_from"] = canonical[reuse_key]
            else:
                spec["reuse_from"] = None
                if method.endswith("tfidf_lr"):
                    canonical[reuse_key] = spec["job_id"]
            jobs.append(spec)
    return jobs


def environment():
    from threadpoolctl import threadpool_info
    return {"python": sys.version, "python_major_minor": list(sys.version_info[:2]), "platform": platform.platform(),
            "packages": {p: importlib.metadata.version(p) for p in PACKAGES}, "logical_cpu_count": os.cpu_count(),
            "threadpools": threadpool_info()}


def validate_exact_reproduction(config):
    """An integration label alone cannot authorise an unseen comparative test."""
    pilot = ROOT / HISTORICAL_PILOT
    if sha(pilot / "predictions.csv") != HISTORICAL_PREDICTIONS_SHA256:
        raise ExecutionBlocked("Original published pilot predictions changed or are unavailable")
    original = json.loads((pilot / "manifest.json").read_text())
    if sha(pilot / "memberships.csv") != original["membership_sha256"]:
        raise ExecutionBlocked("Original reproduction memberships changed")
    members = pd.read_csv(pilot / "memberships.csv")
    test_ids = sorted(map(int, members.loc[members.role == "test", "file_id"]))
    if config["model_config"] != model_config():
        raise ExecutionBlocked("Reproduction model settings differ from fixed historical settings")
    for job in config["jobs"]:
        if job["class"] != "reentrancy" or job["seed"] != 0 or job["method"] != "raw_tfidf_lr":
            raise ExecutionBlocked("Exact pilot reproduction permits only the previously scored class/model/seed")
        train = members[(members.role == "train") & (members.regime == job["regime"])]
        if job["test_ids"] != test_ids or job["train_ids"] != sorted(map(int, train.file_id)):
            raise ExecutionBlocked("Requested memberships are not the exact previously scored pilot")


def validate_execution_assessment(assessment, config, bundle_hash, *, allow_blocked=False):
    if assessment.get("schema") != "security_campaign_execution_assessment_v1":
        raise ExecutionBlocked("Missing or unsupported execution assessment")
    if assessment.get("bundle_manifest_sha256") != bundle_hash:
        raise ExecutionBlocked("Execution assessment belongs to a different selected bundle")
    if assessment.get("execution_allowed") is not True:
        if allow_blocked:
            return False
        raise ExecutionBlocked(assessment.get("reason", "Comparative execution has not passed its scientific gate"))
    evidence = assessment.get("evidence_hashes", {})
    if not evidence:
        raise ExecutionBlocked("Allowed assessment must bind verifiable evidence hashes")
    verify_hashes(ROOT, evidence)
    kind = assessment.get("assessment_kind")
    if kind == "exact_historical_pilot_reproduction":
        validate_exact_reproduction(config)
    elif kind == "expanded_graph_comparative_check":
        if (assessment.get("expanded_graph_check") != "passed" or
                assessment.get("all_training_memberships_checked") is not True or
                assessment.get("joint_overlap_count") != 0 or
                set(assessment.get("test_ids", [])) != set(config["test_ids"])):
            raise ExecutionBlocked("Expanded graph assessment failed or does not cover every configured test/training membership")
        gate_path = assessment.get("evidence_gate_path")
        if gate_path not in evidence:
            raise ExecutionBlocked("Expanded assessment lacks a hash-bound computed graph gate")
        gate = json.loads((ROOT / gate_path).read_text())
        if (gate.get("schema") != "expanded_graph_campaign_gate_v1" or
                gate.get("comparative_training_allowed") is not True or
                gate.get("failed_expanded_operational_screens") is not False or
                gate.get("historical_joint_training_intersects_expanded_test_components") is not False or
                not set(config["test_ids"]).issubset(gate.get("selected_test_ids", [])) or
                bundle_hash not in gate.get("selected_bundle_manifest_hashes", {}).values()):
            raise ExecutionBlocked("Computed expanded-graph gate blocks this selected bundle")
        for directory, files in gate.get("input_hashes", {}).items():
            verify_hashes(ROOT, {f"{directory}/{name}": value for name, value in files.items()})
        if not gate.get("outputs"):
            raise ExecutionBlocked("Computed graph gate must retain its auditable check outputs")
        verify_hashes((ROOT / gate_path).parent, gate["outputs"])
    else:
        raise ExecutionBlocked("Unknown assessment kind cannot authorise fitting")
    return True


def local_bundle_gate(bundle, bundle_hash):
    path = Path(bundle) / "CAMPAIGN_GATE.json"
    if not path.is_file():
        return None
    gate = json.loads(path.read_text())
    if bundle_hash not in gate.get("selected_bundle_manifest_hashes", {}).values():
        raise ExecutionBlocked("Bundle gate does not identify this frozen bundle manifest")
    return path, gate


def make_execution_assessment(design, bundle_hash, config, assessment_path=None, bundle=None):
    computed = local_bundle_gate(bundle, bundle_hash) if bundle is not None else None
    if computed is not None and computed[1].get("comparative_training_allowed") is not True:
        path, gate = computed
        if assessment_path is not None and json.loads(Path(assessment_path).read_text()).get("execution_allowed") is True:
            raise ExecutionBlocked("An asserted approval cannot override the computed failed bundle gate")
        relative = str(path.resolve().relative_to(ROOT))
        assessment = {"schema": "security_campaign_execution_assessment_v1",
                      "assessment_kind": "expanded_graph_comparative_check",
                      "bundle_manifest_sha256": bundle_hash, "execution_allowed": False,
                      "expanded_graph_check": "failed", "test_ids": config["test_ids"],
                      "reason": gate.get("reason", "Computed expanded dependence blocks comparative execution"),
                      "evidence_gate_path": relative, "evidence_hashes": {relative: sha(path)}}
    elif assessment_path is not None:
        assessment = json.loads(Path(assessment_path).read_text())
    elif design.get("schema") == "security_runner_integration_bundle_v1":
        # This exception is validated against exact, already-scored memberships;
        # it does not depend on the source-wide independence claim.
        assessment = {"schema": "security_campaign_execution_assessment_v1",
                      "assessment_kind": "exact_historical_pilot_reproduction",
                      "bundle_manifest_sha256": bundle_hash, "execution_allowed": True,
                      "reason": "Diagnostic reproduction of previously scored fixed pilot predictions only",
                      "evidence_hashes": {f"{HISTORICAL_PILOT}/{name}": sha(ROOT / HISTORICAL_PILOT / name)
                                          for name in ("predictions.csv", "manifest.json", "memberships.csv")}}
    else:
        assessment = {"schema": "security_campaign_execution_assessment_v1",
                      "assessment_kind": "expanded_graph_comparative_check",
                      "bundle_manifest_sha256": bundle_hash, "execution_allowed": False,
                      "expanded_graph_check": "pending", "test_ids": config["test_ids"],
                      "reason": "Prepared diagnostic design only; expanded graph assessment is required before new comparative fits",
                      "evidence_hashes": {}}
    validate_execution_assessment(assessment, config, bundle_hash, allow_blocked=True)
    return assessment


def check_execution_gate(out):
    """Fail closed before model data loading. Legacy comparative configs lack a gate."""
    config = json.loads((out / "config.json").read_text())
    manifest = json.loads((out / "manifest.json").read_text())
    if sha(out / "config.json") != manifest["config_sha256"]:
        raise ExecutionBlocked("Frozen configuration changed")
    if config.get("bundle_path_at_preparation"):
        computed = local_bundle_gate(config["bundle_path_at_preparation"], sha(out / "inputs/design_manifest.json"))
        if computed is not None and computed[1].get("comparative_training_allowed") is not True:
            raise ExecutionBlocked(computed[1].get("reason", "Computed bundle gate forbids comparative training"))
    assessment_hash = config.get("execution_assessment_sha256")
    assessment_path = out / "inputs/execution_assessment.json"
    if not assessment_hash or not assessment_path.is_file() or sha(assessment_path) != assessment_hash:
        raise ExecutionBlocked("No valid hash-frozen execution assessment; prepare a new gated run")
    assessment = json.loads(assessment_path.read_text())
    return validate_execution_assessment(assessment, config, sha(out / "inputs/design_manifest.json"))


def prepare(args):
    out, bundle = args.out, args.bundle
    if out.exists():
        raise FileExistsError("Campaign output exists; choose a new directory")
    design = json.loads((bundle / "design_manifest.json").read_text())
    checked_bundle_manifest(design)
    required = bundle_files(design)
    verify_hashes(bundle, {n: design["hashes"][n] for n in required})
    inventory = pd.read_csv(bundle / "source_inventory.csv")
    members = pd.read_csv(bundle / required[0])
    verify_inventory(inventory)
    classes, seeds, methods = args.classes, args.seeds, args.methods
    if any(len(values) != len(set(values)) for values in (classes, seeds, methods, args.regimes)):
        raise ValueError("Repeated class, seed, method, or regime in campaign configuration")
    if not set(classes).issubset(CLASSES) or not set(methods).issubset(METHODS) or not set(args.regimes).issubset(REGIMES):
        raise ValueError("Undeclared class, model, or regime")
    if any(s < 0 for s in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("Seeds must be distinct nonnegative integers")
    test_ids = args.test_ids or sorted(members.test_id.unique().tolist())
    if len(test_ids) != len(set(test_ids)):
        raise ValueError("Repeated test_id in campaign configuration")
    selected_ids = set(members.loc[members.test_id.isin(test_ids), "file_id"])
    selected = inventory[inventory.file_id.isin(selected_ids)].copy()
    if selected.empty:
        raise ValueError("Empty selected population")
    dapp = ROOT / "data/raw/DAppSCAN"
    if git("rev-parse", "HEAD", cwd=dapp) != DAPP_PIN or git("status", "--porcelain", "--untracked-files=no", cwd=dapp):
        raise ValueError("DAppSCAN must be a clean pinned checkout")
    for row in selected.itertuples():
        if row.dataset != "dappscan" or sha(source_path(row.path)) != row.file_sha256:
            raise ValueError(f"Wrong development source or hash: {row.file_id}")
    labels, annotation_hashes = proxy_labels(selected, json.loads((bundle / "label_input_hashes.json").read_text()))
    cells = validate_memberships(members, inventory, labels, classes, seeds, test_ids)
    jobs = make_jobs(cells, methods, args.regimes)
    if not jobs:
        raise ValueError("No jobs selected")
    config = {"schema": "security_development_campaign_v1", "purpose": "development_only",
              "label_regime": "proxy", "external_scoring_allowed": False, "tuning_budget": 0,
              "classes": classes, "seeds": seeds, "methods": methods, "regimes": args.regimes,
              "test_ids": test_ids, "model_config": model_config(), "review_fractions": [0.05, 0.10, 0.20],
              "budget_rounding": "floor", "aggregation": "mean of per-seed metrics within test_id; never pool scores across tests",
              "uncertainty": "No CI in this runner; one/few dependency components cannot support broad inference",
              "lr_repetition": "reuse exact ordered train/test membership across seeds/regimes for deterministic lbfgs",
              "jobs": jobs, "bundle_path_at_preparation": str(bundle), "prepared_utc": utc()}
    assessment = make_execution_assessment(design, sha(bundle / "design_manifest.json"), config,
                                           getattr(args, "assessment", None), bundle=bundle)
    out.mkdir(parents=True)
    (out / "inputs").mkdir()
    for name in ("design_manifest.json", *required):
        shutil.copy2(bundle / name, out / "inputs" / name)
    if (bundle / "CAMPAIGN_GATE.json").is_file():
        shutil.copy2(bundle / "CAMPAIGN_GATE.json", out / "inputs/CAMPAIGN_GATE.json")
    selected.to_csv(out / "inputs/selected_inventory.csv", index=False)
    dump(out / "inputs/selected_annotation_hashes.json", annotation_hashes)
    dump(out / "inputs/execution_assessment.json", assessment)
    config["execution_assessment_sha256"] = sha(out / "inputs/execution_assessment.json")
    code_hashes = {}
    for relative in CODE:
        dest = out / "code_snapshot" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, dest)
        code_hashes[relative] = sha(dest)
    dump(out / "config.json", config)
    dump(out / "environment.json", environment())
    manifest = {"schema": "security_development_campaign_manifest_v1", "status": "prepared_no_scores",
                "prepared_utc": utc(), "git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain")),
                "data_commit": DAPP_PIN, "config_sha256": sha(out / "config.json"), "source_hashes": code_hashes,
                "input_hashes": {str(p.relative_to(out)): sha(p) for p in sorted((out / "inputs").glob("*"))},
                "environment_sha256": sha(out / "environment.json"), "historical_groups_sha256": sha(ROOT / HISTORY),
                "logical_jobs": len(jobs), "planned_physical_fits": sum(j["reuse_from"] is None for j in jobs),
                "execution_allowed": assessment["execution_allowed"],
                "label_vector_hashes": {cls: fingerprint([(int(i), labels[int(i)][cls]) for i in sorted(selected_ids)]) for cls in classes},
                "external_scores_computed": False}
    manifest["run_fingerprint"] = fingerprint({k: manifest[k] for k in
                                              ("config_sha256", "source_hashes", "input_hashes", "environment_sha256", "historical_groups_sha256")})
    dump(out / "manifest.json", manifest)
    print(json.dumps({k: manifest[k] for k in ("status", "logical_jobs", "planned_physical_fits", "execution_allowed", "run_fingerprint")}))


def validate_run(out):
    manifest = json.loads((out / "manifest.json").read_text())
    config = json.loads((out / "config.json").read_text())
    if config.get("purpose") != "development_only" or config.get("external_scoring_allowed") is not False or config.get("label_regime") != "proxy":
        raise ValueError("This runner permits only development proxy evaluations")
    if sha(out / "config.json") != manifest["config_sha256"]:
        raise ValueError("Frozen config changed; refuse resume")
    verify_hashes(out, manifest["input_hashes"])
    if sha(out / "environment.json") != manifest["environment_sha256"] or sha(ROOT / HISTORY) != manifest["historical_groups_sha256"]:
        raise ValueError("Frozen environment record or historical graph changed")
    for relative, expected in manifest["source_hashes"].items():
        if sha(ROOT / relative) != expected or sha(out / "code_snapshot" / relative) != expected:
            raise ValueError(f"Code differs from frozen snapshot: {relative}")
    recorded, current = json.loads((out / "environment.json").read_text()), environment()
    if recorded["packages"] != current["packages"] or recorded["python_major_minor"] != current["python_major_minor"]:
        raise ValueError("Python/package versions changed; use the frozen environment or prepare a new run")
    design = json.loads((out / "inputs/design_manifest.json").read_text())
    checked_bundle_manifest(design)
    if git("rev-parse", "HEAD", cwd=ROOT / "data/raw/DAppSCAN") != DAPP_PIN or git("status", "--porcelain", "--untracked-files=no", cwd=ROOT / "data/raw/DAppSCAN"):
        raise ValueError("DAppSCAN checkout changed")
    selected = pd.read_csv(out / "inputs/selected_inventory.csv")
    for row in selected.itertuples():
        if row.dataset != "dappscan" or sha(source_path(row.path)) != row.file_sha256:
            raise ValueError(f"Selected input changed: {row.file_id}")
    labels, _ = proxy_labels(selected, json.loads((out / "inputs/selected_annotation_hashes.json").read_text()))
    for cls, expected in manifest["label_vector_hashes"].items():
        if fingerprint([(int(i), labels[int(i)][cls]) for i in sorted(selected.file_id)]) != expected:
            raise ValueError("Development proxy labels changed")
    recomputed = fingerprint({k: manifest[k] for k in
                             ("config_sha256", "source_hashes", "input_hashes", "environment_sha256", "historical_groups_sha256")})
    if recomputed != manifest["run_fingerprint"]:
        raise ValueError("Run fingerprint changed")
    return manifest, config, selected.set_index("file_id"), labels


def checked_result(result_path, run_fingerprint):
    result = json.loads(result_path.read_text())
    if result["run_fingerprint"] != run_fingerprint:
        raise ValueError("Existing result belongs to a different configuration")
    verify_hashes(result_path.parent, result["artifact_hashes"])
    return result


def fit_predict(job, config, sources, labels):
    """One physical fit. Test labels are used only after predictions elsewhere."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    import lightgbm as lgb
    from threadpoolctl import threadpool_limits, threadpool_info
    start = time.perf_counter()
    train_source = [sources[i] for i in job["train_ids"]]
    test_source = [sources[i] for i in job["test_ids"]]
    y_train = np.asarray([labels[i][job["class"]] for i in job["train_ids"]])
    method, params = job["method"], config["model_config"]
    lexical = method.endswith("tfidf_lr")
    with threadpool_limits(limits=1 if lexical else 4), threadpool_limits(limits=1, user_api="blas"):
        t = time.perf_counter()
        if lexical:
            transform = raw_text if method == "raw_tfidf_lr" else normalised_text
            vectorizer = TfidfVectorizer(**{**params["tfidf"], "ngram_range": tuple(params["tfidf"]["ngram_range"])})
            scaler = StandardScaler(with_mean=False)
            a = scaler.fit_transform(vectorizer.fit_transform([transform(s) for s in train_source]))
            train_prep = time.perf_counter() - t
            t = time.perf_counter()
            b = scaler.transform(vectorizer.transform([transform(s) for s in test_source]))
            model = LogisticRegression(**params["lr"], random_state=job["seed"])
        else:
            a = pattern_matrix(train_source).to_numpy(dtype=np.float32)
            train_prep = time.perf_counter() - t
            t = time.perf_counter()
            b = pattern_matrix(test_source).to_numpy(dtype=np.float32)
            model = RandomForestClassifier(**params["rf"], random_state=job["seed"]) if method == "pattern_rf" else lgb.LGBMClassifier(**params["lightgbm"], random_state=job["seed"])
        test_prep = time.perf_counter() - t
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            t = time.perf_counter()
            model.fit(a, y_train)
            fit_seconds = time.perf_counter() - t
            t = time.perf_counter()
            score = model.predict_proba(b)[:, 1]
            predict_seconds = time.perf_counter() - t
        if score.shape != (len(job["test_ids"]),) or not np.isfinite(score).all():
            raise ValueError("Model produced missing or nonfinite predictions")
        details = {"train_preprocessing_seconds": train_prep, "test_preprocessing_seconds": test_prep,
                   "fit_seconds": fit_seconds, "predict_seconds": predict_seconds,
                   "total_seconds": time.perf_counter() - start, "n_features": int(a.shape[1]),
                   "iterations": int(model.n_iter_[0]) if lexical else int(model.n_estimators),
                   "convergence_warning": any(type(w.message).__name__ == "ConvergenceWarning" for w in caught),
                   "warnings": [str(w.message) for w in caught], "native_threadpools": threadpool_info(),
                   "process_peak_rss_mib_cumulative": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}
    return score, details


def publish_job(out, job, config, manifest, sources, labels, *, reuse_result=None):
    job_dir = out / "fits" / job["job_id"]
    job_dir.mkdir(parents=True, exist_ok=True)
    attempt_n = max([int(p.name.split("_")[-1]) for p in job_dir.glob("attempt_*") if p.is_dir()] + [0]) + 1
    attempt = job_dir / f"attempt_{attempt_n:03d}"
    attempt.mkdir()
    started = utc()
    dump(attempt / "started.json", {"started_utc": started, "job": job, "run_fingerprint": manifest["run_fingerprint"]})
    errors, details = None, {}
    if reuse_result is not None:
        old_dir = out / "fits" / job["reuse_from"]
        pred = pd.read_csv(old_dir / reuse_result["predictions_path"], float_precision="round_trip")
        if pred.file_id.tolist() != job["test_ids"]:
            raise ValueError("Deterministic reuse test identities differ")
        status = "failed" if reuse_result["status"] == "failed" else "reused_identical_deterministic_fit"
        score, statuses = pred.score.to_numpy(), pred.status.to_numpy()
        details = json.loads((old_dir / reuse_result["resources_path"]).read_text())
        details.update(physical_fit=False, reused_from=job["reuse_from"],
                       original_fit_total_seconds=details.get("total_seconds"), total_seconds=0.0)
        if status == "failed":
            errors = {"type": "CanonicalFitFailed", "message": f"Same deterministic fit failed: {job['reuse_from']}"}
    else:
        fit_start = time.perf_counter()
        try:
            score, details = fit_predict(job, config, sources, labels)
            status, statuses = "complete", np.full(len(score), "ok", dtype=object)
            details["physical_fit"] = True
        except Exception as exc:
            # Preserve failure. It is not a zero score or a safe prediction.
            status, errors = "failed", {"type": type(exc).__name__, "message": str(exc)}
            score, statuses = np.full(len(job["test_ids"]), np.nan), np.full(len(job["test_ids"]), "fit_error", dtype=object)
            (attempt / "traceback.txt").write_text(traceback.format_exc())
            details = {"physical_fit": True, "failure": errors, "total_seconds": time.perf_counter() - fit_start,
                       "process_peak_rss_mib_cumulative": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}
    pred = pd.DataFrame({"file_id": job["test_ids"], "score": score, "status": statuses})
    pred.to_csv(attempt / "predictions.csv", index=False)
    y_test = [labels[i][job["class"]] for i in job["test_ids"]]
    evaluation = evaluate_workload(y_test, score, statuses=statuses, label_regime="proxy",
                                   label_provenance=f"DAppSCAN SWC proxy for {job['class']}; no published finding is not verified safe",
                                   review_fractions=config["review_fractions"])
    dump(attempt / "evaluation.json", evaluation)
    dump(attempt / "resources.json", details)
    artifacts = {str(p.relative_to(job_dir)): sha(p) for p in attempt.iterdir() if p.is_file()}
    result = {"job_id": job["job_id"], "status": status, "started_utc": started, "finished_utc": utc(),
              "run_fingerprint": manifest["run_fingerprint"], "artifact_hashes": artifacts,
              "predictions_path": str((attempt / "predictions.csv").relative_to(job_dir)),
              "evaluation_path": str((attempt / "evaluation.json").relative_to(job_dir)),
              "resources_path": str((attempt / "resources.json").relative_to(job_dir)),
              "physical_fit": reuse_result is None, "error": errors}
    dump(job_dir / "result.json", result)
    return result


def aggregate(out, config, manifest):
    ranking, workload, failures = [], [], []
    for job in config["jobs"]:
        path = out / "fits" / job["job_id"] / "result.json"
        if not path.exists():
            continue
        result = checked_result(path, manifest["run_fingerprint"])
        evaluation = json.loads((path.parent / result["evaluation_path"]).read_text())
        resources = json.loads((path.parent / result["resources_path"]).read_text())
        identity = {k: job[k] for k in ("job_id", "test_id", "class", "seed", "regime", "method", "training_membership_sha256", "test_joint_components")}
        row = {**identity, "status": result["status"], "label_regime": "proxy", "physical_fit": result["physical_fit"],
               "ap_proxy": evaluation["ranking_ap"], "trapezoidal_pr_area_proxy": evaluation["ranking_trapezoidal_pr_area"],
               "prevalence_proxy": evaluation["ranking_prevalence"], "coverage": evaluation["scoring_coverage"],
               "n_test": evaluation["n_files"], "runtime_seconds": resources.get("total_seconds"),
               "convergence_warning": resources.get("convergence_warning"), "error_type": (result.get("error") or {}).get("type")}
        ranking.append(row)
        workload.extend({**identity, "status": result["status"], **b} for b in evaluation["budgets"])
        if result["status"] == "failed":
            failures.append({**identity, **result["error"]})
    folder = out / "summary"
    folder.mkdir(exist_ok=True)
    frame = pd.DataFrame(ranking)
    frame.to_csv(folder / "per_fit_ranking.csv", index=False)
    workload_frame = pd.DataFrame(workload)
    workload_frame.to_csv(folder / "per_fit_workload.csv", index=False)
    dump(folder / "failures.json", failures)
    grouped = []
    if len(frame):
        for key, part in frame.groupby(["test_id", "class", "regime", "method"], sort=True):
            good = part[part.status != "failed"]
            grouped.append({**dict(zip(["test_id", "class", "regime", "method"], key)),
                            "n_seed_evaluations_available": len(part), "n_successful_seed_evaluations": len(good),
                            "n_failures": len(part) - len(good), "n_physical_fits": int(part.physical_fit.sum()),
                            "n_distinct_training_memberships": int(part.training_membership_sha256.nunique()),
                            "mean_per_seed_ap_proxy_conditional_on_success": good.ap_proxy.mean() if len(good) else None,
                            "sd_per_seed_ap_proxy_conditional_on_success": good.ap_proxy.std(ddof=1) if len(good) > 1 else None,
                            "label_regime": "proxy", "pooling": "per_test_only_no_pooled_scores_no_CI"})
    pd.DataFrame(grouped).to_csv(folder / "per_test_seed_summary.csv", index=False)
    workload_summary = []
    if len(workload_frame):
        keys = ["test_id", "class", "regime", "method", "review_fraction_requested"]
        for key, part in workload_frame.groupby(keys, sort=True):
            good = part[part.status != "failed"]
            workload_summary.append({**dict(zip(keys, key)), "n_seed_evaluations_available": len(part),
                                     "n_failures": len(part) - len(good), "label_regime": "proxy",
                                     "mean_per_seed_review_count_achieved": part.review_count_achieved.mean(),
                                     "mean_per_seed_proxy_positive_yield_including_failures": part.known_positive_reviewed_expected.mean(),
                                     "mean_per_seed_proxy_recall_including_failures": part.known_positive_recall_expected.mean(),
                                     "mean_per_seed_judged_precision_ratio_conditional_on_success":
                                         good.judged_precision_ratio_of_expected_counts.mean() if len(good) else None,
                                     "aggregation": "mean_of_per_seed_metrics_within_one_test_no_score_pooling"})
    pd.DataFrame(workload_summary).to_csv(folder / "per_test_workload_summary.csv", index=False)
    return ranking


def run(args):
    out = args.out
    check_execution_gate(out)
    manifest, config, selected, labels = validate_run(out)
    sources = {int(i): source_path(row.path).read_text(encoding="utf-8", errors="replace") for i, row in selected.iterrows()}
    manifest.update(status="running_development", last_resumed_utc=utc())
    dump(out / "manifest.json", manifest)
    new_physical = 0
    for job in config["jobs"]:
        path = out / "fits" / job["job_id"] / "result.json"
        if path.exists():
            existing = checked_result(path, manifest["run_fingerprint"])
            if existing["status"] != "failed" or not args.retry_failed:
                continue
        reuse = None
        if job["reuse_from"]:
            old = out / "fits" / job["reuse_from"] / "result.json"
            if not old.exists():
                raise ValueError("Canonical deterministic fit is not available")
            candidate = checked_result(old, manifest["run_fingerprint"])
            # A failed deterministic fit is also reused as a recorded failure;
            # repeat only through explicit retry_failed on its canonical job.
            reuse = candidate
        if reuse is None and args.max_fits is not None and new_physical >= args.max_fits:
            break
        result = publish_job(out, job, config, manifest, sources, labels, reuse_result=reuse)
        new_physical += int(reuse is None)
        print(json.dumps({"job_id": job["job_id"], "test_id": job["test_id"], "class": job["class"],
                          "seed": job["seed"], "regime": job["regime"], "method": job["method"], "status": result["status"]}), flush=True)
        gc.collect()
    rows = aggregate(out, config, manifest)
    n_failed = sum(r["status"] == "failed" for r in rows)
    manifest.update(status=("partial_development" if len(rows) < len(config["jobs"]) else
                            "complete_development_with_failures" if n_failed else "complete_development"),
                    last_finished_utc=utc(), completed_logical_jobs=len(rows), failed_logical_jobs=n_failed,
                    output_hashes={str(p.relative_to(out)): sha(p) for p in sorted((out / "summary").glob("*")) if p.is_file()})
    dump(out / "manifest.json", manifest)
    print(json.dumps({k: manifest[k] for k in ("status", "completed_logical_jobs", "failed_logical_jobs")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--bundle", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    prep.add_argument("--classes", nargs="+", default=list(CLASSES))
    prep.add_argument("--seeds", nargs="+", type=int, default=list(range(5)))
    prep.add_argument("--methods", nargs="+", default=list(METHODS))
    prep.add_argument("--regimes", nargs="+", default=list(REGIMES))
    prep.add_argument("--test-ids", nargs="+")
    prep.add_argument("--assessment", type=Path, help="Immutable scientific assessment tied to this bundle; absent means blocked comparative execution")
    execute = commands.add_parser("run")
    execute.add_argument("--out", type=Path, required=True)
    execute.add_argument("--max-fits", type=int, help="Execution cap only; does not change the frozen campaign")
    execute.add_argument("--retry-failed", action="store_true", help="Keep previous attempts and retry only recorded failed jobs")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == "run" and args.max_fits is not None and args.max_fits < 0:
        parser.error("--max-fits must be nonnegative")
    (prepare if args.command == "prepare" else run)(args)


if __name__ == "__main__":
    main()
