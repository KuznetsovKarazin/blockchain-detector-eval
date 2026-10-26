"""Verifier amendment: optimization-safe failure and explicit receipt writes."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_toolchain_v2 as verifier


def run_cli(*args,optimized=False):
    return subprocess.run([sys.executable,*(['-O'] if optimized else []),'-B',str(Path(verifier.__file__)),*map(str,args)],
                          capture_output=True,text=True,timeout=30)


def frozen_hashes():
    manifest=verifier.read(verifier.HERE/'manifest.json')
    names=['manifest.json','verify_toolchain.py','provision_toolchain.py',*manifest['output_sha256']]
    return {name:verifier.sha(verifier.HERE/name) for name in names}


def test_no_asserts_or_import_of_assert_based_helpers():
    tree=ast.parse(Path(verifier.__file__).read_text())
    assert not any(isinstance(node,ast.Assert) for node in ast.walk(tree))
    imported={node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
    assert 'provision_toolchain' not in imported and 'verify_toolchain' not in imported
    with pytest.raises(ValueError,match='intentional'):
        verifier.require(False,'intentional')


@pytest.mark.parametrize('optimized',[False,True])
def test_valid_default_invocation_preserves_all_frozen_files(optimized):
    before=frozen_hashes()
    result=run_cli(optimized=optimized)
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    assert report['status']=='pass' and report['validation_files_written']==0
    assert report['tool_invocations_in_this_verification']==0
    assert report['python_optimization_level']==int(optimized)
    assert frozen_hashes()==before


@pytest.mark.parametrize('optimized',[False,True])
def test_tampered_receipt_rejected_even_with_optimization_and_no_output(tmp_path,optimized):
    metadata=tmp_path/'metadata';metadata.mkdir()
    shutil.copyfile(verifier.HERE/'manifest.json',metadata/'manifest.json')
    shutil.copyfile(verifier.HERE/'verify_toolchain.py',metadata/'verify_toolchain.py')
    shutil.copyfile(verifier.HERE/'provision_toolchain.py',metadata/'provision_toolchain.py')
    original=json.loads((metadata/'manifest.json').read_text());original['solc_versions']=29
    (metadata/'manifest.json').write_text(json.dumps(original))
    receipt=tmp_path/'must_not_exist.json'
    result=run_cli('--metadata-root',metadata,'--receipt',receipt,optimized=optimized)
    assert result.returncode==1 and 'SHA256 mismatch' in result.stderr
    assert json.loads(result.stderr)['status']=='failed'
    assert not receipt.exists()


def test_explicit_receipt_creation_and_refusal_to_overwrite(tmp_path):
    path=tmp_path/'new_receipt.json';before=frozen_hashes()
    result=run_cli('--receipt',path,optimized=True)
    assert result.returncode==0,result.stderr
    created=path.read_bytes();report=json.loads(created)
    assert report['receipt_write']=='explicit_exclusive_create' and report['python_optimization_level']==1
    again=run_cli('--receipt',path,optimized=True)
    assert again.returncode==1 and 'Refusing to overwrite' in again.stderr
    assert path.read_bytes()==created and frozen_hashes()==before


def test_old_code_and_receipt_snapshots_are_exact():
    baseline=verifier.read(verifier.HERE/'amendment_v2/legacy_baseline.json')
    for name,expected in baseline['legacy_files_sha256'].items():
        assert verifier.sha(verifier.HERE/name)==expected
        assert verifier.sha(verifier.HERE/'amendment_v2/source_snapshot_v1'/name)==expected
