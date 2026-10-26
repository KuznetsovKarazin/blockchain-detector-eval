"""Independent compiler harness checks: fictional files/processes only.

No Solidity compiler, Slither, real corpus file or annotation is executed/read.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import pytest

BASE=Path(__file__).parents[1]/'external_protocol/compiler_preflight_v1'
sys.path.insert(0,str(BASE))
spec=importlib.util.spec_from_file_location('independent_compiler_runner',BASE/'runner.py')
r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)
import imports as imp


def pin(root, files):
    hashes={}
    for name,text in files.items():
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
        hashes[name]=hashlib.sha256(target.read_bytes()).hexdigest()
    return hashes


def output(ast=None, contracts=None):
    data={'sources':{'main.sol':{'ast':{'nodeType':'SourceUnit','nodes':[]} if ast is None else ast}},
          'contracts':{} if contracts is None else contracts}
    return dict(process_status='completed',returncode=0,stdout=json.dumps(data).encode(),stderr=b'')


def definition(name='C',kind='contract',abstract=False):
    return dict(nodeType='ContractDefinition',name=name,contractKind=kind,abstract=abstract)


def test_import_lexer_ignores_quoted_and_commented_pseudo_imports():
    src='''// import "hidden.sol";
    contract C { string s="import \\"fake.sol\\";"; }
    /* import "other.sol"; */ import {A as B, C} from "./real.sol";
    import * as D from "direct/second.sol";'''
    assert imp.import_paths(src)==['./real.sol','direct/second.sol']


def test_relative_closure_matches_exact_pinned_namespace(tmp_path):
    pins=pin(tmp_path,{'contracts/Main.sol':'import "../lib/A.sol"; contract Main {}',
                       'lib/A.sol':'import "./B.sol"; contract A {}',
                       'lib/B.sol':'contract B {}'})
    result=imp.closure(tmp_path,'contracts/Main.sol',pins)
    assert [s['unit'] for s in result['source_units']]==['contracts/Main.sol','lib/A.sol','lib/B.sol']
    assert [edge['target'] for edge in result['import_edges']]==['lib/A.sol','lib/B.sol']


def test_same_basename_in_another_directory_cannot_rescue_import(tmp_path):
    pins=pin(tmp_path,{'main.sol':'import "A.sol"; contract Main {}','elsewhere/A.sol':'contract A {}'})
    with pytest.raises(imp.ImportFailure,match='missing_import'):
        imp.closure(tmp_path,'main.sol',pins)


def test_external_context_does_not_expand_to_a_neighboring_address(tmp_path):
    pins=pin(tmp_path,{'one.sol':'import "./two.sol"; contract One {}','two.sol':'contract Two {}'})
    with pytest.raises(imp.ImportFailure,match='external_import_context_unestablished'):
        imp.closure(tmp_path,'one.sol',pins,external=True)


@pytest.mark.parametrize('path', ('../outside.sol','/outside.sol','https://example.invalid/A.sol','x/../../outside.sol'))
def test_import_cannot_escape_declared_snapshot(tmp_path,path):
    pins=pin(tmp_path,{'main.sol':f'import "{path}"; contract Main {{}}'})
    with pytest.raises(imp.ImportFailure):imp.closure(tmp_path,'main.sol',pins)


def test_symlink_parent_is_rejected_even_when_target_bytes_match(tmp_path):
    actual=tmp_path/'actual';actual.mkdir();pin(actual,{'A.sol':'contract A {}'})
    (tmp_path/'linked').symlink_to(actual,target_is_directory=True)
    pins=pin(tmp_path,{'main.sol':'import "linked/A.sol"; contract Main {}'})
    pins['linked/A.sol']=hashlib.sha256((actual/'A.sol').read_bytes()).hexdigest()
    with pytest.raises(imp.ImportFailure,match='symlink'):
        imp.closure(tmp_path,'main.sol',pins)


def test_import_cycles_terminate_with_each_verified_source_once(tmp_path):
    pins=pin(tmp_path,{'A.sol':'import "B.sol"; contract A {}','B.sol':'import "A.sol"; contract B {}'})
    result=imp.closure(tmp_path,'A.sol',pins)
    assert len(result['source_units'])==2 and len(result['import_edges'])==2


def test_changed_import_byte_or_ambiguous_pin_is_not_compile_ready(tmp_path):
    pins=pin(tmp_path,{'main.sol':'contract C {}'});(tmp_path/'main.sol').write_text('contract Changed {}')
    with pytest.raises(imp.ImportFailure,match='source_hash_changed'):
        imp.closure(tmp_path,'main.sol',pins)
    pins=pin(tmp_path,{'main.sol':'contract C {}'});pins['main.sol']=[pins['main.sol']]*2
    with pytest.raises(imp.ImportFailure,match='ambiguous_pinned_import'):
        imp.closure(tmp_path,'main.sol',pins)


def test_ast_contract_with_missing_requested_outputs_cannot_be_success():
    proc=output(ast={'nodeType':'SourceUnit','nodes':[definition()]},contracts={})
    got=r.classify_output(proc,'main.sol')
    assert not got['success'] and got['status']=='compiler_output_schema_error'


@pytest.mark.parametrize('ast,contracts', (
    ({'nodes':None},{}),
    ({'nodes':[definition()]},{'main.sol':{'C':{'abi':[],'evm':'not an object'}}}),
    ({'nodes':[definition()]},{'main.sol':{'C':{'abi':[],'evm':{'bytecode':None}}}}),
    ({'nodes':[definition()]},{'main.sol':{'C':{'abi':None,'evm':{'bytecode':{'object':'00'}}}}}),
))
def test_malformed_compiler_schema_is_a_failure_record_not_a_crash(ast,contracts):
    got=r.classify_output(output(ast,contracts),'main.sol')
    assert not got['success'] and got['status']=='compiler_output_schema_error'


def test_interface_with_explicit_abi_is_not_fabricated_executable_bytecode():
    proc=output({'nodes':[definition('I','interface')]},{'main.sol':{'I':{'abi':[]}}})
    got=r.classify_output(proc,'main.sol')
    assert got['success'] and got['interface_definitions']==1
    assert got['missing_bytecode_interface_or_abstract_contracts']==1
    assert got['nonempty_bytecode_contracts']==0


def test_no_root_contract_is_distinguished_from_missing_output():
    got=r.classify_output(output(),'main.sol')
    assert got['success'] and got['status']=='compiler_success_no_root_contracts'


def test_error_severity_overrides_otherwise_plausible_outputs():
    proc=output();data=json.loads(proc['stdout']);data['errors']=[{'severity':'error','type':'TypeError','message':'fictional'}]
    proc['stdout']=json.dumps(data).encode()
    got=r.classify_output(proc,'main.sol')
    assert not got['success'] and got['status']=='compiler_error'
    assert 'fictional' not in json.dumps(got)


def test_process_wall_limit_applies_after_both_output_pipes_close(tmp_path):
    source=tmp_path/'stdin';source.write_bytes(b'')
    limits={**r.LIMITS,'wall_seconds':.15,'cpu_seconds':1,'memory_bytes':256*1024**2}
    start=time.monotonic()
    got=r.limited_process([sys.executable,'-c','import os,time;os.close(1);os.close(2);time.sleep(3)'],source,tmp_path,limits)
    assert got['process_status']=='timeout' and time.monotonic()-start<2.5


def test_process_output_limit_truncates_without_deadlock(tmp_path):
    source=tmp_path/'stdin';source.write_bytes(b'')
    limits={**r.LIMITS,'wall_seconds':2.,'cpu_seconds':1,'memory_bytes':256*1024**2,'stdout_bytes':64,'stderr_bytes':64}
    got=r.limited_process([sys.executable,'-c','import os;os.write(1,b"x"*4096);os.write(2,b"y"*4096)'],source,tmp_path,limits)
    assert got['process_status']=='output_limit' and len(got['stdout'])<=64 and len(got['stderr'])<=64


def test_no_reviewed_permit_means_no_compiler_operation(tmp_path,monkeypatch):
    plan=tmp_path/'plan';plan.mkdir();(plan/'plan_before_execution.json').write_text('{}')
    def forbidden(*args,**kwargs):raise AssertionError('No subprocess before an approved permit')
    monkeypatch.setattr(r,'limited_process',forbidden)
    with pytest.raises(ValueError,match='permit'):
        r.execute(plan,None,None)
