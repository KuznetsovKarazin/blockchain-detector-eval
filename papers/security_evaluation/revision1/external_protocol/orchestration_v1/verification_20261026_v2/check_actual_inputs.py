"""Read-only coordinator verification; creates a new observation receipt only."""
import hashlib,json,time,sys
from pathlib import Path
from types import ModuleType

ROOT=Path.cwd().resolve()
HERE=ROOT/'papers/security_evaluation/revision1/external_protocol/orchestration_v1'
source=(HERE/'integrity_preflight.py').read_bytes()
module=ModuleType('_observed_exact_preflight');module.__file__=str(HERE/'integrity_preflight.py')
sys.modules[module.__name__]=module
exec(compile(source,module.__file__,'exec'),module.__dict__)
out=HERE/'current_binding_20261026_v2';binding=out/'binding.json';release=out/'release.json'
expected='352de7c7b88d84cedfa1659739920207d3d82c17612f6a83653acf56e2802de2'
inputs=json.loads(binding.read_text());before={role:module.sha(ROOT/ref['path']) for role,ref in inputs['code'].items()}
start=time.perf_counter()
setup=module.check(ROOT,binding,expected,'setup',release)
denial=module.check(ROOT,binding,expected,'begin_scoring',release)
elapsed=time.perf_counter()-start
if not setup['phase_integrity_pass']:raise ValueError('Current setup failed:'+str(setup['blockers']))
if denial['phase_integrity_pass'] or denial['review_admission']['training_label_keys_read']:raise ValueError('Draft was not denied before training inputs')
after={role:module.sha(ROOT/ref['path']) for role,ref in inputs['code'].items()}
if before!=after:raise ValueError('Bound source changed during checks')
receipt={'schema':'external_B_current_readonly_observation_v2','expected_binding_sha256':expected,
 'setup':setup,'begin_scoring':denial,'wall_seconds':elapsed,'source_hashes':before,
 'optimized_python':not __debug__,'real_model_fits':0,'real_external_scores':0,'human_judgments_created':0,
 'tool_executions':0,'authorization_records_created':0,'protocol_frozen':False,
 'check_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (out/'read_only_preflight_receipt.json').open('x') as stream:json.dump(receipt,stream,indent=2,allow_nan=False);stream.write('\n')
print(json.dumps({'setup_pass':True,'begin_scoring_denied':True,'source_bytes_checked':setup['input_summary']['source_bytes_checked'],
 'wall_seconds':elapsed,'optimized_python':not __debug__,'operations_executed':0}))
