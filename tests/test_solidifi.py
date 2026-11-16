"""SolidiFI decomposition: template search on a synthetic injected contract."""

from bal.data import solidifi

BASE = """pragma solidity ^0.5.0;
contract Token {
    uint public total = 100;
    function f() public { total = 1; }
}
"""
SNIP_A = """function bug_tmstmp21() view public returns (bool) {
    return block.timestamp >= 1546300800; }
"""
SNIP_B = """function bug_tmstmp33(uint x) public { uint256 pastBlockTime_tmstmp33 = now; // keep
    require(now != pastBlockTime_tmstmp33); }
"""


def _cat():
    return {"Timestamp-Dependency":
            {tuple(t for t, _, _ in solidifi.template_tokens(s)): f"Timestamp-Dependency/T0{i}"
             for i, s in enumerate((SNIP_A, SNIP_B), 1)}}


def test_tokens_normalise_numbers_suffixes_and_comments():
    a = [t for t, _, _ in solidifi.template_tokens("uint x_tmstmp21 = 15; // c 7\n")]
    b = [t for t, _, _ in solidifi.template_tokens("uint x_tmstmp4 = 99; /* other */\n")]
    assert a == b == ["uint", "x_tmstmp#", "=", "N", ";"]


def test_locate_finds_renumbered_copies_and_removal_restores_base():
    other_a = SNIP_A.replace("21", "7").replace("1546300800", "1")
    lines = BASE.splitlines(keepends=True)
    src = "".join(lines[:2]) + SNIP_A + other_a + "".join(lines[2:4]) + SNIP_B + "".join(lines[4:])
    found = solidifi.locate(src, _cat()["Timestamp-Dependency"])
    assert [s.template for s in found] == ["Timestamp-Dependency/T01"] * 2 + ["Timestamp-Dependency/T02"]
    assert found[0].line_start == 3 and found[0].line_end == 4
    rest = src
    for s in reversed(found):
        rest = rest[:s.char_start] + rest[s.char_end:]
    assert [t for t, _, _ in solidifi.template_tokens(rest)] == [t for t, _, _ in solidifi.template_tokens(BASE)]


def test_only_keeps_the_selected_template():
    src = BASE.replace("}\n}\n", "}\n" + SNIP_A + SNIP_B + "}\n")
    f = solidifi.BuggyFile("Timestamp-Dependency", 1, None, src,
                           solidifi.locate(src, _cat()["Timestamp-Dependency"]))
    kept = f.only({"Timestamp-Dependency/T02"})
    assert "now" in kept and "1546300800" not in kept
    assert f.injected_lines({"Timestamp-Dependency/T01"}) == {5, 6}
