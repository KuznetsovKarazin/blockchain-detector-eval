pragma solidity >=0.4.0 <0.9.0;
contract Smoke {
 uint private x;
 function set(uint a) public { x = a; }
 function get() public view returns (uint) { return x; }
}
