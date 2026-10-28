"""Gated pinned Slither worker. Actual execution here is authored-fixture only.

Production dispatch requires early human/inference admission, a separate trusted
coordinator instruction, and full bound source/tool integrity. No implicit gate.
"""
from pathlib import Path
import argparse
import base64
import collections
import csv
import email
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = HERE.parents[4]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


LOADED_WORKER_SHA256 = sha(__file__)


def load(name, path):
    path = Path(path)
    source = path.read_bytes()
    h = hashlib.sha256(source).hexdigest()
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(source, str(path), "exec", dont_inherit=True), module.__dict__)
    require(sha(path) == h, "Source changed during load: " + str(path))
    module.__loaded_source_sha256__ = h
    return module


policy = load("slither_worker_policy", HERE / "policy.py")
parser = load("slither_worker_parser", HERE / "parse_results.py")


def verify_loaded():
    require(sha(__file__) == LOADED_WORKER_SHA256, "Worker changed since import")
    require(sha(HERE / "policy.py") == policy.__loaded_source_sha256__, "Policy changed since import")
    require(sha(HERE / "parse_results.py") == parser.__loaded_source_sha256__, "Parser changed since import")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def utc():
    return datetime.now(timezone.utc).isoformat()


def compiler_helpers():
    load("solidity_scanner", ROOT / "papers/security_evaluation/normalization_audit/solidity_scanner.py")
    imports = load("imports", BASE / "compiler_preflight_v1/imports.py")
    runner = load("slither_frozen_compiler_helpers", BASE / "compiler_preflight_v1/runner.py")
    return imports, runner


def code_files():
    files = [HERE / n for n in ("worker.py", "analyzer_child.py", "policy.py", "parse_results.py", "fixtures.py")]
    files += [BASE / n for n in ("compiler_preflight_v1/imports.py", "compiler_preflight_v1/runner.py",
        "compiler_policy.py", "orchestration_v1/integrity_preflight.py", "orchestration_v1/validate_gate_v2.py", "review_estimators.py",
        "toolchain_v1/verify_toolchain_v2.py")]
    files += [ROOT / "papers/security_evaluation/normalization_audit/solidity_scanner.py", ROOT / "scripts/c3_slither_baseline.py"]
    return {str(p.relative_to(ROOT)): p for p in files}


def verify_shared_member(actual, owners, record_owner=None, record_sha256=None):
    require(len({x["package"] for x in owners}) > 1, "Shared member requires multiple pinned owners")
    require(actual in {x["sha256"] for x in owners}, "Shared wheel member matches no pinned owner")
    if record_owner is not None:
        normalize = lambda value: re.sub("[-_.]+", "-", value).lower()
        require(any(normalize(x["package"]) == normalize(record_owner) and x["sha256"] == record_sha256 for x in owners), "Collision RECORD differs from its pinned owner")


