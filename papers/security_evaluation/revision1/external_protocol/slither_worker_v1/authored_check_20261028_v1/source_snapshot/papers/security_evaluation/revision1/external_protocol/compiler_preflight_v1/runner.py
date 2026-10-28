#!/usr/bin/env python3
"""Compiler-only preflight preparation/execution; corpus execution needs permit.

No Slither, detectors, labels, models, package installation or network imports.
Preparation only reads pinned sources and emits metadata. Execution is a separate
command requiring an explicit plan-bound reviewed permit; none is supplied here.
"""
from pathlib import Path
import argparse,collections,csv,hashlib,json,math,os,resource,selectors,shutil,signal,subprocess,sys,tempfile,time
from datetime import datetime,timezone
from imports import ROOT,HERE,ImportFailure,SolidityScanError,closure,check_local_source

BASE=HERE.parent
PACKET=BASE/'packet_probability_20261025_v1'
PLANS=BASE/'input_readiness_20261025_v1/compiler_plans.csv'
NODES=ROOT/'papers/security_evaluation/dependency_audit/string_aware_recovered_20261025/nodes.csv'
TOOLCHAIN=BASE/'toolchain_v1'
LIMITS={'wall_seconds':180,'cpu_seconds':180,'memory_bytes':2*1024**3,
        'stdout_bytes':16*1024**2,'stderr_bytes':1024**2,'input_bytes':16*1024**2,
        'open_files':64,'max_sources':128,'source_bytes':8*1024**2,
        'attempts_per_file':5,'total_run_wall_seconds':7200}
SETTINGS={'optimizer':{'enabled':False},'remappings':[],
          'outputSelection':{'*':{'':['ast'],'*':['abi','evm.bytecode.object']}}}
PINS={'DAppSCAN':'66a56619c44770e05c2db600fa6468115ff0dcd5','salzano':'da079440bf2cf4fd803c864ef29aeea8a3da50c3'}


def require(ok,message):
    if not ok:raise ValueError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def utc():return datetime.now(timezone.utc).isoformat()
def csvrows(path):
    with Path(path).open() as stream:return list(csv.DictReader(stream))
def dump_new(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2,sort_keys=True);stream.write('\n')
def hash_check(path,want):require(sha(path)==want,'Hash mismatch: '+str(path))


def fixed_inputs():
    return [PLANS,PACKET/'training_manifest.csv',PACKET/'external_cohort_manifest.csv',
            NODES,TOOLCHAIN/'manifest.json',TOOLCHAIN/'solc_inventory.json',
            BASE/'PROTOCOL_B.md',BASE/'protocol_B_draft.json',BASE/'validate_gate.py']


def verify_pins():
    result={}
    for name,want in PINS.items():
        path=ROOT/'data/raw'/name
        head=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        dirty=subprocess.check_output(['git','-C',str(path),'status','--porcelain'],text=True).strip()
        require(head==want and not dirty,'Pinned raw checkout changed: '+name)
        result[name]={'commit':head,'clean':True}
    return result


def context_for(cohort,path):
    if cohort=='train':
        parts=Path(path).parts
        require(parts[:5]==('data','raw','DAppSCAN','DAppSCAN-source','contracts') and len(parts)>=8,
                'Training path does not identify the declared audit-project/repo-snapshot context')
        root=ROOT/Path(*parts[:7]);unit=Path(*parts[7:]).as_posix()
    elif cohort=='external':
        local=ROOT/'data/raw/salzano'/path;root=local.parent;unit=local.name
    else:raise ValueError('Unknown cohort')
    return root,unit


