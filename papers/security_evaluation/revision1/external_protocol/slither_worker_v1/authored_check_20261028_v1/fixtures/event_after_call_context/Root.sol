pragma solidity 0.8.26;
contract CallEvent { event Paid(uint amount); function pay(address target,uint amount) external { (bool ok,)=target.call(""); require(ok); emit Paid(amount); } }