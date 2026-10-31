"""
V1  Audit of the SolidiFI snippet templates: what does each injected bug contain?

For each of the 44 templates (bal.data.solidifi):

* occurrences in the 350 buggy files and the number of files that contain it;
* a compiler check: the template is placed alone in `contract T { ... }` and
  compiled with solc 0.5.17 (the version that 330 files use in C3). Recorded:
  the compiler warnings (e.g. "can be restricted to pure", which means the
  function has no effect on state or on other accounts), and the number of
  CALL opcodes in the runtime code (send, transfer and call.value compile to
  CALL; a member access such as `callee.call.value(1 ether);` without the
  final call parentheses compiles to no CALL);
* the author's reading of whether the snippet exhibits the weakness its
  SolidiFI type names (READING below, with the reason). This is one person's
  judgement, written before the tool results were inspected; it is reported
  as such and is not used to change any label.

Usage
-----
    python scripts/v1_template_audit.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bal.data import solidifi                                   # noqa: E402
from bal.utils.repro import atomic_to_csv, write_manifest       # noqa: E402
from c3_slither_baseline import ensure_solc                     # noqa: E402

SOLC = "0.5.17"

# yes = exhibits the weakness of its type; limited = the construct is there but the
# effect is limited as stated; no = the named weakness is absent
READING = {
    "Re-entrancy/T01": ("yes", "call.value forwards all gas; balance reset after the call"),
    "Re-entrancy/T02": ("limited", "send forwards the 2300-gas stipend; state written after the send"),
    "Re-entrancy/T03": ("yes", "call.value forwards all gas; balance reduced after the call"),
    "Re-entrancy/T04": ("limited", "transfer forwards the 2300-gas stipend; state reset after the transfer"),
    "Re-entrancy/T05": ("limited", "send with 2300-gas stipend; state reset after the send"),
    "Re-entrancy/T06": ("limited", "send with 2300-gas stipend; guard flag reset after the send"),
    "Re-entrancy/T07": ("limited", "send with 2300-gas stipend; counter updated after the send"),
    "Re-entrancy/T08": ("yes", "call.value forwards all gas; state written after the call"),
    "Re-entrancy/T09": ("limited", "send with 2300-gas stipend; balance reduced after the send"),
    "Re-entrancy/T10": ("yes", "call.value forwards all gas; guard flag reset after the call"),
    "Re-entrancy/T11": ("limited", "send with 2300-gas stipend; balance reset after the send"),
    "Re-entrancy/T12": ("yes", "call.value forwards all gas; balance reset after the call"),
    "Timestamp-Dependency/T01": ("limited", "view function returns a timestamp comparison; no state change depends on it"),
    "Timestamp-Dependency/T02": ("yes", "winner chosen by equality with block.timestamp"),
    "Timestamp-Dependency/T03": ("yes", "winner chosen by equality with block.timestamp (via a local)"),
    "Timestamp-Dependency/T04": ("yes", "payout when now % 15 == 0 (SWC-116 example)"),
    "Timestamp-Dependency/T05": ("no", "state variable initialised to block.timestamp; nothing reads it"),
    "Unchecked-Send/T01": ("yes", "unprotected public transfer of 1 ether to msg.sender (SWC-105)"),
    "Unhandled-Exceptions/T01": ("no", "callee.call.value(2 ether) is not invoked: no call is made"),
    "Unhandled-Exceptions/T02": ("yes", "return value of send ignored"),
    "Unhandled-Exceptions/T03": ("yes", "return value of send ignored"),
    "Unhandled-Exceptions/T04": ("limited", "return value of send tested, both branches empty"),
    "Unhandled-Exceptions/T05": ("yes", "return value of send ignored (amount 0)"),
    "Unhandled-Exceptions/T06": ("no", "return value of send tested and handled (revert on success)"),
    "Unhandled-Exceptions/T07": ("no", "return value of send tested; the function always reverts"),
    "Unhandled-Exceptions/T08": ("yes", "return value of send ignored, flag set afterwards"),
    "Unhandled-Exceptions/T09": ("yes", "return value of send ignored"),
    "Unhandled-Exceptions/T10": ("yes", "return value of send ignored"),
    "Unhandled-Exceptions/T11": ("yes", "return value of send ignored"),
    "Unhandled-Exceptions/T12": ("yes", "return value of call.value(...)(\"\") ignored"),
    "Unhandled-Exceptions/T13": ("no", "callee.call.value(1 ether) is not invoked: no call is made"),
    "Unhandled-Exceptions/T14": ("yes", "return value of send ignored (amount 0)"),
    "TOD/T01": ("yes", "reward goes to whoever set the winner first; front-runnable"),
    "TOD/T02": ("yes", "reward amount can change between submission and claim"),
    "Overflow-Underflow/T01": ("yes", "lock time += user input can wrap"),
    "Overflow-Underflow/T02": ("yes", "balance - value >= 0 is always true; balance can underflow"),
    "Overflow-Underflow/T03": ("limited", "uint8 local underflows; no state or transfer depends on it"),
    "Overflow-Underflow/T04": ("limited", "uint8 local overflows; no state or transfer depends on it"),
    "Overflow-Underflow/T05": ("yes", "lock time += user input can wrap"),
    "Overflow-Underflow/T06": ("yes", "balance - value >= 0 is always true; balance can underflow"),
    "tx.origin/T01": ("limited", "tx.origin compared with an owner address the caller passes as argument"),
    "tx.origin/T02": ("limited", "tx.origin compared with an owner address the caller passes as argument"),
    "tx.origin/T03": ("no", "tx.origin check guards to.call.value(amount), which is not invoked"),
    "tx.origin/T04": ("no", "tx.origin check guards nothing"),
}


def compile_template(src: str, solc: Path) -> dict:
    code = f"pragma solidity ^0.5.0;\ncontract T {{\n{src}\n}}\n"
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "T.sol"
        p.write_text(code)
        r = subprocess.run([str(solc), "--bin-runtime", "--opcodes", str(p)], capture_output=True, text=True, timeout=60)
    warn = sorted({re.sub(r"\s+", " ", m).strip() for m in re.findall(r"Warning: ([^\n]+)", r.stderr)})
    err = re.findall(r"Error: ([^\n]+)", r.stderr)
    ops = r.stdout.split("Opcodes:")[-1] if "Opcodes:" in r.stdout else ""
    return {"compiles": r.returncode == 0, "errors": " | ".join(err), "warnings": " | ".join(warn),
            "call_opcodes": len(re.findall(r"(?<![A-Z])CALL(?![A-Z])", ops)) if r.returncode == 0 else None,
            "restricted_to_pure_or_view": bool(re.search(r"can be restricted to (pure|view)", r.stderr))}


def main():
    run = Path("results/contracts") / time.strftime("v1_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    files, clean, cat = solidifi.load()
    solc = ensure_solc(SOLC)
    root = Path("data/raw/SolidiFI/bugs")
    rows = []
    for t, c in cat.items():
        first = {}
        for f in sorted((root / solidifi.TOOL_DIR.get(t, t)).glob("*/*.txt"), key=lambda p: (p.parent.name, int(p.stem))):
            key = tuple(x for x, _, _ in solidifi.template_tokens(f.read_text(encoding="utf-8", errors="replace")))
            first.setdefault(c[key], f)
        for key, tid in c.items():
            src = first[tid].read_text(encoding="utf-8", errors="replace")
            occ = sum(s.template == tid for f in files for s in f.snippets)
            nf = sum(any(s.template == tid for s in f.snippets) for f in files)
            reading, why = READING[tid]
            rows.append({"template": tid, "bug_type": t, "example_file": str(first[tid].relative_to(root)),
                         "occurrences": occ, "files": nf, "reading": reading, "reason": why,
                         **compile_template(src, solc)})
    df = pd.DataFrame(rows)
    atomic_to_csv(df, run / "template_audit.csv", index=False)
    s = df.groupby(["bug_type", "reading"]).agg(templates=("template", "count"), occurrences=("occurrences", "sum"))
    atomic_to_csv(s, run / "template_audit_summary.csv")
    print(df[["template", "occurrences", "reading", "compiles", "call_opcodes", "restricted_to_pure_or_view"]].to_string())
    print(s.to_string())
    write_manifest(run, script=Path(__file__).name, config={"solc": SOLC},
                   data_files=[f.path for f in files] + sorted(root.glob("*/*/*.txt")))
    print("wrote", run)


if __name__ == "__main__":
    main()
