pragma solidity ^0.5.0;
contract Vault {
    address payable public owner;
    constructor() public payable { owner = msg.sender; }
    function () external payable {}
    function withdrawAll(address payable to) public {
        to.transfer(address(this).balance);
    }
}
