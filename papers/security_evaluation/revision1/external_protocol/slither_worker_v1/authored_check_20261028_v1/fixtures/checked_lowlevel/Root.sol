pragma solidity 0.8.26;
contract Checked { function callIt(address target, bytes calldata data) external { (bool ok,)=target.call(data); require(ok); } }