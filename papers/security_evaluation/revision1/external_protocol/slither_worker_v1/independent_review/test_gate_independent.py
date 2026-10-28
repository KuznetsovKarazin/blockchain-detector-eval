"""Independent denial-order tests; no real source, label or analyzer execution."""
from pathlib import Path
import importlib.util
import json
import copy
from datetime import datetime
import types
from collections import Counter
import pytest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("independent_slither_gate", BASE / "worker.py")
w = importlib.util.module_from_spec(spec)
exec(compile((BASE / "worker.py").read_bytes(), str(BASE / "worker.py"), "exec"), w.__dict__)


def forbidden(*args, **kwargs):
    pytest.fail("Private integrity check or tool scan occurred before admission/authorization")


def auth_file(tmp_path, **updates):
    value = {"schema": "external_B_coordinator_execution_authorization_v1", "action": "slither_scan",
             "authorized": True, "coordinator_id": "fictional-test-only",
             "binding_sha256": "1" * 64, "release_sha256": "2" * 64,
             "worker_sha256": w.sha(BASE / "worker.py"),
             "authorized_job_ids": ["slither:reentrancy:0", "slither:unchecked:0"],
             "issued_utc": "2026-01-01T00:00:00+00:00"}
    value.update(updates)
    path = tmp_path / "fictional_auth.json"
    path.write_text(json.dumps(value))
    return path


def test_admission_denial_precedes_even_authorization_read(tmp_path, monkeypatch):
    p = types.SimpleNamespace(admission_preflight=lambda *a: {
        "admission_artifacts_consistent": False, "blockers": ["fictional closed gate"]}, check=forbidden)
    monkeypatch.setattr(w, "sha", forbidden)
    monkeypatch.setattr(w, "read", forbidden)
    with pytest.raises(ValueError, match="Admission"):
        w._authorize(p, tmp_path, tmp_path / "binding", "1" * 64, tmp_path / "release",
                     tmp_path / "authorization-must-not-be-read", "0" * 64)


def test_wrong_runtime_authorization_anchor_precedes_full_private_check(tmp_path):
    p = types.SimpleNamespace(admission_preflight=lambda *a: {"admission_artifacts_consistent": True}, check=forbidden)
    auth = auth_file(tmp_path)
    with pytest.raises(ValueError):
        w._authorize(p, tmp_path, tmp_path / "binding", "1" * 64, tmp_path / "release", auth, "0" * 64)


@pytest.mark.parametrize("updates", [{"authorized": False}, {"action": "learned_fit_and_score"},
    {"action": "compiler_readiness_only"}, {"schema": "made-up-auth"}])
def test_other_actions_never_authorize_slither(tmp_path, updates):
    p = types.SimpleNamespace(admission_preflight=lambda *a: {"admission_artifacts_consistent": True}, check=forbidden)
    auth = auth_file(tmp_path, **updates)
    with pytest.raises(ValueError):
        w._authorize(p, tmp_path, tmp_path / "binding", "1" * 64, tmp_path / "release", auth, w.sha(auth))


def test_current_draft_dry_preflight_reads_no_private_body(tmp_path, monkeypatch):
    binding = BASE.parent / "orchestration_v1/current_binding_20261026_v2/binding.json"
    release = binding.parent / "release.json"
    expected = w.sha(binding)
    original_open = Path.open
    seen_private = []

    def tracked_open(path, *args, **kwargs):
        parts = Path(path).parts
        # The exact current draft must be rejected without dataset bodies,
        # training labels, sampling keys, or review forms.
        if "data" in parts and ("raw" in parts or "derived" in parts):
            seen_private.append(str(path))
            pytest.fail("Draft admission opened private data: " + str(path))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", tracked_open)
    monkeypatch.setattr(w, "scan_job", forbidden)
    result = w.dry_preflight(w.ROOT, binding, expected, release)
    assert result["execution_authorized"] is False
    assert result["admission"]["admission_artifacts_consistent"] is False
    assert seen_private == []


def test_production_denial_cannot_create_output_or_invoke_scan(tmp_path, monkeypatch):
    binding = BASE.parent / "orchestration_v1/current_binding_20261026_v2/binding.json"
    release = binding.parent / "release.json"
    out = w.ROOT / "data/derived" / ("independent-denial-" + w.digest(str(tmp_path))[:12])
    monkeypatch.setattr(w, "scan_job", forbidden)
    with pytest.raises(ValueError, match="Admission"):
        w.execute(w.ROOT, binding, w.sha(binding), release, tmp_path / "missing_auth", "0" * 64, out)
    assert not out.exists()


