"""Profile fixed ML methods on the development joint-disjoint pool, without test labels.

Run from the repository with its development environment:
  .venv/bin/python papers/security_evaluation/resource_profile.py \
    --pilot-run papers/security_evaluation/runs/dev_fixed_t_20261025_v1 \
    --out papers/security_evaluation/runs/resource_profile_20261025_v1

This is a resource measurement, not an accuracy experiment. It reuses one
development training membership and T, reads only training SWC annotations,
and discards predictions after checking shape and finiteness. No external
candidate, test labels, ranking metric, or model selection is used.
"""
from __future__ import annotations

import argparse
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
import warnings

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from bal.features.contract_features import normalised_text, pattern_matrix, raw_text

DAPP_PIN = "66a56619c44770e05c2db600fa6468115ff0dcd5"
JOINT = "joint_project_clone_disjoint"
METHODS = ("raw_tfidf_lr", "normalized_tfidf_lr", "pattern_rf", "pattern_lightgbm")
SNAPSHOTS = ("papers/security_evaluation/resource_profile.py",
             "src/bal/features/contract_features.py", "src/bal/models/tabular.py")


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def peak_mib():
    # Linux ru_maxrss is KiB and is a high-water mark for the entire process.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()


def load_training_labels(paths, expected_hashes):
    """Resolve only training annotation paths; never enumerate test annotations."""
    labels, used = [], {}
    prefix = "data/raw/DAppSCAN/DAppSCAN-source/contracts/"
    annotation_root = ROOT / "data/raw/DAppSCAN/DAppSCAN-source/SWCsource"
    for source_path in paths:
        if not source_path.startswith(prefix):
            raise ValueError(f"Non-DAppSCAN source in development training: {source_path}")
        suffix = Path(source_path[len(prefix):]).with_suffix(".json")
        annotation = annotation_root / suffix
        if not annotation.exists():
            labels.append(0)  # declared historical proxy, never called confirmed safe
            continue
        relative = str(annotation.relative_to(ROOT))
        actual_hash = digest(annotation)
        if expected_hashes.get(relative) != actual_hash:
            raise ValueError(f"Training label input missing or changed: {relative}")
        data = json.loads(annotation.read_text())
        expected_source = source_path.removeprefix("data/raw/DAppSCAN/")
        if data.get("filePath") != expected_source:
            raise ValueError(f"Annotation-to-source mismatch: {relative}")
        labels.append(int(any(x.get("category", "").split("-")[:2] == ["SWC", "107"]
                              for x in data.get("SWCs", []))))
        used[relative] = actual_hash
    return np.asarray(labels, dtype=np.int8), used


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    pilot, out = args.pilot_run, args.out
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing profile: {out}")
    out.mkdir(parents=True)
    started, setup_start = utc(), time.perf_counter()
    config = {
        "schema": "security_resource_profile_config_v1",
        "purpose": "resource_only_development_no_accuracy_evaluation",
        "pilot_run": str(pilot), "class": "reentrancy", "seed": 0,
        "training_regime": JOINT, "test_role": "common_test_source_only",
        "methods": list(METHODS), "tuning_budget": 0,
        "test_labels_read": False, "external_files_used": False,
        "prediction_persistence": "discard_after_shape_and_finiteness_check",
        "tfidf": {"token_pattern": r"\S+", "ngram_range": [1, 3], "min_df": 2,
                  "max_features": 50000, "sublinear_tf": True, "lowercase": False},
        "lr_scaler": {"class": "StandardScaler", "with_mean": False},
        "lr": {"C": 1.0, "max_iter": 3000, "class_weight": "balanced",
               "random_state": 0, "solver": "lbfgs", "tol": 0.0001},
        "rf": {"n_estimators": 500, "class_weight": "balanced_subsample",
               "min_samples_leaf": 1, "n_jobs": 4, "random_state": 0},
        "lightgbm": {"n_estimators": 400, "learning_rate": 0.05, "num_leaves": 31,
                     "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.8,
                     "class_weight": "balanced", "random_state": 0,
                     "verbose": -1, "n_jobs": 4},
        "threads": {"lr_native_pools": 1, "tree_jobs": 4, "tree_openmp_threads": 4, "tree_blas_threads": 1},
        "ram_metric": "Linux process ru_maxrss MiB, cumulative high-water mark across sequential methods",
        "projection": {"regimes": 4, "classes": 2, "paired_sampling_seeds": 5,
                       "evaluations_per_method": 40, "total_fits": 160,
                       "scope": "one fixed T and one training-size point; sequential no feature-cache reuse",
                       "excluded": ["data retrieval and audit", "expert review", "Slither",
                                    "bootstrap", "additional tests or learning-curve sizes", "hyperparameter tuning"]},
        "timing_scope": "preprocessing/fit/predict measured separately; imports, validation and source I/O reported as setup",
    }
    dump(out / "config.json", config)
    source_hashes = {}
    for relative in SNAPSHOTS:
        target = out / "code_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
        source_hashes[relative] = digest(target)

    # Import before per-model measurements; record all versions and native pools.
    import lightgbm as lgb
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from threadpoolctl import threadpool_info, threadpool_limits

    historical = json.loads((pilot / "manifest.json").read_text())
    if historical["status"] != "complete_development_only":
        raise ValueError("Expected completed development pilot, not an external run")
    for name, key in (("memberships.csv", "membership_sha256"),
                      ("source_inventory.csv", "source_inventory_sha256"),
                      ("label_input_hashes.json", "label_inputs_sha256")):
        if digest(pilot / name) != historical[key]:
            raise ValueError(f"Changed development input manifest: {name}")
    dapp = ROOT / "data/raw/DAppSCAN"
    if git("rev-parse", "HEAD", cwd=dapp) != DAPP_PIN:
        raise ValueError("DAppSCAN checkout not at pinned commit")
    if git("status", "--porcelain", "--untracked-files=no", cwd=dapp):
        raise ValueError("DAppSCAN tracked source has local changes")
    members = pd.read_csv(pilot / "memberships.csv")
    train = members[(members.role == "train") & (members.regime == JOINT)].copy()
    test = members[members.role == "test"].copy()
    if train.empty or test.empty or set(train.file_id) & set(test.file_id):
        raise ValueError("Invalid train/test memberships")
    if set(train.joint_id) & set(test.joint_id):
        raise ValueError("Joint component intersection in saved development memberships")
    if train.path.duplicated().any() or test.path.duplicated().any():
        raise ValueError("Duplicate source path within a profile partition")
    inventory = pd.read_csv(pilot / "source_inventory.csv").set_index("file_id")
    selected = pd.concat([train, test], ignore_index=True)
    selected_hashes = []
    for row in selected.itertuples():
        baseline = inventory.loc[row.file_id]
        for field in ("dataset", "path", "group", "comp", "joint_id"):
            if getattr(row, field) != baseline[field]:
                raise ValueError(f"Membership differs from frozen inventory: {row.file_id}, {field}")
        if row.dataset != "dappscan":
            raise ValueError("Only DAppSCAN development files are permitted")
        if digest(ROOT / row.path) != baseline.file_sha256:
            raise ValueError(f"Changed source code: {row.path}")
        selected_hashes.append({"file_id": row.file_id, "role": row.role,
                                "path": row.path, "file_sha256": baseline.file_sha256})
    pd.DataFrame(selected_hashes).to_csv(out / "selected_source_hashes.csv", index=False)
    # This JSON contains only paths and digests, not third-party label values.
    label_hashes = json.loads((pilot / "label_input_hashes.json").read_text())
    y_train, training_annotations = load_training_labels(train.path, label_hashes)
    if len(train) != historical["matched_training_n"] or int(y_train.sum()) != historical["matched_training_positive_proxy"]:
        raise ValueError("Training-only label extraction differs from frozen pilot counts")
    dump(out / "training_annotation_hashes.json", training_annotations)
    train_source = [(ROOT / p).read_text(encoding="utf-8", errors="replace") for p in train.path]
    test_source = [(ROOT / p).read_text(encoding="utf-8", errors="replace") for p in test.path]
    environment = {
        "python": sys.version, "platform": platform.platform(), "logical_cpu_count": os.cpu_count(),
        "cpu_affinity_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "cpu_max": Path("/sys/fs/cgroup/cpu.max").read_text().strip() if Path("/sys/fs/cgroup/cpu.max").exists() else None,
        "packages": {p: importlib.metadata.version(p) for p in
                     ("numpy", "pandas", "scipy", "scikit-learn", "lightgbm", "psutil", "threadpoolctl")},
        "threadpool_info_before_limits": threadpool_info(), "configured_threads": config["threads"],
    }
    dump(out / "environment.json", environment)
    manifest = {
        "schema": "security_resource_profile_run_v1", "status": "prepared_no_measurements",
        "started_utc": started, "prepared_utc": utc(), "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")), "source_snapshots": source_hashes,
        "data_commit": DAPP_PIN, "config_sha256": digest(out / "config.json"),
        "development_inputs": {str(pilot / n): digest(pilot / n) for n in
                               ("manifest.json", "memberships.csv", "source_inventory.csv", "label_input_hashes.json")},
        "n_train": len(train), "training_positive_proxy": int(y_train.sum()), "n_test_source_only": len(test),
        "test_annotation_files_read": 0, "test_labels_used": False, "external_scores_computed": False,
        "accuracy_metrics_computed": False, "predictions_saved": False,
        "training_label_semantics": "published SWC-107 finding versus no published finding; proxy only",
        "input_output_hashes": {n: digest(out / n) for n in
                              ("selected_source_hashes.csv", "training_annotation_hashes.json", "environment.json")},
        "setup_seconds": time.perf_counter() - setup_start,
    }
    dump(out / "manifest.json", manifest)
    # A complete source snapshot, configuration and validated input hashes exist
    # before this point. Any later error leaves its partial profile visible.
    for relative, expected in source_hashes.items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"Source changed while preparing profile: {relative}")
    rows, pool_records = [], []
    measurement_start = time.perf_counter()
    manifest.update(status="measuring", measurement_started_utc=utc())
    dump(out / "manifest.json", manifest)
    for method in METHODS:
        gc.collect()
        t_method = time.perf_counter()
        lexical = method.endswith("tfidf_lr")
        # Cap native OpenMP as well as the estimator's explicit n_jobs. BLAS
        # remains single-threaded to avoid nested oversubscription for trees.
        with threadpool_limits(limits=1 if lexical else 4), threadpool_limits(limits=1, user_api="blas"):
            pool_records.append({"method": method, "before_fit": threadpool_info()})
            prep = time.perf_counter()
            if lexical:
                transform = raw_text if method == "raw_tfidf_lr" else normalised_text
                vectorizer = TfidfVectorizer(**{**config["tfidf"], "ngram_range": tuple(config["tfidf"]["ngram_range"])})
                scaler = StandardScaler(with_mean=False)
                x_train = scaler.fit_transform(vectorizer.fit_transform([transform(x) for x in train_source]))
                train_prep = time.perf_counter() - prep
                prep = time.perf_counter()
                x_test = scaler.transform(vectorizer.transform([transform(x) for x in test_source]))
                model = LogisticRegression(**config["lr"])
            else:
                x_train = pattern_matrix(train_source).to_numpy(dtype=np.float32)
                train_prep = time.perf_counter() - prep
                prep = time.perf_counter()
                x_test = pattern_matrix(test_source).to_numpy(dtype=np.float32)
                model = RandomForestClassifier(**config["rf"]) if method == "pattern_rf" else lgb.LGBMClassifier(**config["lightgbm"])
            test_prep = time.perf_counter() - prep
            with warnings.catch_warnings(record=True) as observed:
                warnings.simplefilter("always")
                fit_start = time.perf_counter()
                model.fit(x_train, y_train)
                fit_seconds = time.perf_counter() - fit_start
                predict_start = time.perf_counter()
                scores = model.predict_proba(x_test)[:, 1]
                predict_seconds = time.perf_counter() - predict_start
            if scores.shape != (len(test),) or not np.isfinite(scores).all():
                raise ValueError(f"Invalid resource-profile prediction output for {method}")
            pool_records[-1]["after_fit"] = threadpool_info()
            row = {
                "method": method, "seed": 0, "n_train": len(train), "n_test_source_only": len(test),
                "n_features": x_train.shape[1], "train_preprocessing_seconds": train_prep,
                "test_preprocessing_seconds": test_prep, "fit_seconds": fit_seconds,
                "predict_seconds": predict_seconds, "method_total_seconds": time.perf_counter() - t_method,
                "process_peak_rss_mib_cumulative": peak_mib(),
                "instantaneous_rss_status": "not_measured_pid_namespace_incompatible_with_psutil",
                "configured_native_threads": 1 if lexical else 4,
                "iterations": int(model.n_iter_[0]) if lexical else int(model.n_estimators),
                "convergence_warning": any(type(w.message).__name__ == "ConvergenceWarning" for w in observed),
                "warnings": " | ".join(str(w.message) for w in observed),
            }
            rows.append(row)
            pd.DataFrame(rows).to_csv(out / "resource_measurements.csv", index=False)
            print(json.dumps(row), flush=True)
            del model, x_train, x_test, scores
            if lexical:
                del vectorizer, scaler
    measurement_seconds = time.perf_counter() - measurement_start
    dump(out / "threadpools_by_method.json", pool_records)
    projection = {
        **config["projection"],
        "model_seconds_for_40_evaluations": {r["method"]: r["method_total_seconds"] * 40 for r in rows},
        "total_model_seconds_for_160_evaluations": sum(r["method_total_seconds"] for r in rows) * 40,
        "interpretation": "Linear extrapolation from one joint-disjoint training pool, one class and one seed. Not a runtime guarantee; other pools, vocabulary and class can change cost.",
        "setup_seconds_measured_once": manifest["setup_seconds"],
        "peak_rss_mib_for_sequential_profile": peak_mib(),
        "gpu_required": False,
    }
    projection["total_model_minutes_for_160_evaluations"] = projection["total_model_seconds_for_160_evaluations"] / 60
    dump(out / "projection.json", projection)
    manifest.update(status="complete_resource_only", finished_utc=utc(), measurement_seconds=measurement_seconds,
                    process_peak_rss_mib_cumulative=peak_mib(),
                    output_hashes={n: digest(out / n) for n in
                                   ("resource_measurements.csv", "threadpools_by_method.json", "projection.json")})
    dump(out / "manifest.json", manifest)
    print(json.dumps(projection), flush=True)


if __name__ == "__main__":
    main()
