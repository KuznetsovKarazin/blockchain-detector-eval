"""Authored cases fixed before execution; expectations are tooling hypotheses.

No case is an expert-adjudicated vulnerability label. No semantic mapping is
changed based on these checks; observed mismatches are reported honestly.
"""


def cases():
    pragma = "pragma solidity 0.8.26;\n"
    def simple(name, body, expected, note=""):
        return {"id": name, "entry": "Root.sol", "sources": {"Root.sol": pragma + body},
                "expected_execution": expected, "semantic_note": note or "Authored tool-behavior fixture, not expert truth"}
    bank = """contract UnsafeBank {
 mapping(address=>uint) public balances;
 function withdraw() public { uint amount=balances[msg.sender];
 (bool ok,) = msg.sender.call{value:amount}(""); require(ok); balances[msg.sender]=0; }
 receive() external payable { balances[msg.sender]+=msg.value; }
}
"""
    out = [
      simple("reentrant_eth", bank, "analysis_complete", "Callback before clearing balance; expected primary alert is a tool hypothesis"),
      simple("reentrant_no_eth", """interface Hook { function ping() external; }
contract Counter { mapping(address=>uint) public credits; function update() public {
 uint old=credits[msg.sender]; Hook(msg.sender).ping(); credits[msg.sender]=old+1; } }""", "analysis_complete"),
      simple("checked_cei", """contract SafeOrder { mapping(address=>uint) public balances;
function withdraw() public { uint amount=balances[msg.sender]; balances[msg.sender]=0;
(bool ok,)=msg.sender.call{value:amount}(""); require(ok); } }""", "analysis_complete", "No selected alert does not prove security"),
      simple("unchecked_lowlevel", "contract Unchecked { function callIt(address target, bytes calldata data) external { target.call(data); } }", "analysis_complete"),
      simple("checked_lowlevel", "contract Checked { function callIt(address target, bytes calldata data) external { (bool ok,)=target.call(data); require(ok); } }", "analysis_complete"),
      simple("unchecked_send", "contract SendIgnored { function pay(address payable target, uint amount) external { target.send(amount); } }", "analysis_complete"),
      simple("checked_send", "contract SendChecked { function pay(address payable target, uint amount) external { require(target.send(amount)); } }", "analysis_complete"),
      simple("stored_return_context", "contract StoredReturn { bool public lastSuccess; function sendCall(address target) external { (lastSuccess,)=target.call(\"\"); } }", "analysis_complete", "Stored return may evade unused-return alert; storage is not proof of appropriate failure handling"),
      simple("event_after_transfer_context", "contract TransferEvent { event Paid(uint amount); function pay(address payable target,uint amount) external { target.transfer(amount); emit Paid(amount); } }", "analysis_complete", "Informational send/transfer detector retained; adverse-outcome semantics unresolved"),
      simple("event_after_call_context", "contract CallEvent { event Paid(uint amount); function pay(address target,uint amount) external { (bool ok,)=target.call(\"\"); require(ok); emit Paid(amount); } }", "analysis_complete", "Event-only reentrancy interpretation requires human sign-off"),
      simple("benign_write_context", "contract BlindWrite { uint public n; function callIt(address target) external { (bool ok,)=target.call(\"\"); require(ok); n=7; } }", "analysis_complete", "Benign detector name is not an expert harm classification"),
      {"id": "imported_call_context", "entry": "Root.sol", "sources": {"Base.sol": pragma + bank,
        "Root.sol": pragma + 'import "./Base.sol"; contract Caller { function callIt(UnsafeBank b) external { b.withdraw(); } }'},
       "expected_execution": "analysis_complete", "semantic_note": "Root may call an import-defined vulnerable function; import-only alert is not root-safe evidence"},
      {"id": "inherited_context", "entry": "Root.sol", "sources": {"Base.sol": pragma + bank,
        "Root.sol": pragma + 'import "./Base.sol"; contract DerivedBank is UnsafeBank {}'},
       "expected_execution": "analysis_complete", "semantic_note": "Inherited function source remains imported; attribution deliberately does not infer root deployment harm"},
      {"id": "mixed_root_import", "entry": "Root.sol", "sources": {"Base.sol": pragma + bank,
        "Root.sol": pragma + 'import "./Base.sol"; ' + bank.replace("UnsafeBank", "RootBank")},
       "expected_execution": "analysis_complete", "semantic_note": "Root and import contexts both retained; no union across arbitrary imported files"},
      simple("interface_only", "interface InterfaceOnly { function read() external returns(uint); }", "analysis_or_explicit_schema_failure", "Missing runtime bytecode/sourceMap must fail explicitly; never fabricate fields"),
      simple("abstract_only", "abstract contract AbstractOnly { function read() public virtual returns(uint); function value() public pure returns(uint){return 1;} }", "analysis_or_explicit_schema_failure"),
      {"id": "historical_0419", "entry": "Root.sol", "sources": {"Root.sol": 'pragma solidity 0.4.19; contract Historical { function ping(address target) public { target.call(); } }'},
       "expected_execution": "analysis_complete", "semantic_note": "Historical AST/source-map smoke; no old-baseline equivalence claim"},
      {"id": "unsupported_pragma", "entry": "Root.sol", "sources": {"Root.sol": "pragma solidity ^9.0.0; contract Future {}"}, "expected_execution": "unavailable_no_analysis", "semantic_note": "No outside-pragma fallback"},
      simple("missing_import", 'import "./Missing.sol"; contract MissingContext {}', "unavailable_no_analysis"),
      simple("syntax_failure", "contract Broken { function f( }", "compiler_failure_no_analysis"),
      simple("inline_suppression", """contract Suppressed { function ping(address target) external {
// slither-disable-next-line unchecked-lowlevel
target.call(""); } }""", "analysis_complete", "show_ignored_findings is fixed true, no source-annotation-based suppression"),
      simple("consumed_return_context", "contract ReturnEvent { event Attempt(bool ok); function ping(address target) external { (bool ok,)=target.call(\"\"); emit Attempt(ok); } }", "analysis_complete", "Consumption may silence detector without reverting/handling adverse outcome"),
      {"id": "missing_pragma", "entry": "Root.sol", "sources": {"Root.sol": "contract NoPragma {}"}, "expected_execution": "unavailable_no_analysis", "semantic_note": "No guessed compiler"},
      {"id": "ordered_candidates", "entry": "Root.sol", "sources": {"Root.sol": "pragma solidity >=0.7.0 <0.9.0; contract Ordered { function f() external pure returns(uint){return 1;} }"},
       "expected_execution": "analysis_complete", "semantic_note": "First successful compiler wins; detector outcome never selects another compiler"},
      {"id": "crlf_utf8_offsets", "entry": "Root.sol", "sources": {"Root.sol": (
        "pragma solidity 0.8.26;\n// Авторский пример: café\ncontract Utf8Context {\n"
        'string public text = unicode"проба";\nfunction ping(address target) external { target.call(""); }\n}\n').replace("\n", "\r\n")},
       "expected_execution": "analysis_complete", "semantic_note": "Compiler and Slither must share exact UTF-8 bytes and CRLF line endings for source offsets"},
    ]
    expected = {
        "reentrant_eth": (1, 0), "reentrant_no_eth": (1, 0), "checked_cei": (0, 0),
        "unchecked_lowlevel": (0, 1), "checked_lowlevel": (0, 0), "unchecked_send": (0, 1),
        "checked_send": (0, 0), "imported_call_context": (0, 0), "inherited_context": (0, 0),
        "mixed_root_import": (1, 0), "historical_0419": (0, 1), "inline_suppression": (0, 1),
        "ordered_candidates": (0, 0), "crlf_utf8_offsets": (0, 1),
    }
    required = {"reentrant_eth": "reentrancy-eth", "reentrant_no_eth": "reentrancy-no-eth",
        "unchecked_lowlevel": "unchecked-lowlevel", "unchecked_send": "unchecked-send",
        "historical_0419": "unchecked-lowlevel", "inline_suppression": "unchecked-lowlevel",
        "crlf_utf8_offsets": "unchecked-lowlevel", "mixed_root_import": "reentrancy-eth"}
    for case in out:
        case["expectations_scope"] = "predeclared_software_regression_not_human_reference_labels"
        if case["id"] in expected:
            reentrancy, unchecked = expected[case["id"]]
            case["expected_primary_scores"] = {"reentrancy": reentrancy, "unchecked": unchecked}
        if case["id"] in required:
            case["required_root_detectors"] = [required[case["id"]]]
        if case["id"] in ("imported_call_context", "inherited_context", "mixed_root_import"):
            case["required_import_detectors"] = ["reentrancy-eth"]
    return out
