pragma solidity 0.8.26;
contract TransferEvent { event Paid(uint amount); function pay(address payable target,uint amount) external { target.transfer(amount); emit Paid(amount); } }