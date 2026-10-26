"""Prospectively gated learned-model worker; synthetic entry point is separate.

No import-time input reads. Production admission must finish before source or
training-label access. Hashes establish integrity, never human authenticity.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import importlib
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_info, threadpool_limits

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE.parent
ROOT = HERE.parents[4]
METHODS = ("raw_tfidf_lr", "normalized_tfidf_lr", "pattern_rf", "pattern_lgbm")
CLASSES = ("reentrancy", "unchecked")
LR = dict(C=1, max_iter=3000, class_weight="balanced", solver="lbfgs", tol=1e-4)
RF = dict(n_estimators=500, class_weight="balanced_subsample", min_samples_leaf=1, n_jobs=4)
LGBM = dict(n_estimators=400, learning_rate=.05, num_leaves=31, subsample=.8,
            subsample_freq=1, colsample_bytree=.8, class_weight="balanced", n_jobs=4)
PACKAGES = ("numpy", "pandas", "scipy", "scikit-learn", "lightgbm", "joblib", "threadpoolctl")
RAW_STATUS_MAP = {"ok": "ok", "decode_error": "preprocessing_error", "scanner_error": "preprocessing_error",
    "empty_token_stream": "preprocessing_error", "zero_vocabulary_vector": "preprocessing_error",
    "model_error": "model_error"}


class WorkerError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise WorkerError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


WORKER_LOADED_SHA256 = sha(Path(__file__))
_ADAPTER_LOADED_DIGESTS = None


def verify_loaded_sources():
    require(sha(HERE / "worker.py") == WORKER_LOADED_SHA256, "Worker source changed since import; start a fresh process")
    if _ADAPTER_LOADED_DIGESTS is not None:
        for path, expected in _ADAPTER_LOADED_DIGESTS.items():
            require(sha(path) == expected, "Adapter dependency changed since import; start a fresh process")


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def utc():
    return datetime.now(timezone.utc).isoformat()


def module(name, path):
    path = Path(path)
    source = path.read_bytes()
    loaded_sha256 = hashlib.sha256(source).hexdigest()
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(name)
    sys.modules[name] = result
    try:
        # Bypass timestamp/size-valid stale .pyc: execute the exact hashed bytes.
        exec(compile(source, str(path), "exec", dont_inherit=True), result.__dict__)
        require(sha(path) == loaded_sha256, "Module source changed during import")
    except Exception:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    result.__loaded_source_sha256__ = loaded_sha256
    return result


def adapters():
    global _ADAPTER_LOADED_DIGESTS
    verify_loaded_sources()
    name = "external_B_worker_adapters"
    if name in sys.modules:
        require(_ADAPTER_LOADED_DIGESTS is not None, "Unpinned cached adapter module")
        return sys.modules[name]
    paths = [PROTOCOL / "adapters_v1/adapters.py", ROOT / "src/bal/features/contract_features.py",
             ROOT / "papers/security_evaluation/normalization_audit/solidity_scanner.py"]
    before = {p: sha(p) for p in paths}
    sys.path.insert(0, str(ROOT / "src"))
    importlib.import_module("bal.features")
    # Do not silently reuse dependency modules imported under an older binding.
    module("bal.features.contract_features", paths[1])
    module("solidity_scanner", paths[2])
    loaded = module(name, paths[0])
    require(all(sha(p) == h for p, h in before.items()), "Source changed during adapter import")
    _ADAPTER_LOADED_DIGESTS = before
    return loaded


def jobs():
    return [{"job_id": f"{m}:{c}:{s}", "kind": "learned", "method": m, "class": c, "seed": s}
            for m in METHODS for c in CLASSES for s in ([0] if m.endswith("_lr") else range(5))]


def validate_job(job):
    require(job in jobs(), "Job must exactly match one of the 24 fixed learned configurations")
    return dict(job)


def parameters(job):
    validate_job(job)
    fixed = LR if job["method"].endswith("_lr") else RF if job["method"] == "pattern_rf" else LGBM
    return {**fixed, "random_state": job["seed"]}


def estimator(job):
    params = parameters(job)
    if job["method"].endswith("_lr"):
        return LogisticRegression(**params)
    if job["method"] == "pattern_rf":
        return RandomForestClassifier(**params)
    from lightgbm import LGBMClassifier
    return LGBMClassifier(**params, verbosity=-1)


def source_files():
    files = [HERE / "worker.py", PROTOCOL / "review_estimators.py", PROTOCOL / "adapters_v1/adapters.py", PROTOCOL / "adapters_v1/adapter_plan.json", PROTOCOL / "adapters_v1/feature_definitions.json",
             ROOT / "src/bal/features/contract_features.py", ROOT / "papers/security_evaluation/normalization_audit/solidity_scanner.py"]
    for name in ("integrity_preflight.py", "validate_gate_v2.py", "scoring_admission.py"):
        path = PROTOCOL / "orchestration_v1" / name
        if path.exists():
            files.append(path)
    return {str(p.relative_to(ROOT)): p for p in files}


def environment():
    actual_names = {"scikit-learn": "sklearn"}
    versions = {p: importlib.metadata.version(p) for p in PACKAGES}
    for package, version in versions.items():
        loaded = importlib.import_module(actual_names.get(package, package))
        require(loaded.__version__ == version, "Loaded package differs from installed distribution: " + package)
    return {"python": sys.version, "packages": versions}


def _inputs(train_records, external_records, labels, job, synthetic):
    """Validate exact record/label membership before fit, never drop training rows."""
    a = adapters()
    train_records, external_records = tuple(train_records), tuple(external_records)
    require(train_records and external_records, "Nonempty train/external manifests required")
    require(all(isinstance(r, a.SourceRecord) and r.role == "train" for r in train_records), "Training roles required")
    require(all(isinstance(r, a.SourceRecord) and r.role == "external" for r in external_records), "External roles required")
    train_ids, external_ids = [r.sample_id for r in train_records], [r.sample_id for r in external_records]
    require(len(set(train_ids)) == len(train_ids) and len(set(external_ids)) == len(external_ids), "Duplicate source identity")
    require(not set(train_ids) & set(external_ids), "Train/external identity overlap")
    require(list(labels) == train_ids, "Training labels must exactly match ordered training identities")
    y = np.asarray(list(labels.values()))
    require(y.shape == (len(train_ids),) and np.isin(y, [0, 1]).all() and len(np.unique(y)) == 2, "Both binary proxy classes required")
    if synthetic:
        require(all(i.startswith("synthetic:") for i in train_ids + external_ids), "Synthetic identity prefix required")
    else:
        require(len(train_ids) == 691 and len(external_ids) == 1998, "Fixed production membership counts required")
        require(int(y.sum()) == (23 if job["class"] == "reentrancy" else 18), "Pinned training proxy positive count changed")
    raw = lambda r: r.source if isinstance(r.source, bytes) else r.source.encode("utf-8")
    train_hashes = [hashlib.sha256(raw(r)).hexdigest() for r in train_records]
    external_hashes = [hashlib.sha256(raw(r)).hexdigest() for r in external_records]
    require(not set(train_hashes) & set(external_hashes), "Exact source identity overlaps train and external")
    return train_records, external_records, y.astype(int), train_hashes, external_hashes


def _artifact(root, path):
    return {"path": str(Path(path).resolve().relative_to(Path(root).resolve())), "sha256": sha(path)}


def _resume(out, config):
    path = out / "receipt.json"
    require(path.is_file(), "Existing incomplete job cannot be silently resumed or overwritten")
    receipt = json.loads(path.read_text())
    require(receipt.get("status") in ("complete", "complete_failed_fit"), "Job completion receipt required")
    require(receipt.get("config_sha256") == digest(config), "Resume refused: input/config/code/environment changed")
    require(json.loads((out / "config.json").read_text()) == config, "Saved config differs")
    listed = receipt.get("artifact_sha256")
    require(isinstance(listed, dict) and listed, "Artifact inventory missing")
    actual = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and p != path and "__pycache__" not in p.parts}
    require(actual == set(listed), "Resume artifact set changed")
    for rel, expected in listed.items():
        require(sha(out / rel) == expected, "Resume artifact hash changed: " + rel)
    rows = pd.read_csv(out / "scores.csv", keep_default_na=False)
    require(rows.node_id.astype(str).tolist() == config["external_ids"], "Resume score membership/order changed")
    require(rows.path.tolist() == config["external_paths"], "Resume score paths changed")
    return {**receipt, "resume_verified_no_refit": True}


def _run_records(job, train_records, external_records, labels, *, out, binding, external_paths,
                 synthetic=False, resume=False):
    """Private computational core; production caller must pass admission first."""
    job = validate_job(job)
    train, external, y, train_hashes, ext_hashes = _inputs(train_records, external_records, labels, job, synthetic)
    out = Path(out).resolve()
    require(len(external_paths) == len(external) and len(set(external_paths)) == len(external), "Full unique path list required")
    sources = source_files()
    config = {"schema": "external_B_learned_job_config_v1", "job": job, "synthetic_fixture": synthetic,
        "estimator_parameters": parameters(job), "training_ids": [r.sample_id for r in train],
        "training_source_sha256": train_hashes, "training_labels_sha256": digest(dict(labels)),
        "external_ids": [r.sample_id for r in external], "external_source_sha256": ext_hashes,
        "external_paths": list(external_paths), "binding": binding, "environment": environment(),
        "code_sha256": {rel: sha(p) for rel, p in sources.items()}, "status_mapping": RAW_STATUS_MAP,
        "threads": {"blas": 1, "openmp": 1 if job["method"].endswith("_lr") else 4,
                    "tree_n_jobs": None if job["method"].endswith("_lr") else 4},
        "training_proxy_interpretation": "source-reported training findings; absence is proxy zero, not expert-confirmed negative",
        "full_external_scores_without_labels": True, "no_hyperparameter_tuning": True}
    if out.exists():
        require(resume, "Output already exists; explicit resume required")
        return _resume(out, config)
    out.mkdir(parents=True)
    dump(out / "config.json", config)
    for rel, source in sources.items():
        target = out / "source_snapshot" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    started = utc()
    dump(out / "receipt.json", {"status": "prepared_before_feature_fit", "config_sha256": digest(config), "prepared_utc": started})
    a = adapters()
    adapter = a.adapter_for_method(job["method"])
    model = estimator(job)
    timings = {"training_preprocessing_seconds": 0., "fit_seconds": 0., "external_transform_seconds": 0., "predict_seconds": 0.}
    observed_threads, captured_warnings, preprocessing, failure = [], [], [], None
    train_state_before, train_state_after = None, None
    scores = [{"job_id": job["job_id"], "method": job["method"], "class": job["class"], "seed": job["seed"],
               "node_id": r.sample_id, "path": path, "source_sha256": h, "execution_status": "model_error", "status": "model_error", "score": ""}
              for r, path, h in zip(external, external_paths, ext_hashes)]
    index = {row["node_id"]: row for row in scores}
    wall = time.perf_counter()
    cpu = time.process_time()
    openmp = config["threads"]["openmp"]
    fit_success = False
    stage = "training_preprocessing_seconds"
    with threadpool_limits(limits=1, user_api="blas"), threadpool_limits(limits=openmp, user_api="openmp"):
        observed_threads = threadpool_info()
        try:
            t = time.perf_counter()
            training = adapter.fit_transform_training(train)
            timings["training_preprocessing_seconds"] = time.perf_counter() - t
            preprocessing.extend(training.coverage)
            require(training.row_ids == tuple(config["training_ids"]), "Adapter changed training membership/order")
            train_state_before = adapter.training_state_metadata() if hasattr(adapter, "training_state_metadata") else {"representation": "pattern43", "stateless": True, "scaler": "none"}
            stage, t = "fit_seconds", time.perf_counter()
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                model.fit(training.matrix, y)
            timings["fit_seconds"] = time.perf_counter() - t
            captured_warnings = [{"category": type(x.message).__name__, "message": str(x.message),
                                  "convergence_warning": issubclass(x.category, ConvergenceWarning)} for x in caught]
            fit_success = True
            stage, t = "external_transform_seconds", time.perf_counter()
            transformed = adapter.transform(external)
            timings["external_transform_seconds"] = time.perf_counter() - t
            preprocessing.extend(transformed.coverage)
            train_state_after = adapter.training_state_metadata() if hasattr(adapter, "training_state_metadata") else train_state_before
            require(train_state_before == train_state_after, "External transform mutated training feature state")
            positions = {identity: i for i, identity in enumerate(transformed.row_ids)}
            ready_ids = []
            for row in transformed.coverage:
                raw_status = row["representation_status"]
                if row["feature_ready"]:
                    ready_ids.append(row["sample_id"])
                else:
                    require(raw_status in RAW_STATUS_MAP, "Unmapped preprocessing failure: " + raw_status)
                    index[row["sample_id"]].update(execution_status=raw_status, status=RAW_STATUS_MAP[raw_status])
            if ready_ids:
                stage, t = "predict_seconds", time.perf_counter()
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    probability = model.predict_proba(transformed.matrix[[positions[i] for i in ready_ids]])
                captured_warnings.extend({"category": type(x.message).__name__, "message": str(x.message),
                    "convergence_warning": issubclass(x.category, ConvergenceWarning), "stage": "predict"} for x in caught)
                cls = list(model.classes_).index(1)
                values = probability[:, cls]
                require(len(values) == len(ready_ids) and np.isfinite(values).all(), "Nonfinite model probability")
                require(((values >= 0) & (values <= 1)).all(), "Probability outside [0,1]")
                for identity, value in zip(ready_ids, values):
                    index[identity].update(execution_status="ok", status="ok", score=float(value))
                timings["predict_seconds"] = time.perf_counter() - t
        except Exception as exc:
            timings[stage] = time.perf_counter() - t
            failure = {"type": type(exc).__name__, "message": str(exc), "during_or_after_fit": fit_success}
            if hasattr(exc, "coverage"):
                preprocessing.extend(exc.coverage)
            # Preserve prior explicit preprocessing failures; no numerical safe fallback.
    elapsed, process_cpu = time.perf_counter() - wall, time.process_time() - cpu
    pd.DataFrame(scores).to_csv(out / "scores.csv", index=False)
    dump(out / "preprocessing.json", preprocessing)
    dump(out / "fit_log.json", {"failure": failure, "warnings": captured_warnings,
        "convergence_warning_n": sum(x["convergence_warning"] for x in captured_warnings), "timings": timings,
        "elapsed_seconds": elapsed, "process_cpu_seconds": process_cpu,
        "peak_RSS_MiB_cumulative_process": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "peak_memory_scope": "Linux ru_maxrss cumulative process high-water mark; not isolated per-job allocation",
        "configured_threads": config["threads"], "observed_threadpools_during_fit_context": observed_threads,
        "fit_started_utc": started, "scoring_completed_utc": utc()})
    state = {"schema": "external_B_fitted_state_binding_v1", "job_id": job["job_id"], **binding,
        "training_node_ids": config["training_ids"], "training_source_sha256": train_hashes,
        "fit_scope": "training_manifest_only", "fit_status": "ok" if fit_success else "failed",
        "adapter_state_before_external": train_state_before, "adapter_state_after_external": train_state_after,
        "training_reference": config["training_proxy_interpretation"], "synthetic_fixture": synthetic}
    artifact_root = Path(binding["artifact_root"]).resolve()
    if fit_success:
        joblib.dump({"model": model, "adapter": adapter, "job": job, "training_ids": config["training_ids"]}, out / "fitted_bundle.joblib", compress=3)
        joblib.dump(model, out / "model.joblib", compress=3)
        joblib.dump(adapter, out / "adapter.joblib", compress=3)
        state.update(fitted_object=_artifact(artifact_root, out / "fitted_bundle.joblib"),
                     model=_artifact(artifact_root, out / "model.joblib"), adapter=_artifact(artifact_root, out / "adapter.joblib"))
        if hasattr(adapter, "_scaler"):
            joblib.dump(adapter._scaler, out / "scaler.joblib", compress=3)
            state["scaler"] = _artifact(artifact_root, out / "scaler.joblib")
        else:
            state["scaler"] = "none_stateless_pattern43"
        state["effective_model_parameters"] = model.get_params()
    else:
        state["fitted_object"] = None
        state["failure_log"] = _artifact(artifact_root, out / "fit_log.json")
    dump(out / "fitted_state.json", state)
    for rel, expected in config["code_sha256"].items():
        require(sha(ROOT / rel) == expected, "Live code changed during job; completion refused")
    receipt = {"schema": "external_B_learned_job_receipt_v1", "status": "complete" if fit_success else "complete_failed_fit",
        "job_id": job["job_id"], "config_sha256": digest(config), "synthetic_fixture": synthetic,
        "binding_sha256": binding["binding_sha256"], "method_config_sha256": binding["method_config_sha256"],
        "reference_event_sha256": binding["reference_event_sha256"], "training_manifest_sha256": binding["training_manifest_sha256"],
        "fit_scope": "training_manifest_only", "fit_started_utc": started, "scoring_completed_utc": utc(),
        "state_artifact": _artifact(artifact_root, out / "fitted_state.json"), "scores_artifact": _artifact(artifact_root, out / "scores.csv"),
        "external_rows": len(scores), "status_counts": pd.DataFrame(scores).status.value_counts().to_dict(),
        "human_identity_authenticated": False, "resume_verified_no_refit": False,
        "artifact_sha256": {str(p.relative_to(out)): sha(p) for p in out.rglob("*") if p.is_file() and p.name != "receipt.json"}}
    dump(out / "receipt.json", receipt)
    return receipt


def orchestration():
    module("validate_gate_v2", PROTOCOL / "orchestration_v1/validate_gate_v2.py")
    module("review_estimators", PROTOCOL / "review_estimators.py")
    return module("external_B_worker_preflight", PROTOCOL / "orchestration_v1/integrity_preflight.py")


def dry_preflight(root, binding_path, expected_sha256, release_path):
    """Read-only early admission. Never opens training labels or source contents."""
    verify_loaded_sources()
    p = orchestration()
    require(hasattr(p, "admission_preflight"), "Orchestration early-admission API unavailable; fail closed")
    result = p.admission_preflight(Path(root), Path(binding_path), expected_sha256, Path(release_path))
    return {"schema": "external_B_worker_dry_preflight_v1", "admission": result,
            "execution_authorized": False, "model_fits": 0, "training_labels_or_sources_opened_by_worker": False,
            "coordinator_runtime_authorization_still_required": True}


def _authorize(p, root, binding_path, expected_sha256, release_path, authorization_path, authorization_sha256, job):
    require(hasattr(p, "admission_preflight"), "Early-admission API unavailable")
    admission = p.admission_preflight(root, binding_path, expected_sha256, release_path)
    require(admission.get("admission_artifacts_consistent") is True, "Admission denied: " + json.dumps(admission.get("blockers", [])))
    # A separate caller-supplied trusted digest selects the coordinator instruction.
    # This records procedural authorization; names/hashes do not authenticate people.
    require(sha(authorization_path) == authorization_sha256, "Coordinator authorization anchor mismatch")
    auth = json.loads(Path(authorization_path).read_text())
    require(auth.get("schema") == "external_B_coordinator_execution_authorization_v1", "Authorization schema")
    require(auth.get("action") == "learned_fit_and_score" and auth.get("authorized") is True, "Runtime action not authorized")
    require(isinstance(auth.get("coordinator_id"), str) and auth["coordinator_id"].strip(), "Coordinator provenance missing")
    require(auth.get("binding_sha256") == expected_sha256 and auth.get("release_sha256") == sha(release_path), "Authorization input/release mismatch")
    require(auth.get("worker_sha256") == sha(HERE / "worker.py"), "Authorization worker mismatch")
    require(isinstance(auth.get("authorized_job_ids"), list) and job["job_id"] in auth["authorized_job_ids"] and
            set(auth["authorized_job_ids"]) <= {j["job_id"] for j in jobs()}, "Job outside authorized fixed inventory")
    p.timestamp(auth.get("issued_utc"))
    binding = json.loads(Path(binding_path).read_text())
    require(binding.get("synthetic_fixture") is False, "Production execute never accepts synthetic bindings/profiles")
    require(binding["code"]["model_worker"]["sha256"] == sha(HERE / "worker.py"), "Live worker differs from prospective binding")
    release = json.loads(Path(release_path).read_text())
    require(auth.get("reference_event_sha256") == release["events"][-1]["sha256"], "Authorization reference-event mismatch")
    event = p.read_json(p.artifact(root, release["events"][-1]))
    require(p.timestamp(auth["issued_utc"]) >= p.timestamp(event["sealed_utc"]), "Authorization predates sealed adjudication")
    # Only after human release and runtime instruction may full validation inspect
    # private training labels and source bytes. It still must pass before any fit.
    report = p.check(root, binding_path, expected_sha256, phase="begin_scoring", release_path=release_path)
    require(report.get("phase_integrity_pass") is True, "Full source/tool integrity denied: " + json.dumps(report.get("blockers", [])))
    require(job in report.get("declared_jobs", []), "Job differs from orchestration plan")
    config = p.read_json(p.artifact(root, binding["artifacts"]["method_config"]))
    fixed = json.loads((PROTOCOL / "adapters_v1/adapter_plan.json").read_text())["methods"]
    require(config.get("model_configurations") == fixed, "Method configurations differ from fixed historical parameters")
    require(config.get("learned_worker_environment") == environment(), "Installed learned-model environment differs from prospective config")
    require(sorted([j for j in report["declared_jobs"] if j["kind"] == "learned"], key=lambda j: j["job_id"]) ==
            sorted(jobs(), key=lambda j: j["job_id"]), "Expected exactly the 24 fixed learned jobs")
    for raw, canonical in RAW_STATUS_MAP.items():
        require(config["score_status_mapping"].get(raw) == canonical, "Unfrozen worker status mapping: " + raw)
    for role, path in (("adapters", PROTOCOL / "adapters_v1/adapters.py"),
                       ("contract_features", ROOT / "src/bal/features/contract_features.py"),
                       ("solidity_scanner", ROOT / "papers/security_evaluation/normalization_audit/solidity_scanner.py")):
        require(binding["code"][role]["sha256"] == sha(path), "Live dependency differs from binding: " + role)
    return binding, auth, report


def execute(root, binding_path, expected_sha256, release_path, authorization_path, authorization_sha256,
            job_id, out, *, resume=False):
    """Future production entry: no synthetic profile, no permission bypass flag."""
    verify_loaded_sources()
    root, binding_path, release_path, authorization_path, out = map(lambda x: Path(x).resolve(),
        (root, binding_path, release_path, authorization_path, out))
    job = next((j for j in jobs() if j["job_id"] == job_id), None)
    require(job is not None, "Unknown fixed learned job")
    require(out.is_relative_to(root) and out != root, "Output must be a separate directory inside binding root")
    p = orchestration()
    binding, auth, report = _authorize(p, root, binding_path, expected_sha256, release_path,
                                      authorization_path, authorization_sha256, job)
    arts = binding["artifacts"]
    train = p.csv(p.artifact(root, arts["training_manifest"]))
    external = p.csv(p.artifact(root, arts["test_manifest"]))
    labels = p.csv(p.artifact(root, arts["training_labels"]))
    require(labels.file_id.tolist() == train.file_id.tolist() and labels.path.tolist() == train.path.tolist(), "Private training label identities changed")
    a = adapters()
    records = {}
    for role, frame in (("train", train), ("external", external)):
        source_root = p.local(root, binding["source_roots"][role])
        records[role] = []
        for row in frame.itertuples():
            path = p.local(source_root, row.path)
            raw = path.read_bytes()
            expected = row.file_sha256 if role == "train" else row.file_hash
            require(hashlib.sha256(raw).hexdigest() == expected, "Source changed after admission")
            records[role].append(a.SourceRecord(str(row.node_id), role, raw))
    provenance = {"artifact_root": str(root), "binding_sha256": expected_sha256,
        "method_config_sha256": arts["method_config"]["sha256"], "training_manifest_sha256": arts["training_manifest"]["sha256"],
        "training_labels_artifact_sha256": arts["training_labels"]["sha256"], "test_manifest_sha256": arts["test_manifest"]["sha256"],
        "reference_event_sha256": auth["reference_event_sha256"], "authorization_sha256": authorization_sha256,
        "release_sha256": sha(release_path), "human_identity_authenticated": False}
    training_labels = dict(zip(train.node_id.astype(str), labels[job["class"]].astype(int)))
    return _run_records(job, records["train"], records["external"], training_labels, out=out,
                        binding=provenance, external_paths=external.path.tolist(), resume=resume)


def synthetic_records():
    """Fixed built-in fictional inputs. No input paths or user-supplied sources."""
    a = adapters()
    train = []
    for i in range(12):
        action = "msg.sender.call{value: amount}(payload); balances[msg.sender] = 0;" if i % 2 else "require(amount > 0); balances[msg.sender] = amount;"
        text = f"pragma solidity ^0.8.0; contract FictionalTraining{i} {{ mapping(address => uint) balances; function withdraw(uint amount, bytes memory payload) public {{ {action} }} }}"
        train.append(a.SourceRecord(f"synthetic:train:{i}", "train", text))
    external = [a.SourceRecord(f"synthetic:external:{i}", "external", f"pragma solidity ^0.8.0; contract FictionalExternal{i} {{ function draw(uint amount) public {{ require(amount > {i}); }} }}") for i in range(4)]
    external += [a.SourceRecord("synthetic:external:4", "external", b"\xff"),
                 a.SourceRecord("synthetic:external:5", "external", "/* unterminated fictional comment")]
    return tuple(train), tuple(external), {r.sample_id: i % 2 for i, r in enumerate(train)}


def synthetic_job(job_id, out, *, resume=False):
    """Synthetic-only convenience; has no arguments capable of selecting real data."""
    job = next((j for j in jobs() if j["job_id"] == job_id), None)
    require(job is not None, "Unknown synthetic test job")
    train, external, labels = synthetic_records()
    out = Path(out).resolve()
    provenance = {"artifact_root": str(out.parent), "binding_sha256": "0" * 64,
        "method_config_sha256": digest(parameters(job)), "training_manifest_sha256": digest([r.sample_id for r in train]),
        "reference_event_sha256": "0" * 64, "authorization": "BUILT_IN_FICTIONAL_TEST_NOT_REAL_EXECUTION"}
    return _run_records(job, train, external, labels, out=out, binding=provenance,
                        external_paths=[r.sample_id + ".sol" for r in external], synthetic=True, resume=resume)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("preflight", "execute"):
        p = sub.add_parser(command)
        p.add_argument("--root", type=Path, required=True)
        p.add_argument("--binding", type=Path, required=True)
        p.add_argument("--expected-binding-sha256", required=True)
        p.add_argument("--release", type=Path, required=True)
        if command == "execute":
            p.add_argument("--authorization", type=Path, required=True)
            p.add_argument("--expected-authorization-sha256", required=True)
            p.add_argument("--job-id", required=True)
            p.add_argument("--out", type=Path, required=True)
            p.add_argument("--resume", action="store_true")
    p = sub.add_parser("synthetic-fixture")
    p.add_argument("--job-id", choices=[j["job_id"] for j in jobs()], required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            result = dry_preflight(args.root, args.binding, args.expected_binding_sha256, args.release)
        elif args.command == "execute":
            result = execute(args.root, args.binding, args.expected_binding_sha256, args.release,
                args.authorization, args.expected_authorization_sha256, args.job_id, args.out, resume=args.resume)
        else:
            result = synthetic_job(args.job_id, args.out, resume=args.resume)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 2 if args.command == "preflight" and not result["admission"].get("admission_artifacts_consistent") else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked_or_incomplete", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
