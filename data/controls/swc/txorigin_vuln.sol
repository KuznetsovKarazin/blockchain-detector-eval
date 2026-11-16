pragma solidity ^0.5.0;
contract Wallet {
    address public owner;
    constructor() public { owner = msg.sender; }
    function () external payable {}
    function sendTo(address payable to, uint amount) public {
        require(tx.origin == owner);
        to.transfer(amount);
    }
}
