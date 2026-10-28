"""Independent authored dictionaries only; no compiler/Slither/source corpus use."""
from pathlib import Path
import copy
import importlib.util
import json
import pytest

BASE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location("independent_" + name, BASE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    exec(compile((BASE / (name + ".py")).read_bytes(), str(BASE / (name + ".py")), "exec"), module.__dict__)
    return module


parser = load("parse_results")
policy = load("policy")


def payload():
    return {"status": "complete", "registered_detectors": list(policy.DETECTOR_ORDER),
            "completed_detector_order": list(policy.DETECTOR_ORDER), "compilation_units": 1,
            "analysis_options": copy.deepcopy(policy.ANALYSIS_OPTIONS), "slither_version": "0.11.6",
            "crytic_compile_version": "0.4.2", "extra_compiler_invocations": 0, "findings": []}


def mapping(workspace, unit="Root.sol"):
    return {"filename_absolute": str(workspace / unit), "filename_relative": unit,
            "filename_short": "display-name-only.sol", "start": 0, "length": 1, "lines": [1]}


def finding(workspace, unit="Root.sol", detector="reentrancy-eth"):
    return {"check": detector, "id": "fictional-finding", "elements": [
        {"type": "function", "source_mapping": mapping(workspace, unit)}]}


def parse(value, workspace, **kwargs):
    return parser.parse_findings(value, units=["Root.sol", "lib/Base.sol", "other/Base.sol"],
        entry="Root.sol", workspace=workspace, detector_order=policy.DETECTOR_ORDER,
        analysis_options=policy.ANALYSIS_OPTIONS, **kwargs)


def test_root_import_and_cross_file_have_distinct_meanings(tmp_path):
    value = payload()
    root = finding(tmp_path)
    root["elements"].append({"type": "node", "source_mapping": mapping(tmp_path, "lib/Base.sol")})
    imported = finding(tmp_path, "other/Base.sol", "unchecked-lowlevel")
    value["findings"] = [root, imported]
    result = parse(value, tmp_path)
    assert result["root_detector_counts"] == {"reentrancy-eth": 1}
    assert result["import_only_detector_counts"] == {"unchecked-lowlevel": 1}
    assert result["findings"][0]["cross_file_context"] is True
    assert result["findings"][1]["attribution"] == "import_only"


def test_inherited_import_primary_is_not_reassigned_to_later_root(tmp_path):
    value = payload()
    f = finding(tmp_path, "lib/Base.sol")
    f["elements"].append({"type": "node", "source_mapping": mapping(tmp_path)})
    value["findings"] = [f]
    result = parse(value, tmp_path)
    assert result["root_detector_counts"] == {}
    assert result["import_only_detector_counts"] == {"reentrancy-eth": 1}
    assert result["findings"][0]["cross_file_context"] is True


def test_unknown_first_mapping_not_skipped_for_valid_later_one(tmp_path):
    value = payload()
    f = finding(tmp_path, "Unknown.sol")
    f["elements"].append({"type": "node", "source_mapping": mapping(tmp_path)})
    value["findings"] = [f]
    with pytest.raises(parser.ResultError):
        parse(value, tmp_path)


def test_conflicting_same_basename_identity_rejected(tmp_path):
    value = payload()
    f = finding(tmp_path, "lib/Base.sol")
    f["elements"][0]["source_mapping"]["filename_relative"] = "other/Base.sol"
    value["findings"] = [f]
    with pytest.raises(parser.ResultError):
        parse(value, tmp_path)


@pytest.mark.parametrize("field,value", [("start", -1), ("length", -1), ("start", True),
    ("length", 0.5), ("lines", None), ("lines", [False]), ("lines", [0]),
    ("filename_absolute", "/outside/Root.sol"), ("filename_relative", "/Root.sol")])
def test_malformed_mapping_rejected(tmp_path, field, value):
    data = payload()
    f = finding(tmp_path)
    f["elements"][0]["source_mapping"][field] = value
    data["findings"] = [f]
    with pytest.raises(parser.ResultError):
        parse(data, tmp_path)


@pytest.mark.parametrize("field,value", [("status", "partial"), ("findings", None),
    ("registered_detectors", list(reversed(policy.DETECTOR_ORDER))),
    ("registered_detectors", list(policy.DETECTOR_ORDER[:-1])),
    ("completed_detector_order", list(policy.DETECTOR_ORDER[:-1])), ("compilation_units", 0),
    ("extra_compiler_invocations", 1), ("slither_version", "0.11.5"),
    ("analysis_options", {"no_fail": True})])
def test_incomplete_or_altered_analysis_is_not_success(tmp_path, field, value):
    data = payload()
    data[field] = value
    with pytest.raises(parser.ResultError):
        parse(data, tmp_path)


@pytest.mark.parametrize("elements", [None, [], [None], [{"type": "node"}], ["wrong"]])
def test_malformed_first_element_rejected(tmp_path, elements):
    data = payload()
    f = finding(tmp_path)
    f["elements"] = elements
    data["findings"] = [f]
    with pytest.raises(parser.ResultError):
        parse(data, tmp_path)


def test_malformed_nested_mapping_does_not_escape_validation(tmp_path):
    data = payload()
    f = finding(tmp_path)
    f["elements"][0]["type_specific_fields"] = {"parent": {"source_mapping": None}}
    data["findings"] = [f]
    with pytest.raises(parser.ResultError):
        parse(data, tmp_path)


def test_duplicate_and_unrequested_detector_rejected(tmp_path):
    data = payload()
    f = finding(tmp_path)
    data["findings"] = [f, copy.deepcopy(f)]
    with pytest.raises(parser.ResultError):
        parse(data, tmp_path)
    data["findings"] = [finding(tmp_path, detector="not-in-frozen-seven")]
    with pytest.raises(parser.ResultError):
        parse(data, tmp_path)


def test_empty_complete_findings_is_valid_count_zero(tmp_path):
    result = parse(payload(), tmp_path)
    assert result["root_detector_counts"] == result["import_only_detector_counts"] == {}
    assert result["finding_count"] == 0


def test_every_observed_frozen_preparation_failure_has_exact_status_mapping():
    """Read public plan metadata only; no source bodies or annotation files."""
    path = BASE.parent / "compiler_preflight_v1/plan_20261026_v2/jobs.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    failures = {row["preparation_status"] for row in rows} - {"ready_to_attempt"}
    assert failures <= set(policy.RAW_STATUS_MAP)
    assert policy.RAW_STATUS_MAP["missing_import"] == "missing_dependency"
    assert sum(row["preparation_status"] == "missing_import" for row in rows) == 336


@pytest.mark.parametrize("used", ["Root.sol", "ABSOLUTE"])
def test_optional_used_identity_agrees_with_absolute_and_relative(tmp_path, used):
    data = payload()
    f = finding(tmp_path)
    f["elements"][0]["source_mapping"]["filename_used"] = str(tmp_path / "Root.sol") if used == "ABSOLUTE" else used
    data["findings"] = [f]
    assert parse(data, tmp_path)["root_detector_counts"] == {"reentrancy-eth": 1}


def test_byte_span_overflow_rejected_for_nested_import_mapping(tmp_path):
    data = payload()
    f = finding(tmp_path)
    nested = mapping(tmp_path, "lib/Base.sol")
    nested["start"], nested["length"] = 10, 2
    f["elements"].append({"type": "node", "source_mapping": nested})
    data["findings"] = [f]
    with pytest.raises(parser.ResultError):
        parse(data, tmp_path, unit_bytes={"Root.sol": 10, "lib/Base.sol": 11, "other/Base.sol": 20})


@pytest.mark.parametrize("units", [["Root.sol", []], ["Root.sol", ""], ["Root.sol", "."],
    ["Root.sol", "./Root.sol"], ["Root.sol", "a\\Root.sol"], ["Root.sol", "a\x00.sol"]])
def test_invalid_closure_is_result_error_not_raw_exception(tmp_path, units):
    with pytest.raises(parser.ResultError):
        parser.parse_findings(payload(), units=units, entry="Root.sol", workspace=tmp_path,
            detector_order=policy.DETECTOR_ORDER, analysis_options=policy.ANALYSIS_OPTIONS)