def runtime_inventory():
    """Read-only installed RECORD + pinned wheel/executable verification."""
    metadata = BASE / "toolchain_v1"
    verifier = load("slither_toolchain_verification", metadata / "verify_toolchain_v2.py")
    verifier.validate()  # only metadata/binary reads; no source compilation/scan
    pinned = read(metadata / "slither_inventory.json")
    env = ROOT / pinned["python_env"]
    site = env / "lib/python3.12/site-packages"
    require(site.is_dir(), "Isolated pinned runtime absent")
    require(not any(p.is_symlink() for p in site.rglob("*")), "Runtime symlink prohibited")
    files = {}
    wheels = read(metadata / "python_artifacts.json")["artifacts"]
    wheel_owners = collections.defaultdict(list)
    for entry in wheels:
        with zipfile.ZipFile(ROOT / entry["local_path"]) as archive:
            for name in archive.namelist():
                if name.endswith("/") or name.endswith(".dist-info/RECORD") or name.endswith(".pyc"):
                    continue
                parts = Path(name).parts
                if parts[0].endswith(".data"):
                    if len(parts) <= 2 or parts[1] not in ("purelib", "platlib"):
                        continue
                    member = str(Path(*parts[2:]))
                else:
                    member = name
                wheel_owners[member].append({"package": entry["package"], "version": entry["version"], "sha256": hashlib.sha256(archive.read(name)).hexdigest()})
    collisions = {}
    for member, owners in wheel_owners.items():
        if len(owners) > 1:
            actual = sha(site / member)
            verify_shared_member(actual, owners)
            collisions[member] = {"owners": owners, "actual_sha256": actual,
                "matching_owners": [x["package"] for x in owners if x["sha256"] == actual]}
    norm = lambda value: re.sub("[-_.]+", "-", value).lower()
    expected_distributions = {norm(x["package"]): x["version"] for x in wheels}
    expected_distributions["pip"] = "25.0.1"  # explicit Python-venv bootstrap, not one of the47 frozen wheels
    installed = {}
    for meta in site.glob("*.dist-info/METADATA"):
        content = email.message_from_string(meta.read_text())
        name = norm(content["Name"])
        require(name not in installed, "Duplicate installed distribution")
        installed[name] = content["Version"]
    require(installed == expected_distributions, "Installed distribution inventory/versions differ from pinned47 plus declared pip bootstrap")
    for record in sorted(site.glob("*.dist-info/RECORD")):
        record_owner = email.message_from_string((record.parent / "METADATA").read_text())["Name"]
        with record.open(newline="") as f:
            for rel, encoded, size in csv.reader(f):
                path = (site / rel).resolve()
                require(path.is_relative_to(env.resolve()), "Runtime RECORD escapes isolated environment")
                if "__pycache__" in path.parts or path.suffix == ".pyc":
                    continue  # child uses a fresh empty pycache prefix and never writes
                require(path.is_file(), "Installed runtime member absent: " + rel)
                actual = sha(path)
                if encoded:
                    algorithm, expected = encoded.split("=", 1)
                    require(algorithm == "sha256", "Unexpected RECORD hash algorithm")
                    if rel in collisions:
                        verify_shared_member(actual, collisions[rel]["owners"], record_owner,
                            base64.urlsafe_b64decode(expected + "=" * (-len(expected) % 4)).hex())
                    matches_record = base64.urlsafe_b64encode(bytes.fromhex(actual)).rstrip(b"=").decode() == expected
                    require(matches_record or (rel in collisions and actual == collisions[rel]["actual_sha256"]), "Installed RECORD mismatch: " + rel)
                else:
                    require(path.name == "RECORD", "Unhashed executable/runtime member: " + rel)
                if size and rel not in collisions:
                    require(path.stat().st_size == int(size), "Installed runtime size mismatch")
                files[str(path)] = actual
    require(files, "No installed runtime inventory")
    actual_files = {str(p.resolve()) for p in site.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    require(actual_files <= set(files), "Unrecorded installed runtime file")
    # Pin installed dependency members against every actual locked wheel.
    wheel_matches = {}
    for entry in wheels:
        matches = 0
        excluded = []
        with zipfile.ZipFile(ROOT / entry["local_path"]) as archive:
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                parts = Path(name).parts
                if name.endswith(".dist-info/RECORD") or name.endswith(".pyc"):
                    excluded.append(name)
                    continue
                if parts[0].endswith(".data"):
                    if len(parts) > 2 and parts[1] in ("purelib", "platlib"):
                        local = site / Path(*parts[2:])
                    else:
                        excluded.append(name)  # installer relocation/scripts: separately RECORD/hash bound
                        continue
                else:
                    local = site / name
                actual = sha(local)
                member = str(local.relative_to(site))
                require(actual == hashlib.sha256(archive.read(name)).hexdigest() or
                        (member in collisions and actual == collisions[member]["actual_sha256"]), "Installed member differs from pinned wheel: " + name)
                matches += 1
        wheel_matches[entry["package"]] = {"version": entry["version"], "wheel_sha256": entry["artifact_sha256"],
            "wheel_members_verified_including_declared_shared_paths": matches, "installer_rewritten_or_relocated_exclusions": excluded}
    python = env / "bin/python"
    require(sha(python) == pinned["python_executable_sha256"], "Python interpreter changed")
    files[str(python.resolve())] = sha(python)
    return {"schema": "slither_installed_runtime_binding_v1", "python": str(python), "python_sha256": sha(python),
        "files": files, "site_packages": str(site), "site_package_files": sorted(actual_files),
        "installed_distributions": installed, "shared_wheel_member_collisions": collisions,
        "bootstrap_package_not_wheel_anchored": {"pip": "25.0.1"},
        "wheel_sources": wheel_matches, "slither_inventory_sha256": sha(metadata / "slither_inventory.json"),
        "solc_inventory_sha256": sha(metadata / "solc_inventory.json"), "dependency_lock_sha256": pinned["dependency_lock_sha256"],
        "pycache_policy": "isolated -I -B with fresh -X pycache_prefix workspace; no stale .pyc reuse"}


def check_runtime(runtime):
    require(runtime.get("schema") == "slither_installed_runtime_binding_v1", "Runtime binding schema")
    require(sha(runtime["python"]) == runtime["python_sha256"], "Interpreter identity changed")
    require(not any(p.is_symlink() for p in Path(runtime["site_packages"]).rglob("*")), "Runtime symlink prohibited")
    for path, expected in runtime["files"].items():
        require(sha(path) == expected, "Installed runtime changed: " + path)
    actual = sorted(str(p.resolve()) for p in Path(runtime["site_packages"]).rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    require(actual == runtime["site_package_files"], "Installed runtime file set changed")


def stage(job, context_root, workspace):
    imports, _ = compiler_helpers()
    sources = {}
    for row in job["source_units"]:
        source, _ = imports.check_local_source(Path(context_root) / row["unit"], Path(context_root), row["sha256"])
        target = workspace / row["unit"]
        require(target.resolve().is_relative_to(workspace), "Staged unit escapes workspace")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.encode("utf-8"))
        target.chmod(0o444)
        require(sha(target) == row["sha256"], "Source bytes changed during staging")
        sources[row["unit"]] = {"content": source}
    require(set(sources) and job["entry_source_unit"] in sources, "Root source absent")
    payload = {"language": "Solidity", "sources": sources, "settings": policy.SETTINGS}
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    require(len(data) <= policy.LIMITS["input_bytes"], "Frozen input-byte cap exceeded")
    path = workspace / "__slither_compiler_input.json"
    require(not path.exists(), "Reserved input filename collision")
    path.write_bytes(data)
    return path


def classify_analysis(process, **kwargs):
    if process["process_status"] != "completed":
        return {"status": "slither_error" if process["process_status"] == "process_failure" else process["process_status"], "success": False}
    try:
        raw = json.loads(process["stdout"].decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {"status": "malformed_slither_output" if process["returncode"] == 0 else "slither_error", "success": False}
    if process["returncode"] != 0:
        specific = isinstance(raw, dict) and raw.get("status") == "error" and raw.get("error_code") == "missing_slither_compiler_fields"
        return {"status": "missing_slither_compiler_fields" if specific else "slither_error", "success": False}
    if not isinstance(raw, dict) or raw.get("status") != "complete":
        return {"status": "slither_error", "success": False}
    try:
        result = parser.parse_findings(raw, detector_order=policy.DETECTOR_ORDER, analysis_options=policy.ANALYSIS_OPTIONS, **kwargs)
    except (parser.ResultError, TypeError, KeyError, ValueError) as exc:
        return {"status": "attribution_error", "success": False, "validation_error_sha256": hashlib.sha256(str(exc).encode()).hexdigest()}
    return {"status": "ok", "success": True, **result}


def scan_job(job, context_root, out, runtime, *, remaining_seconds=7200):
    """Internal execution core; production CLI must complete admission first."""
    began = time.monotonic()
    out = Path(out)
    require(not out.exists(), "Per-file output already exists")
    out.mkdir(parents=True)
    trace = {"schema": "slither_file_execution_trace_v1", "path": job["path"], "file_sha256": job["file_sha256"],
        "entry_source_unit": job["entry_source_unit"], "candidate_versions": job["candidate_versions"],
        "preparation_status": job["preparation_status"], "compiler_attempts": [], "analysis_attempts": [],
        "outside_pragma_attempts": 0, "started_utc": utc(), "status": job["preparation_status"], "success": False}
    if job["preparation_status"] != "ready_to_attempt":
        require(job["preparation_status"] in policy.RAW_STATUS_MAP, "Unmapped prepared status")
    elif remaining_seconds <= 0:
        trace["status"] = "not_attempted_run_budget"
    else:
        _, compiler = compiler_helpers()
        tools = {x["version"]: x for x in read(BASE / "toolchain_v1/solc_inventory.json")["releases"]}
        require(0 < len(job["candidate_versions"]) <= 5 and len(set(job["candidate_versions"])) == len(job["candidate_versions"]), "Invalid frozen candidate order")
        work = out / "workspace"
        work.mkdir()
        try:
            input_path = stage(job, context_root, work)
        except (ValueError, OSError) as exc:
            trace.update(status="input_staging_failure", detail_sha256=hashlib.sha256(str(exc).encode()).hexdigest())
        else:
            for ordinal, version in enumerate(job["candidate_versions"]):
                remaining = remaining_seconds - (time.monotonic() - began)
                if remaining <= 0:
                    trace["status"] = "not_completed_run_budget"
                    break
                tool = tools[version]
                binary = ROOT / tool["local_path"]
                require(sha(binary) == tool["artifact_sha256"], "Compiler changed")
                limit = min(180, remaining)
                limits = {**policy.LIMITS, "wall_seconds": limit}
                process = compiler.limited_process([str(binary), "--standard-json", "--allow-paths", str(work)], input_path, work, limits)
                (out / f"compiler_{ordinal}.stdout").write_bytes(process["stdout"])
                (out / f"compiler_{ordinal}.stderr").write_bytes(process["stderr"])
                classified = compiler.classify_output(process, job["entry_source_unit"])
                trace["compiler_attempts"].append({"phase": "compile", "candidate_index": ordinal, "compiler_version": version,
                    "compiler_sha256": tool["artifact_sha256"], "process_status": process["process_status"], "returncode": process["returncode"],
                    "wall_seconds": process["wall_seconds"], "stdout_sha256": hashlib.sha256(process["stdout"]).hexdigest(),
                    "stderr_sha256": hashlib.sha256(process["stderr"]).hexdigest(), **classified})
                trace["status"] = classified["status"]
                if not classified["success"]:
                    continue
                # Compiler selection is irrevocable here: a Slither failure must
                # not search another compiler version for a more favorable result.
                trace["selected_compiler_version"] = version
                remaining_analysis = min(limit - process["wall_seconds"], remaining_seconds - (time.monotonic() - began))
                if remaining_analysis <= 0:
                    trace["status"] = "timeout"
                    break
                compiled = work / "__compiled.json"
                compiled.write_bytes(process["stdout"])
                request = {"workspace": str(work.resolve()), "child_sha256": sha(HERE / "analyzer_child.py"),
                    "runtime_files": runtime["files"], "site_packages": runtime["site_packages"], "site_package_files": runtime["site_package_files"],
                    "compiled_path": str(compiled.resolve()), "compiled_sha256": sha(compiled),
                    "source_sha256": {r["unit"]: r["sha256"] for r in job["source_units"]}, "entry": job["entry_source_unit"],
                    "compiler_version": version, "compiler_settings": policy.SETTINGS,
                    "detector_order": list(policy.DETECTOR_ORDER), "analysis_options": policy.ANALYSIS_OPTIONS}
                req = work / "__analysis_request.json"
                dump(req, request)
                # Child .pyc lookup is redirected to a fresh nonexistent prefix;
                # -B alone would not prevent stale cached code execution.
                argv = [runtime["python"], "-I", "-B", "-X", "pycache_prefix=" + str(work.resolve() / "empty_pycache"),
                        str(HERE / "analyzer_child.py"), str(req.resolve())]
                analysis = compiler.limited_process(argv, req, work, {**policy.LIMITS, "wall_seconds": remaining_analysis})
                (out / "slither.stdout").write_bytes(analysis["stdout"])
                (out / "slither.stderr").write_bytes(analysis["stderr"])
                parsed = classify_analysis(analysis, units=[r["unit"] for r in job["source_units"]], entry=job["entry_source_unit"],
                    workspace=work, unit_bytes={r["unit"]: (work / r["unit"]).stat().st_size for r in job["source_units"]})
                trace["analysis_attempts"].append({"phase": "Slither", "process_status": analysis["process_status"],
                    "returncode": analysis["returncode"], "wall_seconds": analysis["wall_seconds"],
                    "stdout_sha256": hashlib.sha256(analysis["stdout"]).hexdigest(), "stderr_sha256": hashlib.sha256(analysis["stderr"]).hexdigest(),
                    "status": parsed["status"], "success": parsed["success"]})
                trace.update(parsed)
                break
    require(trace["status"] in policy.RAW_STATUS_MAP, "Unmapped final execution status: " + trace["status"])
    trace["completed_utc"] = utc()
    trace["end_to_end_seconds"] = time.monotonic() - began
    dump(out / "trace.json", trace)
    return trace


def score_rows(trace, trace_sha256):
    """Four vectors share one trace: two classes × primary/broad sensitivity."""
    status = policy.RAW_STATUS_MAP[trace["status"]]
    require((status == "ok") == bool(trace["success"]), "Status/success inconsistency")
    counts = trace.get("root_detector_counts", {})
    rows = []
    for variant in ("primary", "broad_secondary"):
        for cls in ("reentrancy", "unchecked"):
            detectors = policy.UNCHECKED if cls == "unchecked" else policy.PRIMARY_REENTRANCY + (policy.BROAD_ADDITIONS if variant == "broad_secondary" else ())
            score = int(any(counts.get(d, 0) > 0 for d in detectors)) if status == "ok" else ""
            prefix = "slither" if variant == "primary" else "slither_broad"
            rows.append({"job_id": f"{prefix}:{cls}:0", "method": "slither", "seed": 0, "variant": variant,
                "path": trace["path"], "class": cls, "execution_status": trace["status"], "status": status,
                "score": score, "scan_trace_sha256": trace_sha256})
    return rows


def write_scores(path, rows):
    with Path(path).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prepare_synthetic(out):
    verify_loaded()
    out = Path(out).resolve()
    require(not out.exists(), "Existing synthetic plan must be preserved")
    out.mkdir(parents=True)
    sources = code_files()
    for name in ("README.md", "test_worker.py"):
        if (HERE / name).exists():
            sources[str((HERE / name).relative_to(ROOT))] = HERE / name
    source_hashes = {rel: sha(path) for rel, path in sources.items()}
    for rel, path in sources.items():
        dst = out / "source_snapshot" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dst)
    dump(out / "preparation_started.json", {"source_sha256": source_hashes, "prepared_utc": utc(), "tool_executions": 0})
    runtime = runtime_inventory()
    imports, _ = compiler_helpers()
    compile_policy = load("slither_fixture_compile_policy", BASE / "compiler_policy.py")
    # The historical wrapper internally uses an ordinary loader. Replace that
    # helper with the exact source-byte load before using its constants/functions.
    compile_policy.legacy = load("historical_c3_compiler_policy_exact", ROOT / "scripts/c3_slither_baseline.py")
    compile_policy.CATALOG = tuple(r for r in compile_policy.legacy.RELEASES if r >= compile_policy.legacy.FIRST_STATIC)
    fixture = load("slither_authored_fixtures", HERE / "fixtures.py")
    cases = fixture.cases()
    dump(out / "runtime.json", runtime)
    jobs = []
    for case in cases:
        context = out / "fixtures" / case["id"]
        context.mkdir(parents=True)
        inventory = {}
        for unit, text in case["sources"].items():
            target = context / unit
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
            inventory[unit] = sha(target)
        entry = case["entry"]
        cp = compile_policy.strict_compile_plan(case["sources"][entry])
        job = {"path": "synthetic://" + case["id"] + "/" + entry, "case_id": case["id"],
            "file_sha256": inventory[entry], "entry_source_unit": entry, "candidate_versions": cp["candidates"],
            "preparation_status": "ready_to_attempt" if cp["candidates"] else cp["status"], "source_units": [],
            "context_relative": "fixtures/" + case["id"], "expectations": {k: v for k, v in case.items() if k not in ("sources", "entry", "id")}}
        if cp["candidates"]:
            try:
                job.update(imports.closure(context, entry, inventory, external=False,
                    max_sources=policy.LIMITS["max_sources"], max_bytes=policy.LIMITS["source_bytes"]))
            except (imports.ImportFailure, imports.SolidityScanError) as exc:
                job["preparation_status"] = getattr(exc, "status", "source_scanner_error")
        require(job["preparation_status"] == "ready_to_attempt" or job["preparation_status"] in policy.RAW_STATUS_MAP, "Unmapped fixture preparation status")
        jobs.append(job)
    dump(out / "jobs.json", jobs)
    config = {"schema": "slither_authored_fixture_plan_v1", "synthetic_fixture": True, "prepared_utc": utc(),
        "policy": policy.POLICY, "source_sha256": source_hashes, "runtime_sha256": sha(out / "runtime.json"),
        "jobs_sha256": sha(out / "jobs.json"), "authored_fixture_n": len(jobs),
        "fixture_source_sha256": {str(p.relative_to(out)): sha(p) for p in (out / "fixtures").rglob("*") if p.is_file()},
        "actual_corpus_sources_read": False, "actual_model_scores": 0, "human_semantic_signoff": False,
        "safety_scope": "Application-level closure/process/network guards, not kernel sandbox proof",
        "synthetic_context_scope": "Authored multi-file fixtures exercise attribution; actual external context remains frozen single-file policy"}
    for rel, expected in source_hashes.items():
        require(sha(ROOT / rel) == expected, "Source changed during preparation")
    dump(out / "plan.json", config)
    return {"status": "prepared_before_any_compiler_or_detector_execution", "plan_sha256": sha(out / "plan.json"), "fixture_n": len(jobs)}


def verify_plan(plan_dir, expected_sha256):
    require(sha(plan_dir / "plan.json") == expected_sha256, "Plan anchor mismatch")
    config = read(plan_dir / "plan.json")
    require(config.get("schema") == "slither_authored_fixture_plan_v1" and config.get("synthetic_fixture") is True, "Not an authored-fixture plan")
    require(config["policy"] == policy.POLICY, "Execution policy differs from frozen plan")
    for rel, expected in config["source_sha256"].items():
        require(sha(ROOT / rel) == expected and sha(plan_dir / "source_snapshot" / rel) == expected, "Frozen source mismatch: " + rel)
    for rel, expected in config["fixture_source_sha256"].items():
        require(sha(plan_dir / rel) == expected, "Fixture source changed")
    require(sha(plan_dir / "jobs.json") == config["jobs_sha256"] and sha(plan_dir / "runtime.json") == config["runtime_sha256"], "Plan input changed")
    runtime = read(plan_dir / "runtime.json")
    check_runtime(runtime)
    return config, read(plan_dir / "jobs.json"), runtime


def run_synthetic(plan_dir, expected_sha256, resume=False):
    verify_loaded()
    plan_dir = Path(plan_dir).resolve()
    config, jobs, runtime = verify_plan(plan_dir, expected_sha256)
    require(len(jobs) == config["authored_fixture_n"] and all(j["path"].startswith("synthetic://") for j in jobs), "Synthetic identity inventory required")
    out = plan_dir / "execution"
    if out.exists():
        require(resume, "Explicit resume required")
        receipt = read(out / "receipt.json")
        require(receipt["plan_sha256"] == expected_sha256 and receipt["status"] == "complete_synthetic_only", "Resume plan/status mismatch")
        actual = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and p != out / "receipt.json"}
        require(actual == set(receipt["artifact_sha256"]), "Resume artifact inventory differs")
        for rel, expected in receipt["artifact_sha256"].items():
            require(sha(out / rel) == expected, "Resume artifact changed")
        return {"status": "resume_verified_no_execution", "plan_sha256": expected_sha256, "cases": len(jobs)}
    out.mkdir()
    dump(out / "started.json", {"plan_sha256": expected_sha256, "started_utc": utc(), "actual_corpus_scans": 0})
    rows, outcomes, expectation_failures = [], [], []
    started = time.monotonic()
    for job in jobs:
        target = out / "cases" / job["case_id"]
        trace = scan_job(job, plan_dir / job["context_relative"], target, runtime,
                         remaining_seconds=policy.LIMITS["total_run_wall_seconds"] - (time.monotonic() - started))
        score = score_rows(trace, sha(target / "trace.json"))
        rows.extend(score)
        expected = job["expectations"]
        failed = []
        if expected["expected_execution"] == "analysis_complete" and not trace["success"]:
            failed.append("expected complete Slither analysis")
        if expected["expected_execution"] == "analysis_or_explicit_schema_failure" and trace["status"] not in ("ok", "missing_slither_compiler_fields", "compiler_output_schema_error"):
            failed.append("expected analysis or specifically identified compiler-output schema limitation")
        if expected["expected_execution"] in ("unavailable_no_analysis", "compiler_failure_no_analysis") and trace["analysis_attempts"]:
            failed.append("analysis must not execute for unavailable/compiler-failed fixture")
        for cls, value in expected.get("expected_primary_scores", {}).items():
            observed = next(r["score"] for r in score if r["class"] == cls and r["variant"] == "primary")
            if observed != value:
                failed.append("primary score mismatch: " + cls)
        for kind, field in (("root", "required_root_detectors"), ("import_only", "required_import_detectors")):
            for detector in expected.get(field, []):
                if trace.get(kind + "_detector_counts", {}).get(detector, 0) < 1:
                    failed.append("missing required " + kind + " detector: " + detector)
        if failed:
            expectation_failures.append({"case_id": job["case_id"], "failures": failed})
        outcomes.append({"case_id": job["case_id"], "status": trace["status"], "compiler_attempts": len(trace["compiler_attempts"]),
            "analysis_attempts": len(trace["analysis_attempts"]), "selected_compiler_version": trace.get("selected_compiler_version"),
            "root_detector_counts": trace.get("root_detector_counts", {}), "import_only_detector_counts": trace.get("import_only_detector_counts", {}),
            "expectation_failures": failed, "trace_sha256": sha(target / "trace.json")})
    write_scores(out / "scores.csv", rows)
    dump(out / "summary.json", {"cases": outcomes, "expectation_failures": expectation_failures,
        "runtime_seconds": time.monotonic() - started, "actual_corpus_scans": 0, "human_semantic_signoff": False})
    verify_plan(plan_dir, expected_sha256)
    receipt = {"status": "complete_synthetic_only", "plan_sha256": expected_sha256, "cases": len(jobs),
        "compiler_attempts": sum(x["compiler_attempts"] for x in outcomes), "Slither_attempts": sum(x["analysis_attempts"] for x in outcomes),
        "status_counts": dict(collections.Counter(x["status"] for x in outcomes)), "expectation_failure_cases": len(expectation_failures),
        "actual_corpus_scans": 0, "actual_corpus_scores": 0, "human_semantic_signoff": False,
        "artifact_sha256": {str(p.relative_to(out)): sha(p) for p in out.rglob("*") if p.is_file()}}
    dump(out / "receipt.json", receipt)
    return receipt


