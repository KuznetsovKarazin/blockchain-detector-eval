"""Read-only independent consistency review of the fixed compiler-only plan."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE=HERE.parent/'external_protocol'
PLAN=BASE/'compiler_preflight_v1/plan_20261026_v2'
EXPECTED='7f5da3a7cf0a9fcef75d3b4c1f071552dca7d42dcf8fdb98855a514b90aafa80'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):
    with path.open() as f:return list(csv.DictReader(f))
def require(ok,why):
    if not ok:raise ValueError(why)


def main():
    out=HERE/'compiler_plan_review_20261026_v2.json'
    require(not out.exists(),'Never overwrite the identified independent review')
    config_path=PLAN/'plan_before_execution.json';require(sha(config_path)==EXPECTED,'Plan identity differs from reviewed version')
    config=json.loads(config_path.read_text())
    for name,digest in {**config['input_sha256'],**config['source_sha256']}.items():
        require(sha(ROOT/name)==digest,'Frozen input/source changed: '+name)
    for name,digest in config['source_sha256'].items():
        require(sha(PLAN/'source_snapshot'/Path(name).name)==digest,'Source snapshot changed')
    require(sha(PLAN/'jobs.jsonl')==config['jobs_sha256'],'Job hash changed')
    jobs=[json.loads(line) for line in (PLAN/'jobs.jsonl').read_text().splitlines()]
    packet=BASE/'packet_probability_20261025_v1'
    expected=[('train',r['path'],r['file_sha256']) for r in rows(packet/'training_manifest.csv')]
    expected += [('external',r['path'],r['file_hash']) for r in rows(packet/'external_cohort_manifest.csv')]
    plans=rows(BASE/'input_readiness_20261025_v1/compiler_plans.csv')
    require(len(jobs)==len(expected)==len(plans)==2689,'Full fixed cohort differs')
    require(len({job['job_id'] for job in jobs})==2689,'Duplicate job identity')
    node_rows=rows(ROOT/'papers/security_evaluation/dependency_audit/string_aware_recovered_20261025/nodes.csv')
    raw={row['path']:(row['file_sha256'],int(row['source_bytes'])) for row in node_rows if row['dataset']=='dappscan'}
    units=0
    for job,identity,original in zip(jobs,expected,plans):
        require((job['cohort'],job['path'],job['file_sha256'])==identity,'Job identity/order changed')
        require(job['candidate_versions']==[v for v in original['candidate_versions'].split('|') if v], 'Candidate list/order changed')
        require(job['original_plan_status']==original['status'],'Original unavailable status changed')
        require(len(job['candidate_versions'])<=5,'Attempt cap changed')
        if job['cohort']=='train':
            path=Path(job['path']);require(job['context_root']==Path(*path.parts[:7]).as_posix(),'Wrong repository-snapshot context')
            require(job['entry_source_unit']==Path(*path.parts[7:]).as_posix(),'Wrong source-unit namespace')
        else:
            path=Path('data/raw/salzano')/job['path']
            require(job['context_root']==path.parent.as_posix() and job['entry_source_unit']==path.name,'External context changed')
        if job['preparation_status']=='ready_to_attempt':
            records=job['source_units'];names=[x['unit'] for x in records]
            require(job['entry_source_unit'] in names and len(set(names))==len(names)<=128,'Invalid closure identity')
            require(sum(x['bytes'] for x in records)==job['source_bytes']<=8*1024**2,'Closure byte budget')
            for source in records:
                name=Path(source['unit']);require(not name.is_absolute() and '..' not in name.parts and name.suffix=='.sol','Nonlocal closure unit')
                if job['cohort']=='train':
                    require(raw[str(Path(job['context_root'])/name)]==(source['sha256'],source['bytes']),'Closure differs from pinned node inventory')
                else:require(len(records)==1 and source['sha256']==job['file_sha256'],'External closure expanded')
            require(all(edge['importer'] in names and edge['target'] in names for edge in job['import_edges']),'Import edge outside closure')
            units+=len(records)
    counts=Counter(job['preparation_status'] for job in jobs)
    require(counts==Counter(config['preparation_counts']),'Declared preparation counts differ')
    require(sum(not job['candidate_versions'] for job in jobs)==39,'Original unavailable rows changed')
    ready_by_cohort=Counter(job['cohort'] for job in jobs if job['preparation_status']=='ready_to_attempt')
    require(ready_by_cohort=={'train':336,'external':1968},'Reviewed attemptable count changed')
    require(config['limits']['wall_seconds']==180 and config['limits']['attempts_per_file']==5,'Protocol attempt policy changed')
    require(config['standard_json_settings']=={'optimizer':{'enabled':False},'remappings':[],
            'outputSelection':{'*':{'':['ast'],'*':['abi','evm.bytecode.object']}}},'Compiler output definition changed')
    for name,pin in config['upstream_pins'].items():
        root=ROOT/'data/raw'/name
        require(subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==pin['commit'],'Raw pin changed')
        require(not subprocess.check_output(['git','-C',str(root),'status','--porcelain'],text=True).strip(),'Raw tree dirty')
    smoke=BASE/'compiler_smoke_v1/run_20261026_v1/result.json';smoke_data=json.loads(smoke.read_text())
    require(len(smoke_data['results'])==30 and all(x['success'] for x in smoke_data['results']),'Parent-authored fixture smoke incomplete')
    require({x['version'] for x in smoke_data['results']}==set(config['required_compiler_versions']),'Smoke compiler union mismatch')
    receipt=HERE/'engineering_independent_stage2_compiler_20261026_v1/result.json';test=json.loads(receipt.read_text())
    require(test['passed'] and test['source_hashes_unchanged'],'Independent tests failed or sources changed')
    require(test['source_sha256'][str(config_path.relative_to(ROOT))]==EXPECTED,'Independent test plan mismatch')
    result=dict(status='pass',scope='independent_review_of_compiler_readiness_only',plan_sha256=EXPECTED,
        reviewer_code_sha256=sha(Path(__file__)),jobs_sha256=sha(PLAN/'jobs.jsonl'),
        independent_test_receipt=str(receipt.relative_to(ROOT)),independent_test_receipt_sha256=sha(receipt),independent_tests_passed=22,
        parent_authored_smoke_receipt=str(smoke.relative_to(ROOT)),parent_authored_smoke_sha256=sha(smoke),
        source_and_input_hashes_verified=True,source_snapshots_match=True,pins_clean=True,
        fixed_jobs=2689,ready_to_attempt=dict(ready_by_cohort),original_unplanned_rows=39,
        preparation_status_counts=dict(counts),ready_source_unit_occurrences=units,
        original_order_and_candidate_policy_preserved=True,
        execution_authorized=False,corpus_compilers_executed_by_reviewer=0,
        limitations=['Review is not an end-to-end security guarantee or kernel sandbox claim.',
                     'Compiler success does not imply Slither success or semantic correctness.',
                     'The fixed two-hour work budget may leave explicit unattempted rows.',
                     'Any actual execution still requires the separate parent-authorized plan-bound permit.',
                     'Raw diagnostics remain private; only metadata/aggregate outputs may be published.'])
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
