#!/usr/bin/env python3
"""Provision an isolated verified executable inventory; version probes only.

No Solidity source is passed to any tool. No compilation or static-analysis
command is implemented. Public outputs are metadata; artifacts stay ignored.
"""
from pathlib import Path
import argparse,collections,concurrent.futures,csv,email,hashlib,json,os,platform,re,subprocess,sys,urllib.request,zipfile
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
PRIVATE=ROOT/'data/derived/security_toolchain_v1'
PLANS=ROOT/'papers/security_evaluation/revision1/external_protocol/input_readiness_20261025_v1/compiler_plans.csv'
SOLC_REPOSITORY='argotorg/solc-bin'
SLITHER='0.11.6'
SLITHER_WHEEL_SHA='01f809198d3f171e2d768569c0054c96af5736614e183c64f42c9b51636c33c1'

def utc():return datetime.now(timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'security-evaluation-toolchain-inventory/1'})
    with urllib.request.urlopen(request,timeout=60) as response:return response.read(),response.url

def required_versions(path):
    rows=list(csv.DictReader(Path(path).open()))
    versions=collections.Counter(v for row in rows for v in row['candidate_versions'].split('|') if v)
    assert all(row['outside_pragma']=='False' and row['executed']=='False' for row in rows)
    return rows,versions

def verify_digest(data,expected):
    actual=hashlib.sha256(data).hexdigest()
    if actual!=expected.removeprefix('0x'):raise ValueError(f'SHA256 mismatch: {actual} != {expected}')
    return actual

