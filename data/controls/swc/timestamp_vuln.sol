pragma solidity ^0.5.0;
contract Lottery {
    function play() public payable {
        require(msg.value == 1 ether);
        if (block.timestamp % 15 == 0) {
            msg.sender.transfer(address(this).balance);
        }
    }
}
