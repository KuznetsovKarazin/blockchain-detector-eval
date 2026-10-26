"""Compiler planning only: strict pragmas, strings/comments and no fallback."""
import importlib.util,sys
from pathlib import Path
BASE=Path(__file__).parent;sys.path.insert(0,str(BASE));import compiler_policy as m

def test_range_intersection_and_descending_minor_order():
    p=m.strict_compile_plan('pragma solidity >=0.4.22 <0.6.0; contract C{}')
    assert p['candidates']==['0.5.17','0.4.26'] and not p['outside_pragma']

def test_string_pragma_and_line_comment_block_marker_ignored():
    p=m.strict_compile_plan('// /* comment\npragma solidity ^0.5.0; string s="pragma solidity ^0.8.0;"; // */')
    assert p['candidates']==['0.5.17']

def test_outside_pragma_fallback_never_used():
    p=m.strict_compile_plan('pragma solidity <0.4.11;')
    assert p['candidates']==[] and p['status']=='no_compatible_catalog_release' and not p['outside_pragma']

def test_missing_and_invalid_pragma_fail_closed():
    assert m.strict_compile_plan('contract C{}')['status']=='missing_pragma'
    assert m.strict_compile_plan('pragma solidity >=0.4.22 banana;')['status']=='unsupported_constraint'

def test_incompatible_multiple_pragmas_fail_closed():
    assert m.strict_compile_plan('pragma solidity ^0.4.20; pragma solidity >=0.5.0;')['candidates']==[]

def test_or_alternatives_allow_only_fixed_catalog():
    p=m.strict_compile_plan('pragma solidity ^0.4.20 || ^0.5.0;')
    assert p['candidates']==['0.5.17','0.4.26']