def orchestration():
    return load("slither_worker_admission", BASE / "orchestration_v1/integrity_preflight.py")


def dry_preflight(root, binding_path, expected_sha256, release_path):
    """Admission only: no training key, source body, compiler or detector read/run."""
    verify_loaded()
    p = orchestration()
    result = p.admission_preflight(Path(root), Path(binding_path), expected_sha256, Path(release_path))
    return {"schema": "external_B_slither_dry_preflight_v1", "admission": result,
            "execution_authorized": False, "human_identity_authenticated": False,
            "corpus_sources_opened_by_worker": False, "compiler_invocations": 0, "detector_invocations": 0}


def _authorize(p, root, binding_path, expected_sha256, release_path, authorization_path, authorization_sha256):
    admission = p.admission_preflight(root, binding_path, expected_sha256, release_path)
    require(admission.get("admission_artifacts_consistent") is True, "Admission denied")
    require(sha(authorization_path) == authorization_sha256, "Coordinator authorization anchor mismatch")
    auth = read(authorization_path)
    require(auth.get("schema") == "external_B_coordinator_execution_authorization_v1", "Authorization schema")
    require(auth.get("action") == "slither_scan" and auth.get("authorized") is True, "Slither action not authorized")
    require(isinstance(auth.get("coordinator_id"), str) and auth["coordinator_id"].strip(), "Coordinator provenance missing")
    require(auth.get("binding_sha256") == expected_sha256 and auth.get("release_sha256") == sha(release_path), "Authorization binding/release mismatch")
    require(auth.get("worker_sha256") == sha(__file__), "Authorization worker mismatch")
    required_jobs = ["slither:reentrancy:0", "slither:unchecked:0"]
    require(auth.get("authorized_job_ids") == required_jobs, "Exact two static primary slots must be authorized")
    binding = read(binding_path)
    require(binding.get("synthetic_fixture") is False, "Production never accepts synthetic profiles")
    release = read(release_path)
    require(auth.get("reference_event_sha256") == release["events"][-1]["sha256"], "Authorization reference mismatch")
    event = p.read_json(p.artifact(root, release["events"][-1]))
    require(p.timestamp(auth.get("issued_utc")) >= p.timestamp(event["sealed_utc"]), "Authorization predates adjudication")
    config = p.read_json(p.artifact(root, binding["artifacts"]["method_config"]))
    static = config.get("slither_worker", {})
    require(static.get("schema") == "external_B_slither_worker_config_v1" and static.get("policy") == policy.POLICY, "Prospective Slither policy not frozen")
    current_code = {rel: sha(path) for rel, path in code_files().items()}
    require(static.get("code_sha256") == current_code, "Slither source closure differs from prospective binding")
    for raw, canonical in policy.RAW_STATUS_MAP.items():
        require(config["score_status_mapping"].get(raw) == canonical, "Unfrozen Slither status: " + raw)
    runtime = p.read_json(p.artifact(root, static["runtime_inventory"]))
    check_runtime(runtime)
    require(auth.get("runtime_inventory_sha256") == static["runtime_inventory"]["sha256"], "Authorization runtime mismatch")
    require(auth.get("compiler_plan_sha256") == static["compiler_plan"]["sha256"], "Authorization compiler plan mismatch")
    p.artifact(root, static["compiler_plan"])
    # This later step may inspect private keys/source bytes, only after admission,
    # runtime instruction, and bound static code/config/runtime passed above.
    report = p.check(root, binding_path, expected_sha256, phase="begin_scoring", release_path=release_path)
    require(report.get("phase_integrity_pass") is True, "Full source/tool integrity denied")
    require([j["job_id"] for j in report["declared_jobs"] if j["kind"] == "static"] == required_jobs, "Static slot inventory changed")
    protocol = p.read_json(p.artifact(root, binding["artifacts"]["protocol"]))
    slither = protocol["slither"]
    for key, expected in (("version", "0.11.6"), ("timeout_seconds_per_attempt", 180), ("maximum_attempts", 5),
        ("outside_pragma_allowed", False), ("diagnostic_rerun_changes_outcome", False),
        ("primary_reentrancy_detectors", list(policy.PRIMARY_REENTRANCY)),
        ("secondary_broad_additions", list(policy.BROAD_ADDITIONS)), ("unchecked_detectors", list(policy.UNCHECKED))):
        require(slither.get(key) == expected, "Bound protocol Slither mapping/options differ: " + key)
    # The admission gate binds the protocol; this worker additionally binds the
    # complete prospective settings in method_config rather than editing legacy roles.
    return binding, auth, report, static, runtime


