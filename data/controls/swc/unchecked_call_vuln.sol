pragma solidity ^0.5.0;
contract Payer {
    mapping(address => uint) public owed;
    function deposit() public payable { owed[msg.sender] += msg.value; }
    function pay(address payable to) public {
        uint amount = owed[to];
        owed[to] = 0;
        to.call.value(amount)("");
    }
}
