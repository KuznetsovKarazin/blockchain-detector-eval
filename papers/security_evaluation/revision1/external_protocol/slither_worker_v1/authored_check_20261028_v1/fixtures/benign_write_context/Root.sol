pragma solidity 0.8.26;
contract BlindWrite { uint public n; function callIt(address target) external { (bool ok,)=target.call(""); require(ok); n=7; } }