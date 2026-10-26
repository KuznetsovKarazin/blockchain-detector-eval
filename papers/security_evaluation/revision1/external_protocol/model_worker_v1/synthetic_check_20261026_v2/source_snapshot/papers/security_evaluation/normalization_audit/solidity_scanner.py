"""String-aware comment scanning for a narrowly scoped lexical sensitivity audit.

This module does not parse Solidity or establish semantic equivalence. The
corrected representation changes comment recognition only: it deliberately
retains the historical token regex, KEEP set and identifier/numeral collapse.
Literal contents therefore remain tokenized by that historical regex.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from bal.features.contract_features import KEEP, TOKEN_RE


class SolidityScanError(ValueError):
    """An unfinished source region makes safe comment classification impossible."""

    def __init__(self, code: str, source: str, offset: int):
        self.code = code
        self.offset = offset
        self.line = source.count("\n", 0, offset) + 1
        self.column = offset - source.rfind("\n", 0, offset)
        super().__init__(f"{code} at line {self.line}, column {self.column}")


@dataclass(frozen=True)
class ScanResult:
    text: str
    line_comments: int
    block_comments: int
    string_literals: int
    multiline_string_literals: int
    # Kind, character offset, 1-based line, 1-based column; never source snippets.
    literal_comment_markers: tuple[tuple[str, int, int, int], ...]


def scan_comments(source: str) -> ScanResult:
    """Blank comments, preserving strings, character positions and CR/LF.

    Both quote styles and backslash escapes are recognized. ``hex`` and
    ``unicode`` prefixes are retained as ordinary preceding source characters.
    Newlines inside a quoted region are preserved and counted; this scanner
    does not decide whether a compiler accepts that source. Nested block
    comments are not supported by this scanner: the first */ closes a block.
    EOF in a quote or block comment raises SolidityScanError; EOF in a line
    comment is valid. No automatic repair or legacy fallback is performed.
    """
    chars = list(source)
    n = len(source)
    i = 0
    line_comments = block_comments = string_literals = multiline = 0
    markers: list[tuple[str, int, int, int]] = []

    def blank(start: int, end: int) -> None:
        for k in range(start, end):
            if chars[k] not in "\r\n":
                chars[k] = " "

    while i < n:
        ch = source[i]
        if ch in "\"'":
            quote, begin = ch, i
            j = i + 1
            while j < n:
                if source[j] == "\\":
                    # Escaping is lexical; no attempt to validate the escape.
                    j += 2
                    continue
                if source[j] == quote:
                    break
                j += 1
            if j >= n:
                raise SolidityScanError("unterminated_string", source, begin)
            string_literals += 1
            if "\n" in source[begin:j + 1] or "\r" in source[begin:j + 1]:
                multiline += 1
            # Diagnostic markers use raw literal bytes/characters, because the
            # historical regex has no notion of escapes or literal boundaries.
            for k in range(begin + 1, j):
                marker = source[k:k + 2]
                if marker in ("//", "/*"):
                    kind = "line_comment_marker" if marker == "//" else "block_comment_marker"
                    markers.append((kind, k, source.count("\n", 0, k) + 1,
                                    k - source.rfind("\n", 0, k)))
            i = j + 1
        elif source.startswith("//", i):
            j = i + 2
            while j < n and source[j] not in "\r\n":
                j += 1
            blank(i, j)
            line_comments += 1
            i = j
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            if end < 0:
                raise SolidityScanError("unterminated_block_comment", source, i)
            blank(i, end + 2)
            block_comments += 1
            i = end + 2
        else:
            i += 1
    return ScanResult("".join(chars), line_comments, block_comments,
                      string_literals, multiline, tuple(markers))


def normalize_scanned_text(scanned_text: str) -> str:
    """Use exactly the historical token regex and normalization rules."""
    out = []
    for token in TOKEN_RE.findall(scanned_text):
        if token[0].isalpha() or token[0] == "_":
            out.append(token if token in KEEP else "ID")
        elif token[0].isdigit():
            out.append("NUM")
        else:
            out.append(token)
    return " ".join(out)


def corrected_normalised_text(source: str) -> str:
    return normalize_scanned_text(scan_comments(source).text)
