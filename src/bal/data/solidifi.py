"""
SolidiFI decomposed: clean base contracts, injected snippets and their templates (V).

The SolidiFI benchmark (DependableSystemsLab/SolidiFI-benchmark @4b0573e) ships
350 buggy files (50 base contracts x 7 bug types) and a BugLog per file. The
SolidiFI tool repository (DependableSystemsLab/SolidiFI @ebb02e3) also holds
the 50 original contracts (`contracts/<k>.sol`) and the snippet files the
injector draws from (`bugs/<type>/{tf,ts}/*.txt`).

Template catalogue: a snippet file becomes a token sequence in which comments
are removed, numbers become `N` and trailing digits of identifiers become `#`
(`balances_re_ent7` -> `balances_re_ent#`). Snippet files with the same
sequence are one template. Templates are numbered per bug type in the order of
their first snippet file.

Locating snippets: every template sequence is searched in the token sequence
of a buggy file, longest templates first, without overlaps. Each occurrence
gives one injected snippet with its template id and its line span. Removing all
occurrences must give the token sequence of the original contract; `verify`
checks that file by file and compares the count with the BugLog.

Variants built from one buggy file (all compile-free source texts):
    clean       the original contract (`contracts/<k>.sol`)
    only(T)     the buggy file with every snippet NOT in template set T removed
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

TYPES = ["Re-entrancy", "Timestamp-Dependency", "Unchecked-Send", "Unhandled-Exceptions", "TOD",
         "Overflow-Underflow", "tx.origin"]
TOOL_DIR = {"tx.origin": "tx-origin"}          # folder name in the tool repository

_TOK = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|\S")


def _blank_comments(src: str) -> str:
    """Comments replaced by spaces, newlines kept, so offsets and line numbers stay valid."""
    return re.sub(r"/\*.*?\*/|//[^\n]*", lambda m: re.sub(r"[^\n]", " ", m.group()), src, flags=re.S)


def template_tokens(src: str) -> list[tuple[str, int, int]]:
    """(normalised token, start offset, end offset) for every token outside comments."""
    out = []
    for m in _TOK.finditer(_blank_comments(src)):
        t = m.group()
        if t[0].isdigit():
            t = "N"
        elif t[0].isalpha() or t[0] == "_":
            t = re.sub(r"\d+$", "#", t)
        out.append((t, m.start(), m.end()))
    return out


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


@dataclass
class Snippet:
    template: str                 # e.g. "Re-entrancy/T03"
    tok_start: int
    tok_len: int
    char_start: int
    char_end: int
    line_start: int               # 1-based, inclusive
    line_end: int


@dataclass
class BuggyFile:
    bug_type: str
    k: int
    path: Path
    source: str
    snippets: list[Snippet] = field(default_factory=list)
    buglog_rows: int = 0
    buglog_lines: set = field(default_factory=set)

    def only(self, keep: set[str]) -> str:
        """Source with every snippet whose template is not in `keep` cut out."""
        cut = sorted((s.char_start, s.char_end) for s in self.snippets if s.template not in keep)
        out, pos = [], 0
        for a, b in cut:
            out.append(self.source[pos:a])
            pos = b
        out.append(self.source[pos:])
        return "".join(out)

    def injected_lines(self, templates: set[str] | None = None) -> set[int]:
        return {ln for s in self.snippets if templates is None or s.template in templates
                for ln in range(s.line_start, s.line_end + 1)}


def load_templates(tool_root="data/raw/SolidiFI") -> dict[str, dict[tuple, str]]:
    """bug type -> {token sequence: template id}."""
    root = Path(tool_root) / "bugs"
    cat = {}
    for t in TYPES:
        files = sorted((root / TOOL_DIR.get(t, t)).glob("*/*.txt"),
                       key=lambda p: (p.parent.name, int(p.stem)))
        seqs = {}
        for f in files:
            key = tuple(x for x, _, _ in template_tokens(_read(f)))
            if key and key not in seqs:
                seqs[key] = f"{t}/T{len(seqs) + 1:02d}"
        cat[t] = seqs
    return cat


def _find_all(seq: list[str], pat: tuple) -> list[int]:
    n, first = len(pat), pat[0]
    return [i for i in range(len(seq) - n + 1) if seq[i] == first and tuple(seq[i:i + n]) == pat]


def locate(source: str, templates: dict[tuple, str]) -> list[Snippet]:
    tk = template_tokens(source)
    seq = [t for t, _, _ in tk]
    used = np.zeros(len(seq), bool)
    found = []
    for key, tid in sorted(templates.items(), key=lambda kv: (-len(kv[0]), kv[1])):
        for i in _find_all(seq, key):
            if used[i:i + len(key)].any():
                continue
            used[i:i + len(key)] = True
            a, b = tk[i][1], tk[i + len(key) - 1][2]
            found.append(Snippet(tid, i, len(key), a, b, source.count("\n", 0, a) + 1,
                                 source.count("\n", 0, b) + 1))
    return sorted(found, key=lambda s: s.tok_start)


def _buglog(p: Path, n_lines: int) -> tuple[int, set]:
    if not p.exists():
        return 0, set()
    rows = [r for r in csv.reader(p.open(encoding="utf-8", errors="replace"))][1:]
    rows = [r for r in rows if r and r[0].strip().isdigit()]
    lines = {ln for r in rows for ln in range(int(r[0]), int(r[0]) + int(r[1])) if ln <= n_lines}
    return len(rows), lines


def load(bench_root="data/raw/SolidiFI-benchmark", tool_root="data/raw/SolidiFI"):
    """(buggy files, clean bases {k: source}, template catalogue)."""
    cat = load_templates(tool_root)
    clean = {int(p.stem): _read(p) for p in (Path(tool_root) / "contracts").glob("*.sol")
             if p.stem.isdigit()}
    files = []
    for t in TYPES:
        d = Path(bench_root) / "buggy_contracts" / t
        for p in sorted(d.glob("buggy_*.sol"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1))):
            k = int(re.search(r"(\d+)", p.stem).group(1))
            src = _read(p)
            n, lines = _buglog(d / f"BugLog_{k}.csv", src.count("\n") + 1)
            files.append(BuggyFile(t, k, p, src, locate(src, cat[t]), n, lines))
    return files, clean, cat


def verify(files: list[BuggyFile], clean: dict[int, str]) -> list[dict]:
    """Per buggy file: snippets found vs BugLog rows, and whether removing every
    snippet gives the original contract token for token."""
    rows = []
    for f in files:
        rest = [t for t, _, _ in template_tokens(f.only(set()))]
        base = [t for t, _, _ in template_tokens(clean.get(f.k, ""))]
        inj = f.injected_lines()
        rows.append({"bug_type": f.bug_type, "k": f.k, "n_snippets": len(f.snippets),
                     "n_buglog": f.buglog_rows, "base_equal": rest == base,
                     "base_token_diff": abs(len(rest) - len(base)),
                     "buglog_line_recall": len(inj & f.buglog_lines) / max(1, len(inj)),
                     "n_templates": len({s.template for s in f.snippets})})
    return rows
