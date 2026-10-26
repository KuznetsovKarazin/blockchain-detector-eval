"""Run all24 fixed jobs on built-in fictional records; no real-data arguments."""
import argparse
import json
from pathlib import Path
import shutil
import time

import worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("Preserve previous synthetic receipts")
    out.mkdir(parents=True)
    files = worker.source_files()
    for name in ("run_synthetic.py", "test_worker.py", "README.md"):
        p = worker.HERE / name
        files[str(p.relative_to(worker.ROOT))] = p
    config = {"schema": "synthetic_model_worker_engineering_config_v1", "purpose": "built_in_fictional_records_only",
        "created_utc": worker.utc(), "jobs": worker.jobs(), "synthetic_training_files": 12, "synthetic_external_files": 6,
        "expected_success_per_job": 4, "expected_preprocessing_failures_per_job": 2,
        "environment": worker.environment(), "source_hashes": {rel: worker.sha(p) for rel, p in files.items()},
        "actual_external_fits_or_scores": False, "actual_training_label_key_reads": False,
        "prospective_study_freeze": False, "execution_gate_override": False}
    worker.dump(out / "config.json", config)
    for rel, source in files.items():
        target = out / "source_snapshot" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    worker.dump(out / "receipt.json", {"status": "prepared_before_synthetic_fits", "config_sha256": worker.sha(out / "config.json")})
    start = time.perf_counter()
    results = []
    for job in config["jobs"]:
        job_out = out / "jobs" / job["job_id"].replace(":", "__")
        result = worker.synthetic_job(job["job_id"], job_out)
        assert result["status"] == "complete"
        assert result["status_counts"] == {"ok": 4, "preprocessing_error": 2}
        before = {str(p.relative_to(job_out)): worker.sha(p) for p in job_out.rglob("*") if p.is_file()}
        resumed = worker.synthetic_job(job["job_id"], job_out, resume=True)
        assert resumed["resume_verified_no_refit"]
        assert before == {str(p.relative_to(job_out)): worker.sha(p) for p in job_out.rglob("*") if p.is_file()}
        results.append({"job_id": job["job_id"], "receipt": str((job_out / "receipt.json").relative_to(out)),
            "receipt_sha256": worker.sha(job_out / "receipt.json"), "status_counts": result["status_counts"], "resume_verified_no_refit": True})
    for rel, expected in config["source_hashes"].items():
        assert worker.sha(worker.ROOT / rel) == worker.sha(out / "source_snapshot" / rel) == expected
    receipt = {"schema": "synthetic_model_worker_engineering_receipt_v1", "status": "complete_synthetic_only",
        "config_sha256": worker.sha(out / "config.json"), "source_sha256": config["source_hashes"],
        "synthetic_fits": len(results), "synthetic_score_rows": len(results) * 6,
        "actual_external_fits": 0, "actual_external_scores": 0, "actual_training_label_key_reads": 0,
        "elapsed_seconds": time.perf_counter() - start, "completed_utc": worker.utc(),
        "all_resume_checks_no_refit": True, "prospective_study_freeze": False, "execution_gate_override": False, "jobs": results}
    worker.dump(out / "receipt.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("status", "synthetic_fits", "actual_external_fits", "all_resume_checks_no_refit")}))


if __name__ == "__main__":
    main()
