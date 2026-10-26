"""Synthetic sources/processes only; never invokes solc, Slither or real corpus."""
import hashlib,json,os,signal,subprocess,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import imports as resolver
import runner


@pytest.mark.parametrize('statement',[
 'import "A.sol";', 'import "A.sol" as Alias;', 'import * as Alias from "A.sol";',
 'import {A} from "A.sol";', 'import {A as B,C} from "A.sol";'])
def test_supported_import_forms(statement):
    assert resolver.import_paths(statement)==['A.sol']


def test_comments_literals_and_braces_do_not_fake_imports():
    text='// import "bad.sol";\n/* import "bad2.sol"; */ contract C { string x="import \\\"bad3.sol\\\"; }"; }\nimport "real.sol";'
    assert resolver.import_paths(text)==['real.sol']


@pytest.mark.parametrize('text,status',[
 ('import "https://host/A.sol";','remote_or_absolute_import_forbidden'),
 ('import "/outside/A.sol";','remote_or_absolute_import_forbidden'),
 ('import "A\\x2esol";','import_literal_unsupported'),
 ('import {A,} from "A.sol";','import_syntax_unresolved'),
 ('import "A.sol"','import_syntax_unresolved')])
def test_unsupported_or_remote_imports_fail_closed(text,status):
    with pytest.raises(resolver.ImportFailure) as exc:resolver.import_paths(text)
    assert exc.value.status==status


def make_source(root,unit,text):
    p=root/unit;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_relative_and_direct_closure_with_cycles_preserves_exact_hashes(tmp_path):
    pins={'contracts/A.sol':make_source(tmp_path,'contracts/A.sol','import "../lib/B.sol"; contract A {}'),
          'lib/B.sol':make_source(tmp_path,'lib/B.sol','import "contracts/A.sol"; library B {}')}
    result=resolver.closure(tmp_path,'contracts/A.sol',pins)
    assert [r['unit'] for r in result['source_units']]==['contracts/A.sol','lib/B.sol']
    assert len(result['import_edges'])==2


def test_no_basename_rescue_and_external_context_not_invented(tmp_path):
    pins={'A.sol':make_source(tmp_path,'A.sol','import "missing/B.sol"; contract A {}'),
          'B.sol':make_source(tmp_path,'B.sol','library B {}')}
    with pytest.raises(resolver.ImportFailure,match='missing_import'):resolver.closure(tmp_path,'A.sol',pins)
    pins['A.sol']=make_source(tmp_path,'A.sol','import "B.sol"; contract A {}')
    with pytest.raises(resolver.ImportFailure,match='external_import_context_unestablished'):
        resolver.closure(tmp_path,'A.sol',pins,external=True)


def test_ambiguous_and_changed_dependency_rejected(tmp_path):
    h=make_source(tmp_path,'A.sol','contract A {}')
    with pytest.raises(resolver.ImportFailure,match='ambiguous_pinned_import'):resolver.closure(tmp_path,'A.sol',{'A.sol':[h,h]})
    with pytest.raises(resolver.ImportFailure,match='source_hash_changed'):resolver.closure(tmp_path,'A.sol',{'A.sol':'0'*64})


def test_symlink_and_snapshot_escape_rejected(tmp_path):
    root=tmp_path/'root';root.mkdir();outside=tmp_path/'outside.sol';outside.write_text('contract O {}')
    (root/'A.sol').symlink_to(outside)
    with pytest.raises(resolver.ImportFailure,match='source_symlink_forbidden'):
        resolver.closure(root,'A.sol',{'A.sol':hashlib.sha256(outside.read_bytes()).hexdigest()})
    with pytest.raises(resolver.ImportFailure,match='import_outside_snapshot'):
        resolver.source_unit_target('A.sol','../outside.sol')


def test_closure_resource_limit(tmp_path):
    pins={'A.sol':make_source(tmp_path,'A.sol','contract A {}')}
    with pytest.raises(resolver.ImportFailure,match='import_closure_limit'):resolver.closure(tmp_path,'A.sol',pins,max_bytes=1)


def payload(errors=None,contracts=None,nodes=None):
    obj={'sources':{'A.sol':{'ast':{'nodeType':'SourceUnit','nodes':nodes or []}}},'contracts':{'A.sol':contracts or {}}}
    if errors is not None:obj['errors']=errors
    return {'process_status':'completed','returncode':0,'stdout':json.dumps(obj).encode(),'stderr':b''}


def test_json_error_is_failure_even_zero_exit_and_private_message_not_returned():
    result=runner.classify_output(payload([{'severity':'error','type':'Secret source excerpt','message':'private source text'}]),'A.sol')
    assert result['status']=='compiler_error' and not result['success']
    assert result['diagnostic_types']=={'OtherDiagnostic':1}
    assert 'private source text' not in json.dumps(result) and 'Secret source excerpt' not in json.dumps(result)


