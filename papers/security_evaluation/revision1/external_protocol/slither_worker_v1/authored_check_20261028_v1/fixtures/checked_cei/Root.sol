pragma solidity 0.8.26;
contract SafeOrder { mapping(address=>uint) public balances;
function withdraw() public { uint amount=balances[msg.sender]; balances[msg.sender]=0;
(bool ok,)=msg.sender.call{value:amount}(""); require(ok); } }