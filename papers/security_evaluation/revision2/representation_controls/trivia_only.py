"""Lexical equality retaining token spellings; discard comments and whitespace.

This is an equality-control scanner, not a compiler or semantic comparator.
"""
from pathlib import Path
import re,sys,json
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'papers/security_evaluation/normalization_audit'))
from solidity_scanner import scan_comments,SolidityScanError
OPS=tuple(sorted(('>>>=','<<=','>>=','**','++','--','&&','||','==','!=','<=','>=','<<','>>>','>>','+=','-=','*=','/=','%=','|=','&=','^=','=>',':='),key=lambda s:(-len(s),s)))
ID=re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*')
NUMBER=re.compile(r'0[xX][0-9A-Fa-f_]+|(?:[0-9][0-9_]*(?:\.[0-9_]*)?|\.[0-9][0-9_]*)(?:[eE][+-]?[0-9_]+)?')
def canonical_tokens(source):
 text=scan_comments(source).text;result=[];i=0;n=len(text)
 while i<n:
  if text[i].isspace():i+=1;continue
  start=i;prefix=next((p for p in ('unicode','hex') if text.startswith(p,i) and i+len(p)<n and text[i+len(p)] in '\"\''),None)
  if prefix:i+=len(prefix)
  if text[i] in '\"\'':
   quote=text[i];i+=1
   while i<n:
    if text[i]=='\\':i+=2
    elif text[i]==quote:i+=1;break
    else:i+=1
   result.append(text[start:i]);continue
  m=NUMBER.match(text,i) or ID.match(text,i)
  if m:result.append(m.group());i=m.end();continue
  op=next((op for op in OPS if text.startswith(op,i)),None)
  if op:result.append(op);i+=len(op)
  else:result.append(text[i]);i+=1
 return result

def canonical_bytes(source):
 return json.dumps(canonical_tokens(source),ensure_ascii=True,separators=(',',':')).encode()
