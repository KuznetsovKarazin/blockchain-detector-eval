pragma solidity ^0.5.0;
contract Bank {
    mapping(address => uint) public balances;
    function deposit() public payable { balances[msg.sender] += msg.value; }
    function withdraw() public {
        uint amount = balances[msg.sender];
        msg.sender.transfer(amount);
        balances[msg.sender] = 0;
    }
}
