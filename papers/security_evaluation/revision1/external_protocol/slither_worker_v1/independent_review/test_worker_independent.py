"""Independent control-flow tests; mocked children never invoke analysis tools."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import types
import subprocess
import sys
import pytest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("independent_slither_worker", BASE / "worker.py")
w = importlib.util.module_from_spec(spec)
exec(compile((BASE / "worker.py").read_bytes(), str(BASE / "worker.py"), "exec"), w.__dict__)


@pytest.mark.parametrize("status", sorted(set(w.policy.RAW_STATUS_MAP) - {"ok"}))
def test_every_failure_status_has_four_empty_scores(status):
    trace = {"status": status, "success": False, "path": "synthetic://failure.sol",
             "root_detector_counts": {"reentrancy-eth": 10, "unchecked-send": 10}}
    rows = w.score_rows(trace, "f" * 64)
    assert len(rows) == 4
    assert all(row["score"] == "" and row["status"] != "ok" for row in rows)
    assert all(row["execution_status"] == status for row in rows)


def test_broad_and_root_only_mappings_do_not_change_primary_union():
    trace = {"status": "ok", "success": True, "path": "synthetic://Root.sol",
             "root_detector_counts": {"reentrancy-benign": 3, "unchecked-send": 1},
             "import_only_detector_counts": {"reentrancy-eth": 9}}
    scores = {(row["variant"], row["class"]): row["score"] for row in w.score_rows(trace, "a" * 64)}
    assert scores == {("primary", "reentrancy"): 0, ("primary", "unchecked"): 1,
                      ("broad_secondary", "reentrancy"): 1, ("broad_secondary", "unchecked"): 1}


@pytest.mark.parametrize("status,success", [("ok", False), ("slither_error", True)])
def test_status_success_disagreement_rejected(status, success):
    with pytest.raises(ValueError):
        w.score_rows({"status": status, "success": success, "path": "synthetic://x.sol"}, "0" * 64)


def test_child_nonzero_exit_cannot_produce_safe_score():
    result = w.classify_analysis({"process_status": "completed", "returncode": 2,
                                 "stdout": b'{"status":"complete","findings":[]} '})
    assert result == {"status": "slither_error", "success": False}


@pytest.mark.parametrize("stdout", [b"not-json", b"\xff", b"null", b"[]", b'{"status":"error"}'])
def test_bad_or_error_payload_is_not_analysis_success(stdout):
    result = w.classify_analysis({"process_status": "completed", "returncode": 0, "stdout": stdout})
    assert result["success"] is False
    assert result["status"] in {"malformed_slither_output", "slither_error"}


def configured_job(tmp_path, monkeypatch, compiler_successes):
    """Synthetic files and simulated process returns; never launches anything."""
    calls = []
    source = b"contract Authored {}"
    job = {"path": "synthetic://Root.sol", "file_sha256": hashlib.sha256(source).hexdigest(),
           "entry_source_unit": "Root.sol", "candidate_versions": ["0.8.26", "0.7.6"],
           "preparation_status": "ready_to_attempt", "source_units": [
               {"unit": "Root.sol", "sha256": hashlib.sha256(source).hexdigest()}]}
    binaries = []
    for version in job["candidate_versions"]:
        binary = tmp_path / ("fake-solc-" + version)
        binary.write_bytes(b"not an executable")
        binaries.append({"version": version, "local_path": binary.name, "artifact_sha256": w.sha(binary)})
    monkeypatch.setattr(w, "ROOT", tmp_path)
    monkeypatch.setattr(w, "read", lambda path: {"releases": binaries})

    def stage(job, context, workspace):
        (workspace / "Root.sol").write_bytes(source)
        path = workspace / "input.json"
        path.write_bytes(b"{}")
        return path

    def process(argv, input_path, work, limits):
        calls.append((argv, dict(limits)))
        return {"process_status": "completed", "returncode": 0 if "fake-solc" in argv[0] else 2,
                "stdout": b"{}", "stderr": b"", "wall_seconds": 0.01}

    successes = iter(compiler_successes)
    def classify(process, entry):
        success = next(successes)
        return {"status": "compiler_success" if success else "compiler_error", "success": success}

    compiler = types.SimpleNamespace(limited_process=process, classify_output=classify)
    monkeypatch.setattr(w, "compiler_helpers", lambda: (None, compiler))
    monkeypatch.setattr(w, "stage", stage)
    runtime = {"files": {}, "python": str(tmp_path / "fake-python"), "site_packages": str(tmp_path),
               "site_package_files": []}
    return job, runtime, calls


def test_slither_failure_never_selects_second_compiler(tmp_path, monkeypatch):
    job, runtime, calls = configured_job(tmp_path, monkeypatch, [True])
    result = w.scan_job(job, tmp_path, tmp_path / "out", runtime)
    assert result["status"] == "slither_error" and result["success"] is False
    assert len(result["compiler_attempts"]) == len(result["analysis_attempts"]) == 1
    assert len(calls) == 2
    assert result["selected_compiler_version"] == "0.8.26"
    assert all(row["score"] == "" for row in w.score_rows(result, "0" * 64))


def test_compile_failure_moves_to_next_ordered_candidate_only(tmp_path, monkeypatch):
    job, runtime, calls = configured_job(tmp_path, monkeypatch, [False, True])
    result = w.scan_job(job, tmp_path, tmp_path / "out", runtime)
    assert [row["compiler_version"] for row in result["compiler_attempts"]] == ["0.8.26", "0.7.6"]
    assert len(result["analysis_attempts"]) == 1 and len(calls) == 3
    assert result["selected_compiler_version"] == "0.7.6"
    assert result["status"] == "slither_error"


def test_exhausted_budget_preserves_row_without_staging(tmp_path, monkeypatch):
    job, runtime, calls = configured_job(tmp_path, monkeypatch, [])
    monkeypatch.setattr(w, "stage", lambda *args: pytest.fail("staging after exhausted budget"))
    result = w.scan_job(job, tmp_path, tmp_path / "out", runtime, remaining_seconds=0)
    assert result["status"] == "not_attempted_run_budget" and not calls
    assert len(w.score_rows(result, "0" * 64)) == 4


def test_staging_failure_is_retained_without_child_execution(tmp_path, monkeypatch):
    job, runtime, calls = configured_job(tmp_path, monkeypatch, [])
    def failed_stage(*args):
        raise ValueError("authored source integrity failure")
    monkeypatch.setattr(w, "stage", failed_stage)
    result = w.scan_job(job, tmp_path, tmp_path / "out", runtime)
    assert result["status"] == "input_staging_failure" and not calls
    assert "detail_sha256" in result and "detail" not in result


def test_runtime_file_tampering_rejected(tmp_path):
    python = tmp_path / "python"
    module = tmp_path / "module.py"
    python.write_bytes(b"fictional interpreter identity")
    module.write_bytes(b"fictional module bytes")
    runtime = {"schema": "slither_installed_runtime_binding_v1", "python": str(python),
               "python_sha256": w.sha(python), "files": {str(module): w.sha(module)},
               "site_packages": str(tmp_path), "site_package_files": sorted([str(python), str(module)])}
    w.check_runtime(runtime)
    module.write_bytes(b"changed module")
    with pytest.raises(ValueError, match="Installed runtime changed"):
        w.check_runtime(runtime)


def test_unrecorded_runtime_module_rejected(tmp_path):
    python = tmp_path / "python"
    python.write_bytes(b"fictional interpreter")
    runtime = {"schema": "slither_installed_runtime_binding_v1", "python": str(python),
               "python_sha256": w.sha(python), "files": {}, "site_packages": str(tmp_path),
               "site_package_files": [str(python)]}
    w.check_runtime(runtime)
    (tmp_path / "unrecorded.py").write_bytes(b"fictional added module")
    with pytest.raises(ValueError, match="file set changed"):
        w.check_runtime(runtime)


def test_failure_guard_remains_active_under_optimized_python():
    script = """
import importlib.util, pathlib
p = pathlib.Path(%r)
spec = importlib.util.spec_from_file_location('optimized_independent_worker', p)
w = importlib.util.module_from_spec(spec)
exec(compile(p.read_bytes(), str(p), 'exec'), w.__dict__)
try:
    w.score_rows({'status': 'ok', 'success': False, 'path': 'synthetic://only'}, '0' * 64)
except ValueError:
    print('guard-active')
else:
    raise RuntimeError('Guard disappeared under optimization')
""" % str(BASE / "worker.py")
    result = subprocess.run([sys.executable, "-O", "-c", script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "guard-active"


def test_symlinked_unrecorded_package_directory_rejected(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    python = tmp_path / "python"
    python.write_bytes(b"fictional interpreter")
    outside = tmp_path / "outside_package"
    outside.mkdir()
    (outside / "__init__.py").write_bytes(b"fictional external package")
    runtime = {"schema": "slither_installed_runtime_binding_v1", "python": str(python),
               "python_sha256": w.sha(python), "files": {}, "site_packages": str(site),
               "site_package_files": []}
    w.check_runtime(runtime)
    (site / "unrecorded_package").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        w.check_runtime(runtime)
