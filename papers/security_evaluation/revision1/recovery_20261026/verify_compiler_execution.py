"""Read-only accounting of completed compiler-only results; never rerun tools.

Private diagnostic bytes are hashed and parsed locally. Only aggregate metadata
and hashes are emitted; no diagnostic messages, source text, ABI or AST copied.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
BASE=HERE.parent/'external_protocol'
PLAN=BASE/'compiler_preflight_v1/plan_20261026_v2'
EXPECTED_PLAN='7f5da3a7cf0a9fcef75d3b4c1f071552dca7d42dcf8fdb98855a514b90aafa80'
DIAGNOSTIC_TYPES={'ParserError','SyntaxError','TypeError','DeclarationError','CompilerError','Warning',
                 'JSONError','IOError','InternalCompilerError','UnimplementedFeatureError','DocstringParsingError'}


def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()
def read(path):return json.loads(path.read_text())
def dump(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def inspect_json_output(data,entry,attempt):
    require(isinstance(data,dict),'Compiler JSON not an object')
    diagnostics=data.get('errors',[])
    require(isinstance(diagnostics,list) and all(isinstance(d,dict) for d in diagnostics),'Malformed diagnostics')
    severity=Counter(d['severity'] for d in diagnostics)
    types=Counter(d.get('type') if d.get('type') in DIAGNOSTIC_TYPES else 'OtherDiagnostic' for d in diagnostics)
    require(dict(severity)==attempt['diagnostic_severities'],'Diagnostic severity count differs')
    require(dict(types)==attempt['diagnostic_types'],'Diagnostic type count differs')
    require(attempt['returncode']==0,'Unexpected process return code in completed actual run')
    if severity['error']:
        require(attempt['status']=='compiler_error' and attempt['success'] is False,'Errors reported as success')
        return
    require(attempt['status']=='compiler_success' and attempt['success'] is True,'Clean output success mismatch')
    ast=data['sources'][entry]['ast'];definitions={}
    nodes=ast.get('nodes',ast.get('children',[]))
    require(isinstance(nodes,list),'Malformed AST top-level nodes')
    for node in nodes:
        if node.get('nodeType',node.get('name'))=='ContractDefinition':
            attrs=node.get('attributes',node);name=attrs['name']
            require(name not in definitions,'Duplicate AST definition')
            definitions[name]=(attrs.get('contractKind')=='interface',attrs.get('abstract') is True or attrs.get('fullyImplemented') is False)
    contracts=data.get('contracts',{}).get(entry,{})
    require(set(contracts)==set(definitions),'AST declaration/output names differ')
    empty=nonempty=unlinked=missing=0
    for name,contract in contracts.items():
        require(isinstance(contract.get('abi'),list),'Requested ABI missing')
        code=contract.get('evm',{}).get('bytecode',{}).get('object')
        if code is None:
            require(any(definitions[name]),'Concrete contract bytecode missing');missing+=1
        else:
            require(isinstance(code,str),'Malformed bytecode object')
            empty+=not bool(code);nonempty+=bool(code);unlinked+='_' in code
    expected={'root_contracts':len(contracts),'interface_definitions':sum(x[0] for x in definitions.values()),
              'abstract_definitions':sum(x[1] for x in definitions.values()),'empty_bytecode_contracts':empty,
              'nonempty_bytecode_contracts':nonempty,'unlinked_bytecode_contracts':unlinked,
              'missing_bytecode_interface_or_abstract_contracts':missing}
    require(all(attempt[name]==value for name,value in expected.items()),'Contract/bytecode accounting differs')


def main():
    out=HERE/'compiler_execution_review_20261026_v1'
    require(not out.exists(),'Never overwrite an identified review run')
    start=time.monotonic();plan_path=PLAN/'plan_before_execution.json'
    require(sha(plan_path)==EXPECTED_PLAN,'Unexpected compiler plan')
    plan=read(plan_path);summary_path=PLAN/'execution_results/summary.json';results_path=PLAN/'execution_results/per_file_status.json'
    summary=read(summary_path);results=read(results_path)
    jobs_path=PLAN/'jobs.jsonl';jobs=[json.loads(line) for line in jobs_path.read_text().splitlines()]
    require(sha(jobs_path)==plan['jobs_sha256'],'Prepared jobs changed')
    require(summary['plan_sha256']==EXPECTED_PLAN,'Execution belongs to another plan')
    review=read(HERE/'compiler_plan_review_20261026_v2.json')
    require(review['status']=='pass' and review['plan_sha256']==EXPECTED_PLAN,'Pre-execution independent review mismatch')
    private=(ROOT/summary['private_diagnostic_root']).resolve()
    require(private.is_relative_to((ROOT/'data/derived').resolve()),'Diagnostics outside private derived tree')
    started=read(private/'execution_started.json')
    require(started['plan_sha256']==EXPECTED_PLAN and started['permit_sha256']==summary['permit_sha256'],'Execution start bindings differ')
    tool_path=BASE/'toolchain_v1/solc_inventory.json';tools={x['version']:x for x in read(tool_path)['releases']}
    inputs=[Path(__file__),plan_path,jobs_path,summary_path,results_path,tool_path,HERE/'compiler_plan_review_20261026_v2.json',private/'execution_started.json']
    before={str(path.relative_to(ROOT)):sha(path) for path in inputs}
    out.mkdir();shutil.copy2(Path(__file__),out/'source_before.py')
    dump(out/'plan_before_checks.json',dict(schema='read_only_completed_compiler_accounting_v1',input_sha256=before,
        compiler_reruns_permitted=False,raw_diagnostics_redistributed=False,model_or_annotation_analysis=False))
    require(len(results)==len(jobs)==summary['files']==2689,'Missing/excess completed source rows')
    require(len({r['job_id'] for r in results})==2689,'Duplicate result identity')
    actual_attempts=Counter();version_attempts=Counter();success_versions=Counter();cohorts={}
    raw_files=set();total_stdout=total_stderr=0;maximum_attempt_wall=0.
    for outcome,job in zip(results,jobs):
        for name in ('job_id','cohort','path','file_sha256','original_plan_status','preparation_status'):
            require(outcome[name]==job[name],'Result identity/order differs: '+name)
        require(read(private/(job['job_id']+'.json'))==outcome,'Private/public per-file records differ')
        attempts=outcome['attempts'];ready=job['preparation_status']=='ready_to_attempt'
        if not ready:
            require(not attempts and outcome['success'] is False and outcome['status']==job['preparation_status'],'Unavailable preparation silently changed')
        else:
            require(1<=len(attempts)<=5,'Ready file missing attempts or over cap')
            require([a['version'] for a in attempts]==job['candidate_versions'][:len(attempts)],'Candidate order/identity changed')
            require(all(not a['success'] for a in attempts[:-1]),'Attempt continued after success')
            last=attempts[-1]
            require((outcome['status'],outcome['success'])==(last['status'],last['success']),'Final outcome differs from last attempt')
            require(outcome['successful_version']==(last['version'] if last['success'] else None),'Successful version differs')
            if not outcome['success']:require(len(attempts)==len(job['candidate_versions']),'Failed file stopped before its frozen candidates')
        for index,attempt in enumerate(attempts):
            require(attempt['candidate_index']==index,'Candidate index changed')
            require(attempt['compiler_sha256']==tools[attempt['version']]['artifact_sha256'],'Compiler artifact digest differs')
            require(math.isfinite(attempt['wall_seconds']) and 0<=attempt['wall_seconds']<=plan['limits']['wall_seconds']+3,'Attempt timing outside policy')
            maximum_attempt_wall=max(maximum_attempt_wall,attempt['wall_seconds'])
            buffers={}
            for stream in ('stdout','stderr'):
                path=private/'attempts'/f"{job['job_id']}_{index:02d}_{attempt['version']}.{stream}"
                raw_files.add(path.name);require(path.stat().st_size==attempt[stream+'_bytes'],'Private diagnostic length differs')
                require(sha(path)==attempt[stream+'_sha256'],'Private diagnostic hash differs')
                require(path.stat().st_size<=plan['limits'][stream+'_bytes'],'Diagnostic byte cap exceeded')
                if stream=='stdout':buffers[stream]=path.read_bytes()
            inspect_json_output(json.loads(buffers['stdout']),job['entry_source_unit'],attempt)
            total_stdout+=attempt['stdout_bytes'];total_stderr+=attempt['stderr_bytes']
            actual_attempts[attempt['status']]+=1;version_attempts[attempt['version']]+=1
        if outcome['success']:success_versions[outcome['successful_version']]+=1
    require(raw_files=={p.name for p in (private/'attempts').iterdir() if p.is_file()},'Extra or missing private attempt output')
    require(sum(actual_attempts.values())==summary['compiler_attempts']==3514,'Attempt total differs')
    require(dict(Counter(r['status'] for r in results))==summary['status_counts'],'Summary status counts differ')
    for cohort,N in [('train',691),('external',1998)]:
        subset=[r for r in results if r['cohort']==cohort];require(len(subset)==N,'Cohort denominator changed')
        attempted=[r for r in subset if r['attempts']];success=[r for r in subset if r['success']]
        cohorts[cohort]=dict(full_files=N,attempted_files=len(attempted),compiler_success_files=len(success),
            success_fraction_full_cohort=len(success)/N,success_fraction_attempted=len(success)/len(attempted),
            status_counts=dict(Counter(r['status'] for r in subset)),
            success_without_nonempty_root_bytecode=sum(r['attempts'][-1]['nonempty_bytecode_contracts']==0 for r in success),
            success_with_unlinked_root_bytecode=sum(r['attempts'][-1]['unlinked_bytecode_contracts']>0 for r in success))
    for name,digest in {**plan['input_sha256'],**plan['source_sha256']}.items():require(sha(ROOT/name)==digest,'Frozen input/source changed after execution')
    for version in version_attempts:require(sha(ROOT/tools[version]['local_path'])==tools[version]['artifact_sha256'],'Current compiler binary changed')
    for name,pin in plan['upstream_pins'].items():
        path=ROOT/'data/raw'/name
        require(subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()==pin['commit'],'Raw source pin changed')
        require(not subprocess.check_output(['git','-C',str(path),'status','--porcelain'],text=True).strip(),'Raw source tree dirty')
    require(all(sha(ROOT/name)==digest for name,digest in before.items()),'Reviewed inputs changed during verification')
    require(not summary['annotation_files_read'] and summary['slither_executions']==summary['detectors_executed']==summary['model_scores']==summary['models_fitted']==0,'Execution scope changed')
    result=dict(status='pass',schema='independent_completed_compiler_accounting_v1',plan_sha256=EXPECTED_PLAN,
        reviewed_input_sha256=before,rows_checked=2689,attempts_checked=3514,private_output_files_hashed=len(raw_files),
        private_stdout_bytes_hashed=total_stdout,private_stderr_bytes_hashed=total_stderr,
        all_compiler_json_reclassified=True,cohorts=cohorts,attempt_status_counts=dict(actual_attempts),
        candidate_attempt_counts=dict(version_attempts),successful_version_counts=dict(success_versions),
        maximum_attempt_wall_seconds=maximum_attempt_wall,execution_wall_seconds=summary['wall_seconds'],
        verifier_wall_seconds=time.monotonic()-start,pinned_source_trees_clean=True,
        compiler_reruns=0,raw_diagnostic_text_published=False,source_annotation_or_human_labels_read=False,
        limitation='Compiler AST/ABI/unlinked-bytecode coverage under the frozen local context policy; not Slither, deployability, semantic correctness, or model eligibility. Interfaces/abstract-only files may succeed with no nonempty bytecode.')
    dump(out/'result.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
