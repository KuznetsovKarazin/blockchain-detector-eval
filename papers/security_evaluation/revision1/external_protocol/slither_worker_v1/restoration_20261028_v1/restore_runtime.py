"""Restore exact published binary/wheel artifacts; no contract inputs or analysis."""
from pathlib import Path
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import urllib.request

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[5]
METADATA=HERE.parents[1]/'toolchain_v1'
PRIVATE=ROOT/'data/derived/security_toolchain_v1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(ok,text):
    if not ok:raise ValueError(text)
def dump_new(p,value):
    with Path(p).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
def utc():return datetime.now(timezone.utc).isoformat()

def main():
    original_names=['manifest.json','solc_download_plan.json','solc_inventory.json','python_artifacts.json','requirements.lock','installed_freeze.txt','slither_inventory.json']
    originals={n:sha(METADATA/n) for n in original_names}
    slither=read(METADATA/'slither_inventory.json');solc=read(METADATA/'solc_inventory.json');wheels=read(METADATA/'python_artifacts.json')['artifacts']
    need(sha(Path(sys.executable).resolve())==slither['python_executable_sha256'],'Original interpreter digest unavailable')
    need(len(solc['releases'])==30 and len(wheels)==47,'Pinned artifact counts differ')
    need(not (HERE/'restoration_before_downloads.json').exists(),'Preserve existing restoration record; no overwrite')
    plan={'schema':'pinned_tool_runtime_restoration_plan_v1','prepared_utc':utc(),'script_sha256':sha(__file__),
          'original_metadata_sha256':originals,'python_executable':str(Path(sys.executable).resolve()),'python_sha256':sha(Path(sys.executable).resolve()),
          'source': 'Published immutable artifact URLs and SHA256 only; no resolution or metadata regeneration',
          'solc_count':30,'wheel_count':47,'actual_corpus_inputs':0,'compiler_analysis_invocations':0,'Slither_analysis_invocations':0}
    dump_new(HERE/'restoration_before_downloads.json',plan)
    PRIVATE.mkdir(parents=True,exist_ok=True)
    jobs=[{'download_url':solc['official_list_url'],'local_path':str((PRIVATE/'solc-list.json').relative_to(ROOT)),
           'artifact_sha256':solc['official_list_sha256'],'kind':'compiler_catalog'}]
    jobs += [dict(r,kind='solc') for r in solc['releases']]
    jobs += [dict(r,kind='wheel') for r in wheels]
    def restore(record):
        path=ROOT/record['local_path'];path.parent.mkdir(parents=True,exist_ok=True)
        downloaded=False
        if not path.exists():
            request=urllib.request.Request(record['download_url'],headers={'User-Agent':'security-evaluation-exact-recovery/1'})
            with urllib.request.urlopen(request,timeout=60) as response:data=response.read()
            need(hashlib.sha256(data).hexdigest()==record['artifact_sha256'],'Downloaded artifact digest mismatch: '+path.name)
            if 'artifact_bytes' in record:need(len(data)==record['artifact_bytes'],'Artifact byte length mismatch')
            with path.open('xb') as f:f.write(data)
            downloaded=True
        need(sha(path)==record['artifact_sha256'],'Existing artifact digest mismatch: '+path.name)
        if record['kind']=='solc':path.chmod(0o755)
        return {'path':record['local_path'],'sha256':sha(path),'bytes':path.stat().st_size,'downloaded':downloaded,'kind':record['kind']}
    outputs=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(restore,jobs):
            outputs.append(result);print('verified',len(outputs),result['kind'],Path(result['path']).name,flush=True)
    dump_new(HERE/'download_verification.json',{'completed_utc':utc(),'artifacts':outputs,'original_metadata_unchanged':all(sha(METADATA/n)==h for n,h in originals.items())})
    env=ROOT/slither['python_env'];py=env/'bin/python'
    need(not env.exists(),'Do not overwrite an existing Python environment')
    subprocess.run([sys.executable,'-m','venv',str(env)],check=True)
    with (HERE/'pip_install.log').open('x') as log:
        subprocess.run([str(py),'-m','pip','install','--disable-pip-version-check','--no-index','--find-links',str(PRIVATE/'wheelhouse'),
                        '--require-hashes','-r',str(METADATA/'requirements.lock')],stdout=log,stderr=subprocess.STDOUT,check=True)
    check=subprocess.run([str(py),'-m','pip','check'],check=True,capture_output=True,text=True)
    freeze=subprocess.check_output([str(py),'-m','pip','freeze','--all'],text=True)
    need(freeze==(METADATA/'installed_freeze.txt').read_text(),'Installed distribution freeze differs')
    need(sha(ROOT/slither['executable'])==slither['executable_sha256'],'Installed Slither entry executable differs')
    need(sha(py.resolve())==slither['python_executable_sha256'],'Installed interpreter differs')
    for name,digest in originals.items():need(sha(METADATA/name)==digest,'Original metadata changed: '+name)
    worker=HERE.parent/'worker.py';spec=importlib.util.spec_from_file_location('restored_slither_worker',worker);module=importlib.util.module_from_spec(spec)
    exec(compile(worker.read_bytes(),str(worker),'exec'),module.__dict__)
    runtime=module.runtime_inventory()
    dump_new(HERE/'runtime_inventory.json',runtime)
    dump_new(HERE/'restoration_result.json',{'status':'pinned_runtime_restored','completed_utc':utc(),'plan_sha256':sha(HERE/'restoration_before_downloads.json'),
        'script_sha256':sha(__file__),'original_metadata_sha256':originals,'original_metadata_unchanged':True,'artifact_count':len(outputs),
        'solc_count':30,'wheel_count':47,'installed_distributions':len(runtime['installed_distributions']),'installed_file_hashes':len(runtime['files']),
        'runtime_inventory_sha256':sha(HERE/'runtime_inventory.json'),'pip_check':check.stdout,'slither_entry_sha256':sha(ROOT/slither['executable']),
        'python_executable_sha256':sha(py.resolve()),'actual_corpus_inputs':0,'compiler_analysis_invocations':0,'Slither_analysis_invocations':0})
    print('Restored exact pinned runtime; no contract analysis.',flush=True)

if __name__=='__main__':main()
