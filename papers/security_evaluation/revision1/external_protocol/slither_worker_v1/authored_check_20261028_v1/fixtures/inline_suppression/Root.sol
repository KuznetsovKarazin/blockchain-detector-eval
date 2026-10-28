pragma solidity 0.8.26;
contract Suppressed { function ping(address target) external {
// slither-disable-next-line unchecked-lowlevel
target.call(""); } }