def version_probe(binary,expected,kind):
    # This is the only tool invocation in the module, and it accepts no target.
    result=subprocess.run([str(binary),'--version'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,check=True)
    output=result.stdout+result.stderr
    if kind=='solc':
        matched=re.search(r'Version:\s*([^\s]+)',output)
        if not matched or matched.group(1).split('+')[0]!=expected:raise ValueError(output)
    elif kind=='slither':
        if output.strip()!=expected:raise ValueError(output)
    else:raise ValueError(kind)
    return {'argv':[str(binary.relative_to(ROOT)),'--version'],'returncode':result.returncode,
            'stdout':result.stdout,'stderr':result.stderr,'executed_utc':utc()}

def provision_solc():
    PRIVATE.mkdir(parents=True,exist_ok=True);bins=PRIVATE/'solc';bins.mkdir(exist_ok=True)
    rows,counts=required_versions(PLANS)
    api=f'https://api.github.com/repos/{SOLC_REPOSITORY}/commits/gh-pages'
    commit_bytes,_=fetch(api);commit=json.loads(commit_bytes)['sha']
    base=f'https://raw.githubusercontent.com/{SOLC_REPOSITORY}/{commit}/linux-amd64'
    index,index_url=fetch(base+'/list.json');catalog=json.loads(index)
    (PRIVATE/'solc-list.json').write_bytes(index)
    releases=[]
    for version in sorted(counts,key=lambda v:tuple(map(int,v.split('.')))):
        path=catalog['releases'][version]
        matches=[entry for entry in catalog['builds'] if entry['path']==path and entry['version']==version]
        assert len(matches)==1 and 'prerelease' not in matches[0]
        entry=matches[0]
        releases.append({'version':version,'official_path':path,'long_version':entry['longVersion'],
                         'sha256':entry['sha256'].removeprefix('0x'),'keccak256_official':entry['keccak256'],
                         'download_url':base+'/'+path,'candidate_plan_slots':counts[version]})
    frozen={'schema':'verified_solc_inventory_v1','prepared_utc':utc(),'platform':'linux-amd64',
            'required_versions_only':True,'planner_sha256':sha(PLANS),'source_rows':len(rows),
            'planned_rows':sum(bool(row['candidate_versions']) for row in rows),'candidate_version_slots':sum(counts.values()),
            'official_repo':f'https://github.com/{SOLC_REPOSITORY}','official_repo_commit':commit,
            'official_list_url':index_url,'official_list_sha256':hashlib.sha256(index).hexdigest(),
            'metadata_api_url':api,'metadata_api_sha256':hashlib.sha256(commit_bytes).hexdigest(),
            'primary_mirror_observation':'https://binaries.soliditylang.org/linux-amd64/list.json returned HTTP403; used official repository linked by Solidity documentation',
            'documentation_url':'https://docs.soliditylang.org/en/latest/installing-solidity.html#static-binaries',
            'releases':releases,'execution_scope':'--version only; no contract processing'}
    dump(HERE/'solc_download_plan.json',frozen)
    def one(record):
        dest=bins/('solc-'+record['version'])
        if dest.exists():verify_digest(dest.read_bytes(),record['sha256'])
        else:
            data,final_url=fetch(record['download_url']);verify_digest(data,record['sha256'])
            dest.write_bytes(data)
        dest.chmod(0o755)
        probe=version_probe(dest,record['version'],'solc')
        return {**record,'local_path':str(dest.relative_to(ROOT)),'artifact_bytes':dest.stat().st_size,
                'artifact_sha256':sha(dest),'checksum_verified':True,'version_probe':probe}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        completed=list(pool.map(one,releases))
    result={**frozen,'status':'verified_version_inventory_only','completed_utc':utc(),'installed_versions':len(completed),
            'download_plan_sha256':sha(HERE/'solc_download_plan.json'),'releases':completed,'compiler_executions_on_sources':0}
    dump(HERE/'solc_inventory.json',result);print('verified solc versions',len(completed),flush=True)

def provision_slither():
    wheels=sorted((PRIVATE/'wheelhouse').glob('*.whl'))
    if not wheels:raise ValueError('First use official PyPI pip download, wheels only, as documented')
    def one(path):
        with zipfile.ZipFile(path) as archive:
            meta=[name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
            assert len(meta)==1
            metadata=email.message_from_bytes(archive.read(meta[0]));name=metadata['Name'];version=metadata['Version']
        url=f'https://pypi.org/pypi/{name}/{version}/json';body,final=fetch(url);record=json.loads(body)
        matches=[item for item in record['urls'] if item['filename']==path.name]
        assert len(matches)==1 and matches[0]['packagetype']=='bdist_wheel' and not matches[0]['yanked']
        item=matches[0];verify_digest(path.read_bytes(),item['digests']['sha256'])
        if name.lower().replace('_','-')=='slither-analyzer':assert version==SLITHER and sha(path)==SLITHER_WHEEL_SHA
        return {'package':name,'version':version,'filename':path.name,'download_url':item['url'],
                'artifact_sha256':sha(path),'artifact_bytes':path.stat().st_size,
                'pypi_metadata_url':final,'pypi_metadata_sha256':hashlib.sha256(body).hexdigest(),
                'requires_python':item['requires_python'],'checksum_verified':True,'local_path':str(path.relative_to(ROOT))}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:artifacts=list(pool.map(one,wheels))
    artifacts.sort(key=lambda row:row['package'].lower())
    assert sum(row['package'].lower().replace('_','-')=='slither-analyzer' for row in artifacts)==1
    lock=''.join(f"{row['package']}=={row['version']} --hash=sha256:{row['artifact_sha256']}\n" for row in artifacts)
    (HERE/'requirements.lock').write_text(lock)
    dump(HERE/'python_artifacts.json',{'status':'official_pypi_artifact_hashes_verified','recorded_utc':utc(),
         'resolution':'pip download --only-binary=:all: --index-url https://pypi.org/simple slither-analyzer==0.11.6',
         'artifacts':artifacts,'lock_sha256':sha(HERE/'requirements.lock')})
    env=PRIVATE/'python_env'
    if not env.exists():subprocess.run([sys.executable,'-m','venv',str(env)],check=True)
    py=env/'bin/python'
    subprocess.run([str(py),'-m','pip','install','--disable-pip-version-check','--no-index','--find-links',str(PRIVATE/'wheelhouse'),
                    '--require-hashes','-r',str(HERE/'requirements.lock')],check=True,stdout=(PRIVATE/'pip_install.log').open('w'),stderr=subprocess.STDOUT)
    check=subprocess.run([str(py),'-m','pip','check'],check=True,capture_output=True,text=True)
    frozen=subprocess.check_output([str(py),'-m','pip','freeze','--all'],text=True)
    (HERE/'installed_freeze.txt').write_text(frozen)
    binary=env/'bin/slither';probe=version_probe(binary,SLITHER,'slither')
    actual=json.loads(subprocess.check_output([str(py),'-c','import importlib.metadata as m,json;print(json.dumps({d.metadata["Name"]:d.version for d in m.distributions()}))'],text=True))
    for item in artifacts:assert actual[item['package']]==item['version']
    dump(HERE/'slither_inventory.json',{'status':'verified_version_inventory_only','completed_utc':utc(),
        'slither_version':SLITHER,'executable':str(binary.relative_to(ROOT)),'executable_sha256':sha(binary),
        'python_env':str(env.relative_to(ROOT)),'python_version':subprocess.check_output([str(py),'--version'],text=True).strip(),
        'python_executable_sha256':sha(py.resolve()),'platform':platform.platform(),'machine':platform.machine(),
        'dependency_artifacts':len(artifacts),'dependency_lock_sha256':sha(HERE/'requirements.lock'),
        'python_artifact_manifest_sha256':sha(HERE/'python_artifacts.json'),'installed_freeze_sha256':sha(HERE/'installed_freeze.txt'),
        'pip_check_stdout':check.stdout,'version_probe':probe,'contract_analyses':0,
        'provenance_scope':'Artifact SHA256 verified against official PyPI JSON. PyPI reports Trusted Publishing for the Slither release; no independent Sigstore verification performed.',
        'primary_project_url':'https://pypi.org/project/slither-analyzer/0.11.6/'})
    print('verified Slither',SLITHER,'with',len(artifacts),'locked wheels',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['solc','slither']);args=parser.parse_args()
    if platform.machine()!='x86_64' or platform.system()!='Linux':raise RuntimeError('This inventory is Linux x86_64 only')
    (provision_solc if args.action=='solc' else provision_slither)()
