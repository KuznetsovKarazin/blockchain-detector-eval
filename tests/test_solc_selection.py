"""Compiler choice for the Slither baseline must respect the whole pragma range."""

import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "scripts" / "c3_slither_baseline.py"
_spec = importlib.util.spec_from_file_location("c3", _p)
c3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c3)


def test_range_pragma_tries_newest_allowed_minor_first():
    assert c3.solc_candidates("pragma solidity >=0.4.22 <0.6.0;") == (["0.5.17", "0.4.26"], False)


def test_caret_and_exact():
    assert c3.solc_candidates("pragma solidity ^0.4.19;") == (["0.4.26"], False)
    assert c3.solc_candidates("pragma solidity 0.4.24;") == (["0.4.24"], False)
    assert c3.solc_candidates("pragma solidity >0.4.99 <0.6.0;") == (["0.5.17"], False)


def test_old_exact_pragma_is_flagged_outside():
    cands, outside = c3.solc_candidates("pragma solidity 0.4.2;")
    assert outside and cands == ["0.4.11"]


def test_or_ranges_and_unknown_newer_releases():
    assert c3.solc_candidates("pragma solidity ^0.4.24 || ^0.5.0;") == (["0.5.17", "0.4.26"], False)
    assert c3.solc_candidates("pragma solidity ^0.8.28;") == ([], False)
    assert c3.run_slither("x.sol", [])["status"] == "unsupported_pragma"


def test_compile_failure_is_told_from_tool_crash():
    assert c3._is_compile_failure("a.sol:417:14: Error: Unbalanced stack at the end of a block")
    assert not c3._is_compile_failure("AssertionError\n    assert isinstance(right, TupleVariable)")