def production_jobs(p, root, binding, static):
    path = p.artifact(root, static["compiler_plan"])
    plan = read(path)
    require(plan.get("schema") == "compiler_only_preflight_plan_v1" and plan.get("outside_pragma_fallback") is False, "Compiler plan scope changed")
    require(sha(path.parent / "jobs.jsonl") == plan["jobs_sha256"], "Frozen compiler jobs changed")
    for rel, expected in plan["source_sha256"].items():
        require(sha(root / rel) == expected, "Frozen compiler helper changed")
    jobs = [json.loads(line) for line in (path.parent / "jobs.jsonl").read_text().splitlines()]
    jobs = [j for j in jobs if j["cohort"] == "external"]
    test = p.csv(p.artifact(root, binding["artifacts"]["test_manifest"]))
    require(len(jobs) == len(test) == 1998, "Complete fixed1998 external frame required")
    require([j["path"] for j in jobs] == test.path.tolist() and [j["file_sha256"] for j in jobs] == test.file_hash.tolist(), "Frozen compiler/test identity mismatch")
    source_root = p.local(root, binding["source_roots"]["external"]).resolve()
    for job in jobs:
        context = p.local(root, job["context_root"]).resolve()
        require((context / job["entry_source_unit"]).resolve() == (source_root / job["path"]).resolve(), "Compiler context root identity mismatch")
        require(job["preparation_status"] == "ready_to_attempt" or job["preparation_status"] in policy.RAW_STATUS_MAP, "Unknown preparation status")
        if job["preparation_status"] == "ready_to_attempt":
            require(len(job["source_units"]) == 1 and not job["import_edges"], "External single-source context changed")
            require(job["source_units"][0]["unit"] == job["entry_source_unit"] and job["source_units"][0]["sha256"] == job["file_sha256"], "Source unit identity mismatch")
    return jobs


