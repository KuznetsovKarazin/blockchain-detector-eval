pragma solidity 0.8.26;
interface Hook { function ping() external; }
contract Counter { mapping(address=>uint) public credits; function update() public {
 uint old=credits[msg.sender]; Hook(msg.sender).ping(); credits[msg.sender]=old+1; } }