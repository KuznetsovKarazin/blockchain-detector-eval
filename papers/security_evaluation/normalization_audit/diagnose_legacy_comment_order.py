#!/usr/bin/env python3
"""Locate legacy block-regex matches starting inside actual line comments.

This post-audit explanation does not alter the frozen scanner or token streams.
Output contains only source identity and line/column pointers, not source text.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import pandas as pd
from solidity_scanner import ROOT, scan_comments


def line_comment_spans(source):
    # scan_comments first validates that quotes/blocks terminate. The loop here
    # extracts diagnostic spans without changing the frozen scanner interface.
    scan_comments(source)
    spans = []
    i = 0
    while i < len(source):
        if source[i] in "\"'":
            quote = source[i]
            j = i + 1
            while j < len(source):
                if source[j] == "\\":
                    j += 2
                elif source[j] == quote:
                    break
                else:
                    j += 1
            i = j + 1
        elif source.startswith("//", i):
            j = i + 2
            while j < len(source) and source[j] not in "\r\n":
                j += 1
            spans.append((i, j))
            i = j
        elif source.startswith("/*", i):
            i = source.index("*/", i + 2) + 2
        else:
            i += 1
    return spans


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    destination = args.run / "comment_order_diagnostic.csv"
    if destination.exists():
        raise FileExistsError(destination)
    metadata = pd.read_csv(args.run / "source_normalization_audit.csv", keep_default_na=False)
    selected = metadata[metadata.change_reason == "legacy_comment_order_or_boundary"]
    output = []
    for row in selected.itertuples():
        raw = (ROOT / row.path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row.file_sha256
        text = raw.decode("utf-8", errors="replace")
        spans = line_comment_spans(text)
        starts = [match.start() for match in re.finditer(r"/\*.*?\*/", text, re.S)
                  if any(a <= match.start() < b for a, b in spans)]
        output.append({"source": row.source, "path": row.path, "file_sha256": row.file_sha256,
                       "legacy_block_matches_starting_inside_line_comment": len(starts),
                       "first_start_line": text.count("\n", 0, starts[0]) + 1 if starts else "",
                       "first_start_column": starts[0] - text.rfind("\n", 0, starts[0]) if starts else "",
                       "mechanism_confirmed": bool(starts)})
    pd.DataFrame(output).to_csv(destination, index=False)
    summary = {"status": "post_audit_diagnostic_no_stream_changes",
               "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "input_metadata_sha256": hashlib.sha256((args.run / "source_normalization_audit.csv").read_bytes()).hexdigest(),
               "records_examined": len(output), "mechanism_confirmed": sum(r["mechanism_confirmed"] for r in output),
               "source_counts": dict(Counter(r["source"] for r in output)),
               "output_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
    (args.run / "comment_order_diagnostic.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
