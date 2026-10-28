"""Seal an independent review of the exact authored-only plan, before execution."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import re
import subprocess

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = HERE.parents[5]
RUN = BASE / "authored_check_20261026_v1"
EXPECTED_PLAN = "075232c6db1974ccffca6ea322655517e676da6902789e5c7e541715d9e4204f"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    require(not (RUN / "execution").exists(), "Review must precede authored tool execution")
    require(not (HERE / "PREEXECUTION_REVIEW.json").exists(), "Preserve prior review receipt")
    spec = importlib.util.spec_from_file_location("independent_preexecution_worker", BASE / "worker.py")
    worker = importlib.util.module_from_spec(spec)
    exec(compile((BASE / "worker.py").read_bytes(), str(BASE / "worker.py"), "exec"), worker.__dict__)
    config, jobs, runtime = worker.verify_plan(RUN, EXPECTED_PLAN)
    require(len(jobs) == 25 and len(config["fixture_source_sha256"]) == 28, "Unexpected authored fixture population")
    require(all(job["path"] == "synthetic://" + job["case_id"] + "/" + job["entry_source_unit"] and
                job["context_relative"] == "fixtures/" + job["case_id"] for job in jobs), "Non-authored fixture identity")
    collision_audit = json.loads((HERE / "WHEEL_COLLISION_AUDIT.json").read_text())
    require(collision_audit["status"] == "pass" and collision_audit["unmatched_paths"] == 0, "Independent wheel audit failed")
    require(len(runtime["shared_wheel_member_collisions"]) == len(collision_audit["collisions"]) == 6, "Collision inventory changed")
    for row in collision_audit["collisions"]:
        target = runtime["shared_wheel_member_collisions"][row["relative_path"]]
        require(target["actual_sha256"] == row["actual_sha256"], "Actual collision bytes changed")
        require({(x["package"], x["version"], x["sha256"]) for x in target["owners"]} ==
                {(x["package"], x["version"], x["member_sha256"]) for x in row["owners"]}, "Pinned collision ownership changed")
    own_sources = [HERE / name for name in ("REVIEW_SCOPE.md", "test_parser_independent.py",
        "test_worker_independent.py", "test_gate_independent.py", "audit_wheel_collisions.py", "seal_preexecution_review.py")]
    review_hashes = {path.name: sha(path) for path in own_sources}
    snapshot = HERE / "preexecution_source_snapshot"
    snapshot.mkdir()
    for path in own_sources:
        (snapshot / (path.name + ".txt")).write_bytes(path.read_bytes())
    command = [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", str(BASE / "test_worker.py"), str(HERE)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=90)
    log = result.stdout + result.stderr
    with (HERE / "PREEXECUTION_TEST_LOG.txt").open("x") as stream:
        stream.write(log)
    require(result.returncode == 0, "Independent/owner engineering tests failed")
    match = re.search(r"(\d+) passed", log)
    require(match is not None and int(match.group(1)) == 114, "Unexpected test inventory")
    worker.verify_plan(RUN, EXPECTED_PLAN)
    require(review_hashes == {path.name: sha(path) for path in own_sources}, "Reviewer sources changed during tests")
    require(not (RUN / "execution").exists(), "Tool execution began before review seal")
    receipt = {"schema": "independent_slither_preexecution_review_v1", "status": "pass",
        "reviewed_utc": datetime.now(timezone.utc).isoformat(), "reviewer": "protocol_review engineering agent",
        "plan_sha256": EXPECTED_PLAN, "plan_path": str((RUN / "plan.json").relative_to(ROOT)),
        "scope": "only_the_exact_25_predeclared_authored_fixtures", "approved_authored_fixture_execution": True,
        "external_corpus_execution_authorized": False, "human_identity_authenticated": False,
        "human_semantic_signoff": False, "source_code_sha256": config["source_sha256"],
        "review_source_sha256": review_hashes, "tests_passed": 114, "independent_tests": 105, "owner_tests": 9,
        "test_log_sha256": sha(HERE / "PREEXECUTION_TEST_LOG.txt"), "test_command": command,
        "runtime_sha256": config["runtime_sha256"], "installed_runtime_files": len(runtime["files"]),
        "installed_distributions": len(runtime["installed_distributions"]), "pinned_wheel_anchors": len(runtime["wheel_sources"]),
        "independent_collision_audit_sha256": sha(HERE / "WHEEL_COLLISION_AUDIT.json"),
        "readonly_toolchain_check_sha256": sha(HERE / "TOOLCHAIN_READONLY_CHECK.json"),
        "compilers_or_slither_invoked_by_this_review": 0, "corpus_sources_or_annotations_processed": 0,
        "limitations": ["No human semantic sign-off", "Binary alerts are not vulnerability probabilities",
            "Import-defined inherited findings remain import-attributed", "Current B gate remains closed",
            "Historical C3 execution differs (informational exclusion, retries, attribution)",
            "Application guards are not a kernel sandbox; host standard library is outside wheel inventory"]}
    with (HERE / "PREEXECUTION_REVIEW.json").open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "pass", "plan_sha256": EXPECTED_PLAN, "tests_passed": 114,
                      "receipt_sha256": sha(HERE / "PREEXECUTION_REVIEW.json")}))


if __name__ == "__main__":
    main()
