pragma solidity 0.8.26;
contract Unchecked { function callIt(address target, bytes calldata data) external { target.call(data); } }