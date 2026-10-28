pragma solidity 0.8.26;
contract StoredReturn { bool public lastSuccess; function sendCall(address target) external { (lastSuccess,)=target.call(""); } }