"""Isolated pinned Slither analysis of one previously compiled artifact.

No compiler invocation, source resolution, network or project build is allowed.
The parent binds this script and every installed runtime file before launching.
"""
from pathlib import Path
import builtins
import hashlib
import importlib.metadata
import io
import json
import os
import socket
import subprocess
import sys


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CompilerFieldError(ValueError):
    pass


def analyze(request_path):
    request_path = Path(request_path).resolve()
    request = json.loads(request_path.read_text())
    workspace = Path.cwd().resolve()
    require(request["workspace"] == str(workspace), "Wrong working directory")
    require(digest(Path(__file__)) == request["child_sha256"], "Child source changed")
    require(sys.flags.isolated == 1 and sys.dont_write_bytecode and sys.pycache_prefix == str(workspace / "empty_pycache"), "Isolated fresh-bytecode policy required")
    require(not any(p.is_symlink() for p in Path(request["site_packages"]).rglob("*")), "Runtime symlink prohibited")
    for path, expected in request["runtime_files"].items():
        require(digest(path) == expected, "Runtime file changed: " + path)
    actual = sorted(str(p.resolve()) for p in Path(request["site_packages"]).rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    require(actual == request["site_package_files"], "Runtime file inventory changed")
    require(importlib.metadata.version("slither-analyzer") == "0.11.6", "Slither version changed")
    require(importlib.metadata.version("crytic-compile") == "0.4.2", "Crytic version changed")
    from crytic_compile import CryticCompile
    from crytic_compile.compilation_unit import CompilationUnit
    from crytic_compile.compiler.compiler import CompilerVersion
    from crytic_compile.platform.solc_standard_json import SolcStandardJson, parse_standard_json_output
    from slither.slither import Slither
    from slither.detectors.reentrancy.reentrancy_eth import ReentrancyEth
    from slither.detectors.reentrancy.reentrancy_read_before_write import ReentrancyReadBeforeWritten
    from slither.detectors.reentrancy.reentrancy_no_gas import ReentrancyNoGas
    from slither.detectors.reentrancy.reentrancy_benign import ReentrancyBenign
    from slither.detectors.reentrancy.reentrancy_events import ReentrancyEvent
    from slither.detectors.operations.unchecked_low_level_return_values import UncheckedLowLevel
    from slither.detectors.operations.unchecked_send_return_value import UncheckedSend
    detectors = [ReentrancyEth, ReentrancyReadBeforeWritten, ReentrancyNoGas, ReentrancyBenign,
                 ReentrancyEvent, UncheckedLowLevel, UncheckedSend]
    require([d.ARGUMENT for d in detectors] == request["detector_order"], "Detector order differs")
    expected_options = {"no_fail": False, "disallow_partial": True, "skip_analyze": False,
        "skip_assembly": False, "exclude_dependencies": False, "filter_paths": [], "include_paths": [],
        "triage_mode": False, "show_ignored_findings": True, "codex": False, "generate_patches": False}
    require(request["analysis_options"] == expected_options, "Unsafe analysis options")
    source_paths = {}
    for unit, expected in request["source_sha256"].items():
        p = (workspace / unit).resolve()
        require(p.is_relative_to(workspace) and p.is_file() and not p.is_symlink(), "Invalid staged source")
        require(digest(p) == expected, "Staged source changed")
        source_paths[unit] = p
    compiled_path = Path(request["compiled_path"])
    require(compiled_path.parent == workspace and digest(compiled_path) == request["compiled_sha256"], "Compiler artifact changed")
    compiled = json.loads(compiled_path.read_text())
    require(set(compiled.get("sources", {})) == set(source_paths), "Compiled source-unit set differs from closure")
    for contracts in compiled.get("contracts", {}).values():
        for contract in contracts.values():
            require(isinstance(contract.get("abi"), list), "ABI missing")
            for name in ("bytecode", "deployedBytecode"):
                obj = contract.get("evm", {}).get(name)
                if not (isinstance(obj, dict) and isinstance(obj.get("object"), str) and isinstance(obj.get("sourceMap"), str)):
                    raise CompilerFieldError("Required Slither compiler fields missing")
    # No lazy compiler, network rescue, autolink process or source read outside
    # the exact staged closure. Runtime code files remain readable for lazy imports.
    permitted = {p.resolve() for p in source_paths.values()} | {compiled_path, request_path}
    permitted |= {Path(p).resolve() for p in request["runtime_files"]}
    real_open, real_io_open, real_os_open = builtins.open, io.open, os.open
    def check_file(file, mode="r"):
        if isinstance(file, int):
            require(file in (0, 1, 2), "Unexpected file descriptor")
            return
        p = Path(file).resolve()
        require(not any(x in mode for x in ("w", "a", "+", "x")), "Analysis writes prohibited")
        require(p in permitted, "Analysis attempted unrecorded file read: " + str(p))
    def safe_open(file, mode="r", *args, **kwargs):
        check_file(file, mode)
        return real_open(file, mode, *args, **kwargs)
    def safe_io_open(file, mode="r", *args, **kwargs):
        check_file(file, mode)
        return real_io_open(file, mode, *args, **kwargs)
    def safe_os_open(file, flags, *args, **kwargs):
        require(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND) == 0, "Analysis write descriptor prohibited")
        check_file(file)
        return real_os_open(file, flags, *args, **kwargs)
    def denied(*args, **kwargs):
        raise RuntimeError("Nested process/network operation prohibited during precompiled analysis")
    builtins.open, io.open, os.open = safe_open, safe_io_open, safe_os_open
    subprocess.Popen = subprocess.run = subprocess.call = subprocess.check_call = subprocess.check_output = denied
    os.system = os.popen = denied
    socket.socket = socket.create_connection = denied
    class FrozenOutput(SolcStandardJson):
        def __init__(self):
            super().__init__({"language": "Solidity", "sources": {}, "settings": request["compiler_settings"]})
        def compile(self, crytic_compile, **kwargs):
            unit = CompilationUnit(crytic_compile, "frozen_precompiled_standard_json")
            unit.compiler_version = CompilerVersion("solc", request["compiler_version"], False)
            parse_standard_json_output(compiled, unit, solc_working_dir=str(workspace))
            crytic_compile.src_content = {str(p): p.read_bytes().decode("utf-8", errors="strict") for p in source_paths.values()}
    compilation = CryticCompile(FrozenOutput(), cwd=str(workspace), skip_clean=True,
                               compile_autolink=False, compile_custom_build=None)
    triage = workspace / "never_existing_triage_database.json"
    require(not triage.exists(), "Ambient triage database is not allowed")
    slither = Slither(compilation, **expected_options, triage_database=str(triage))
    require(len(slither.compilation_units) == 1, "Exactly one compilation unit required")
    for detector in detectors:
        slither.register_detector(detector)
    actual_order = [d.ARGUMENT for d in slither.detectors]
    require(actual_order == request["detector_order"], "Actual detector registration differs")
    result_groups = slither.run_detectors()
    require(isinstance(result_groups, list) and len(result_groups) == len(detectors) and
            all(isinstance(group, list) and all(isinstance(f, dict) for f in group) for group in result_groups), "Incomplete detector result groups")
    findings = [finding for group in result_groups for finding in group]
    return {"schema": "pinned_slither_trace_v1", "status": "complete", "slither_version": "0.11.6",
        "crytic_compile_version": "0.4.2", "registered_detectors": actual_order, "completed_detector_order": actual_order,
        "analysis_options": expected_options, "extra_compiler_invocations": 0,
        "compiler_version": request["compiler_version"], "findings": findings,
        "compilation_units": len(slither.compilation_units), "root_entry": request["entry"]}


def main():
    try:
        result = analyze(sys.argv[1])
    except Exception as exc:
        result = {"schema": "pinned_slither_trace_v1", "status": "error", "error_type": type(exc).__name__, "error": str(exc),
                  "error_code": "missing_slither_compiler_fields" if isinstance(exc, CompilerFieldError) else "slither_error"}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
