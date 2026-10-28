pragma solidity 0.8.26;
abstract contract AbstractOnly { function read() public virtual returns(uint); function value() public pure returns(uint){return 1;} }