def prepare(out,private_root):
    out=Path(out).resolve();private_root=Path(private_root).resolve()
    require(not out.exists(),'Output plan already exists')
    require(private_root.is_relative_to(ROOT/'data/derived'),'Private outputs must remain under ignored data/derived')
    source_paths=[Path(__file__),HERE/'imports.py',ROOT/'papers/security_evaluation/normalization_audit/solidity_scanner.py']
    source_hashes={str(p.relative_to(ROOT)):sha(p) for p in source_paths}
    pins=verify_pins();inputs={str(p.relative_to(ROOT)):sha(p) for p in fixed_inputs()}
    out.mkdir(parents=True);snapshots=out/'source_snapshot';snapshots.mkdir()
    for path in source_paths:
        shutil.copyfile(path,snapshots/path.name);hash_check(snapshots/path.name,source_hashes[str(path.relative_to(ROOT))])
    dump_new(out/'preparation_started.json',{'prepared_utc':utc(),'stage':'metadata_preparation_only',
        'source_sha256_before_enumeration':source_hashes,'input_sha256_before_enumeration':inputs,
        'limits':LIMITS,'standard_json_settings':SETTINGS,'compiler_executions':0})
    protocol=read(BASE/'protocol_B_draft.json')
    require(protocol['external_scoring_allowed'] is False and protocol['model_fitting_allowed'] is False,
            'Original external scoring/fitting boundary is no longer the reviewed draft state')
    previous=read(TOOLCHAIN/'manifest.json');solc=read(TOOLCHAIN/'solc_inventory.json')
    hash_check(TOOLCHAIN/'solc_inventory.json',previous['output_sha256']['solc_inventory.json'])
    tools={r['version']:r for r in solc['releases']}
    for record in tools.values():hash_check(ROOT/record['local_path'],record['artifact_sha256'])
    train=csvrows(PACKET/'training_manifest.csv');external=csvrows(PACKET/'external_cohort_manifest.csv')
    require(len(train)==691 and len(external)==1998,'Fixed cohort size changed')
    expected=[('train',r['path'],r['file_sha256']) for r in train]+[('external',r['path'],r['file_hash']) for r in external]
    plans=csvrows(PLANS)
    require([(r['cohort'],r['path']) for r in plans]==[(c,p) for c,p,h in expected],'Plan ordering differs from fixed manifests')
    require(all(r['outside_pragma']=='False' and r['executed']=='False' for r in plans),'Original compiler planning flags changed')
    full=csvrows(NODES);context_indexes=collections.defaultdict(lambda:collections.defaultdict(list))
    for row in full:
        if row['dataset']=='dappscan':
            parts=Path(row['path']).parts
            if len(parts)>=8:context_indexes[Path(*parts[:7]).as_posix()][Path(*parts[7:]).as_posix()].append(row['file_sha256'])
    jobs=[];closure_cache={}
    for i,((cohort,path,digest),row) in enumerate(zip(expected,plans)):
        root,entry=context_for(cohort,path)
        local=ROOT/path if cohort=='train' else ROOT/'data/raw/salzano'/path
        hash_check(local,digest)
        versions=[v for v in row['candidate_versions'].split('|') if v]
        require(len(versions)<=LIMITS['attempts_per_file'] and len(set(versions))==len(versions),'Invalid candidate sequence')
        require(all(v in tools for v in versions),'Required compiler not inventoried')
        job={'job_id':f'compile_{i:04d}','cohort':cohort,'path':path,'file_sha256':digest,
             'context_root':str(root.relative_to(ROOT)),'entry_source_unit':entry,
             'candidate_versions':versions,'original_plan_status':row['status'],
             'preparation_status':row['status'] if not versions else 'ready_to_attempt',
             'source_units':[],'import_edges':[],'source_bytes':0,'detail_sha256':''}
        if versions:
            if cohort=='train':
                pinned=context_indexes[str(root.relative_to(ROOT))]
            else:pinned={entry:digest}
            try:job.update(closure(root,entry,pinned,external=cohort=='external',max_sources=LIMITS['max_sources'],max_bytes=LIMITS['source_bytes'],cache=closure_cache))
            except (ImportFailure,SolidityScanError) as exc:
                job['preparation_status']=getattr(exc,'status','source_scanner_error')
                job['detail_sha256']=hashlib.sha256(str(exc).encode()).hexdigest()
        jobs.append(job)
        if (i+1)%500==0:print(f'Prepared source/import metadata {i+1}/{len(expected)}; compilers executed=0',flush=True)
    require(sum(not j['candidate_versions'] for j in jobs)==39,'Unplanned cohort rows changed')
    for name,want in {**source_hashes,**inputs}.items():hash_check(ROOT/name,want)
    verify_pins()
    with (out/'jobs.jsonl').open('x') as stream:
        for job in jobs:stream.write(json.dumps(job,sort_keys=True)+'\n')
    config={'schema':'compiler_only_preflight_plan_v1','prepared_utc':utc(),'stage':'prepared_not_executed',
        'execution_requires_separate_reviewed_permit':True,'private_work_root':str(private_root.relative_to(ROOT)),
        'cohort_counts':{'train':691,'external':1998},'plan_rows':2689,'unplanned_rows_preserved':39,
        'required_compiler_versions':sorted({v for j in jobs for v in j['candidate_versions']},key=lambda v:tuple(map(int,v.split('.')))),
        'limits':LIMITS,'standard_json_settings':SETTINGS,'compiler_args':['--standard-json','--allow-paths','<fresh-pinned-only-workspace>'],
        'stop_after_first_success':True,'diagnostic_reruns':0,'outside_pragma_fallback':False,
        'compiler_scope':'AST, ABI and unlinked bytecode generation with optimizer disabled; compiler-default EVM target; not Slither or deployment success',
        'context_policy':{'train':'Exact DAppSCAN audit-project/repo-snapshot root from pinned source paths; no sibling snapshot or project rescue',
                          'external':'Single source only; an import of another file has no verified project context and is unavailable',
                          'relative_imports':'Canonical relative VFS path within declared root',
                          'direct_imports':'Exact canonical source-unit path relative to declared root; no inferred npm/remappings',
                          'ambiguous_imports':'Fail closed if an exact source-unit key has multiple candidates',
                          'network_or_absolute_imports':'Rejected before execution; Standard JSON has contents only, no URLs',
                          'filesystem':'Fresh copies of verified closure only; symlink/path escape rejected; solc allow-paths restricted to workspace',
                          'kernel_sandbox':'Not claimed; Landlock query ENOSYS and bwrap namespace setup denied in this runtime'},
        'annotation_files_read':False,'human_judgments_read':False,'model_scores_read':False,'compilers_executed':0,
        'slither_executed':False,'detectors_executed':False,'models_fitted':False,'protocol_score_gate_changed':False,
        'no_outcome_driven_cohort_changes':True,'input_sha256':inputs,'upstream_pins':pins,
        'source_sha256':source_hashes,'jobs_sha256':sha(out/'jobs.jsonl'),
        'preparation_counts':dict(collections.Counter(j['preparation_status'] for j in jobs))}
    dump_new(out/'plan_before_execution.json',config)
    dump_new(out/'execution_permit.template.json',{'approved':False,'scope':'compiler_readiness_only',
        'plan_sha256':sha(out/'plan_before_execution.json'),'independent_review_receipt':'',
        'independent_review_sha256':'','parent_authorization_reference':'',
        'note':'Template is not permission; root and independent review must approve the concrete frozen runner/plan before corpus compilation'})
    print(json.dumps({'plan_sha256':sha(out/'plan_before_execution.json'),'preparation_counts':config['preparation_counts'],'compilers_executed':0},indent=2))


