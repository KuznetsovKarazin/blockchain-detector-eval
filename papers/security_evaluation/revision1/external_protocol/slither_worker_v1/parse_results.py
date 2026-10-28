"""Strict result/schema/attribution checks; no executable or source reads."""
from pathlib import Path, PurePosixPath
from collections import Counter
import hashlib
import json


class ResultError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ResultError(message)


def canonical_mapping(mapping, units, workspace):
    require(isinstance(mapping, dict), "Source mapping must be an object")
    expected = {str((Path(workspace) / u).resolve()): u for u in units}
    identities = []
    for field in ("filename_absolute", "filename_relative", "filename_used"):
        if field == "filename_used" and field not in mapping:
            continue
        value = mapping.get(field)
        require(isinstance(value, str) and value.strip(), "Missing canonical source identity: " + field)
        require("\\" not in value and "\x00" not in value, "Unsupported source identity")
        candidate = Path(value)
        if field != "filename_used":
            require(candidate.is_absolute() if field == "filename_absolute" else not candidate.is_absolute(), "Wrong path form: " + field)
        absolute = str((candidate if candidate.is_absolute() else Path(workspace) / candidate).resolve())
        require(absolute in expected, "Source mapping is outside exact compiled closure")
        identities.append(expected[absolute])
    require(len(set(identities)) == 1, "Conflicting canonical source mapping identities")
    for field in ("start", "length"):
        require(type(mapping.get(field)) is int and mapping[field] >= 0, "Invalid source span")
    lines = mapping.get("lines")
    require(isinstance(lines, list) and all(type(x) is int and x >= 1 for x in lines), "Invalid source line list")
    # filename_short is explicitly display-only in Slither; retain but never resolve it.
    return {"unit": identities[0], "start": mapping["start"], "length": mapping["length"], "lines": lines,
            "filename_short": mapping.get("filename_short")}


def parse_findings(payload, *, units, entry, workspace, detector_order, analysis_options, unit_bytes=None):
    require(isinstance(payload, dict) and payload.get("status") == "complete", "Analysis did not complete")
    require(payload.get("registered_detectors") == list(detector_order), "Detector registration inventory/order differs")
    require(payload.get("completed_detector_order") == list(detector_order) and payload.get("compilation_units") == 1,
            "Incomplete detector execution or compilation-unit inventory")
    require(payload.get("analysis_options") == analysis_options, "Analysis options differ")
    require(payload.get("slither_version") == "0.11.6" and payload.get("crytic_compile_version") == "0.4.2", "Runtime version differs")
    require(payload.get("extra_compiler_invocations") == 0, "Unexpected compiler invocation")
    require(isinstance(units, list) and units and all(isinstance(u, str) for u in units), "Invalid closure unit inventory")
    require(len(set(units)) == len(units) and entry in units, "Invalid closure unit inventory")
    require(all(u and u != "." and "\\" not in u and "\x00" not in u and str(PurePosixPath(u)) == u and
                not PurePosixPath(u).is_absolute() and ".." not in PurePosixPath(u).parts for u in units), "Noncanonical closure")
    if unit_bytes is not None:
        require(set(unit_bytes) == set(units) and all(type(n) is int and n >= 0 for n in unit_bytes.values()), "Invalid source byte-length inventory")
    findings = payload.get("findings")
    require(isinstance(findings, list), "Missing complete finding list")
    normalized, ids = [], set()
    for finding in findings:
        require(isinstance(finding, dict) and finding.get("check") in detector_order, "Unexpected detector result")
        require(isinstance(finding.get("id"), str) and finding["id"], "Missing finding identity")
        identity = (finding["check"], finding["id"])
        require(identity not in ids, "Duplicate detector finding")
        ids.add(identity)
        elements = finding.get("elements")
        require(isinstance(elements, list) and elements and isinstance(elements[0], dict), "Missing primary result element")
        require(elements[0].get("type") == "function", "Selected detector primary element must be a function definition")
        primary = canonical_mapping(elements[0].get("source_mapping"), units, workspace)
        mappings = []
        def collect(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "source_mapping":
                        mappings.append(canonical_mapping(item, units, workspace))
                    else:
                        collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)
        collect(elements)
        collect(finding.get("additional_fields", {}))
        if unit_bytes is not None:
            require(all(m["start"] + m["length"] <= unit_bytes[m["unit"]] for m in mappings), "Source span exceeds frozen source bytes")
        normalized.append({"detector": finding["check"], "finding_id": finding["id"],
            "attribution": "root" if primary["unit"] == entry else "import_only", "primary_mapping": primary,
            "all_mappings": mappings, "cross_file_context": len({m["unit"] for m in mappings}) > 1,
            "raw_finding_sha256": hashlib.sha256(json.dumps(finding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()})
    return {"root_detector_counts": dict(Counter(x["detector"] for x in normalized if x["attribution"] == "root")),
            "import_only_detector_counts": dict(Counter(x["detector"] for x in normalized if x["attribution"] == "import_only")),
            "finding_count": len(normalized), "findings": normalized,
            "root_score_zero_does_not_mean_dependency_or_contract_safe": True}
