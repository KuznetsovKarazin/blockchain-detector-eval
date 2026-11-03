pragma solidity ^0.5.0;
contract Token {
    mapping(address => uint) public balanceOf;
    constructor() public { balanceOf[msg.sender] = 1000; }
    function transfer(address to, uint value) public {
        balanceOf[msg.sender] -= value;
        balanceOf[to] += value;
    }
}
