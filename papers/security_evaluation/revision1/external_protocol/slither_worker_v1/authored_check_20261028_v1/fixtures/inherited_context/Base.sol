pragma solidity 0.8.26;
contract UnsafeBank {
 mapping(address=>uint) public balances;
 function withdraw() public { uint amount=balances[msg.sender];
 (bool ok,) = msg.sender.call{value:amount}(""); require(ok); balances[msg.sender]=0; }
 receive() external payable { balances[msg.sender]+=msg.value; }
}
