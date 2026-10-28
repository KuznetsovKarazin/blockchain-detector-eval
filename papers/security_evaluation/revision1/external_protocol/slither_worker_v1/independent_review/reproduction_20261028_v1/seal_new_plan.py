"""Review and permit only the NEW 28 October authored fixture plan."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import importlib.util
import json

HERE = Path(__file__).resolve().parent
REVIEW = HERE.parent
BASE = REVIEW.parent
ROOT = HERE.parents[6]
RUN = BASE / "authored_check_20261028_v1"
EXPECTED = "ec7c7f3758a91bb194de02f1f9a2dfeacabe1d6945af08366fcbf570d0db22b5"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(name, path):
    source = Path(path).read_bytes()
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, str(path), "exec"), module.__dict__)
    require(hashlib.sha256(source).hexdigest() == sha(path), "Loaded source changed")
    return module


def main():
    require(not (RUN / "execution").exists(), "Actual fixture execution must wait for review")
    require(not (HERE / "PREEXECUTION_REVIEW.json").exists(), "Preserve existing new review")
    tests = read(HERE / "TEST_RECEIPT.json")
    require(tests["status"] == "pass" and tests["tests_passed"] == 114, "New test suite incomplete")
    require(sha(HERE / "TEST_PLAN.json") == tests["plan_sha256"] and
            sha(HERE / "TEST_LOG.txt") == tests["log_sha256"], "New test record changed")
    for relative, expected in tests["source_sha256"].items():
        require(sha(ROOT / relative) == expected, "Tested source changed")
    worker = load("independent_new28_worker", BASE / "worker.py")
    plan, jobs, runtime = worker.verify_plan(RUN, EXPECTED)
    require(len(jobs) == 25 and len(plan["fixture_source_sha256"]) == 28, "Fixture population changed")
    require(Counter(job["preparation_status"] for job in jobs) == {
        "ready_to_attempt": 22, "no_compatible_catalog_release": 1, "missing_import": 1, "missing_pragma": 1},
        "Predeclared fixture preparation differs")
    require(all(job["path"] == "synthetic://" + job["case_id"] + "/" + job["entry_source_unit"] and
                job["context_relative"] == "fixtures/" + job["case_id"] for job in jobs), "Non-authored fixture path")
    restoration = BASE / "restoration_20261028_v1"
    restored = read(restoration / "restoration_result.json")
    download_plan = read(restoration / "restoration_before_downloads.json")
    require(restored["status"] == "pinned_runtime_restored" and restored["original_metadata_unchanged"] is True, "Runtime restoration incomplete")
    require(sha(restoration / "restoration_before_downloads.json") == restored["plan_sha256"] and
            sha(restoration / "restore_runtime.py") == restored["script_sha256"] == download_plan["script_sha256"], "Restoration provenance changed")
    for name, expected in restored["original_metadata_sha256"].items():
        require(sha(BASE.parent / "toolchain_v1" / name) == expected, "Original toolchain metadata changed")
    downloads = read(restoration / "download_verification.json")["artifacts"]
    require(len(downloads) == 78, "Expected catalog,30 compilers,47 wheels")
    for item in downloads:
        path = ROOT / item["path"]
        require(sha(path) == item["sha256"] and path.stat().st_size == item["bytes"], "Restored artifact changed")
    require(sha(restoration / "runtime_inventory.json") == restored["runtime_inventory_sha256"] ==
            plan["runtime_sha256"], "Restored/frozen runtime mismatch")
    # Reuse the reconstructed independent audit algorithm. Only its destination
    # is relocated; this produces a NEW audit, not the missing26October JSON.
    auditor_path = REVIEW / "audit_wheel_collisions.py"
    auditor = load("independent_new28_wheel_audit", auditor_path)
    auditor.HERE = HERE
    auditor.main()
    audit = read(HERE / "WHEEL_COLLISION_AUDIT.json")
    require(audit["status"] == "pass" and audit["unmatched_paths"] == 0 and audit["wheels"] == 47, "Independent installed-member audit failed")
    require(len(audit["collisions"]) == len(runtime["shared_wheel_member_collisions"]) == 6, "Collision inventory changed")
    for row in audit["collisions"]:
        expected = runtime["shared_wheel_member_collisions"][row["relative_path"]]
        require(expected["actual_sha256"] == row["actual_sha256"], "Collision actual bytes differ")
        require({(item["package"], item["version"], item["sha256"]) for item in expected["owners"]} ==
                {(item["package"], item["version"], item["member_sha256"]) for item in row["owners"]}, "Collision ownership differs")
    worker.verify_plan(RUN, EXPECTED)
    require(not (RUN / "execution").exists(), "Run began before seal")
    result = {"schema": "independent_slither_preexecution_review_20261028_v1", "status": "pass",
        "reviewed_utc": datetime.now(timezone.utc).isoformat(), "plan_sha256": EXPECTED,
        "plan_path": str((RUN / "plan.json").relative_to(ROOT)),
        "scope": "only_the_new_25_authored_fixtures_in_authored_check_20261028_v1",
        "approved_authored_fixture_execution": True, "external_corpus_execution_authorized": False,
        "human_identity_authenticated": False, "human_semantic_signoff": False,
        "source_code_sha256": plan["source_sha256"], "test_source_sha256": tests["source_sha256"],
        "test_receipt_sha256": sha(HERE / "TEST_RECEIPT.json"), "tests_passed": 114,
        "independent_tests": 105, "owner_tests": 9,
        "test_oracle_provenance": "Reconstructed from recorded patches; old hashes unavailable; freshly hashed and reviewed for this new run",
        "restoration_result_sha256": sha(restoration / "restoration_result.json"),
        "runtime_sha256": plan["runtime_sha256"], "runtime_files": len(runtime["files"]),
        "pinned_wheels": 47, "installed_distributions": len(runtime["installed_distributions"]),
        "download_artifacts_rehashed": len(downloads), "original_toolchain_metadata_unchanged": True,
        "new_collision_audit_sha256": sha(HERE / "WHEEL_COLLISION_AUDIT.json"),
        "collision_audit_algorithm_sha256": sha(auditor_path), "review_source_sha256": sha(__file__),
        "tools_or_models_invoked_by_review": 0, "corpus_or_annotation_bodies_read": 0,
        "original26October_receipts_recreated": False,
        "limitations": ["Authored regression checks do not establish corpus accuracy or coverage",
            "Root-only attribution does not prove contract safety, especially inherited/imported definitions",
            "Detector/class semantic signoff remains a human prerequisite",
            "Python application guards are not a kernel sandbox; host standard library lies outside wheel anchors"]}
    with (HERE / "PREEXECUTION_REVIEW.json").open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "pass", "plan_sha256": EXPECTED,
        "receipt_sha256": sha(HERE / "PREEXECUTION_REVIEW.json")}))


if __name__ == "__main__":
    main()