def limited_process(argv,stdin_path,cwd,limits):
    """Bounded subprocess primitive; production caller supplies verified solc only."""
    def child_limits():
        resource.setrlimit(resource.RLIMIT_AS,(limits['memory_bytes'],limits['memory_bytes']))
        resource.setrlimit(resource.RLIMIT_CPU,(limits['cpu_seconds'],limits['cpu_seconds']+1))
        resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_NOFILE,(limits['open_files'],limits['open_files']))
        resource.setrlimit(resource.RLIMIT_FSIZE,(limits['stdout_bytes']+limits['stderr_bytes'],limits['stdout_bytes']+limits['stderr_bytes']))
    start=time.monotonic();buffers={'stdout':bytearray(),'stderr':bytearray()};status='completed';returncode=None
    with Path(stdin_path).open('rb') as source:
        try:proc=subprocess.Popen(argv,stdin=source,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=cwd,
            env={'PATH':'','HOME':str(cwd),'TMPDIR':str(cwd),'LANG':'C','LC_ALL':'C'},
            preexec_fn=child_limits,start_new_session=True)
        except OSError as exc:return {'process_status':'launch_error','returncode':None,'wall_seconds':time.monotonic()-start,'stdout':b'','stderr':str(exc).encode()}
        selector=selectors.DefaultSelector()
        for stream,name in [(proc.stdout,'stdout'),(proc.stderr,'stderr')]:os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        killed=False;kill_time=None
        def kill_group():
            nonlocal killed,kill_time
            if not killed:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                killed=True;kill_time=time.monotonic()
        while selector.get_map() or proc.poll() is None:
            if not killed and time.monotonic()-start>=limits['wall_seconds']:status='timeout';kill_group()
            if killed and time.monotonic()-kill_time>2:
                for key in list(selector.get_map().values()):selector.unregister(key.fileobj);key.fileobj.close()
                break
            for key,_ in selector.select(.05):
                try:chunk=os.read(key.fileobj.fileno(),65536)
                except BlockingIOError:continue
                if not chunk:selector.unregister(key.fileobj);key.fileobj.close();continue
                name=key.data;remaining=limits[name+'_bytes']-len(buffers[name]);buffers[name].extend(chunk[:max(0,remaining)])
                if len(chunk)>remaining and not killed:status='output_limit';kill_group()
        selector.close();returncode=proc.wait(timeout=5)
    if status=='completed' and returncode==-signal.SIGXCPU:status='cpu_limit'
    return {'process_status':status,'returncode':returncode,'wall_seconds':time.monotonic()-start,**{k:bytes(v) for k,v in buffers.items()}}


