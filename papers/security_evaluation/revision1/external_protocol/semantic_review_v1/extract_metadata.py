#!/usr/bin/env python3
"""Read pinned detector Python sources as text/AST; never import or run Slither.

Only the explicit Python-source allowlist, wheel, wheel metadata, artifact index
and draft protocol are read. No target Solidity, annotation or score is opened.
Existing outputs are not overwritten. The JSON is deterministic for fixed inputs.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile


DETECTORS = {
    "reentrancy/reentrancy_eth.py": ("reentrancy-eth", "HIGH"),
    "reentrancy/reentrancy_read_before_write.py": ("reentrancy-no-eth", "MEDIUM"),
    "reentrancy/reentrancy_no_gas.py": ("reentrancy-unlimited-gas", "INFORMATIONAL"),
    "reentrancy/reentrancy_benign.py": ("reentrancy-benign", "LOW"),
    "reentrancy/reentrancy_events.py": ("reentrancy-events", "LOW"),
    "operations/unchecked_low_level_return_values.py": ("unchecked-lowlevel", "MEDIUM"),
    "operations/unchecked_send_return_value.py": ("unchecked-send", "MEDIUM"),
}
HELPERS = ["reentrancy/reentrancy.py", "operations/unused_return_values.py", "abstract_detector.py"]
FIELDS = {"ARGUMENT", "HELP", "IMPACT", "CONFIDENCE", "STANDARD_JSON", "WIKI", "VULNERABLE_SOLC_VERSIONS"}
EXPECTED_MAPPING = {
    "primary_reentrancy_detectors": ["reentrancy-eth", "reentrancy-no-eth", "reentrancy-unlimited-gas"],
    "secondary_broad_additions": ["reentrancy-benign", "reentrancy-events"],
    "unchecked_detectors": ["unchecked-lowlevel", "unchecked-send"],
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scalar(node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    raise ValueError(f"Unexpected metadata expression: {type(node).__name__}")


def describe_source(relative: str, data: bytes) -> dict:
    tree = ast.parse(data.decode("utf-8"), filename=relative)
    classes = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        fields, methods = {}, {}
        for item in node.body:
            targets = item.targets if isinstance(item, ast.Assign) else [item.target] if isinstance(item, ast.AnnAssign) else []
            for target in targets:
                if isinstance(target, ast.Name) and target.id in FIELDS and item.value is not None:
                    fields[target.id] = {"value": scalar(item.value), "line": item.lineno}
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods[item.name] = {"start_line": item.lineno, "end_line": item.end_lineno}
        classes.append({"name": node.name, "start_line": node.lineno, "end_line": node.end_lineno,
                        "declared_metadata": fields, "method_ranges": methods})
    return {"relative_to_detectors": relative, "source_sha256": digest(data),
            "source_bytes": len(data), "source_lines": len(data.splitlines()), "classes": classes}


def collect(repo: Path) -> dict:
    protocol_dir = repo / "papers/security_evaluation/revision1/external_protocol"
    index_path = protocol_dir / "toolchain_v1/python_artifacts.json"
    index_bytes = index_path.read_bytes()
    artifacts = json.loads(index_bytes)["artifacts"]
    records = [x for x in artifacts if x["package"].replace("_", "-") == "slither-analyzer"]
    if len(records) != 1 or records[0]["version"] != "0.11.6":
        raise ValueError("Expected exactly one pinned Slither 0.11.6 wheel")
    wheel = records[0]
    wheel_bytes = (repo / wheel["local_path"]).read_bytes()
    if digest(wheel_bytes) != wheel["artifact_sha256"]:
        raise ValueError("Pinned wheel SHA256 mismatch")
    detector_root = repo / "data/derived/security_toolchain_v1/python_env/lib/python3.12/site-packages/slither/detectors"
    sources = []
    with zipfile.ZipFile(repo / wheel["local_path"]) as archive:
        metadata = archive.read("slither_analyzer-0.11.6.dist-info/METADATA")
        if b"\nVersion: 0.11.6\n" not in metadata:
            raise ValueError("Wheel metadata version mismatch")
        for relative in [*DETECTORS, *HELPERS]:
            data = (detector_root / relative).read_bytes()
            if data != archive.read("slither/detectors/" + relative):
                raise ValueError(f"Installed source differs from pinned wheel: {relative}")
            entry = describe_source(relative, data)
            entry["matches_pinned_wheel_member"] = True
            if relative in DETECTORS:
                argument, impact = DETECTORS[relative]
                matching = [c for c in entry["classes"] if c["declared_metadata"].get("ARGUMENT", {}).get("value") == argument]
                if len(matching) != 1 or matching[0]["declared_metadata"]["IMPACT"]["value"] != "DetectorClassification." + impact:
                    raise ValueError(f"Detector metadata mismatch: {relative}")
                if matching[0]["declared_metadata"]["CONFIDENCE"]["value"] != "DetectorClassification.MEDIUM":
                    raise ValueError(f"Unexpected confidence: {relative}")
            sources.append(entry)
    protocol_path = protocol_dir / "protocol_B_draft.json"
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    mapping = {key: protocol["slither"][key] for key in EXPECTED_MAPPING}
    if mapping != EXPECTED_MAPPING:
        raise ValueError("Draft detector mapping differs from this review's declared mapping")
    abstract_source = (detector_root / "abstract_detector.py").read_text()
    output_lines = [n for n, line in enumerate(abstract_source.splitlines(), 1) if "standard_format=self.STANDARD_JSON" in line]
    if len(output_lines) != 1:
        raise ValueError("Expected one output-format use of STANDARD_JSON")
    return {
        "schema": "slither_semantic_source_review_v1", "review_date": "2026-10-26",
        "audience": "coordinator_only_not_blind_reviewer_packet",
        "status": "preliminary_source_mapping_review_not_human_signoff",
        "human_semantic_signoff": False, "detectors_executed": False,
        "target_solidity_read": False, "source_labels_read": False, "scores_read": False,
        "existing_mapping_changed": False,
        "extractor_sha256": digest(Path(__file__).read_bytes()),
        "artifact_index_sha256": digest(index_bytes),
        "pinned_wheel": {key: wheel[key] for key in ["package", "version", "filename", "artifact_sha256", "download_url"]},
        "wheel_metadata_sha256": digest(metadata),
        "draft_protocol_sha256": digest(protocol_bytes), "draft_detector_mapping": mapping,
        "sources": sources,
        "standard_json_interpretation": {"scope": "output formatting, not compiler standard-JSON compatibility",
                                         "file": "abstract_detector.py", "output_constructor_line": output_lines[0]},
        "current_wiki": {"url": "https://github.com/crytic/slither/wiki/Detector-Documentation",
                         "checked_date": "2026-10-26", "version_fixed": False,
                         "authority_for_implemented_predicates": "pinned wheel and matching installed Python sources",
                         "note": "Wiki reviewed separately; this offline script does not fetch it."},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[5])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.repo.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"Verified 7 detectors and 3 helpers; wrote {args.output}")


if __name__ == "__main__":
    main()