def test_interface_abstract_and_unlinked_outputs_counted_without_exclusion():
    contracts={'I':{'abi':[]},'A':{'abi':[],'evm':{'bytecode':{'object':''}}},'L':{'abi':[],'evm':{'bytecode':{'object':'60__$abc$__'}}}}
    nodes=[{'nodeType':'ContractDefinition','name':'I','contractKind':'interface'},
           {'nodeType':'ContractDefinition','name':'A','contractKind':'contract','abstract':True},
           {'nodeType':'ContractDefinition','name':'L','contractKind':'library'}]
    result=runner.classify_output(payload(contracts=contracts,nodes=nodes),'A.sol')
    assert result['success'] and result['root_contracts']==3
    assert result['interface_definitions']==result['abstract_definitions']==1
    assert result['empty_bytecode_contracts']==result['missing_bytecode_interface_or_abstract_contracts']==1
    assert result['nonempty_bytecode_contracts']==result['unlinked_bytecode_contracts']==1


def test_no_contract_file_retained_and_incomplete_output_rejected():
    result=runner.classify_output(payload(),'A.sol')
    assert result['success'] and result['status']=='compiler_success_no_root_contracts'
    bad=payload(contracts={'C':{'abi':[]}})
    assert not runner.classify_output(bad,'A.sol')['success']


def fake_process(tmp_path,code,**override):
    inp=tmp_path/'input.json';inp.write_text('{}')
    return runner.limited_process([sys.executable,'-c',code],inp,tmp_path,{**runner.LIMITS,**override})


def test_wall_timeout_kills_fake_process_even_after_pipes_close(tmp_path):
    result=fake_process(tmp_path,'import os,time;os.close(1);os.close(2);time.sleep(2)',wall_seconds=.15)
    assert result['process_status']=='timeout' and result['wall_seconds']<1.5


def test_stdout_limit_bounds_captured_bytes(tmp_path):
    result=fake_process(tmp_path,'import sys;sys.stdout.write("x"*100000)',stdout_bytes=100)
    assert result['process_status']=='output_limit' and len(result['stdout'])==100


def test_memory_cap_enforced_on_fake_python(tmp_path):
    result=fake_process(tmp_path,'x=bytearray(512*1024*1024)',memory_bytes=128*1024**2)
    assert result['returncode']!=0 and b'MemoryError' in result['stderr']


def test_cpu_cap_enforced_on_fake_python(tmp_path):
    result=fake_process(tmp_path,'while True: pass',cpu_seconds=1,wall_seconds=3)
    assert result['process_status']=='cpu_limit' and result['returncode']==-signal.SIGXCPU


def test_limits_are_set_in_child_not_main_process(tmp_path):
    result=fake_process(tmp_path,'import resource,json;print(json.dumps([resource.getrlimit(resource.RLIMIT_AS),resource.getrlimit(resource.RLIMIT_NOFILE)]))')
    limits=json.loads(result['stdout'])
    assert limits==[[runner.LIMITS['memory_bytes']]*2,[runner.LIMITS['open_files']]*2]


def test_missing_permit_blocks_before_any_subprocess(tmp_path,monkeypatch):
    monkeypatch.setattr(runner.subprocess,'Popen',lambda *a,**kw:pytest.fail('process must not start'))
    with pytest.raises(ValueError,match='permit'):
        runner.execute(tmp_path,None,None)


def test_unapproved_template_is_not_permission(tmp_path):
    p=tmp_path/'permit.json';p.write_text(json.dumps({'approved':False,'scope':'compiler_readiness_only'}))
    with pytest.raises(ValueError,match='not approved'):
        runner.check_execution_permission(tmp_path/'plan.json',p,runner.sha(p))


def test_ast_declared_concrete_contract_cannot_disappear_from_requested_outputs():
    node={'nodeType':'ContractDefinition','name':'C','contractKind':'contract'}
    result=runner.classify_output(payload(nodes=[node]),'A.sol')
    assert result['status']=='compiler_output_schema_error' and not result['success']


@pytest.mark.parametrize('mutation',[
 lambda obj:obj['sources']['A.sol']['ast'].update(nodes=None),
 lambda obj:obj['contracts']['A.sol']['C'].update(evm='not a dict'),
 lambda obj:obj['contracts']['A.sol']['C'].update(evm={'bytecode':None}),
 lambda obj:obj['contracts']['A.sol']['C'].update(evm={'bytecode':{'object':None}}),
 lambda obj:obj['sources']['A.sol']['ast'].update(nodes=[{'nodeType':'ContractDefinition','attributes':None}]),
])
def test_malformed_nested_json_is_per_file_failure_not_campaign_exception(mutation):
    process=payload(contracts={'C':{'abi':[],'evm':{'bytecode':{'object':'60'}}}},
        nodes=[{'nodeType':'ContractDefinition','name':'C','contractKind':'contract'}])
    obj=json.loads(process['stdout']);mutation(obj);process['stdout']=json.dumps(obj).encode()
    result=runner.classify_output(process,'A.sol')
    assert result['status']=='compiler_output_schema_error' and not result['success']
