pragma solidity ^0.5.0;
contract Lottery {
    address payable public owner;
    constructor() public { owner = msg.sender; }
    function play() public payable {
        require(msg.value == 1 ether);
    }
    function close() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}
