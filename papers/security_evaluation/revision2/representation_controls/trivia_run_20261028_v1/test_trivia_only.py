import pytest
from trivia_only import canonical_bytes,canonical_tokens,SolidityScanError
@pytest.mark.parametrize('left,right',[
 ('contract A { uint a=1; }','/* SPDX-License-Identifier: MIT */\ncontract\tA{uint a = 1 ;}//tail'),
 ('a/* comment */+b','a + b'),('a//line\n+b','a+b'),
 ('hex"aa" + unicode"hello"','hex"aa"\n+\tunicode"hello"'),
])
def test_trivia_equal(left,right):assert canonical_bytes(left)==canonical_bytes(right)
@pytest.mark.parametrize('left,right',[
 ('a b','ab'),('a + + b','a++b'),('x => y','x = > y'),
 ('1e+2','1 e + 2'),('"a b"','"ab"'),('"a//b"','"a/b"'),
 ('"a/*b*/"','"a"'),('"x"',"'x'"),('a=1','a=2'),('a=1','b=1'),
 ('hex"aa"','hex "aa"'),('unicode"a"','unicode "a"'),
 ('a**b','a* *b'),('x:=y','x: =y'),('a+b','a-b'),
 ('x=0x01','x=1'),('"a\\\"b"','"ab"'),
])
def test_nontrivia_changes_retained(left,right):assert canonical_bytes(left)!=canonical_bytes(right)
@pytest.mark.parametrize('source',['"unterminated','/* unterminated'])
def test_error_no_fallback(source):
 with pytest.raises(SolidityScanError):canonical_tokens(source)
