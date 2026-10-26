"""Alternative lexical representations; no compiler AST or semantic claims."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'papers/security_evaluation/normalization_audit'))
from solidity_scanner import scan_comments, normalize_scanned_text, SolidityScanError
from bal.features.contract_features import TOKEN_RE


class StructuralScanError(ValueError):
    def __init__(self, code, offset):
        self.code, self.offset = code, offset
        super().__init__(f'{code} at character {offset}')


@dataclass(frozen=True)
class Token:
    value: str
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class MaskResult:
    text: str
    units: list[dict]
    informative: bool
    removed_unit_count: int
    has_top_level_contract: bool
    remaining_structural_token_count: int


def structural_tokens(cleaned_source):
    """Identifier/punctuation tokens with positions; strings are atomic tokens."""
    out = []
    i, n = 0, len(cleaned_source)
    while i < n:
        ch = cleaned_source[i]
        if ch.isspace():
            i += 1
        elif ch in '\"\'':
            q, j = ch, i + 1
            while j < n:
                if cleaned_source[j] == '\\':
                    j += 2
                elif cleaned_source[j] == q:
                    break
                else:
                    j += 1
            if j >= n:
                raise StructuralScanError('unterminated_literal', i)
            out.append(Token('<literal>', i, j + 1, 'literal'))
            i = j + 1
        elif re.match(r'[A-Za-z_$]', ch):
            j = i + 1
            while j < n and re.match(r'[A-Za-z0-9_$]', cleaned_source[j]):
                j += 1
            out.append(Token(cleaned_source[i:j], i, j, 'identifier'))
            i = j
        else:
            out.append(Token(ch, i, i + 1, 'punctuation'))
            i += 1
    return out


def inspect_top_level(source):
    """Find balanced top-level contract/library/interface declaration blocks.

    Bodies are balanced lexically, with quoted braces ignored. Imports/pragmas
    are recognized only to classify directive-only residue after masking.
    Other top-level constructs are retained; they are not classified as safe,
    application-specific, or compiler-valid. Unsupported/malformed declaration
    headers and unmatched braces fail explicitly.
    """
    clean = scan_comments(source).text
    tokens = structural_tokens(clean)
    units, directives = [], []
    depth = 0
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if depth == 0 and t.kind == 'identifier' and t.value in ('pragma', 'import'):
            j = i + 1
            while j < len(tokens) and tokens[j].value != ';':
                j += 1
            if j == len(tokens):
                raise StructuralScanError('unterminated_directive', t.start)
            directives.append((t.start, tokens[j].end))
            i = j + 1
            continue
        if depth == 0 and t.kind == 'identifier' and t.value in ('contract', 'library', 'interface'):
            if i + 1 >= len(tokens) or tokens[i + 1].kind != 'identifier':
                raise StructuralScanError('declaration_missing_name', t.start)
            name = tokens[i + 1].value
            j, paren, bracket = i + 2, 0, 0
            while j < len(tokens):
                v = tokens[j].value
                if v == '(':
                    paren += 1
                elif v == ')':
                    paren -= 1
                elif v == '[':
                    bracket += 1
                elif v == ']':
                    bracket -= 1
                elif v == '{':
                    if paren or bracket:
                        raise StructuralScanError('brace_inside_declaration_header_group', tokens[j].start)
                    break
                elif v in (';', '}'):
                    raise StructuralScanError('declaration_missing_body', t.start)
                if paren < 0 or bracket < 0:
                    raise StructuralScanError('unbalanced_declaration_header', t.start)
                j += 1
            if j == len(tokens):
                raise StructuralScanError('declaration_missing_body', t.start)
            k, nesting = j + 1, 1
            while k < len(tokens) and nesting:
                if tokens[k].value == '{':
                    nesting += 1
                elif tokens[k].value == '}':
                    nesting -= 1
                k += 1
            if nesting:
                raise StructuralScanError('unclosed_declaration_body', t.start)
            end = tokens[k - 1].end
            units.append({'kind': t.value, 'name': name, 'start': t.start, 'end': end,
                          'start_line': source.count('\n', 0, t.start) + 1,
                          'end_line': source.count('\n', 0, end) + 1})
            i = k
            continue
        if t.kind != 'literal':
            if t.value == '{':
                depth += 1
            elif t.value == '}':
                depth -= 1
                if depth < 0:
                    raise StructuralScanError('unmatched_closing_brace', t.start)
        i += 1
    if depth:
        raise StructuralScanError('unclosed_top_level_brace', len(source))
    return clean, tokens, units, directives


def extract_top_level_units(source):
    return inspect_top_level(source)[2]


def mask_library_interface_blocks(source):
    clean, tokens, units, directives = inspect_top_level(source)
    masked = [u for u in units if u['kind'] in ('library', 'interface')]
    spans = [(u['start'], u['end']) for u in masked]
    chars = list(clean)
    for start, end in spans:
        for i in range(start, end):
            if chars[i] not in '\r\n':
                chars[i] = ' '
    # Pragma/import text remains in an informative stream. It is ignored only
    # when deciding whether any non-directive code remains at all.
    excluded = spans + directives
    remainder = [t for t in tokens if t.value != ';' and
                 not any(start <= t.start < end for start, end in excluded)]
    return MaskResult(''.join(chars), units, bool(remainder), len(masked),
                      any(u['kind'] == 'contract' for u in units), len(remainder))


def lexical_stream(cleaned_source, preserve_identifiers_numbers=False):
    if preserve_identifiers_numbers:
        return ' '.join(TOKEN_RE.findall(cleaned_source))
    return normalize_scanned_text(cleaned_source)


def represent(source, masked=False, preserve_identifiers_numbers=False):
    if masked:
        result = mask_library_interface_blocks(source)
        if not result.informative:
            return None, result
        return lexical_stream(result.text, preserve_identifiers_numbers), result
    return lexical_stream(scan_comments(source).text, preserve_identifiers_numbers), None
