pragma solidity 0.8.26;
// Авторский пример: café
contract Utf8Context {
string public text = unicode"проба";
function ping(address target) external { target.call(""); }
}