def classify_output(process,entry):
    if process['process_status']!='completed':return {'status':process['process_status'],'success':False}
    if process['returncode']!=0:return {'status':'process_failure','success':False}
    try:data=json.loads(process['stdout'].decode('utf-8'))
    except (UnicodeDecodeError,json.JSONDecodeError):return {'status':'malformed_compiler_output','success':False}
    bad={'status':'compiler_output_schema_error','success':False}
    if not isinstance(data,dict):return bad
    errors=data.get('errors',[])
    if not isinstance(errors,list) or any(not isinstance(e,dict) or e.get('severity') not in ('warning','error','info') for e in errors):return bad
    allowed_types={'ParserError','SyntaxError','TypeError','DeclarationError','CompilerError','Warning',
        'JSONError','IOError','InternalCompilerError','UnimplementedFeatureError','DocstringParsingError'}
    severity=collections.Counter(e['severity'] for e in errors)
    types=collections.Counter(e.get('type') if isinstance(e.get('type'),str) and e.get('type') in allowed_types else 'OtherDiagnostic' for e in errors)
    common={'diagnostic_severities':dict(severity),'diagnostic_types':dict(types)}
    bad={**bad,**common}
    if severity['error']:return {'status':'compiler_error','success':False,**common}
    sources=data.get('sources',{});contracts=data.get('contracts',{})
    if not isinstance(sources,dict) or not isinstance(sources.get(entry),dict) or 'ast' not in sources[entry] or not isinstance(contracts,dict):return bad
    root_contracts=contracts.get(entry,{})
    if not isinstance(root_contracts,dict):return bad
    ast=sources[entry]['ast']
    if not isinstance(ast,dict):return bad
    nodes=ast.get('nodes',ast.get('children',[]))
    if not isinstance(nodes,list) or any(not isinstance(node,dict) for node in nodes):return bad
    definitions={}
    for node in nodes:
        if node.get('nodeType',node.get('name'))=='ContractDefinition':
            attrs=node.get('attributes',node)
            if not isinstance(attrs,dict):return bad
            name=attrs.get('name')
            if not isinstance(name,str) or not name or name in definitions:return bad
            definitions[name]={'interface':attrs.get('contractKind')=='interface',
                'abstract':attrs.get('abstract') is True or attrs.get('fullyImplemented') is False}
    # Requested outputs must cover every declared root contract; absence is not
    # reclassified as an accepted source containing no contracts.
    if set(root_contracts)!=set(definitions):return bad
    bytecodes=[];missing_bytecode=0;missing=object()
    for name,contract in root_contracts.items():
        if not isinstance(contract,dict) or not isinstance(contract.get('abi'),list) or any(not isinstance(item,dict) for item in contract['abi']):return bad
        allowed_missing=definitions[name]['interface'] or definitions[name]['abstract']
        evm=contract.get('evm',missing)
        if evm is missing:
            if not allowed_missing:return bad
            missing_bytecode+=1;continue
        if not isinstance(evm,dict):return bad
        bytecode=evm.get('bytecode',missing)
        if bytecode is missing:
            if not allowed_missing:return bad
            missing_bytecode+=1;continue
        if not isinstance(bytecode,dict):return bad
        code=bytecode.get('object',missing)
        if code is missing:
            if not allowed_missing:return bad
            missing_bytecode+=1;continue
        if not isinstance(code,str):return bad
        bytecodes.append(code)
    return {'status':'compiler_success' if root_contracts else 'compiler_success_no_root_contracts','success':True,
        'root_contracts':len(root_contracts),'interface_definitions':sum(x['interface'] for x in definitions.values()),
        'abstract_definitions':sum(x['abstract'] for x in definitions.values()),
        'empty_bytecode_contracts':sum(not code for code in bytecodes),
        'missing_bytecode_interface_or_abstract_contracts':missing_bytecode,
        'nonempty_bytecode_contracts':sum(bool(code) for code in bytecodes),
        'unlinked_bytecode_contracts':sum('_' in code for code in bytecodes),**common}


