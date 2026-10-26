"""Create a NEW, deliberately blocked binding of existing B inputs.

This records metadata hashes and exact public source copies; it does not freeze
the protocol, write human records, run models, execute tools, or authorize work.
"""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
from integrity_preflight import ROOT,sha

B=ROOT/'papers/security_evaluation/revision1/external_protocol'

def ref(path):return {'path':str(path.relative_to(ROOT)),'sha256':sha(path)}
def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')

def prepare(out):
    out=Path(out).resolve()
    if out.exists():raise FileExistsError('Use a new binding directory')
    if not out.is_relative_to(ROOT):raise ValueError('Binding artifacts must remain under repository root')
    out.mkdir(parents=True)
    protocol=json.loads((B/'protocol_B_draft.json').read_text())
    solc=json.loads((B/'toolchain_v1/solc_inventory.json').read_text());slither=json.loads((B/'toolchain_v1/slither_inventory.json').read_text());wheels=json.loads((B/'toolchain_v1/python_artifacts.json').read_text())
    inventory={'schema':'external_B_runtime_binding_v1','executables':[{'kind':'solc','version':r['version'],'path':r['local_path'],'sha256':r['artifact_sha256']} for r in solc['releases']]+[{'kind':'slither','version':slither['slither_version'],'path':slither['executable'],'sha256':slither['executable_sha256']}],
      'dependency_artifacts':[{'package':r['package'],'version':r['version'],'path':r['local_path'],'sha256':r['artifact_sha256']} for r in wheels['artifacts']],
      'compiler_plans':ref(B/'input_readiness_20261025_v1/compiler_plans.csv'),
      'metadata_origins':{name:ref(B/'toolchain_v1'/name) for name in ['manifest.json','solc_inventory.json','slither_inventory.json','python_artifacts.json','requirements.lock','installed_freeze.txt','amendment_v2/verification_receipt.json']},
      'execution_permission':'none; artifact checks only, no human authority claimed'}
    write(out/'runtime_inventory.json',inventory)
    status_map={'ok':'ok','decode_error':'preprocessing_error','scanner_error':'preprocessing_error','empty_token_stream':'preprocessing_error','zero_vocabulary_vector':'preprocessing_error','preprocessing_error':'preprocessing_error','unavailable_compiler':'unavailable_binary','no_compatible_catalog_release':'unavailable_binary','unavailable_binary':'unavailable_binary','missing_pragma':'unsupported_pragma','unsupported_constraint':'unsupported_pragma','unsupported_pragma':'unsupported_pragma','compile_error':'compile_error','tool_error':'tool_error','timeout':'timeout','missing_dependency':'missing_dependency','missing_score':'missing_score','model_error':'model_error'}
    config={'schema':'external_B_method_jobs_v1','model_configurations':protocol['model_configurations'],'slither':protocol['slither'],'static_comparator_required':True,'score_status_mapping':status_map,
      'learned_worker_environment':{'python':sys.version,'packages':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','scikit-learn','lightgbm','joblib','threadpoolctl']}},
      'purpose':'blocked current-input binding; not a prospective freeze or an execution request'}
    write(out/'method_config.json',config)
    private=ROOT/'data/derived/revision1_external_review_probability_20261025_v1';packet=B/'packet_probability_20261025_v1'
    artifacts={'protocol':B/'protocol_B_draft.json','training_manifest':packet/'training_manifest.csv','training_labels':private/'training_proxy_key.csv','test_manifest':packet/'external_cohort_manifest.csv','source_labels':ROOT/'data/derived/security_external_recovered_20261025/provisional_label_manifest.csv','sample_key':private/'coordinator_sampling_key.csv','allocation':packet/'stratum_allocation.csv','method_config':out/'method_config.json','toolchain_inventory':out/'runtime_inventory.json','inference_policy':B/'INFERENCE_GATE_20261026.json'}
    code={'integrity_preflight':B/'orchestration_v1/integrity_preflight.py','validate_gate_v2':B/'orchestration_v1/validate_gate_v2.py','adapters':B/'adapters_v1/adapters.py','feature_definitions':B/'adapters_v1/feature_definitions.json','performance':B/'performance_v2/performance.py','performance_dependency':B/'performance_v1/performance.py','review_estimators':B/'review_estimators.py','compiler_policy':B/'compiler_policy.py','toolchain_verifier':B/'toolchain_v1/verify_toolchain_v2.py','solidity_scanner':ROOT/'papers/security_evaluation/normalization_audit/solidity_scanner.py','contract_features':ROOT/'src/bal/features/contract_features.py','legacy_compiler_catalog':ROOT/'scripts/c3_slither_baseline.py','toolchain_provisioner':B/'toolchain_v1/provision_toolchain.py','model_worker':B/'model_worker_v1/worker.py'}
    binding={'schema':'external_B_orchestration_binding_v1','synthetic_fixture':False,'artifacts':{k:ref(v) for k,v in artifacts.items()},'code':{k:ref(v) for k,v in code.items()},'source_roots':{'train':'.','external':'data/raw/salzano'}}
    # Snapshot every bound source before any read-only preflight observation.
    # Keep original repository-relative paths; no private labels or sources.
    snapshot=out/'source_snapshot';snapshot.mkdir()
    for role,path in code.items():
        target=snapshot/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(path.read_bytes())
        if sha(target)!=binding['code'][role]['sha256']:raise ValueError('Source changed during preparation: '+role)
    builder=snapshot/Path(__file__).resolve().relative_to(ROOT)
    with builder.open('xb') as stream:stream.write(Path(__file__).read_bytes())
    write(out/'source_snapshot_manifest.json',{'schema':'external_B_public_source_snapshot_v1','code':binding['code'],'builder':ref(Path(__file__).resolve()),'source_snapshot_root':str(snapshot.relative_to(ROOT))})
    write(out/'binding.json',binding)
    write(out/'release.json',{'schema':'external_B_release_chain_v1','events':[]})
    write(out/'preparation_receipt.json',{'schema':'external_B_blocked_binding_preparation_v1','binding_sha256':sha(out/'binding.json'),'protocol_status':protocol['status'],'inference_policy_sha256':binding['artifacts']['inference_policy']['sha256'],'real_human_judgments':0,'model_fits_or_scores':0,'freeze_events_created':0,'authorization_records_created':0,'source_sha256':sha(Path(__file__))})
    return {'binding':str(out/'binding.json'),'expected_binding_sha256':sha(out/'binding.json'),'release':str(out/'release.json')}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();print(json.dumps(prepare(a.out),indent=2))
