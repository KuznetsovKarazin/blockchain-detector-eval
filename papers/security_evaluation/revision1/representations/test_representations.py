"""Structural lexical extraction fidelity and similarity-definition tests."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from structural_lexical import (extract_top_level_units, mask_library_interface_blocks,
                                StructuralScanError, SolidityScanError, represent)


def test_comments_and_literals_cannot_create_library_units_or_brace_edges():
    src = '/* library Fake { } */ contract A { string x="interface Nope { } //"; }'
    units = extract_top_level_units(src)
    assert [(u['kind'],u['name']) for u in units] == [('contract','A')]


def test_library_and_interface_blocks_masked_but_application_contract_preserved():
    src = 'pragma solidity ^0.8.0; library L { function f() internal {} } interface I { function f() external; } contract A is I { function f() public {} }'
    result = mask_library_interface_blocks(src)
    assert result.removed_unit_count == 2 and result.informative and result.has_top_level_contract
    assert 'library L' not in result.text and 'interface I' not in result.text
    assert 'contract A is I' in result.text


def test_escaped_quote_and_quoted_braces_do_not_close_declaration():
    src = r'''library L { string x="escaped\"} contract Fake {"; } contract Real {}'''
    assert [u['name'] for u in extract_top_level_units(src)] == ['L','Real']


def test_abstract_contract_and_inheritance_arguments_are_retained():
    src = 'abstract contract A is B(123), C { function f() external virtual; }'
    result = mask_library_interface_blocks(src)
    assert result.informative and result.removed_unit_count == 0
    assert result.units[0]['name'] == 'A'


def test_pure_library_and_interface_have_no_informative_representation():
    src = 'pragma solidity >=0.5.0; import {A as B} from "a.sol"; library L {} interface I {}'
    stream,result = represent(src, masked=True)
    assert stream is None and not result.informative and result.removed_unit_count == 2


def test_free_function_residue_is_retained_without_claiming_contract_ast():
    src = 'library L {} function f(uint x) pure returns(uint) { return x+1; }'
    stream,result = represent(src, masked=True)
    assert stream is not None and result.informative and not result.has_top_level_contract


def test_mask_preserves_newline_positions():
    src = 'library L {\n function f() internal {\n }\n}\ncontract A {}'
    result = mask_library_interface_blocks(src)
    assert len(result.text) == len(src)
    assert [i for i,c in enumerate(src) if c=='\n'] == [i for i,c in enumerate(result.text) if c=='\n']


@pytest.mark.parametrize('src', ['library L {', 'contract A {} }', 'contract { }', 'interface A;', 'import "x.sol"'])
def test_malformed_structural_input_is_explicit(src):
    with pytest.raises((StructuralScanError, SolidityScanError)):
        mask_library_interface_blocks(src)


def test_identifier_and_numeric_sensitivity_is_isolated():
    a='contract Alpha { uint x=123; }';b='contract Beta { uint y=456; }'
    assert represent(a)[0] == represent(b)[0]
    assert represent(a,preserve_identifiers_numbers=True)[0] != represent(b,preserve_identifiers_numbers=True)[0]


def test_empty_and_directive_only_do_not_produce_shared_empty_clone_stream():
    assert represent('',masked=True)[0] is None
    assert represent('pragma solidity ^0.8.0;',masked=True)[0] is None


def test_segmented_windows_cannot_cross_deleted_declaration_boundary():
    from run_segmented_control import segment_shingles
    assert segment_shingles(['a b c','d e f']) == set()
    assert segment_shingles(['a b c d e','f g']) == {('a','b','c','d','e')}


def test_segmented_control_does_not_invent_short_segment_shingles():
    from run_segmented_control import segment_shingles
    assert segment_shingles(['a b','c d e f']) == set()
    assert segment_shingles(['a b']) == {('a','b')}
    assert segment_shingles(['a','b']) == set()


def test_segmented_shingles_are_subset_of_concatenated_windows():
    from run_segmented_control import segment_shingles
    segments=['a b c d e f','g h i j k','l m']
    tokens=' '.join(segments).split()
    complete={tuple(tokens[i:i+5]) for i in range(len(tokens)-4)}
    assert segment_shingles(segments) < complete


def test_segment_extraction_reproduces_existing_mask_token_sequence():
    from run_segmented_control import retained_segments
    source='contract A { uint a=1; } library L { uint b; } contract C { uint c=2; }'
    for preserve in [False,True]:
        old,_=represent(source,masked=True,preserve_identifiers_numbers=preserve)
        assert ' '.join(s for s in retained_segments(source,preserve) if s) == old