def stage_input(job,workspace,settings,limits):
    root=ROOT/job['context_root'];sources={}
    for record in job['source_units']:
        source,size=check_local_source(root/record['unit'],root,record['sha256'])
        target=workspace/record['unit'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.encode('utf-8'));target.chmod(0o444)
        hash_check(target,record['sha256'])
        sources[record['unit']]={'content':source}
    payload=json.dumps({'language':'Solidity','sources':sources,'settings':settings},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    require(len(payload)<=limits['input_bytes'],'Standard JSON input exceeds frozen byte cap')
    path=workspace/'__compiler_input.json';require(not path.exists(),'Reserved input filename collision')
    path.write_bytes(payload)
    return path


def check_execution_permission(plan_path,permit_path,permit_digest):
    require(permit_path is not None and permit_digest,'An explicit plan-bound reviewed execution permit is required')
    hash_check(permit_path,permit_digest);permit=read(permit_path)
    require(permit.get('approved') is True and permit.get('scope')=='compiler_readiness_only','Execution permit is not approved for compiler-only readiness')
    require(permit.get('plan_sha256')==sha(plan_path),'Execution permit is for a different plan')
    require(bool(permit.get('parent_authorization_reference')),'Missing explicit parent authorization reference')
    review=ROOT/permit.get('independent_review_receipt','')
    require(review.is_file() and bool(permit.get('independent_review_sha256')),'Independent review receipt missing')
    hash_check(review,permit['independent_review_sha256']);review_data=read(review)
    require(review_data.get('status')=='pass' and review_data.get('plan_sha256')==sha(plan_path),'Independent review does not pass for this exact plan')
    return permit


def execute(plan_dir,permit_path,permit_digest):
    plan_dir=Path(plan_dir).resolve();plan_path=plan_dir/'plan_before_execution.json'
    permit=check_execution_permission(plan_path,permit_path,permit_digest);config=read(plan_path)
    for name,want in {**config['input_sha256'],**config['source_sha256']}.items():hash_check(ROOT/name,want)
    hash_check(plan_dir/'jobs.jsonl',config['jobs_sha256']);verify_pins()
    jobs=[json.loads(line) for line in (plan_dir/'jobs.jsonl').read_text().splitlines()]
    require(len(jobs)==2689,'Prepared job population changed')
    work=ROOT/config['private_work_root'];require(work.is_relative_to(ROOT/'data/derived') and not work.exists(),'Private execution root must be new and ignored')
    require(subprocess.check_output(['git','-C',str(ROOT),'check-ignore',str(work)],text=True).strip()==str(work),'Private execution directory is not ignored')
    work.mkdir(parents=True);(work/'attempts').mkdir();started=time.monotonic();results=[]
    tools={r['version']:r for r in read(TOOLCHAIN/'solc_inventory.json')['releases']}
    dump_new(work/'execution_started.json',{'started_utc':utc(),'plan_sha256':sha(plan_path),'permit_sha256':permit_digest})
    for job in jobs:
        outcome={k:job[k] for k in ['job_id','cohort','path','file_sha256','original_plan_status','preparation_status']};outcome['attempts']=[]
        if job['preparation_status']!='ready_to_attempt':outcome.update(status=job['preparation_status'],success=False)
        elif time.monotonic()-started>=config['limits']['total_run_wall_seconds']:outcome.update(status='not_attempted_run_budget',success=False)
        else:
            with tempfile.TemporaryDirectory(prefix=job['job_id']+'_',dir=work) as temp:
                workspace=Path(temp)
                try:input_path=stage_input(job,workspace,config['standard_json_settings'],config['limits'])
                except (ValueError,ImportFailure) as exc:
                    outcome.update(status='input_staging_failure',success=False,detail_sha256=hashlib.sha256(str(exc).encode()).hexdigest())
                    results.append(outcome);dump_new(work/(job['job_id']+'.json'),outcome);continue
                for index,version in enumerate(job['candidate_versions']):
                    remaining=config['limits']['total_run_wall_seconds']-(time.monotonic()-started)
                    if remaining<=0:
                        outcome.update(status='not_completed_run_budget',success=False,successful_version=None);break
                    artifact=tools[version];binary=ROOT/artifact['local_path'];hash_check(binary,artifact['artifact_sha256'])
                    argv=[str(binary),'--standard-json','--allow-paths',str(workspace)]
                    attempt_limits={**config['limits'],'wall_seconds':min(config['limits']['wall_seconds'],remaining)}
                    process=limited_process(argv,input_path,workspace,attempt_limits);classified=classify_output(process,job['entry_source_unit'])
                    prefix=work/'attempts'/f"{job['job_id']}_{index:02d}_{version}"
                    Path(str(prefix)+'.stdout').write_bytes(process['stdout']);Path(str(prefix)+'.stderr').write_bytes(process['stderr'])
                    attempt={'version':version,'compiler_sha256':artifact['artifact_sha256'],'candidate_index':index,
                        'returncode':process['returncode'],'wall_seconds':process['wall_seconds'],
                        'stdout_bytes':len(process['stdout']),'stderr_bytes':len(process['stderr']),
                        'stdout_sha256':hashlib.sha256(process['stdout']).hexdigest(),'stderr_sha256':hashlib.sha256(process['stderr']).hexdigest(),**classified}
                    outcome['attempts'].append(attempt)
                    if classified['success']:break
                if 'status' not in outcome:
                    last=outcome['attempts'][-1];outcome.update(status=last['status'],success=last['success'],successful_version=last['version'] if last['success'] else None)
        results.append(outcome);dump_new(work/(job['job_id']+'.json'),outcome)
    public=plan_dir/'execution_results';require(not public.exists(),'Public execution result directory already exists');public.mkdir()
    dump_new(public/'per_file_status.json',results)
    summary={'status':'compiler_preflight_complete','plan_sha256':sha(plan_path),'permit_sha256':permit_digest,'files':len(results),
        'status_counts':dict(collections.Counter(r['status'] for r in results)),'compiler_attempts':sum(len(r['attempts']) for r in results),
        'annotation_files_read':False,'slither_executions':0,'detectors_executed':0,'models_fitted':0,'model_scores':0,
        'wall_seconds':time.monotonic()-started,'source_edits':False,'private_diagnostic_root':str(work.relative_to(ROOT)),
        'scientific_scope':'Compiler-only declared-source-context coverage; no Slither/model/semantic readiness implication'}
    dump_new(public/'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--out',type=Path,required=True);prep.add_argument('--private-work-root',type=Path,required=True)
    run=sub.add_parser('execute');run.add_argument('--plan',type=Path,required=True);run.add_argument('--permit',type=Path,required=True);run.add_argument('--permit-sha256',required=True)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.out,args.private_work_root)
    else:execute(args.plan,args.permit,args.permit_sha256)
