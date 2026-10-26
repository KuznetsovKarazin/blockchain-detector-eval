"""Integrity/identity and strict version-probe tests; no compilation or scans."""
import hashlib,json,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import provision_toolchain as tool
from verify_toolchain import full_version_matches


def test_corrupt_artifact_is_rejected_before_use():
    good=b'pinned artifact'
    assert tool.verify_digest(good,hashlib.sha256(good).hexdigest())
    with pytest.raises(ValueError,match='SHA256 mismatch'):
        tool.verify_digest(good+b'changed',hashlib.sha256(good).hexdigest())


def test_full_compiler_build_identity_not_only_semver():
    assert full_version_matches('Version: 0.8.26+commit.8a97fa7a.Linux.g++\n','0.8.26+commit.8a97fa7a')
    assert not full_version_matches('Version: 0.8.26+commit.ffffffff.Linux.g++\n','0.8.26+commit.8a97fa7a')
    assert not full_version_matches('Version: 0.8.26+commit.8a97fa7a2.Linux.g++\n','0.8.26+commit.8a97fa7a')


def test_probe_never_passes_contract_or_stdin(monkeypatch):
    recorded=[]
    def fake(argv,**kwargs):
        recorded.append((argv,kwargs));return SimpleNamespace(stdout='0.11.6\n',stderr='',returncode=0)
    monkeypatch.setattr(tool.subprocess,'run',fake)
    binary=tool.ROOT/'data/derived/fake-slither'
    probe=tool.version_probe(binary,'0.11.6','slither')
    assert recorded[0][0]==[str(binary),'--version']
    assert recorded[0][1]['stdin']==subprocess.DEVNULL and recorded[0][1]['timeout']==30
    assert probe['argv']==['data/derived/fake-slither','--version']


def test_wrong_executable_version_is_rejected(monkeypatch):
    monkeypatch.setattr(tool.subprocess,'run',lambda *a,**kw:SimpleNamespace(stdout='0.11.5\n',stderr='',returncode=0))
    with pytest.raises(ValueError):tool.version_probe(tool.ROOT/'data/derived/fake','0.11.6','slither')


def test_inventory_exactly_covers_frozen_plan_union_and_does_not_upgrade_unplanned():
    rows,versions=tool.required_versions(tool.PLANS)
    manifest=json.loads((tool.HERE/'manifest.json').read_text())
    solc=json.loads((tool.HERE/'solc_inventory.json').read_text())
    assert len(rows)==2689 and sum(bool(row['candidate_versions']) for row in rows)==2650
    assert len(versions)==30 and sum(versions.values())==3900
    assert set(versions)=={item['version'] for item in solc['releases']}
    assert manifest['unplanned_source_rows']==sum(not row['candidate_versions'] for row in rows)==39
    assert not manifest['compilation_success_coverage_established']
    assert not manifest['external_readiness_or_semantic_signoff']
    assert manifest['compiler_executions_on_sources']==manifest['slither_analyses']==0


def test_dependency_lock_has_exact_verified_artifacts():
    metadata=json.loads((tool.HERE/'python_artifacts.json').read_text())
    expected={f"{r['package']}=={r['version']} --hash=sha256:{r['artifact_sha256']}" for r in metadata['artifacts']}
    assert set((tool.HERE/'requirements.lock').read_text().splitlines())==expected
    assert len(expected)==47
    slither=next(r for r in metadata['artifacts'] if r['package']=='slither-analyzer')
    assert slither['artifact_sha256']==tool.SLITHER_WHEEL_SHA
    assert all(r['pypi_metadata_url'].startswith('https://pypi.org/') for r in metadata['artifacts'])
    assert all(r['download_url'].startswith('https://files.pythonhosted.org/') for r in metadata['artifacts'])


def test_local_installed_artifact_integrity_without_executing_tools():
    if not (tool.PRIVATE/'python_env/bin/slither').exists():pytest.skip('ignored executable inventory is not provisioned in this checkout')
    solc=json.loads((tool.HERE/'solc_inventory.json').read_text())
    for entry in solc['releases']:
        assert tool.sha(tool.ROOT/entry['local_path'])==entry['sha256']
        assert full_version_matches(entry['version_probe']['stdout'],entry['long_version'])
    wheels=json.loads((tool.HERE/'python_artifacts.json').read_text())['artifacts']
    for entry in wheels:assert tool.sha(tool.ROOT/entry['local_path'])==entry['artifact_sha256']
