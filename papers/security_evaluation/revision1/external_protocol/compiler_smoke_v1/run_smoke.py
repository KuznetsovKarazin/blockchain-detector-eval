"""Exercise pinned compiler JSON interfaces on one authored benign fixture only."""
from pathlib import Path
import argparse
import hashlib
import json
import resource
import subprocess
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
SOURCE = 'pragma solidity >=0.4.0 <0.9.0;\ncontract Smoke {\n uint private x;\n function set(uint a) public { x = a; }\n function get() public view returns (uint) { return x; }\n}\n'
SETTINGS = {'optimizer': {'enabled': False}, 'remappings': [],
            'outputSelection': {'*': {'': ['ast'], '*': ['abi', 'evm.bytecode.object']}}}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 ** 3, 2 * 1024 ** 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 ** 2, 4 * 1024 ** 2))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(); out = args.out.resolve()
    if out.exists(): raise ValueError('Use a fresh output directory')
    inventory = HERE.parent / 'toolchain_v1/solc_inventory.json'
    releases = json.loads(inventory.read_text())['releases']
    if len(releases) != 30: raise ValueError('Expected exact inventory of 30 compilers')
    for entry in releases:
        if digest((ROOT / entry['local_path']).read_bytes()) != entry['artifact_sha256']:
            raise ValueError('Compiler checksum mismatch')
    payload = json.dumps({'language': 'Solidity', 'sources': {'Smoke.sol': {'content': SOURCE}}, 'settings': SETTINGS}).encode()
    out.mkdir(parents=True)
    (out / 'Smoke.sol').write_text(SOURCE)
    (out / 'run_smoke_snapshot.py').write_bytes(Path(__file__).read_bytes())
    plan = {'schema': 'authored_fixture_compiler_smoke_v1', 'prepared_utc': datetime.now(timezone.utc).isoformat(),
            'source_sha256': digest(SOURCE.encode()), 'input_json_sha256': digest(payload),
            'runner_sha256': digest(Path(__file__).read_bytes()), 'inventory_sha256': digest(inventory.read_bytes()),
            'versions': [e['version'] for e in releases], 'settings': SETTINGS,
            'corpus_sources_read': 0, 'labels_read': 0, 'detectors_executed': 0,
            'scope': 'Compiler interface smoke test on one authored fixture, not source-corpus coverage.'}
    (out / 'plan_before_execution.json').write_text(json.dumps(plan, indent=2) + '\n')
    rows = []
    for entry in releases:
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='article1_solc_smoke_') as temp:
            folder = Path(temp)
            with (folder/'input.json').open('wb') as f: f.write(payload)
            try:
                with (folder/'input.json').open('rb') as fi, (folder/'stdout').open('wb') as fo, (folder/'stderr').open('wb') as fe:
                    result = subprocess.run([str(ROOT/entry['local_path']), '--standard-json', '--allow-paths', str(folder)],
                                            stdin=fi, stdout=fo, stderr=fe, cwd=folder, timeout=40, preexec_fn=limits, check=False)
                stdout = (folder/'stdout').read_bytes(); stderr = (folder/'stderr').read_bytes()
                decoded = json.loads(stdout)
                errors = [e for e in decoded.get('errors', []) if e.get('severity') == 'error']
                artifact = decoded.get('contracts', {}).get('Smoke.sol', {}).get('Smoke', {})
                ast = decoded.get('sources', {}).get('Smoke.sol', {}).get('ast')
                bytecode = artifact.get('evm', {}).get('bytecode', {}).get('object')
                success = result.returncode == 0 and not errors and isinstance(ast, dict) and isinstance(artifact.get('abi'), list) and isinstance(bytecode, str) and len(bytecode) > 0
                row = {'version': entry['version'], 'success': success, 'returncode': result.returncode,
                       'compiler_error_count': len(errors), 'warning_count': sum(e.get('severity') == 'warning' for e in decoded.get('errors', [])),
                       'ast_present': isinstance(ast, dict), 'abi_entries': len(artifact.get('abi', [])),
                       'bytecode_hex_characters': len(bytecode) if isinstance(bytecode, str) else None,
                       'stdout_sha256': digest(stdout), 'stderr_sha256': digest(stderr)}
            except (subprocess.TimeoutExpired, ValueError, TypeError, AttributeError, OSError) as exc:
                row = {'version': entry['version'], 'success': False, 'error': type(exc).__name__ + ': ' + str(exc)}
        row['wall_seconds'] = time.monotonic()-start; rows.append(row)
    if digest(Path(__file__).read_bytes()) != plan['runner_sha256']:
        raise ValueError('Runner changed during smoke test')
    receipt = {'schema': 'authored_fixture_compiler_smoke_result_v1', 'results': rows,
               'compiler_invocations': len(rows), 'successful_compilers': sum(r['success'] for r in rows),
               'target_corpus_compilations': 0, 'model_fits': 0, 'slither_or_detector_runs': 0,
               'source_or_protocol_edits': False, 'status': 'pass' if all(r['success'] for r in rows) else 'fail'}
    (out/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k != 'results'}))


if __name__ == '__main__': main()
