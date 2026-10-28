"""Prospective tool execution choices; NOT human semantic sign-off."""
PRIMARY_REENTRANCY = ("reentrancy-eth", "reentrancy-no-eth", "reentrancy-unlimited-gas")
BROAD_ADDITIONS = ("reentrancy-benign", "reentrancy-events")
UNCHECKED = ("unchecked-lowlevel", "unchecked-send")
DETECTOR_ORDER = PRIMARY_REENTRANCY + BROAD_ADDITIONS + UNCHECKED
ANALYSIS_OPTIONS = {"no_fail": False, "disallow_partial": True, "skip_analyze": False,
    "skip_assembly": False, "exclude_dependencies": False, "filter_paths": [], "include_paths": [],
    "triage_mode": False, "show_ignored_findings": True, "codex": False, "generate_patches": False}
SETTINGS = {"optimizer": {"enabled": False}, "remappings": [], "outputSelection": {
    "*": {"": ["ast"], "*": ["abi", "evm.bytecode.object", "evm.bytecode.sourceMap",
                                "evm.deployedBytecode.object", "evm.deployedBytecode.sourceMap"]}}}
LIMITS = {"wall_seconds": 180, "cpu_seconds": 180, "memory_bytes": 2 * 1024**3,
          "stdout_bytes": 16 * 1024**2, "stderr_bytes": 1024**2, "input_bytes": 16 * 1024**2,
          "open_files": 64, "max_sources": 128, "source_bytes": 8 * 1024**2,
          "attempts_per_file": 5, "total_run_wall_seconds": 7200}
RAW_STATUS_MAP = {"ok": "ok", "compiler_error": "compile_error", "process_failure": "compile_error",
    "missing_pragma": "unsupported_pragma", "unsupported_constraint": "unsupported_pragma",
    "no_compatible_catalog_release": "unsupported_pragma", "import_missing": "missing_dependency", "missing_import": "missing_dependency",
    "remote_or_absolute_import_forbidden": "missing_dependency", "import_outside_snapshot": "missing_dependency",
    "import_syntax_unresolved": "missing_dependency", "import_literal_unsupported": "missing_dependency",
    "direct_import_noncanonical": "missing_dependency", "import_ambiguous": "missing_dependency",
    "import_scan_error": "preprocessing_error", "source_scanner_error": "preprocessing_error",
    "scanner_error": "preprocessing_error", "decode_error": "preprocessing_error",
    "timeout": "timeout", "cpu_limit": "timeout", "not_attempted_run_budget": "timeout",
    "not_completed_run_budget": "timeout", "output_limit": "tool_error", "launch_error": "unavailable_binary",
    "malformed_compiler_output": "tool_error", "compiler_output_schema_error": "tool_error",
    "missing_slither_compiler_fields": "tool_error", "slither_error": "tool_error",
    "malformed_slither_output": "tool_error", "slither_output_schema_error": "tool_error",
    "attribution_error": "tool_error", "input_staging_failure": "tool_error"}
POLICY = {"schema": "prospective_slither_execution_policy_v1", "slither_version": "0.11.6", "crytic_compile_version": "0.4.2",
    "detector_order": list(DETECTOR_ORDER), "primary_reentrancy_detectors": list(PRIMARY_REENTRANCY),
    "secondary_broad_additions": list(BROAD_ADDITIONS), "unchecked_detectors": list(UNCHECKED),
    "analysis_options": ANALYSIS_OPTIONS, "score": "binary_root_attributed_detector_union_not_probability",
    "attribution": "exact_first_element_source_mapping; no search for first recognized mapping; import-defined inherited functions remain import-attributed",
    "filename_short": "display_only_never_identity", "absolute_relative_used": "all supplied canonical identity fields must agree with exact closure",
    "compiler_selection": "original ordered candidates; stop at first compiler success; no fallback after Slither failure",
    "standard_json_settings": SETTINGS, "limits": LIMITS, "status_mapping": RAW_STATUS_MAP,
    "diagnostic_reruns": 0, "outside_pragma_fallback": False, "human_semantic_signoff": False,
    "historical_equivalence": False}