def test_public_metadata_only_full_external_job_identity_and_failure_coverage(monkeypatch):
    """No permission to scan is implied by reading the already-public plans."""
    binding = json.loads((BASE.parent / "orchestration_v1/current_binding_20261026_v2/binding.json").read_text())
    path = BASE.parent / "compiler_preflight_v1/plan_20261026_v2/plan_before_execution.json"
    static = {"compiler_plan": {"path": str(path.relative_to(w.ROOT)), "sha256": w.sha(path)}}
    original_open = Path.open
    def public_only(path, *args, **kwargs):
        parts = Path(path).parts
        if "data" in parts and ("raw" in parts or "derived" in parts):
            pytest.fail("Public job identity validation opened private bytes")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", public_only)
    jobs = w.production_jobs(w.orchestration(), w.ROOT, binding, static)
    assert len(jobs) == len({job["path"] for job in jobs}) == 1998
    assert Counter(job["preparation_status"] for job in jobs) == {
        "ready_to_attempt": 1968, "missing_pragma": 23,
        "unsupported_constraint": 4, "no_compatible_catalog_release": 3}


def prospective_fake_authorization(tmp_path, mutation):
    """Fictional mechanics only: this is not a real human release or authorization."""
    def save(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        return {"path": name, "sha256": w.sha(path)}
    py = tmp_path / "fake-python"
    py.write_bytes(b"authored fake interpreter")
    site = tmp_path / "site"
    site.mkdir()
    runtime = {"schema": "slither_installed_runtime_binding_v1", "python": str(py),
               "python_sha256": w.sha(py), "files": {}, "site_packages": str(site), "site_package_files": []}
    runtime_ref = save("runtime.json", runtime)
    plan_ref = save("compiler.json", {"fictional": True})
    static = {"schema": "external_B_slither_worker_config_v1", "policy": copy.deepcopy(w.policy.POLICY),
              "code_sha256": {rel: w.sha(path) for rel, path in w.code_files().items()},
              "runtime_inventory": runtime_ref, "compiler_plan": plan_ref}
    if mutation == "policy":
        static["policy"]["analysis_options"]["no_fail"] = True
    if mutation == "code":
        static["code_sha256"][next(iter(static["code_sha256"]))] = "0" * 64
    config = {"slither_worker": static, "score_status_mapping": copy.deepcopy(w.policy.RAW_STATUS_MAP)}
    if mutation == "status_map":
        config["score_status_mapping"]["slither_error"] = "ok"
    method_ref = save("method.json", config)
    binding_ref = save("binding.json", {"synthetic_fixture": mutation == "synthetic",
                                       "artifacts": {"method_config": method_ref}})
    event_ref = save("event.json", {"sealed_utc": "2026-01-02T00:00:00+00:00"})
    release_ref = save("release.json", {"events": [event_ref]})
    auth = auth_file(tmp_path, binding_sha256=binding_ref["sha256"], release_sha256=release_ref["sha256"],
        reference_event_sha256=event_ref["sha256"], issued_utc="2026-01-03T00:00:00+00:00",
        runtime_inventory_sha256=runtime_ref["sha256"], compiler_plan_sha256=plan_ref["sha256"])
    value = json.loads(auth.read_text())
    if mutation == "runtime_anchor":
        value["runtime_inventory_sha256"] = "0" * 64
    if mutation == "compiler_anchor":
        value["compiler_plan_sha256"] = "0" * 64
    if mutation == "predated":
        value["issued_utc"] = "2026-01-01T00:00:00+00:00"
    auth.write_text(json.dumps(value))
    if mutation == "runtime_bytes":
        py.write_bytes(b"changed fictional runtime")
    def artifact(root, ref):
        path = root / ref["path"]
        if w.sha(path) != ref["sha256"]:
            raise ValueError("Fictional artifact mismatch")
        return path
    p = types.SimpleNamespace(admission_preflight=lambda *a: {"admission_artifacts_consistent": True},
        artifact=artifact, read_json=lambda path: json.loads(path.read_text()),
        timestamp=lambda value: datetime.fromisoformat(value), check=forbidden)
    return p, tmp_path / "binding.json", binding_ref["sha256"], tmp_path / "release.json", auth


@pytest.mark.parametrize("mutation", ["synthetic", "policy", "code", "status_map", "runtime_bytes",
    "runtime_anchor", "compiler_anchor", "predated"])
def test_late_integrity_and_authorization_failures_precede_private_check(tmp_path, mutation):
    p, binding, binding_hash, release, auth = prospective_fake_authorization(tmp_path, mutation)
    with pytest.raises(ValueError):
        w._authorize(p, tmp_path, binding, binding_hash, release, auth, w.sha(auth))
