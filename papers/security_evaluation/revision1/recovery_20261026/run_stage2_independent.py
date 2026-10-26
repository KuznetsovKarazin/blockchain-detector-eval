"""Snapshot one reviewed component and run only its fictional-input tests."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component',required=True)
    parser.add_argument('--main-source',type=Path,required=True)
    parser.add_argument('--expected-main-sha256',required=True)
    parser.add_argument('--test',type=Path,required=True)
    parser.add_argument('--source',type=Path,action='append',default=[])
    args=parser.parse_args()
    if not re.fullmatch('[a-z0-9_]+',args.component): raise ValueError('Component ID must be a safe fixed identifier')
    main_source=(ROOT/args.main_source).resolve()
    if sha(main_source)!=args.expected_main_sha256: raise ValueError('Implementation differs from reviewed identity')
    test=(ROOT/args.test).resolve()
    if not test.is_relative_to(HERE): raise ValueError('Only independently owned synthetic tests are permitted')
    sources=sorted({Path(__file__),HERE/'conftest.py',test,main_source,*[(ROOT/p).resolve() for p in args.source]})
    if any(not p.is_relative_to(ROOT) for p in sources): raise ValueError('All source snapshots must be repository files')
    before={str(p.relative_to(ROOT)):sha(p) for p in sources}
    out=HERE/f'engineering_independent_stage2_{args.component}_20261026_v1'
    if out.exists(): raise FileExistsError('An identified receipt is immutable; select a new component/run ID')
    command=[sys.executable,'-m','pytest','-q',str(test.relative_to(ROOT))]
    plan=dict(schema='independent_B_stage2_synthetic_check_v1',component=args.component,
        frozen_utc=datetime.now(timezone.utc).isoformat(),command=command,source_sha256=before,
        reviewed_main_sha256=args.expected_main_sha256,synthetic_inputs_only=True,
        real_corpus_compilation=False,real_model_fitting=False,real_scores_or_human_answers=False,
        protocol_freeze_or_gate_override=False,environment=dict(python=platform.python_version(),
        packages={name:importlib.metadata.version(name) for name in ['pytest','numpy','pandas','scipy','scikit-learn']}))
    out.mkdir();(out/'plan_before_tests.json').write_text(json.dumps(plan,indent=2)+'\n')
    for path in sources:
        dest=out/'source_snapshot'/path.relative_to(ROOT)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    start=time.monotonic();run=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    (out/'pytest_stdout.txt').write_text(run.stdout);(out/'pytest_stderr.txt').write_text(run.stderr)
    after={str(p.relative_to(ROOT)):sha(p) for p in sources}
    result=dict(schema='independent_B_stage2_synthetic_result_v1',component=args.component,
        passed=run.returncode==0 and before==after,returncode=run.returncode,
        source_hashes_unchanged=before==after,source_sha256=after,
        elapsed_seconds=time.monotonic()-start,plan_sha256=sha(out/'plan_before_tests.json'),
        stdout_sha256=sha(out/'pytest_stdout.txt'),stderr_sha256=sha(out/'pytest_stderr.txt'),
        real_operations_executed=0,synthetic_inputs_only=True)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    if not result['passed']: raise SystemExit(run.returncode or 2)


if __name__=='__main__': main()
