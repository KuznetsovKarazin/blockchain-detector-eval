pragma solidity 0.8.26;
contract ReturnEvent { event Attempt(bool ok); function ping(address target) external { (bool ok,)=target.call(""); emit Attempt(ok); } }