"""Strict lexical import closure over a declared pinned snapshot namespace.

No basename search, suffix search, npm inference, filesystem/network rescue or
source edits. This is an explicit preflight policy, not a recovered build system.
"""
from pathlib import Path,PurePosixPath
import hashlib
import posixpath
import re
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT/'papers/security_evaluation/normalization_audit'))
from solidity_scanner import scan_comments,SolidityScanError


class ImportFailure(ValueError):
    def __init__(self,status,detail):
        self.status,self.detail=status,detail
        super().__init__(status+': '+detail)


def tokens(source):
    text=scan_comments(source).text;out=[];i=0
    while i<len(text):
        c=text[i]
        if c.isspace():i+=1;continue
        if c in '\"\'':
            quote=c;j=i+1
            while j<len(text):
                if text[j]=='\\':j+=2
                elif text[j]==quote:break
                else:j+=1
            if j>=len(text):raise ImportFailure('import_scan_error','unterminated literal')
            out.append(('string',text[i+1:j]));i=j+1
        elif c.isascii() and (c.isalpha() or c in '_$'):
            j=i+1
            while j<len(text) and text[j].isascii() and (text[j].isalnum() or text[j] in '_$'):j+=1
            out.append(('id',text[i:j]));i=j
        else:out.append(('punct',c));i+=1
    return out


def import_paths(source):
    """Parse the supported complete Solidity import declaration forms."""
    stream=tokens(source);paths=[];i=0
    while i<len(stream):
        if stream[i]!=('id','import'):i+=1;continue
        # Recognize all import keywords outside literals, including malformed
        # nesting: unsupported syntax fails closed instead of hiding an import.
        j=i+1
        while j<len(stream) and stream[j]!=('punct',';'):j+=1
        if j==len(stream):raise ImportFailure('import_syntax_unresolved','unterminated import declaration')
        body=stream[i+1:j];literal=[x for x in body if x[0]=='string']
        if len(literal)!=1:raise ImportFailure('import_syntax_unresolved','import requires one quoted path')
        valid=False
        if body and body[0][0]=='string':
            valid=len(body)==1 or (len(body)==3 and body[1]==('id','as') and body[2][0]=='id')
        elif len(body)==5 and body[:2]==[('punct','*'),('id','as')]:
            valid=body[2][0]=='id' and body[3]==('id','from') and body[4][0]=='string'
        elif len(body)>=5 and body[0]==('punct','{') and body[-3:][0:2]==[('punct','}'),('id','from')] and body[-1][0]=='string':
            middle=body[1:-3];k=0;valid=bool(middle)
            while valid and k<len(middle):
                if middle[k][0]!='id':valid=False;break
                k+=1
                if k<len(middle) and middle[k]==('id','as'):
                    k+=1
                    if k>=len(middle) or middle[k][0]!='id':valid=False;break
                    k+=1
                if k<len(middle):
                    if middle[k]!=('punct',','):valid=False;break
                    k+=1
                    if k==len(middle):valid=False
        if not valid:raise ImportFailure('import_syntax_unresolved','unsupported import declaration')
        path=literal[0][1]
        if not path or '\\' in path or any(ord(c)<32 for c in path):
            raise ImportFailure('import_literal_unsupported','empty, escaped or control-character import path')
        if path.startswith('/') or ':' in path:
            raise ImportFailure('remote_or_absolute_import_forbidden',path)
        paths.append(path);i=j+1
    return paths


def source_unit_target(importer,path):
    if path.startswith(('./','../')):target=posixpath.normpath(posixpath.join(posixpath.dirname(importer),path))
    else:
        # Direct imports are opaque names in Solidity VFS. Require canonical
        # path spelling so physical normalization cannot silently change names.
        if posixpath.normpath(path)!=path:raise ImportFailure('direct_import_noncanonical',path)
        target=path
    if target in ('','.','..') or target.startswith('../') or target.startswith('/'):
        raise ImportFailure('import_outside_snapshot',path)
    if not target.endswith('.sol'):raise ImportFailure('import_extension_unsupported',path)
    return target


def check_local_source(path,root,expected):
    path=Path(path);root=Path(root)
    if path.is_symlink() or path.resolve()!=path.absolute():
        raise ImportFailure('source_symlink_forbidden',str(path))
    if not path.is_relative_to(root):raise ImportFailure('import_outside_snapshot',str(path))
    if not path.is_file():raise ImportFailure('missing_import',str(path.relative_to(root)))
    data=path.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual!=expected:raise ImportFailure('source_hash_changed',str(path.relative_to(root)))
    try:return data.decode('utf-8'),len(data)
    except UnicodeDecodeError as exc:raise ImportFailure('source_decode_error',str(path.relative_to(root))) from exc


def closure(root,entry,pinned,external=False,max_sources=128,max_bytes=8*1024*1024,cache=None):
    """pinned maps exact context-relative unit names to expected raw hashes."""
    root=Path(root).absolute();pending=[entry];done={};links=[];total=0
    cache={} if cache is None else cache
    while pending:
        unit=pending.pop(0)
        if unit in done:continue
        if unit not in pinned:raise ImportFailure('missing_import',unit)
        value=pinned[unit]
        if isinstance(value,list):
            if len(value)!=1:raise ImportFailure('ambiguous_pinned_import',unit)
            value=value[0]
        key=(str(root/unit),value)
        if key not in cache:
            source,size=check_local_source(root/unit,root,value)
            cache[key]=(size,import_paths(source))
        size,imports=cache[key]
        done[unit]={'unit':unit,'sha256':value,'bytes':size};total+=size
        if len(done)>max_sources or total>max_bytes:raise ImportFailure('import_closure_limit',unit)
        for imported in imports:
            target=source_unit_target(unit,imported)
            if external and target!=entry:
                raise ImportFailure('external_import_context_unestablished',imported)
            if target not in pinned:
                raise ImportFailure('missing_import',target)
            links.append({'importer':unit,'import_path':imported,'target':target})
            if target not in done and target not in pending:pending.append(target)
    return {'source_units':[done[k] for k in sorted(done)],'import_edges':links,'source_bytes':total}
