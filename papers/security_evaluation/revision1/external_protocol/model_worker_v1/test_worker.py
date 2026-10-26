"""Built-in fictional fits and adversarial admission/resume tests only."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tested_learned_worker", HERE / "worker.py")
w = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = w
spec.loader.exec_module(w)


@pytest.fixture(scope="module")
def fitted(tmp_path_factory):
    root = tmp_path_factory.mktemp("fictional_worker")
    outputs = {}
    for method in w.METHODS:
        path = root / method
        receipt = w.synthetic_job(f"{method}:reentrancy:0", path)
        outputs[method] = (path, receipt)
    return outputs


def test_exact_24_jobs_and_fixed_parameters():
    assert len(w.jobs()) == 24
    assert sum(j["method"].endswith("_lr") for j in w.jobs()) == 4
    assert len({j["job_id"] for j in w.jobs()}) == 24
    for job in w.jobs():
        p = w.parameters(job)
        assert p["random_state"] == job["seed"]
        if job["method"].endswith("_lr"):
            assert job["seed"] == 0 and p["max_iter"] == 3000 and p["class_weight"] == "balanced"
        elif job["method"] == "pattern_rf":
            assert p["n_estimators"] == 500 and p["class_weight"] == "balanced_subsample"
        else:
            assert p["n_estimators"] == 400 and p["subsample_freq"] == 1
    with pytest.raises(w.WorkerError):
        w.validate_job({**w.jobs()[0], "seed": 1})


@pytest.mark.parametrize("method", w.METHODS)
def test_all_methods_fit_and_preserve_full_failure_rows(fitted, method):
    path, receipt = fitted[method]
    assert receipt["status"] == "complete"
    assert receipt["synthetic_fixture"] is True
    scores = pd.read_csv(path / "scores.csv", keep_default_na=False)
    assert len(scores) == 6
    assert scores.status.tolist() == ["ok"] * 4 + ["preprocessing_error"] * 2
    assert scores.iloc[4:].score.eq("").all()
    assert np.isfinite(scores.iloc[:4].score.astype(float)).all()
    assert not {"label", "target", "adjudication"} & set(scores.columns)
    state = json.loads((path / "fitted_state.json").read_text())
    assert state["fit_status"] == "ok"
    assert state["adapter_state_before_external"] == state["adapter_state_after_external"]
    assert len(state["training_node_ids"]) == 12
    assert state["training_node_ids"][0].startswith("synthetic:train:")
    if method.endswith("_lr"):
        assert state["adapter_state_before_external"]["fit_rows"] == 12
        assert isinstance(state["scaler"], dict)
    else:
        assert state["scaler"] == "none_stateless_pattern43"
    log = json.loads((path / "fit_log.json").read_text())
    assert log["timings"]["fit_seconds"] > 0
    assert log["peak_RSS_MiB_cumulative_process"] > 0
    assert log["configured_threads"]["blas"] == 1
    assert receipt["state_artifact"]["sha256"] == w.sha(path / "fitted_state.json")


def test_resume_exact_and_does_not_fit(fitted, monkeypatch):
    path, before = fitted["raw_tfidf_lr"]
    hashes = {str(p): w.sha(p) for p in path.rglob("*") if p.is_file()}
    monkeypatch.setattr(w, "estimator", lambda *a: (_ for _ in ()).throw(AssertionError("resume attempted fitting")))
    result = w.synthetic_job("raw_tfidf_lr:reentrancy:0", path, resume=True)
    assert result["resume_verified_no_refit"]
    assert hashes == {str(p): w.sha(p) for p in path.rglob("*") if p.is_file()}


def test_resume_rejects_changed_artifact(fitted):
    path, _ = fitted["pattern_rf"]
    file = path / "scores.csv"
    original = file.read_bytes()
    try:
        file.write_bytes(original + b"\n")
        with pytest.raises(w.WorkerError, match="artifact hash"):
            w.synthetic_job("pattern_rf:reentrancy:0", path, resume=True)
    finally:
        file.write_bytes(original)


def test_resume_rejects_changed_environment_or_extra_artifact(fitted, monkeypatch):
    path, _ = fitted["pattern_lgbm"]
    old = w.environment()
    monkeypatch.setattr(w, "environment", lambda: {**old, "python": "changed"})
    with pytest.raises(w.WorkerError, match="config/code/environment"):
        w.synthetic_job("pattern_lgbm:reentrancy:0", path, resume=True)
    monkeypatch.setattr(w, "environment", lambda: old)
    extra = path / "untracked.txt"
    extra.write_text("changed")
    try:
        with pytest.raises(w.WorkerError, match="artifact set"):
            w.synthetic_job("pattern_lgbm:reentrancy:0", path, resume=True)
    finally:
        extra.unlink()


def _binding(root):
    return {"artifact_root": str(root), "binding_sha256": "0" * 64, "method_config_sha256": "1" * 64,
            "training_manifest_sha256": "2" * 64, "reference_event_sha256": "3" * 64}


def test_failed_training_aborts_no_drop_no_fake_model(tmp_path):
    train, ext, labels = w.synthetic_records()
    a = w.adapters()
    train = (a.SourceRecord(train[0].sample_id, "train", b"\xff invalid training only"), *train[1:])
    result = w._run_records(w.jobs()[0], train, ext, labels, out=tmp_path / "failed", binding=_binding(tmp_path),
        external_paths=[r.sample_id for r in ext], synthetic=True)
    assert result["status"] == "complete_failed_fit"
    scores = pd.read_csv(tmp_path / "failed/scores.csv", keep_default_na=False)
    assert scores.status.eq("model_error").all() and scores.score.eq("").all() and len(scores) == 6
    state = json.loads((tmp_path / "failed/fitted_state.json").read_text())
    assert state["fit_status"] == "failed" and state["fitted_object"] is None
    assert not (tmp_path / "failed/fitted_bundle.joblib").exists()


@pytest.mark.parametrize("kind", ["label_order", "external_role", "duplicate_id", "overlap", "one_class", "unknown_label", "real_counts"])
def test_input_provenance_fails_before_fit(tmp_path, monkeypatch, kind):
    train, ext, labels = w.synthetic_records()
    a = w.adapters()
    synthetic = True
    if kind == "label_order": labels = dict(reversed(list(labels.items())))
    if kind == "external_role": ext = (a.SourceRecord(ext[0].sample_id, "train", ext[0].source), *ext[1:])
    if kind == "duplicate_id": train = (train[1], *train[1:])
    if kind == "overlap": ext = (a.SourceRecord(ext[0].sample_id, "external", train[0].source), *ext[1:])
    if kind == "one_class": labels = {k: 0 for k in labels}
    if kind == "unknown_label": labels[next(iter(labels))] = np.nan
    if kind == "real_counts": synthetic = False
    monkeypatch.setattr(w, "estimator", lambda *a: (_ for _ in ()).throw(AssertionError("fit should not start")))
    with pytest.raises(w.WorkerError):
        w._run_records(w.jobs()[0], train, ext, labels, out=tmp_path / "bad", binding=_binding(tmp_path),
            external_paths=[r.sample_id for r in ext], synthetic=synthetic)
    assert not (tmp_path / "bad").exists()


def test_actual_current_draft_gate_is_closed_before_any_private_read(tmp_path, monkeypatch):
    p = w.orchestration()
    gate = p.gate
    draft = json.loads((w.PROTOCOL / "protocol_B_draft.json").read_text())
    assert gate.blockers(draft, "begin_scoring")
    # This deliberately incomplete anchor is blocked before private access too.
    binding = tmp_path / "binding.json"
    w.dump(binding, {"schema": "external_B_orchestration_binding_v1", "synthetic_fixture": False,
        "artifacts": {"protocol": {"path": "protocol.json", "sha256": "0" * 64}}, "code": {}})
    monkeypatch.setattr(p, "bind_sources", lambda *a: (_ for _ in ()).throw(AssertionError("private data opened")))
    monkeypatch.setattr(w, "orchestration", lambda: p)
    with pytest.raises(w.WorkerError, match="Admission denied"):
        w.execute(tmp_path, binding, w.sha(binding), tmp_path / "absent_release", tmp_path / "absent_authorization", "0" * 64,
                  "raw_tfidf_lr:reentrancy:0", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_admission_denial_precedes_authorization_and_input_open(tmp_path, monkeypatch):
    p = SimpleNamespace(admission_preflight=lambda *a: {"admission_artifacts_consistent": False, "blockers": ["blank_initial_reviews"]})
    monkeypatch.setattr(w, "orchestration", lambda: p)
    real_sha = w.sha
    code_paths = {w.HERE / "worker.py", *w._ADAPTER_LOADED_DIGESTS}
    monkeypatch.setattr(w, "sha", lambda path: real_sha(path) if path in code_paths else (_ for _ in ()).throw(AssertionError("opened input before admission")))
    with pytest.raises(w.WorkerError, match="blank_initial_reviews"):
        w.execute(tmp_path, tmp_path / "binding", "0" * 64, tmp_path / "release", tmp_path / "auth", "0" * 64,
                  "raw_tfidf_lr:reentrancy:0", tmp_path / "out")


def test_no_authorization_anchor_no_private_full_check(tmp_path):
    auth = tmp_path / "auth.json"
    w.dump(auth, {"authorized": True})
    p = SimpleNamespace(admission_preflight=lambda *a: {"admission_artifacts_consistent": True},
                        check=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("full data check before runtime authorization")))
    with pytest.raises(w.WorkerError, match="anchor mismatch"):
        w._authorize(p, tmp_path, tmp_path / "binding", "0" * 64, tmp_path / "release", auth, "0" * 64, w.jobs()[0])


@pytest.mark.parametrize("reason", ["current_draft", "blank_reviews"])
def test_real_orchestration_admission_rejects_before_private_training_reads(tmp_path, monkeypatch, reason):
    helpers = w.module("worker_test_orchestration_fixture", w.PROTOCOL / "orchestration_v1/test_preflight.py")
    f = helpers.Fixture(tmp_path)
    if reason == "current_draft":
        protocol = tmp_path / "protocol.json"
        protocol.write_bytes((w.PROTOCOL / "protocol_B_draft.json").read_bytes())
        f.binding["artifacts"]["protocol"] = helpers.ref(tmp_path, protocol)
        helpers.write_json(f.binding_path, f.binding)
        f.digest = w.sha(f.binding_path)
    else:
        path = tmp_path / "reviewer1.csv"
        form = pd.read_csv(path)
        form.loc[0, "judgment_positive_negative_unknown"] = ""
        form.to_csv(path, index=False)
        e = json.loads((tmp_path / "initial_reviews_sealed.json").read_text())
        e["artifacts"]["reviewer_1"] = helpers.ref(tmp_path, path)
        f.replace_event(1, e)
        e = json.loads((tmp_path / "adjudication_sealed.json").read_text())
        e["previous_event_sha256"] = f.events[1]["sha256"]
        f.replace_event(2, e)
    release = tmp_path / "release.json"
    helpers.write_json(release, {"schema": "external_B_release_chain_v1", "events": f.events[:3]})
    real_open = Path.open
    forbidden = {tmp_path / "training_labels.csv", *(tmp_path / "train").glob("*"), *(tmp_path / "external").glob("*")}
    def guarded_open(path, *args, **kwargs):
        assert path not in forbidden, "Training labels/source bytes opened before admission"
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded_open)
    p = SimpleNamespace(admission_preflight=lambda root, binding, sha, release: helpers.p.admission_preflight(root, binding, sha, release, f.profile))
    monkeypatch.setattr(w, "orchestration", lambda: p)
    with pytest.raises(w.WorkerError, match="protocol_gate" if reason == "current_draft" else "blank_or_invalid_initial_judgment"):
        w.execute(tmp_path, f.binding_path, f.digest, release, tmp_path / "no_auth", "0" * 64,
                  "raw_tfidf_lr:reentrancy:0", tmp_path / "no_output")
    assert not (tmp_path / "no_output").exists()


def test_synthetic_cli_has_no_data_input_flags():
    import subprocess
    out = subprocess.run([sys.executable, str(HERE / "worker.py"), "synthetic-fixture", "--help"], capture_output=True, text=True)
    assert out.returncode == 0
    assert "--out" in out.stdout and "--job-id" in out.stdout
    assert "--binding" not in out.stdout and "--source" not in out.stdout and "--labels" not in out.stdout


def test_cached_source_or_installed_distribution_change_is_rejected(monkeypatch):
    w.adapters()
    real_sha = w.sha
    target = w.PROTOCOL / "adapters_v1/adapters.py"
    monkeypatch.setattr(w, "sha", lambda path: "0" * 64 if path == target else real_sha(path))
    with pytest.raises(w.WorkerError, match="changed since import"):
        w.adapters()
    monkeypatch.setattr(w, "sha", real_sha)
    real_version = w.importlib.metadata.version
    monkeypatch.setattr(w.importlib.metadata, "version", lambda p: "changed" if p == "numpy" else real_version(p))
    with pytest.raises(w.WorkerError, match="Loaded package differs"):
        w.environment()


def test_loader_ignores_stale_timestamp_size_valid_bytecode(tmp_path):
    import os
    import py_compile
    path = tmp_path / "fictional_module.py"
    path.write_text("VALUE = 1\n")
    py_compile.compile(str(path), doraise=True)
    original_stat = path.stat()
    assert w.module("fictional_worker_loader_case", path).VALUE == 1
    path.write_text("VALUE = 2\n")
    os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    loaded = w.module("fictional_worker_loader_case", path)
    assert loaded.VALUE == 2
    assert loaded.__loaded_source_sha256__ == w.sha(path)
