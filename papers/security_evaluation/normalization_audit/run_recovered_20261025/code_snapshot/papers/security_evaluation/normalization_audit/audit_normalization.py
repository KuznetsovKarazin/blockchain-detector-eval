#!/usr/bin/env python3
"""Freeze and run comment-scanner sensitivity, without labels or model scores."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import resource
import shutil
import sys
import time

import pandas as pd

from solidity_scanner import ROOT, SolidityScanError, scan_comments, normalize_scanned_text
from bal.features.contract_features import normalised_text

HERE = Path(__file__).resolve().parent
AUDIT = ROOT / "papers/security_evaluation/external_audit/source_audit_full_20261025"
CODE = [HERE / "solidity_scanner.py", Path(__file__), ROOT / "src/bal/features/contract_features.py"]
INPUTS = [AUDIT / "candidate_source_metadata.csv", AUDIT / "upstream_source_metadata.csv"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def records():
    external = pd.read_csv(INPUTS[0], keep_default_na=False)
    upstream = pd.read_csv(INPUTS[1], keep_default_na=False)
    out = []
    for row in external.itertuples():
        out.append({"source": "candidate:" + row.source_id,
                    "path": "data/raw/salzano/" + row.path, "file_sha256": row.file_hash})
    for row in upstream.itertuples():
        out.append({"source": "reference:" + row.dataset,
                    "path": row.path, "file_sha256": row.file_hash})
    assert len(out) == 24131
    assert len({r["path"] for r in out}) == len(out)
    return sorted(out, key=lambda r: r["path"])


def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    rows = records()
    config = {
        "schema": "security_comment_normalization_sensitivity_v1",
        "status": "frozen_before_scanner_audit_and_corrected_graph",
        "frozen_utc": utc(), "population_records": len(rows),
        "population_by_source": dict(Counter(r["source"] for r in rows)),
        "scope": "Full pinned candidate 2181 plus uncapped references 21950; no cohort restriction",
        "changed_factor": "Comment recognition only; historical TOKEN_RE, KEEP and ID/NUM mapping retained",
        "literal_representation": "Source strings retained; historical regex still tokenizes their contents and omits quote delimiters",
        "scanner_semantics": {
            "quotes": ["single", "double"], "escapes": "Backslash consumes the following character lexically",
            "prefixes": "hex and unicode preserved as preceding ordinary characters",
            "comments": "// ends at CR or LF or EOF; /* ends at first */; no nesting",
            "replacement": "Every comment character becomes space except CR/LF; character positions preserved",
            "multiline_literals": "Retained and counted without deciding compiler validity",
            "unterminated_string_or_block": "Explicit error; corrected stream unavailable; no fallback or repair",
        },
        "input_decoding": "UTF-8; strict decode checked, errors=replace fallback matches inherited loader and is flagged",
        "comparison": "SHA256 and direct equality of normalized strings for successfully scanned records",
        "error_graph_rule": "Quarantine unavailable corrected streams; report lost records and inability to certify links through them",
        "example_policy": "First 20 changed paths per source and all errors; metadata pointers only, no source snippets",
        "inputs": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in INPUTS},
        "code": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in CODE},
        "external_scoring": False, "semantic_equivalence_claim": False,
    }
    save(out / "config.json", config)
    snapshot = out / "code_snapshot"
    for p in CODE:
        dest = snapshot / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    save(out / "manifest.json", {"status": "prepared_no_comparison", "prepared_utc": utc(),
                                  "config_sha256": sha((out / "config.json").read_bytes())})
    print(json.dumps({"config_sha256": sha((out / "config.json").read_bytes()),
                      "scanner_sha256": sha((HERE / "solidity_scanner.py").read_bytes()),
                      "records": len(rows)}))


def run(out):
    start = time.perf_counter()
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["status"] == "prepared_no_comparison"
    assert sha((out / "config.json").read_bytes()) == manifest["config_sha256"]
    config = json.loads((out / "config.json").read_text())
    for key in ("inputs", "code"):
        for path, digest in config[key].items():
            assert sha((ROOT / path).read_bytes()) == digest, path
    manifest.update(status="running", started_utc=utc())
    save(out / "manifest.json", manifest)
    rows = []
    examples = []
    example_count = Counter()
    for source in records():
        b = (ROOT / source["path"]).read_bytes()
        assert sha(b) == source["file_sha256"], source["path"]
        decode_replacement = False
        try:
            text = b.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            text = b.decode("utf-8", errors="replace")
            decode_replacement = True
        legacy = normalised_text(text)
        row = dict(source, legacy_normalized_sha256=sha(legacy.encode()),
                   corrected_normalized_sha256="", scanner_status="ok", error_code="",
                   error_line="", error_column="", normalization_changed="",
                   legacy_token_count=len(legacy.split()), corrected_token_count="",
                   line_comments="", block_comments="", string_literals="",
                   multiline_string_literals="", literal_comment_markers="",
                   first_marker_line="", first_marker_column="", change_reason="",
                   utf8_decode_replacement=decode_replacement)
        try:
            scanned = scan_comments(text)
            corrected = normalize_scanned_text(scanned.text)
            changed = legacy != corrected
            markers = scanned.literal_comment_markers
            row.update(corrected_normalized_sha256=sha(corrected.encode()),
                       normalization_changed=changed, corrected_token_count=len(corrected.split()),
                       line_comments=scanned.line_comments, block_comments=scanned.block_comments,
                       string_literals=scanned.string_literals,
                       multiline_string_literals=scanned.multiline_string_literals,
                       literal_comment_markers=len(markers),
                       first_marker_line=markers[0][2] if markers else "",
                       first_marker_column=markers[0][3] if markers else "",
                       change_reason=("literal_contains_comment_marker" if markers else "legacy_comment_order_or_boundary") if changed else "unchanged")
            if changed and example_count[source["source"]] < 20:
                examples.append(row.copy())
                example_count[source["source"]] += 1
        except SolidityScanError as exc:
            row.update(scanner_status="error", error_code=exc.code,
                       error_line=exc.line, error_column=exc.column,
                       change_reason="corrected_stream_unavailable")
            examples.append(row.copy())
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame.to_csv(out / "source_normalization_audit.csv", index=False)
    pd.DataFrame(examples, columns=frame.columns).to_csv(out / "example_metadata.csv", index=False)
    totals = []
    for source, group in frame.groupby("source", sort=True):
        ok = group.scanner_status == "ok"
        changed = group.normalization_changed == True
        totals.append({"source": source, "records": len(group), "scanned_ok": int(ok.sum()),
                       "scanner_errors": int((~ok).sum()), "normalized_changed": int(changed.sum()),
                       "normalized_unchanged": int((ok & ~changed).sum()),
                       "utf8_replacement_files": int(group.utf8_decode_replacement.sum()),
                       "multiline_literal_files": int((pd.to_numeric(group.multiline_string_literals, errors="coerce") > 0).sum()),
                       "changed_with_literal_marker": int((changed & (group.change_reason == "literal_contains_comment_marker")).sum()),
                       "changed_other_legacy_comment_behavior": int((changed & (group.change_reason == "legacy_comment_order_or_boundary")).sum())})
    pd.DataFrame(totals).to_csv(out / "source_summary.csv", index=False)
    manifest.update(status="complete_no_scoring", completed_utc=utc(),
                    total_records=len(rows), normalized_changed=int((frame.normalization_changed == True).sum()),
                    scanner_errors=int((frame.scanner_status != "ok").sum()),
                    source_summary=totals, runtime_seconds=time.perf_counter() - start,
                    peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                    environment={"python": sys.version, "platform": platform.platform(), "pandas": pd.__version__},
                    outputs={name: sha((out / name).read_bytes()) for name in
                             ("source_normalization_audit.csv", "example_metadata.csv", "source_summary.csv")},
                    limitations=["Isolated lexical sensitivity, not compiler validation or semantic equivalence",
                                 "Preserved literals remain subject to the historical lossy token representation",
                                 "Scanner errors cannot become empty streams or legacy fallbacks",
                                 "No model training, comparative scores or external performance computed"])
    save(out / "manifest.json", manifest)
    print(json.dumps({k: manifest[k] for k in ("status", "total_records", "normalized_changed", "scanner_errors", "source_summary", "runtime_seconds")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    (prepare if args.action == "prepare" else run)(args.out)
