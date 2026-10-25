"""Scientific fidelity checks for the isolated comment-scanner sensitivity."""
import importlib.util
from pathlib import Path
import sys

import pytest

PATH = Path(__file__).resolve().parents[1] / "papers/security_evaluation/normalization_audit/solidity_scanner.py"
spec = importlib.util.spec_from_file_location("security_solidity_scanner", PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
from bal.features.contract_features import normalised_text


def test_url_and_following_statement_are_preserved():
    source = 'string x = "https://example.org/a"; transfer(1); // actual comment\n'
    out = m.scan_comments(source)
    assert '"https://example.org/a"; transfer(1);' in out.text
    assert 'actual comment' not in out.text
    assert out.string_literals == 1 and out.line_comments == 1
    assert len(out.literal_comment_markers) == 1
    assert m.corrected_normalised_text(source) != normalised_text(source)


def test_escaped_quote_does_not_end_literal():
    source = r'''string x = "a\"//still literal"; uint y = 2;'''
    assert m.scan_comments(source).text == source
    assert m.scan_comments(source).string_literals == 1


def test_even_backslashes_allow_closing_quote():
    source = r'''string x = "a\\"; // real comment'''
    out = m.scan_comments(source)
    assert out.line_comments == 1 and 'real comment' not in out.text
    assert out.string_literals == 1


def test_literal_block_markers_and_real_block_are_distinct():
    source = 'string x="/* keep */"; /* remove\nremove */ uint y;'
    out = m.scan_comments(source)
    assert '"/* keep */"' in out.text and 'remove' not in out.text
    assert out.block_comments == 1 and out.string_literals == 1
    assert [i for i,c in enumerate(source) if c == '\n'] == [i for i,c in enumerate(out.text) if c == '\n']


def test_unicode_hex_and_adjacent_literals_are_preserved():
    source = '''string x = unicode"Привет // текст"; bytes y = hex"ab00ff"; string z = 'a' "b";'''
    out = m.scan_comments(source)
    assert out.text == source and out.string_literals == 4


def test_multiline_literal_is_preserved_without_claiming_compiler_validity():
    source = 'string x="line1\n//still string\nline3";\n// remove\n'
    out = m.scan_comments(source)
    assert out.multiline_string_literals == 1
    assert '//still string' in out.text and '// remove' not in out.text
    assert len(out.text) == len(source)


def test_crlf_and_line_comment_at_eof():
    source = 'uint x; // first\r\n/* second\r\nline */uint y;// eof'
    out = m.scan_comments(source)
    assert len(out.text) == len(source)
    assert [i for i,c in enumerate(source) if c in '\r\n'] == [i for i,c in enumerate(out.text) if c in '\r\n']
    assert out.line_comments == 2 and out.block_comments == 1


@pytest.mark.parametrize('source,code', [
    ('string x="unfinished', 'unterminated_string'),
    ("string x='unfinished", 'unterminated_string'),
    ('string x="unfinished\\', 'unterminated_string'),
    ('uint x; /* unfinished', 'unterminated_block_comment'),
])
def test_unterminated_source_is_explicit_error(source, code):
    with pytest.raises(m.SolidityScanError) as exc:
        m.scan_comments(source)
    assert exc.value.code == code and exc.value.line >= 1 and exc.value.column >= 1


def test_quotes_inside_comment_do_not_start_literals():
    source = '/* " unfinished quote */ uint x; // another "\nuint y;'
    out = m.scan_comments(source)
    assert out.string_literals == 0 and 'uint y;' in out.text


def test_ordinary_code_and_literals_keep_historical_tokenization():
    source = 'pragma solidity ^0.8.0; // hi\ncontract A { string x="hello"; /* bye */ uint y=1/2; }'
    assert m.corrected_normalised_text(source) == normalised_text(source)


def test_comment_boundary_does_not_join_identifiers():
    assert m.corrected_normalised_text('abc/* gap */def') == 'ID ID'


def test_empty_source_and_division_are_accepted():
    assert m.corrected_normalised_text('') == ''
    source = 'uint x = a / b; x /= 2;'
    assert m.scan_comments(source).text == source


def test_block_opener_inside_line_comment_does_not_delete_later_code():
    source = '// /* documentary marker\nuint retained = 1; /* actual block */ uint last = 2;'
    out = m.scan_comments(source)
    assert 'uint retained = 1;' in out.text
    assert out.line_comments == 1 and out.block_comments == 1
    assert m.corrected_normalised_text(source) != normalised_text(source)


def test_overlapping_line_and_block_markers_do_not_leave_slash_artifacts():
    source = '//** comment **/\ncontract A {}'
    assert m.corrected_normalised_text(source) == 'contract ID { }'
    assert m.corrected_normalised_text(source) != normalised_text(source)
