pragma solidity 0.8.26;
contract SendIgnored { function pay(address payable target, uint amount) external { target.send(amount); } }