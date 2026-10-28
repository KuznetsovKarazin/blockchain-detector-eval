"""Record a NEW 28 October engineering test run; never invoke corpus tools."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REVIEW = HERE.parent
WORKER = REVIEW.parent
ROOT = HERE.parents[6]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def main():
    source_files = [WORKER / name for name in ("worker.py", "analyzer_child.py", "parse_results.py",
        "policy.py", "fixtures.py", "README.md", "test_worker.py")]
    source_files += [REVIEW / name for name in ("test_parser_independent.py", "test_worker_independent.py", "test_gate_independent.py")]
    source_files += [Path(__file__)]
    hashes = {str(path.relative_to(ROOT)): sha(path) for path in source_files}
    versions = {name: importlib.metadata.version(name) for name in
                ("pytest", "numpy", "pandas", "scikit-learn", "scipy")}
    command = [sys.executable, "-m", "pytest", "-q", str(WORKER / "test_worker.py"),
               str(REVIEW / "test_parser_independent.py"), str(REVIEW / "test_worker_independent.py"),
               str(REVIEW / "test_gate_independent.py")]
    plan = {"schema": "new_slither_engineering_test_plan_20261028_v1",
        "prepared_utc": datetime.now(timezone.utc).isoformat(), "command": command,
        "python": sys.version, "python_executable": sys.executable, "python_sha256": sha(sys.executable),
        "distribution_versions": versions, "source_sha256": hashes,
        "expected_test_count": 114, "test_oracle_provenance": "Recovered from full patch history; old digest unavailable; this is a new source-hash-bound review",
        "scope": "Authored dictionaries/temporary files/mocked children and public metadata only; no compiler/Slither/corpus/labels/model execution"}
    write_new(HERE / "TEST_PLAN.json", plan)
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
    log = result.stdout + result.stderr
    with (HERE / "TEST_LOG.txt").open("x") as stream:
        stream.write(log)
    unchanged = hashes == {str(path.relative_to(ROOT)): sha(path) for path in source_files}
    passed = result.returncode == 0 and "114 passed" in log and unchanged
    receipt = {"schema": "new_slither_engineering_test_receipt_20261028_v1",
        "completed_utc": datetime.now(timezone.utc).isoformat(), "status": "pass" if passed else "fail",
        "plan_sha256": sha(HERE / "TEST_PLAN.json"), "log_sha256": sha(HERE / "TEST_LOG.txt"),
        "returncode": result.returncode, "sources_unchanged": unchanged,
        "tests_passed": 114 if passed else None, "independent_tests": 105 if passed else None,
        "owner_tests": 9 if passed else None, "source_sha256": hashes,
        "compiler_invocations": 0, "Slither_invocations": 0, "corpus_or_annotation_body_reads": 0,
        "model_fits_or_predictions": 0, "restoration_of_original_test_receipt_claimed": False,
        "human_semantic_signoff": False, "external_B_execution_authorized": False}
    write_new(HERE / "TEST_RECEIPT.json", receipt)
    print(json.dumps({"status": receipt["status"], "returncode": result.returncode,
        "tests_passed": receipt["tests_passed"], "receipt_sha256": sha(HERE / "TEST_RECEIPT.json")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
