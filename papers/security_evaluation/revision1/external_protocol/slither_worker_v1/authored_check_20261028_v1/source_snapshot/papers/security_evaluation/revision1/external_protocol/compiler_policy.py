"""Strict read-only compiler planning from the historical finite release catalog.

No solc download, compilation or Slither execution occurs. Historical outside-
pragma fallback is intentionally rejected. Installed binaries are inventoried
separately and are never inferred from the candidate catalog.
"""
from __future__ import annotations
import importlib.util,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'papers/security_evaluation/normalization_audit'))
from solidity_scanner import scan_comments,SolidityScanError
spec=importlib.util.spec_from_file_location('historical_c3_compiler_policy',ROOT/'scripts/c3_slither_baseline.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
CATALOG=tuple(r for r in legacy.RELEASES if r>=legacy.FIRST_STATIC)


def mask_strings(text):
    chars=list(text);i=0
    while i<len(text):
        if text[i] not in '\"\'':i+=1;continue
        q=text[i];start=i;i+=1
        while i<len(text):
            if text[i]=='\\':i+=2
            elif text[i]==q:i+=1;break
            else:i+=1
        for j in range(start,min(i,len(text))):
            if chars[j] not in '\r\n':chars[j]=' '
    return ''.join(chars)


def strict_compile_plan(source):
    try:code=mask_strings(scan_comments(source).text)
    except SolidityScanError as e:return {'status':'scanner_error','candidates':[],'reason':str(e),'outside_pragma':False}
    specs=re.findall(r'\bpragma\s+solidity\s+([^;]+);',code)
    if not specs:return {'status':'missing_pragma','candidates':[],'outside_pragma':False}
    constraints=[]
    atom=rf'(?:\^|~|>=|<=|>|<|=)?\s*{legacy._VER}'
    for spec in specs:
        alternatives=[]
        for alt in spec.split('||'):
            hyphen=re.fullmatch(rf'\s*{legacy._VER}\s+-\s+{legacy._VER}\s*',alt)
            if not alt.strip() or (not hyphen and re.sub(atom,'',alt).strip()):
                return {'status':'unsupported_constraint','candidates':[],'pragma_specs':specs,'outside_pragma':False}
            expanded=legacy._expand(alt)
            if not expanded:return {'status':'unsupported_constraint','candidates':[],'pragma_specs':specs,'outside_pragma':False}
            alternatives.append(expanded)
        constraints.append(alternatives)
    allowed=[r for r in CATALOG if legacy.allowed(r,constraints)]
    if not allowed:return {'status':'no_compatible_catalog_release','candidates':[],'pragma_specs':specs,'outside_pragma':False}
    best={}
    for r in allowed:best[r[1]]=max(best.get(r[1],r),r)
    candidates=['.'.join(map(str,best[m])) for m in sorted(best,reverse=True)]
    return {'status':'compile_plan_ready_not_executed','candidates':candidates[:5],'pragma_specs':specs,'outside_pragma':False,
            'compiler_execution_performed':False,'catalog_not_latest_release_claim':True}