def execute(root, binding_path, expected_sha256, release_path, authorization_path, authorization_sha256, out, *, resume=False):
    """Future private production entry; no gate bypass or synthetic argument."""
    verify_loaded()
    root, binding_path, release_path, authorization_path, out = [Path(x).resolve() for x in (root, binding_path, release_path, authorization_path, out)]
    require(root == ROOT, "Worker source root differs from binding root")
    require(out.is_relative_to(root / "data/derived") and out != root / "data/derived", "Raw analysis artifacts require private derived output directory")
    p = orchestration()
    binding, auth, report, static, runtime = _authorize(p, root, binding_path, expected_sha256, release_path, authorization_path, authorization_sha256)
    jobs = production_jobs(p, root, binding, static)
    provenance = {"binding_sha256": expected_sha256, "release_sha256": sha(release_path), "authorization_sha256": authorization_sha256,
        "method_config_sha256": binding["artifacts"]["method_config"]["sha256"], "reference_event_sha256": auth["reference_event_sha256"],
        "static_config": static, "source_code_sha256": {rel: sha(path) for rel, path in code_files().items()},
        "jobs_sha256": digest(jobs), "human_identity_authenticated": False}
    if out.exists():
        require(resume, "Existing execution requires explicit resume")
        receipt = read(out / "receipt.json")
        require(receipt["provenance"] == provenance and receipt["status"] == "complete_static_execution", "Resume provenance differs")
        actual = {str(f.relative_to(out)) for f in out.rglob("*") if f.is_file() and f != out / "receipt.json"}
        require(actual == set(receipt["artifact_sha256"]), "Resume artifact inventory differs")
        for rel, expected in receipt["artifact_sha256"].items():
            require(sha(out / rel) == expected, "Resume artifact changed")
        return {"status": "resume_verified_no_execution", "files": len(jobs)}
    out.mkdir(parents=True, mode=0o700)
    for rel, source in code_files().items():
        target = out / "source_snapshot" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    dump(out / "config_before_execution.json", provenance)
    dump(out / "jobs.json", jobs)
    started_utc, started = utc(), time.monotonic()
    rows = []
    for i, job in enumerate(jobs):
        target = out / "files" / f"{i:04d}"
        trace = scan_job(job, root / job["context_root"], target, runtime,
            remaining_seconds=policy.LIMITS["total_run_wall_seconds"] - (time.monotonic() - started))
        rows.extend(score_rows(trace, sha(target / "trace.json")))
    write_scores(out / "scores_primary.csv", [r for r in rows if r["variant"] == "primary"])
    write_scores(out / "scores_broad_secondary.csv", [r for r in rows if r["variant"] == "broad_secondary"])
    completed = utc()
    static_runs = []
    for cls in ("reentrancy", "unchecked"):
        log = out / (cls + "_tool_log.json")
        dump(log, {"job_id": f"slither:{cls}:0", "binding_sha256": expected_sha256, "outside_pragma_attempts": 0,
            "source_paths": [j["path"] for j in jobs], "scan_started_utc": started_utc, "scan_completed_utc": completed,
            "raw_artifacts_private": True, "status_counts": dict(collections.Counter(r["status"] for r in rows if r["class"] == cls and r["variant"] == "primary"))})
        static_runs.append({"job_id": f"slither:{cls}:0", "toolchain_inventory_sha256": binding["artifacts"]["toolchain_inventory"]["sha256"],
            "reference_event_sha256": auth["reference_event_sha256"], "tool_log": {"path": str(log.relative_to(root)), "sha256": sha(log)},
            "scan_started_utc": started_utc, "scan_completed_utc": completed})
    verify_loaded()
    check_runtime(runtime)
    require(provenance["source_code_sha256"] == {rel: sha(path) for rel, path in code_files().items()}, "Code changed during execution")
    receipt = {"status": "complete_static_execution", "provenance": provenance, "static_runs": static_runs,
        "files": len(jobs), "primary_score_rows": len(jobs) * 2, "broad_secondary_score_rows": len(jobs) * 2,
        "artifact_sha256": {str(f.relative_to(out)): sha(f) for f in out.rglob("*") if f.is_file()}}
    dump(out / "receipt.json", receipt)
    return {"status": receipt["status"], "files": len(jobs), "receipt_sha256": sha(out / "receipt.json")}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare-synthetic")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("run-synthetic")
    p.add_argument("--plan-dir", type=Path, required=True)
    p.add_argument("--expected-plan-sha256", required=True)
    p.add_argument("--resume", action="store_true")
    for name in ("preflight", "execute"):
        p = sub.add_parser(name)
        p.add_argument("--root", type=Path, required=True)
        p.add_argument("--binding", type=Path, required=True)
        p.add_argument("--expected-binding-sha256", required=True)
        p.add_argument("--release", type=Path, required=True)
        if name == "execute":
            p.add_argument("--authorization", type=Path, required=True)
            p.add_argument("--expected-authorization-sha256", required=True)
            p.add_argument("--out", type=Path, required=True)
            p.add_argument("--resume", action="store_true")
    args = cli.parse_args()
    try:
        if args.command == "prepare-synthetic":
            result = prepare_synthetic(args.out)
        elif args.command == "run-synthetic":
            result = run_synthetic(args.plan_dir, args.expected_plan_sha256, args.resume)
            result = {k: v for k, v in result.items() if k != "artifact_sha256"}
        elif args.command == "preflight":
            result = dry_preflight(args.root, args.binding, args.expected_binding_sha256, args.release)
        else:
            result = execute(args.root, args.binding, args.expected_binding_sha256, args.release, args.authorization,
                args.expected_authorization_sha256, args.out, resume=args.resume)
        print(json.dumps(result, indent=2))
        return 2 if args.command == "preflight" and not result["admission"].get("admission_artifacts_consistent") else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Production failures may contain source fragments in exception text.
        print(json.dumps({"status": "blocked_or_incomplete", "exception_type": type(exc).__name__, "detail_sha256": hashlib.sha256(str(exc).encode()).hexdigest()}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
