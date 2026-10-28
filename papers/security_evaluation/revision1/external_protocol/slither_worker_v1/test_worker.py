"""Owner regression guards; actual authored tools run only via frozen plan CLI."""
from pathlib import Path
import importlib.util
import json
import types
import pytest
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('owner_slither_worker', HERE/'worker.py')
w = importlib.util.module_from_spec(spec)
exec(compile((HERE/'worker.py').read_bytes(), str(HERE/'worker.py'), 'exec'), w.__dict__)


def test_load_bypasses_same_timestamp_same_size_bytecode(tmp_path):
    import py_compile, os
    p = tmp_path/'f.py';p.write_text('VALUE=1\n');py_compile.compile(str(p))
    stat=p.stat();p.write_text('VALUE=2\n');os.utime(p,ns=(stat.st_atime_ns,stat.st_mtime_ns))
    assert w.load('slither_owner_authored',p).VALUE==2


def test_closed_admission_does_not_read_runtime_authorization_or_full_inputs(tmp_path):
    p=types.SimpleNamespace(admission_preflight=lambda *a:{'admission_artifacts_consistent':False},
        check=lambda *a,**k:pytest.fail('Full private input check was reached'))
    with pytest.raises(ValueError,match='Admission denied'):
        w._authorize(p,tmp_path,tmp_path/'absent_binding','0'*64,tmp_path/'absent_release',tmp_path/'absent_auth','0'*64)


def test_analysis_failure_is_not_compile_failure():
    assert w.classify_analysis({'process_status':'process_failure'}) == {'status':'slither_error','success':False}


def test_explicit_missing_fields_status_only():
    x=w.classify_analysis({'process_status':'completed','returncode':2,'stdout':b'{"status":"error","error_code":"missing_slither_compiler_fields"}'})
    assert x=={'status':'missing_slither_compiler_fields','success':False}


def test_fixture_crlf_utf8_and_predeclared_expectations():
    fixture=w.load('owner_authored_fixture', HERE/'fixtures.py').cases()
    assert len(fixture)==25 and len({x['id'] for x in fixture})==25
    case=next(x for x in fixture if x['id']=='crlf_utf8_offsets')
    raw=case['sources'][case['entry']].encode('utf-8')
    assert b'\r\n' in raw and len(raw)>len(raw.decode('utf-8'))
    assert case['expected_primary_scores']=={'reentrancy':0,'unchecked':1}


def test_stage_preserves_exact_newlines_and_utf8(tmp_path):
    context=tmp_path/'context';context.mkdir();workspace=tmp_path/'work';workspace.mkdir()
    source=b'pragma solidity 0.8.26;\r\n// caf\xc3\xa9\r\ncontract Authored {}\r\n'
    (context/'Root.sol').write_bytes(source)
    job={'entry_source_unit':'Root.sol','source_units':[{'unit':'Root.sol','sha256':w.sha(context/'Root.sol')}]}
    payload=w.stage(job,context,workspace)
    assert (workspace/'Root.sol').read_bytes()==source
    assert json.loads(payload.read_text())['sources']['Root.sol']['content'].encode('utf-8')==source


def test_runtime_directory_symlink_rejected(tmp_path):
    python=tmp_path/'python';python.write_bytes(b'authored')
    site=tmp_path/'site';site.mkdir();outside=tmp_path/'outside';outside.mkdir();(site/'added').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='symlink'):
        w.check_runtime({'schema':'slither_installed_runtime_binding_v1','python':str(python),'python_sha256':w.sha(python),
            'files':{},'site_packages':str(site),'site_package_files':[]})


def test_production_cli_has_no_synthetic_bypass():
    import inspect
    assert 'synthetic' not in inspect.signature(w.execute).parameters
    with pytest.raises(ValueError,match='private derived'):
        w.execute(w.ROOT,Path('/absent'),'0'*64,Path('/absent'),Path('/absent'),'0'*64,w.HERE/'disallowed')


def test_shared_wheel_files_need_known_owner_bytes_and_record_hash():
    owners=[{'package':'first','sha256':'a'*64},{'package':'second','sha256':'b'*64}]
    w.verify_shared_member('b'*64,owners,'first','a'*64)
    with pytest.raises(ValueError,match='no pinned owner'):
        w.verify_shared_member('c'*64,owners)
    with pytest.raises(ValueError,match='multiple'):
        w.verify_shared_member('b'*64,owners[:1])
    with pytest.raises(ValueError,match='RECORD'):
        w.verify_shared_member('b'*64,owners,'first','c'*64)
