"""Freeze and run independent fictional-input tests; never score real sources."""
from datetime import datetime, timezone
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXTERNAL = HERE.parent / 'external_protocol'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = HERE / 'engineering_independent_20261026_v1'
    if out.exists():
        raise FileExistsError('Choose a new identified review run; never overwrite a receipt')
    sources = [Path(__file__), HERE / 'test_engineering_independent.py', HERE / 'conftest.py',
               EXTERNAL / 'PROTOCOL_B.md', EXTERNAL / 'review_estimators.py',
               EXTERNAL / 'adapters_v1/adapters.py',
               EXTERNAL / 'adapters_v1/api_amendment_after_coverage.json',
               EXTERNAL / 'adapters_v1/adapter_plan.json',
               EXTERNAL / 'performance_v1/performance.py',
               ROOT / 'papers/security_evaluation/normalization_audit/solidity_scanner.py',
               ROOT / 'src/bal/features/contract_features.py',
               EXTERNAL / 'toolchain_v1/manifest.json']
    original_adapter = EXTERNAL / 'adapters_v1/coverage_20261026_v1/source_snapshot/adapters.py'
    sources.append(original_adapter)
    amendment = json.loads((EXTERNAL / 'adapters_v1/api_amendment_after_coverage.json').read_text())
    current_adapter = EXTERNAL / 'adapters_v1/adapters.py'
    if sha(original_adapter) != amendment['original_adapter_sha256'] or sha(current_adapter) != amendment['current_adapter_sha256']:
        raise ValueError('Adapter amendment source identity mismatch')
    def functions(path):
        return {node.name: ast.dump(node, include_attributes=False)
                for node in ast.parse(path.read_text()).body if isinstance(node, ast.FunctionDef)}
    old_functions, current_functions = functions(original_adapter), functions(current_adapter)
    unchanged = {name: old_functions[name] == current_functions[name]
                 for name in amendment['unchanged_representation_function_ast_sha256']}
    if not all(unchanged.values()):
        raise ValueError('Amended representation functions are not identical')
    before = {str(path.relative_to(ROOT)): sha(path) for path in sources}
    command = [sys.executable, '-m', 'pytest', '-q',
               str((HERE / 'test_engineering_independent.py').relative_to(ROOT))]
    plan = dict(schema='independent_external_B_synthetic_review_v1',
                frozen_utc=datetime.now(timezone.utc).isoformat(),
                command=command, source_sha256=before,
                synthetic_inputs_only=True, real_human_judgments_read=False,
                independently_verified_unchanged_representation_functions=unchanged,
                real_models_fitted_or_scored=0, real_source_preprocessing=False,
                external_protocol_gate_overridden=False,
                environment=dict(python=platform.python_version(),
                  packages={name: importlib.metadata.version(name) for name in
                            ['numpy', 'pandas', 'scipy', 'scikit-learn', 'pytest']}))
    out.mkdir()
    (out / 'plan_before_tests.json').write_text(json.dumps(plan, indent=2)+'\n')
    for path in sources:
        target = out / 'source_snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    start = time.monotonic()
    process = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    elapsed = time.monotonic()-start
    (out / 'pytest_stdout.txt').write_text(process.stdout)
    (out / 'pytest_stderr.txt').write_text(process.stderr)
    after = {str(path.relative_to(ROOT)): sha(path) for path in sources}
    stable = before == after
    result = dict(schema='independent_external_B_synthetic_review_result_v1',
                  returncode=process.returncode, passed=process.returncode == 0 and stable,
                  elapsed_seconds=elapsed, sources_unchanged_during_run=stable,
                  source_sha256=after, plan_sha256=sha(out/'plan_before_tests.json'),
                  stdout_sha256=sha(out/'pytest_stdout.txt'),
                  stderr_sha256=sha(out/'pytest_stderr.txt'),
                  synthetic_inputs_only=True, actual_model_or_external_results=False)
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    if process.returncode or not stable:
        raise SystemExit(process.returncode or 2)


if __name__ == '__main__':
    main()
