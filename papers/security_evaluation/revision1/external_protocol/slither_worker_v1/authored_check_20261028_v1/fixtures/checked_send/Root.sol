pragma solidity 0.8.26;
contract SendChecked { function pay(address payable target, uint amount) external { require(target.send(amount)); } }