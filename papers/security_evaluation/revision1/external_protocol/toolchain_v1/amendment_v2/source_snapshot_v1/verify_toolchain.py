#!/usr/bin/env python3
"""Read-only verification of the provisioned inventory; executes no tool."""
from pathlib import Path
import csv,hashlib,json,re,sys
from datetime import datetime,timezone
from provision_toolchain import HERE,ROOT,PRIVATE,PLANS,required_versions,sha

def full_version_matches(output,long_version):
    match=re.search(r'Version:\s*([^\s]+)',output)
    return bool(match and (match.group(1)==long_version or match.group(1).startswith(long_version+'.')))

def validate():
    solc=json.loads((HERE/'solc_inventory.json').read_text());slither=json.loads((HERE/'slither_inventory.json').read_text())
    artifacts=json.loads((HERE/'python_artifacts.json').read_text())
    plans,counts=required_versions(PLANS)
    assert sha(PLANS)==solc['planner_sha256']
    assert len(solc['releases'])==len(counts)==30
    assert {record['version'] for record in solc['releases']}==set(counts)
    assert sha(PRIVATE/'solc-list.json')==solc['official_list_sha256']
    catalog=json.loads((PRIVATE/'solc-list.json').read_text())
    for record in solc['releases']:
        path=ROOT/record['local_path'];assert sha(path)==record['sha256']==record['artifact_sha256']
        assert path.stat().st_size==record['artifact_bytes']
        official=next(item for item in catalog['builds'] if item['path']==catalog['releases'][record['version']])
        assert official['sha256'].removeprefix('0x')==record['sha256']
        assert official['longVersion']==record['long_version']
        probe=record['version_probe'];assert probe['argv']==[record['local_path'],'--version'] and probe['returncode']==0
        assert full_version_matches(probe['stdout']+probe['stderr'],record['long_version']),record['version']
    assert sha(HERE/'requirements.lock')==slither['dependency_lock_sha256']==artifacts['lock_sha256']
    assert sha(HERE/'python_artifacts.json')==slither['python_artifact_manifest_sha256']
    assert sha(HERE/'installed_freeze.txt')==slither['installed_freeze_sha256']
    assert sha(ROOT/slither['executable'])==slither['executable_sha256']
    for record in artifacts['artifacts']:
        assert sha(ROOT/record['local_path'])==record['artifact_sha256']
    assert slither['version_probe']['argv']==[slither['executable'],'--version']
    assert slither['version_probe']['stdout'].strip()=='0.11.6' and slither['version_probe']['returncode']==0
    cfg=(ROOT/slither['python_env']/'pyvenv.cfg').read_text()
    assert 'include-system-site-packages = false' in cfg
    assert solc['compiler_executions_on_sources']==slither['contract_analyses']==0
    rows=[]
    for version in sorted(counts,key=lambda v:tuple(map(int,v.split('.')))):
        record=next(item for item in solc['releases'] if item['version']==version)
        rows.append({'version':version,'candidate_slots':counts[version],
            'train_candidate_slots':sum(row['cohort']=='train' and version in row['candidate_versions'].split('|') for row in plans),
            'external_candidate_slots':sum(row['cohort']=='external' and version in row['candidate_versions'].split('|') for row in plans),
            'artifact_sha256':record['artifact_sha256'],'full_version_identity_verified':True})
    with (HERE/'required_version_inventory.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    sources=[HERE/'provision_toolchain.py',Path(__file__),ROOT/'papers/security_evaluation/revision1/external_protocol/compiler_policy.py',PLANS]
    data=[HERE/name for name in ['solc_download_plan.json','solc_inventory.json','python_artifacts.json','requirements.lock','installed_freeze.txt','slither_inventory.json','required_version_inventory.csv']]
    result={'schema':'external_toolchain_inventory_manifest_v1','status':'verified_executable_inventory_only',
        'verified_utc':datetime.now(timezone.utc).isoformat(),'execution_permission':'version probes only',
        'solc_versions':30,'slither_version':'0.11.6','locked_python_wheels':len(artifacts['artifacts']),
        'all_official_checksums_match':True,'all_full_solc_build_identifiers_match':True,
        'planned_source_rows':2650,'all_source_rows':2689,'candidate_version_slots':3900,
        'unplanned_source_rows':39,'unplanned_rows_remain_unavailable':True,
        'compiler_plan_candidate_order_unchanged':True,'isolated_python_without_system_site_packages':True,
        'compiler_executions_on_sources':0,'slither_analyses':0,'model_scoring':False,
        'compilation_success_coverage_established':False,'external_readiness_or_semantic_signoff':False,
        'private_artifact_root':str(PRIVATE.relative_to(ROOT)),
        'source_and_planner_sha256':{str(path.relative_to(ROOT)):sha(path) for path in sources},
        'output_sha256':{path.name:sha(path) for path in data},
        'limitations':['File pragma plans do not establish imported dependency compatibility.',
                       'Version probes do not establish successful compilation or detector execution.',
                       'Linux x86_64 and Python3.12 wheel environment only; no universal platform lock.',
                       'PyPI artifact checksums checked; independent Sigstore verification was not performed.']}
    (HERE/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(validate(),indent=2))
