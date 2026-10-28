"""New dated verification of transcript-recovered fictional reporting tests.

This runner cannot restore the former run's timing, output or receipt bytes.
It reads implementation/policy files and invokes only the recovered fictional
test module. No source corpus, actual annotation key, tool or model is opened.
"""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
B = HERE.parent / 'external_protocol'
OLD = HERE.parent / 'recovery_20261026'
OUT = HERE / 'reporting_independent_reproduction_20261028_v1'
EXPECTED_TEST = '0df301bf6ad537d5d5b84c611781c07d1487295a3df3ebb550439b46888c4316'
EXPECTED = {
    'reporting_v1/reporting.py': 'eb2502b2604955e6cbe1cd54819481c0a9911d5c3738d3b0525426b04e7aa504',
    'performance_v1/performance.py': 'b5bdd17f6e90b0456b03ca64a5d528e53927437a9d72cfef0d9d962316e46d9b',
    'performance_v2/performance.py': '71837b15960b1b9b26434957437934cda04c4092a288ca661e1a4eb31ef48b69',
    'ap_bounds_v1/ap_bounds.py': '71147a09cec0f755a735224f127ef379d7b4e78c17094d3ee48c3635df54ef2c',
    'review_estimators.py': '6975911668d93abed5176c63e2d90b77e00a1e1e64a99e1faa04e9b4bcf3b274',
    'INFERENCE_AMENDMENT_DRAFT_20261026.md': 'fbf798ba4a6c2da96a0eb3afb6d3e57561a21f448da5413f192e37b58f9adc53',
    'INFERENCE_GATE_20261026.json': '0c789dcf4d03e532d3a20298bec0412852a334351a2c021709b288419897fa1e',
    'PROTOCOL_B.md': 'd54c70f59abf63ac3580408fd352b3ff3f77fb006f8a857539f64ed0669ca3ca',
    'protocol_B_draft.json': 'c4f6f4220bf4b4f3bda92c0be7226e7d96bfcaf97aed9ce1b1be9ee388ab6fd6',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def old_presence():
    names = ['test_reporting_independent.py',
             'engineering_independent_stage2_reporting_20261026_v1/plan_before_tests.json',
             'engineering_independent_stage2_reporting_20261026_v1/result.json',
             'engineering_independent_stage2_reporting_20261026_v1/pytest_stdout.txt']
    return {str((OLD/name).relative_to(ROOT)): (OLD/name).exists() for name in names}


def main():
    if OUT.exists():
        raise FileExistsError('Identified recovery runs are immutable; select a new dated run')
    test = HERE/'test_reporting_independent.py'
    if sha(test) != EXPECTED_TEST:
        raise ValueError('Recovered test source does not match the original recorded SHA256')
    for name, expected in EXPECTED.items():
        if sha(B/name) != expected:
            raise ValueError('Protected source/policy differs from the previously reviewed bytes: '+name)
    sources = [Path(__file__), test, HERE/'conftest.py', *[B/name for name in EXPECTED]]
    before = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    previous_presence = old_presence()
    packages = {name: importlib.metadata.version(name) for name in ['pytest','numpy','pandas','scipy','scikit-learn']}
    command = [sys.executable, '-m', 'pytest', '-q', str(test.relative_to(ROOT)),
               '--junitxml='+str((OUT/'pytest.xml').relative_to(ROOT))]
    OUT.mkdir()
    inventory = {
        'schema': 'transcript_test_source_recovery_inventory_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'recovered_source': str(test.relative_to(ROOT)),
        'original_recorded_test_sha256': EXPECTED_TEST,
        'reconstructed_test_sha256': sha(test), 'exact_original_source_bytes_recovered': True,
        'reconstruction_method': 'Reassembled original tool-history patch plus its amendments; SHA256 independently agrees with the original recorded value.',
        'old_artifacts_present_before': previous_presence,
        'old_original_receipt_sha256_from_record': '3675090410bfeb03b78199a772a87eacfa140f6f1ed059c9387cfea597495279',
        'old_run_outputs_restored': False,
        'old_receipt_restored': False,
        'new_run_is_not_original_receipt_or_output_recovery': True,
        'protected_original_source_and_policy_sha256': EXPECTED,
    }
    write_new(OUT/'RECOVERY_INVENTORY.json', inventory)
    plan = {
        'schema': 'independent_reporting_reproduction_plan_20261028_v1',
        'frozen_utc': datetime.now(timezone.utc).isoformat(), 'command': command,
        'source_sha256': before, 'recovery_inventory_sha256': sha(OUT/'RECOVERY_INVENTORY.json'),
        'expected_test_count': 34, 'synthetic_inputs_only': True,
        'actual_reference_source_score_access': False, 'actual_tool_or_model_execution': False,
        'protocol_or_gate_activation': False, 'new_dated_run': True,
        'environment': {'python_executable': sys.executable, 'python': platform.python_version(),
                        'python_executable_sha256': sha(Path(sys.executable)), 'packages': packages,
                        'PYTEST_ADDOPTS': os.environ.get('PYTEST_ADDOPTS'),
                        'PYTEST_DISABLE_PLUGIN_AUTOLOAD': os.environ.get('PYTEST_DISABLE_PLUGIN_AUTOLOAD')},
        'known_environment_difference_from_20261026': {
            'pytest_original': '8.4.2', 'pytest_current': packages['pytest'],
            'note': 'A fresh run in the restored runtime; original timing/output bytes cannot be recovered by rerunning.'},
    }
    write_new(OUT/'plan_before_tests.json', plan)
    for source in sources:
        dest = OUT/'source_snapshot'/source.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        if sha(dest) != before[str(source.relative_to(ROOT))]:
            raise ValueError('Source changed during freeze')
    started = time.monotonic()
    run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    elapsed = time.monotonic()-started
    (OUT/'pytest_stdout.txt').write_text(run.stdout)
    (OUT/'pytest_stderr.txt').write_text(run.stderr)
    after = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    cases = ET.parse(OUT/'pytest.xml').getroot().findall('.//testcase') if (OUT/'pytest.xml').exists() else []
    counts = {'tests': len(cases), 'failures': sum(x.find('failure') is not None for x in cases),
              'errors': sum(x.find('error') is not None for x in cases),
              'skipped': sum(x.find('skipped') is not None for x in cases)}
    result = {
        'schema': 'independent_reporting_reproduction_result_20261028_v1',
        'passed': run.returncode==0 and counts=={'tests':34,'failures':0,'errors':0,'skipped':0}
                  and before==after and old_presence()==previous_presence,
        'returncode': run.returncode, 'counts': counts, 'elapsed_seconds': elapsed,
        'source_hashes_unchanged': before==after, 'source_sha256': after,
        'original_test_source_recovered_exactly': sha(test)==EXPECTED_TEST,
        'old_artifact_presence_unchanged': old_presence()==previous_presence,
        'old_artifacts_present_after': old_presence(),
        'original_receipt_or_output_bytes_recovered': False,
        'new_dated_synthetic_verification_only': True, 'actual_operations_executed': 0,
        'plan_sha256': sha(OUT/'plan_before_tests.json'),
        'output_sha256': {p.name:sha(p) for p in OUT.glob('pytest*') if p.is_file()},
    }
    write_new(OUT/'result.json', result)
    print(json.dumps({k:result[k] for k in ['passed','counts','elapsed_seconds','source_hashes_unchanged',
          'original_test_source_recovered_exactly','old_artifact_presence_unchanged','actual_operations_executed']},indent=2))
    if not result['passed']:
        raise SystemExit(run.returncode or 2)


if __name__=='__main__':
    main()
