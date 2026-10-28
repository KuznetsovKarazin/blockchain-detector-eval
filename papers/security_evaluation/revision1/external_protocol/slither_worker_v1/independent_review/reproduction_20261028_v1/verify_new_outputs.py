"""NEW28October output verification; no original receipt recovery or tool execution."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
RUN = HERE.parents[1] / "authored_check_20261028_v1"
EXPECTED = "ec7c7f3758a91bb194de02f1f9a2dfeacabe1d6945af08366fcbf570d0db22b5"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mappings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "source_mapping":
                yield item
            else:
                yield from mappings(item)
    elif isinstance(value, list):
        for item in value:
            yield from mappings(item)


def main():
    require(sha(RUN / "plan.json") == EXPECTED, "Frozen plan changed")
    plan, jobs = read(RUN / "plan.json"), read(RUN / "jobs.json")
    pre = read(HERE / "PREEXECUTION_REVIEW.json")
    out = RUN / "execution"
    receipt, summary, started = [read(out / name) for name in ("receipt.json", "summary.json", "started.json")]
    require(receipt["plan_sha256"] == pre["plan_sha256"] == started["plan_sha256"] == EXPECTED, "Plan/review/run mismatch")
    require(datetime.fromisoformat(pre["reviewed_utc"]) < datetime.fromisoformat(started["started_utc"]), "Run preceded review seal")
    require(receipt["status"] == "complete_synthetic_only" and receipt["actual_corpus_scans"] == receipt["actual_corpus_scores"] == 0, "Execution scope changed")
    for rel, expected in plan["source_sha256"].items():
        require(sha(ROOT / rel) == sha(RUN / "source_snapshot" / rel) == expected, "Source snapshot changed")
    for rel, expected in plan["fixture_source_sha256"].items():
        require(sha(RUN / rel) == expected, "Authored source changed")
    require(sha(RUN / "jobs.json") == plan["jobs_sha256"] and sha(RUN / "runtime.json") == plan["runtime_sha256"], "Frozen inputs changed")
    actual_files = {str(path.relative_to(out)) for path in out.rglob("*") if path.is_file() and path != out / "receipt.json"}
    require(actual_files == set(receipt["artifact_sha256"]), "Result file inventory differs")
    for rel, expected in receipt["artifact_sha256"].items():
        require(sha(out / rel) == expected, "Result artifact changed")
    scores = list(csv.DictReader((out / "scores.csv").open(newline="")))
    require(len(scores) == 100 and len(jobs) == len(summary["cases"]) == 25, "Incomplete row coverage")
    score_lookup = {(r["path"], r["variant"], r["class"]): r for r in scores}
    require(len(score_lookup) == 100, "Duplicate score identity")
    observations, statuses = [], Counter()
    compile_n = analysis_n = mapping_n = 0
    for job, summary_row in zip(jobs, summary["cases"]):
        case = out / "cases" / job["case_id"]
        trace = read(case / "trace.json")
        require(summary_row["case_id"] == job["case_id"] and summary_row["trace_sha256"] == sha(case / "trace.json"), "Case identity mismatch")
        require(trace["path"] == job["path"] and trace["file_sha256"] == job["file_sha256"], "Trace input mismatch")
        require(trace["outside_pragma_attempts"] == 0, "Unexpected outside-pragma attempt")
        versions = [a["compiler_version"] for a in trace["compiler_attempts"]]
        require(versions == job["candidate_versions"][:len(versions)] and len(versions) <= 5, "Candidate order changed")
        for i, attempt in enumerate(trace["compiler_attempts"]):
            require(sha(case / f"compiler_{i}.stdout") == attempt["stdout_sha256"] and
                    sha(case / f"compiler_{i}.stderr") == attempt["stderr_sha256"], "Compiler trace bytes mismatch")
            if attempt["success"]:
                require(i == len(versions) - 1 and trace["selected_compiler_version"] == versions[i], "Compiler selection changed after success")
        require(len(trace["analysis_attempts"]) <= 1, "Analysis rerun")
        root, imported = Counter(), Counter()
        if trace["analysis_attempts"]:
            attempt = trace["analysis_attempts"][0]
            require(sha(case / "slither.stdout") == attempt["stdout_sha256"] and sha(case / "slither.stderr") == attempt["stderr_sha256"], "Slither trace bytes mismatch")
        if trace["success"]:
            payload = read(case / "slither.stdout")
            require(payload["status"] == "complete" and payload["completed_detector_order"] == plan["policy"]["detector_order"] and
                    payload["registered_detectors"] == plan["policy"]["detector_order"] and payload["compilation_units"] == 1 and
                    payload["extra_compiler_invocations"] == 0, "Incomplete actual detector analysis")
            workspace = case / "workspace"
            source_bytes = {unit["unit"]: (workspace / unit["unit"]).read_bytes() for unit in job["source_units"]}
            for unit in job["source_units"]:
                require(hashlib.sha256(source_bytes[unit["unit"]]).hexdigest() == unit["sha256"], "Staged source bytes changed")
            for finding in payload["findings"]:
                principal = finding["elements"][0]
                require(principal["type"] == "function", "First element is not the declared principal type")
                first = principal["source_mapping"]
                principal_unit = first["filename_relative"]
                require(principal_unit in source_bytes and Path(first["filename_absolute"]) == workspace / principal_unit, "Principal mapping mismatch")
                (root if principal_unit == job["entry_source_unit"] else imported)[finding["check"]] += 1
                for mapping in mappings(finding):
                    unit = mapping["filename_relative"]
                    require(unit in source_bytes and Path(mapping["filename_absolute"]) == workspace / unit, "Other mapping mismatch")
                    source = source_bytes[unit]
                    require(0 <= mapping["start"] <= mapping["start"] + mapping["length"] <= len(source), "Source mapping byte bounds")
                    require(mapping["lines"] and mapping["lines"][0] == source[:mapping["start"]].count(b"\n") + 1, "Source mapping line/byte offset mismatch")
                    mapping_n += 1
            require(dict(root) == trace["root_detector_counts"] and dict(imported) == trace["import_only_detector_counts"], "Attribution counts disagree with raw first elements")
        for variant in ("primary", "broad_secondary"):
            for cls in ("reentrancy", "unchecked"):
                row = score_lookup[(job["path"], variant, cls)]
                require(row["scan_trace_sha256"] == sha(case / "trace.json") and row["execution_status"] == trace["status"], "Score/trace binding changed")
                detectors = plan["policy"]["unchecked_detectors"] if cls == "unchecked" else plan["policy"]["primary_reentrancy_detectors"] + (
                    plan["policy"]["secondary_broad_additions"] if variant == "broad_secondary" else [])
                expected = str(int(any(root[d] > 0 for d in detectors))) if trace["success"] else ""
                require(row["score"] == expected, "Binary union or missing-score policy changed")
        require(summary_row["expectation_failures"] == [], "Predeclared expectation failed")
        expected = job["expectations"]
        for cls, value in expected.get("expected_primary_scores", {}).items():
            require(score_lookup[(job["path"], "primary", cls)]["score"] == str(value), "Independent predeclared primary expectation mismatch")
        for detector in expected.get("required_root_detectors", []):
            require(root[detector] > 0, "Required root detector absent")
        for detector in expected.get("required_import_detectors", []):
            require(imported[detector] > 0, "Required imported detector absent")
        compile_n += len(versions)
        analysis_n += len(trace["analysis_attempts"])
        statuses[trace["status"]] += 1
        observations.append({"case_id": job["case_id"], "status": trace["status"], "root_counts": dict(root), "import_counts": dict(imported)})
    require(compile_n == receipt["compiler_attempts"] == 22 and analysis_n == receipt["Slither_attempts"] == 21, "Tool attempt count mismatch")
    require(statuses == Counter({"ok": 21, "missing_import": 1, "missing_pragma": 1, "no_compatible_catalog_release": 1, "compiler_error": 1}), "Unexpected actual status inventory")
    require(summary["expectation_failures"] == [] and receipt["expectation_failure_cases"] == 0, "Expectation failure reported")
    result = {"schema": "independent_authored_slither_postrun_review_20261028_v1", "status": "pass",
        "original26October_receipts_recreated": False,
        "verified_utc": datetime.now(timezone.utc).isoformat(), "verification_source_sha256": sha(__file__),
        "plan_sha256": EXPECTED, "preexecution_review_sha256": sha(HERE / "PREEXECUTION_REVIEW.json"),
        "owner_execution_receipt_sha256": sha(out / "receipt.json"), "owner_summary_sha256": sha(out / "summary.json"),
        "owner_score_rows_sha256": sha(out / "scores.csv"), "artifact_hashes_reverified": len(actual_files),
        "cases": 25, "compiler_attempts_observed": compile_n, "Slither_attempts_observed": analysis_n,
        "score_rows": 100, "failed_rows_with_empty_scores": sum(row["score"] == "" for row in scores),
        "source_mappings_independently_checked": mapping_n, "status_counts": dict(statuses), "expectation_failure_cases": 0,
        "case_observations": observations, "tool_invocations_by_this_verifier": 0,
        "corpus_scans_or_scores": 0, "human_semantic_signoff": False, "external_B_execution_authorized": False,
        "conclusion": "Exact authored fixture execution and metadata verified; no population accuracy, corpus Slither coverage or human semantic validation established."}
    with (HERE / "POSTRUN_REVIEW.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": "pass", "cases": 25, "compiler_attempts": compile_n, "Slither_attempts": analysis_n,
        "checked_mappings": mapping_n, "receipt_sha256": sha(HERE / "POSTRUN_REVIEW.json")}))


if __name__ == "__main__":
    main()
