#!/usr/bin/env python3
"""Validate frozen toolchain inputs without writes or executable invocations.

Default: read files and emit a JSON result to stdout. --receipt explicitly
creates one NEW receipt using exclusive creation; existing files are refused.
All integrity checks use exceptions and remain active under python -O.
"""
from pathlib import Path
import argparse
import collections
import csv
from datetime import datetime,timezone
import hashlib
import json
import re
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]


def require(condition,message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check_sha(path,expected):
    actual=sha(path)
    require(actual==expected,f'SHA256 mismatch for {path}: {actual} != {expected}')
    return actual


def full_version_matches(output,long_version):
    match=re.search(r'Version:\s*([^\s]+)',output)
    return bool(match and (match.group(1)==long_version or match.group(1).startswith(long_version+'.')))


def validate(metadata_root=HERE,repo_root=ROOT):
    """Return a new result in memory; never create or overwrite any file."""
    metadata_root=Path(metadata_root);repo_root=Path(repo_root)
    baseline=read(HERE/'amendment_v2/legacy_baseline.json')
    for name,expected in baseline['legacy_files_sha256'].items():
        check_sha(metadata_root/name,expected)
        check_sha(HERE/'amendment_v2/source_snapshot_v1'/name,expected)
    previous=read(metadata_root/'manifest.json')
    for name,expected in previous['output_sha256'].items():
        check_sha(metadata_root/name,expected)
    for name,expected in previous['source_and_planner_sha256'].items():
        check_sha(repo_root/name,expected)
    solc=read(metadata_root/'solc_inventory.json')
    slither=read(metadata_root/'slither_inventory.json')
    artifacts=read(metadata_root/'python_artifacts.json')
    plan_path=repo_root/'papers/security_evaluation/revision1/external_protocol/input_readiness_20261025_v1/compiler_plans.csv'
    check_sha(plan_path,solc['planner_sha256'])
    with plan_path.open() as stream:
        plans=list(csv.DictReader(stream))
    require(all(row['outside_pragma']=='False' and row['executed']=='False' for row in plans),
            'Planner records outside-pragma selection or previous execution')
    counts=collections.Counter(version for row in plans for version in row['candidate_versions'].split('|') if version)
    require(len(plans)==previous['all_source_rows'],'Source row count differs from frozen receipt')
    require(sum(bool(row['candidate_versions']) for row in plans)==previous['planned_source_rows'],
            'Planned row count differs from frozen receipt')
    require(sum(not row['candidate_versions'] for row in plans)==previous['unplanned_source_rows'],
            'Unavailable source row count differs from frozen receipt')
    require(sum(counts.values())==previous['candidate_version_slots'],'Candidate slot count changed')
    require(len(solc['releases'])==len(counts)==previous['solc_versions'],'Installed release count differs from plan union')
    require({record['version'] for record in solc['releases']}==set(counts),'Installed version set differs from plan union')
    private=repo_root/previous['private_artifact_root']
    check_sha(private/'solc-list.json',solc['official_list_sha256'])
    catalog=read(private/'solc-list.json')
    for record in solc['releases']:
        version=record['version'];path=repo_root/record['local_path']
        require(record['sha256']==record['artifact_sha256'],f'Conflicting artifact hash for {version}')
        check_sha(path,record['sha256'])
        require(path.stat().st_size==record['artifact_bytes'],f'Artifact length mismatch for {version}')
        builds=[item for item in catalog['builds'] if item['path']==catalog['releases'][version]]
        require(len(builds)==1,f'Official build selection is not unique for {version}')
        official=builds[0]
        require(official['version']==version and 'prerelease' not in official,f'Not an official release: {version}')
        require(official['sha256'].removeprefix('0x')==record['sha256'],f'Official digest mismatch for {version}')
        require(official['longVersion']==record['long_version'],f'Official build identifier mismatch for {version}')
        probe=record['version_probe']
        require(probe['argv']==[record['local_path'],'--version'] and probe['returncode']==0,
                f'Unexpected recorded tool command or exit status for {version}')
        require(full_version_matches(probe['stdout']+probe['stderr'],record['long_version']),
                f'Full executable build identity mismatch for {version}')
    lock_hash=check_sha(metadata_root/'requirements.lock',slither['dependency_lock_sha256'])
    require(lock_hash==artifacts['lock_sha256'],'Dependency lock hash differs between manifests')
    check_sha(metadata_root/'python_artifacts.json',slither['python_artifact_manifest_sha256'])
    check_sha(metadata_root/'installed_freeze.txt',slither['installed_freeze_sha256'])
    check_sha(repo_root/slither['executable'],slither['executable_sha256'])
    require(len(artifacts['artifacts'])==previous['locked_python_wheels'],'Wheel count changed')
    for record in artifacts['artifacts']:
        check_sha(repo_root/record['local_path'],record['artifact_sha256'])
    probe=slither['version_probe']
    require(probe['argv']==[slither['executable'],'--version'],'Unexpected recorded Slither command')
    require(probe['stdout'].strip()==previous['slither_version'] and probe['returncode']==0,
            'Slither recorded version or exit status mismatch')
    cfg=(repo_root/slither['python_env']/'pyvenv.cfg').read_text()
    require('include-system-site-packages = false' in cfg,'Python environment is not isolated')
    require(solc['compiler_executions_on_sources']==slither['contract_analyses']==0,'Recorded source execution is nonzero')
    require(previous['model_scoring'] is False and previous['external_readiness_or_semantic_signoff'] is False,
            'Original scientific readiness boundary changed')
    return {'schema':'toolchain_reverification_receipt_v2','status':'pass',
            'verified_utc':datetime.now(timezone.utc).isoformat(),
            'verifier_sha256':sha(Path(__file__)),'python_optimization_level':sys.flags.optimize,
            'legacy_manifest_sha256':sha(metadata_root/'manifest.json'),
            'legacy_baseline_sha256':sha(HERE/'amendment_v2/legacy_baseline.json'),
            'legacy_receipt_rewritten':False,'validation_files_written':0,
            'solc_artifacts_checked':len(solc['releases']),'python_wheels_checked':len(artifacts['artifacts']),
            'artifact_and_metadata_hashes_match':True,'recorded_full_solc_build_identifiers_match':True,
            'tool_invocations_in_this_verification':0,'compilations':0,'slither_analyses':0,
            'external_readiness_or_semantic_signoff':False,
            'verification_scope':'Read-only revalidation against frozen metadata and artifact bytes; no fresh tool execution or network access'}


def write_new_receipt(path,result):
    """An explicit opt-in write, separate from validation; never overwrite."""
    try:
        with Path(path).open('x') as stream:
            json.dump({**result,'receipt_write':'explicit_exclusive_create'},stream,indent=2)
            stream.write('\n')
    except FileExistsError as exc:
        raise ValueError(f'Refusing to overwrite an existing receipt: {path}') from exc


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-root',type=Path,default=HERE)
    parser.add_argument('--repo-root',type=Path,default=ROOT)
    parser.add_argument('--receipt',type=Path,help='Explicitly create a new receipt; existing path is refused')
    args=parser.parse_args(argv)
    try:
        result=validate(args.metadata_root,args.repo_root)
        if args.receipt is not None:
            write_new_receipt(args.receipt,result)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'failed','error':str(exc)}),file=sys.stderr)
        return 1
    print(json.dumps(result,indent=2))
    return 0


if __name__=='__main__':sys.exit(main())
