"""Entirely fictional temporary artifacts; no real expert/model records created."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import sys
import tempfile
from types import ModuleType
import unittest
import pandas as pd

HERE=Path(__file__).parent;sys.path.insert(0,str(HERE))
import integrity_preflight as p
import validate_gate_v2 as g


def write_json(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')
def ref(root,path):return {'path':str(path.relative_to(root)),'sha256':p.sha(path)}

class Fixture:
    def __init__(self,root):
        self.root=root;self.profile=p.Profile(2,2,4,2,1,1,1,True)
        self.train=[];self.test=[]
        for role,count in [('train',2),('external',2)]:
            for i in range(count):
                name=f'{role}{i}.sol';path=root/role/name;path.parent.mkdir(exist_ok=True);path.write_text(f'contract Fictional{role}{i} {{}}')
                if role=='train':self.train.append(dict(file_id=i,node_id=i,path=name,component=f'train{i}',file_sha256=p.sha(path)))
                else:self.test.append(dict(node_id=i+2,path=name,source_id='fictional',file_hash=p.sha(path),address_expanded_080=f'external{i}'))
        # directory may already exist on second iteration; created with exist_ok below by patched fixture.
        self.train=pd.DataFrame(self.train);self.test=pd.DataFrame(self.test)
        self.labels=pd.DataFrame([dict(path=row.path,**{'class':cls},label_status='source_reported_positive_pending_adjudication',binary_target='') for row in self.test.itertuples() for cls in ['reentrancy','unchecked']])
        self.key=self.labels[['path','class','label_status']].copy();self.key.insert(0,'case_id',[f'fictional{i}' for i in range(4)]);self.key['source_id']='fictional';self.key['N_h']=2;self.key['n_h']=2;self.key['inclusion_probability']=1.;self.key['design_weight']=1.
        self.allocation=self.key[['source_id','class','label_status','N_h','n_h','inclusion_probability','design_weight']].drop_duplicates().sort_values(['source_id','class','label_status'])
        self.artifacts={}
        self.training_labels=self.train[['file_id','path']].copy();self.training_labels['reentrancy']=[0,1];self.training_labels['unchecked']=[1,0]
        for role,data in [('training_manifest',self.train),('training_labels',self.training_labels),('test_manifest',self.test),('source_labels',self.labels),('sample_key',self.key),('allocation',self.allocation)]:
            path=root/(role+'.csv');data.to_csv(path,index=False);self.artifacts[role]=ref(root,path)
        self.config={'schema':'external_B_method_jobs_v1','model_configurations':{m:{'seeds':[0],'synthetic_fixture':True} for m in ['raw_tfidf_lr','normalized_tfidf_lr','pattern_rf','pattern_lgbm']},'slither':{'version':'0.11.6'},'static_comparator_required':True,'score_status_mapping':{'ok':'ok','model_error':'model_error','scanner_error':'preprocessing_error'}}
        path=root/'method_config.json';write_json(path,self.config);self.artifacts['method_config']=ref(root,path)
        executables=[]
        for kind,version in [('solc','0.5.17'),('slither','0.11.6')]:
            path=root/(kind+'.fake');path.write_bytes(b'fictional never-executed bytes');executables.append({'kind':kind,'version':version,**ref(root,path)})
        dep=root/'dependency.fake';dep.write_bytes(b'fictional dependency')
        plans=root/'compiler_plans.csv';pd.DataFrame({'candidate_versions':['0.5.17']}).to_csv(plans,index=False)
        inventory={'schema':'external_B_runtime_binding_v1','executables':executables,'dependency_artifacts':[{'package':'fictional-dependency','version':'1.0',**ref(root,dep)}],'compiler_plans':ref(root,plans)}
        path=root/'toolchain_inventory.json';write_json(path,inventory);self.artifacts['toolchain_inventory']=ref(root,path)
        inference=root/'inference_policy.json';write_json(inference,{'schema':'external_B_inference_policy_v1','applicable_scope':'fixed_external_probability_sample','survey_weighted_performance_and_interval_tests_complete':True,'external_ap_confirmatory_uncertainty':True,'evidence':'fictional unit-test policy, not a real inference finding'});self.artifacts['inference_policy']=ref(root,inference)
        self.code={}
        for role in g.CODE_ROLES:
            path=root/(role+'.fake-code');path.write_text('fictional immutable source bytes: '+role);self.code[role]=ref(root,path)
        self.protocol={'schema':g.SCHEMA,'status':'frozen_before_human_judgments_and_scores','protocol_id':'fictional-only',
          'freeze_prerequisites':{key:True for key in g.FREEZE_KEYS},'score_requirements':{key:'required_sealed_evidence' for key in g.SCORE_KEYS},
          'model_fitting_allowed':True,'external_scoring_allowed':True,'classes':['reentrancy','unchecked'],
          'reviewers':[{'reviewer_id':'fictional-A','display_name':'Fictional A'},{'reviewer_id':'fictional-B','display_name':'Fictional B'}],
          'release_order':g.RELEASE_ORDER,'model_configurations':self.config['model_configurations'],'slither':self.config['slither'],
          'hashes':{**{role:r['sha256'] for role,r in self.artifacts.items()},**{'code.'+role:r['sha256'] for role,r in self.code.items()}}}
        path=root/'protocol.json';write_json(path,self.protocol);self.artifacts['protocol']=ref(root,path)
        self.binding={'schema':'external_B_orchestration_binding_v1','synthetic_fixture':True,'artifacts':self.artifacts,'code':self.code,'source_roots':{'train':'train','external':'external'}}
        self.binding_path=root/'binding.json';write_json(self.binding_path,self.binding);self.digest=p.sha(self.binding_path)
        self.events=[]
        freeze=root/'freeze.json';write_json(freeze,{'binding_sha256':self.digest,'human_judgments_completed':0,'model_fits_completed':0,'external_scores_completed':0,'immutable_record_reference':'fictional-test-only-not-a-registration'})
        self.add_event('protocol_frozen','2026-01-01T00:00:00+00:00',{'freeze_record':ref(root,freeze)})
        self.forms=[]
        for index in [1,2]:
            form=self.key[['case_id','class']].copy();form['reviewer_id']=f'fictional-{chr(64+index)}';form['reviewed_utc']='2026-01-02T00:00:00+00:00';form['judgment_positive_negative_unknown']=['positive','negative','unknown','positive'];form['reason']='fictional test only'
            path=root/f'reviewer{index}.csv';form.to_csv(path,index=False);self.forms.append(form)
        self.add_event('initial_reviews_sealed','2026-01-03T00:00:00+00:00',{f'reviewer_{i}':ref(root,root/f'reviewer{i}.csv') for i in [1,2]})
        adjud=self.key[['case_id','class']].copy();adjud['reviewer_1_judgment']=self.forms[0].judgment_positive_negative_unknown;adjud['reviewer_2_judgment']=self.forms[1].judgment_positive_negative_unknown;adjud['adjudicated_judgment']=adjud.reviewer_1_judgment;adjud['adjudicator_id']='fictional-A';adjud['adjudication_reason']='fictional test only';adjud['adjudicated_utc']='2026-01-04T00:00:00+00:00';adjud.to_csv(root/'adjudication.csv',index=False)
        self.add_event('adjudication_sealed','2026-01-05T00:00:00+00:00',{'adjudication':ref(root,root/'adjudication.csv')})
        jobs=p.job_plan(self.config,self.protocol);scores=[];states=[];static_runs=[]
        for j in jobs:
            for row in self.test.itertuples():scores.append(dict(job_id=j['job_id'],path=row.path,**{'class':j['class']},execution_status='ok',status='ok',score=.5))
            if j['kind']=='static':
                log=root/(j['job_id']+'.tool-log.json');write_json(log,{'job_id':j['job_id'],'binding_sha256':self.digest,'outside_pragma_attempts':0,'source_paths':self.test.path.tolist()})
                static_runs.append({'job_id':j['job_id'],'toolchain_inventory_sha256':self.artifacts['toolchain_inventory']['sha256'],'reference_event_sha256':self.events[-1]['sha256'],'tool_log':ref(root,log),'scan_started_utc':'2026-01-06T00:00:00+00:00','scan_completed_utc':'2026-01-07T00:00:00+00:00'})
                continue
            obj=root/(j['job_id']+'.fake-model');obj.write_bytes(b'fictional not a model')
            state={'schema':'external_B_fitted_state_binding_v1','job_id':j['job_id'],'binding_sha256':self.digest,'method_config_sha256':self.artifacts['method_config']['sha256'],'training_manifest_sha256':self.artifacts['training_manifest']['sha256'],'training_node_ids':self.train.node_id.astype(str).tolist(),'training_source_sha256':self.train.file_sha256.tolist(),'fit_scope':'training_manifest_only','fit_status':'ok','fitted_object':ref(root,obj)}
            statepath=root/(j['job_id']+'.state.json');write_json(statepath,state)
            states.append({'job_id':j['job_id'],'training_manifest_sha256':self.artifacts['training_manifest']['sha256'],'fit_scope':'training_manifest_only','state_artifact':ref(root,statepath)})
        self.scores=pd.DataFrame(scores);self.scores.to_csv(root/'scores.csv',index=False)
        receipt={'binding_sha256':self.digest,'method_config_sha256':self.artifacts['method_config']['sha256'],'reference_event_sha256':self.events[-1]['sha256'],'training_manifest_sha256':self.artifacts['training_manifest']['sha256'],'scores_sha256':p.sha(root/'scores.csv'),'fit_started_utc':'2026-01-06T00:00:00+00:00','scoring_completed_utc':'2026-01-07T00:00:00+00:00','fitted_states':states,'static_runs':static_runs}
        write_json(root/'run_receipt.json',receipt)
        self.add_event('scores_sealed','2026-01-08T00:00:00+00:00',{'scores':ref(root,root/'scores.csv'),'run_receipt':ref(root,root/'run_receipt.json')})

    def add_event(self,phase,time,artifacts):
        path=self.root/(phase+'.json');write_json(path,{'schema':'external_B_release_event_v1','phase':phase,'binding_sha256':self.digest,'previous_event_sha256':self.events[-1]['sha256'] if self.events else None,'sealed_utc':time,'artifacts':artifacts});self.events.append(ref(self.root,path))

    def check(self,phase='analyze',count=None):
        count={'setup':0,'begin_review':1,'initial_reviews':2,'adjudication':3,'begin_scoring':3,'analyze':4}[phase] if count is None else count
        release=self.root/'release.json';write_json(release,{'schema':'external_B_release_chain_v1','events':self.events[:count]})
        return p.check(self.root,self.binding_path,self.digest,phase,release,self.profile)

    def replace_event(self,index,event):
        path=self.root/self.events[index]['path'];write_json(path,event);self.events[index]=ref(self.root,path)

class PreflightTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.f=Fixture(self.root)
    def tearDown(self):self.temp.cleanup()
    def test_exact_source_loader_ignores_same_size_timestamp_bytecode(self):
        path=self.root/'fictional_dependency.py';path.write_text('VALUE = 1\n')
        py_compile.compile(str(path),doraise=True)
        old=path.stat();path.write_text('VALUE = 2\n');os.utime(path,ns=(old.st_atime_ns,old.st_mtime_ns))
        loaded=p._load_exact_source('_fictional_exact_byte_dependency',path)
        self.assertEqual(loaded.VALUE,2)
        self.assertEqual(loaded.__source_sha256__,p.sha(path))
        sys.modules.pop('_fictional_exact_byte_dependency',None)
    def test_exact_source_loader_ignores_preloaded_module(self):
        path=self.root/'fictional_dependency.py';path.write_text('VALUE = 2\n')
        fake=ModuleType('_fictional_cached_dependency');fake.VALUE=1
        sys.modules[fake.__name__]=fake
        loaded=p._load_exact_source(fake.__name__,path)
        self.assertEqual(loaded.VALUE,2);self.assertIsNot(loaded,fake)
        self.assertEqual(loaded.__source_sha256__,p.sha(path))
        sys.modules.pop(fake.__name__,None)
    def test_all_synthetic_phases_integrity_pass_never_authorize(self):
        for phase in g.PHASES:
            out=self.f.check(phase);self.assertTrue(out['phase_integrity_pass'],out)
            self.assertFalse(out['execution_authorized']);self.assertFalse(out['human_identity_authenticated']);self.assertEqual(out['operations_executed'],0)
    def test_production_profile_cannot_override_counts(self):
        with self.assertRaises(ValueError):p.Profile(training_files=2)
    def test_missing_or_changed_artifacts_fail(self):
        for name in ['training_manifest.csv','test_manifest.csv','method_config.json','adapters.fake-code','scores.csv','adjudication.csv','reviewer1.csv','solc.fake']:
            path=self.root/name;original=path.read_bytes();path.write_bytes(original+b'changed')
            self.assertFalse(self.f.check()['phase_integrity_pass'],name);path.write_bytes(original)
    def test_missing_training_member_fails(self):
        (self.root/'train/train0.sol').unlink();self.assertFalse(self.f.check()['phase_integrity_pass'])
    def test_changed_raw_source_fails(self):
        (self.root/'external/external0.sol').write_text('changed');self.assertFalse(self.f.check()['phase_integrity_pass'])
    def test_binding_digest_is_not_self_accepted(self):
        out=p.check(self.root,self.f.binding_path,'0'*64,profile=self.f.profile);self.assertFalse(out['phase_integrity_pass'])
    def test_unknown_phase_and_wrong_fixture_profile_fail(self):
        self.assertFalse(p.check(self.root,self.f.binding_path,self.f.digest,'execute',profile=self.f.profile)['phase_integrity_pass'])
        self.assertFalse(p.check(self.root,self.f.binding_path,self.f.digest,'setup')['phase_integrity_pass'])
    def test_score_before_reference_fails_even_when_event_hash_rebound(self):
        path=self.root/'run_receipt.json';d=json.loads(path.read_text());d['fit_started_utc']='2026-01-04T00:00:00+00:00';write_json(path,d)
        event=json.loads((self.root/'scores_sealed.json').read_text());event['artifacts']['run_receipt']=ref(self.root,path);self.f.replace_event(3,event)
        out=self.f.check();self.assertFalse(out['phase_integrity_pass']);self.assertIn('before_adjudication',out['blockers'][0])
    def test_wrong_phase_chain_and_reentry_fail(self):
        self.assertFalse(self.f.check('begin_review',4)['phase_integrity_pass'])
        e=json.loads((self.root/'scores_sealed.json').read_text());e['previous_event_sha256']='0'*64;self.f.replace_event(3,e)
        self.assertFalse(self.f.check()['phase_integrity_pass'])
    def rebind_scores(self):
        self.f.scores.to_csv(self.root/'scores.csv',index=False);r=json.loads((self.root/'run_receipt.json').read_text());r['scores_sha256']=p.sha(self.root/'scores.csv');write_json(self.root/'run_receipt.json',r)
        e=json.loads((self.root/'scores_sealed.json').read_text());e['artifacts']={'scores':ref(self.root,self.root/'scores.csv'),'run_receipt':ref(self.root,self.root/'run_receipt.json')};self.f.replace_event(3,e)
    def test_failure_status_and_missing_score_preserved(self):
        self.f.scores['score']=self.f.scores.score.astype(object);self.f.scores.loc[0,['execution_status','status','score']]=['scanner_error','preprocessing_error',''];self.rebind_scores()
        out=self.f.check();self.assertTrue(out['phase_integrity_pass'],out)
        self.assertTrue(any(x['original_execution_status_counts'].get('scanner_error')==1 for x in out['score_coverage']))
    def test_failure_cannot_receive_fabricated_safe_score(self):
        self.f.scores.loc[0,['execution_status','status','score']]=['model_error','model_error',0.];self.rebind_scores()
        out=self.f.check();self.assertFalse(out['phase_integrity_pass']);self.assertIn('synthetic_score',out['blockers'][0])
    def test_missing_score_row_not_common_success_shortcut(self):
        self.f.scores=self.f.scores.iloc[1:].copy();self.rebind_scores();self.assertFalse(self.f.check()['phase_integrity_pass'])
    def test_unknown_status_not_mapped_to_success(self):
        self.f.scores.loc[0,'execution_status']='unrecorded';self.rebind_scores();self.assertFalse(self.f.check()['phase_integrity_pass'])
    def test_state_artifact_change_fails(self):
        state=next(self.root.glob('*.state.json'));state.write_text('{}');self.assertFalse(self.f.check()['phase_integrity_pass'])
    def test_review_admission_does_not_open_training_or_source_labels(self):
        from unittest.mock import patch
        self.f.check('begin_scoring')
        original=p.csv;read=[]
        def read_csv(path):
            read.append(Path(path).name)
            if Path(path).name in ['training_labels.csv','source_labels.csv']:raise AssertionError('forbidden early label read')
            return original(path)
        (self.root/'train/train0.sol').unlink()
        with patch.object(p,'csv',side_effect=read_csv):
            out=p.admission_preflight(self.root,self.f.binding_path,self.f.digest,self.root/'release.json',self.f.profile)
        self.assertTrue(out['admission_artifacts_consistent'],out)
        self.assertNotIn('training_labels.csv',read);self.assertNotIn('source_labels.csv',read)
        self.assertFalse(out['training_label_keys_read']);self.assertFalse(out['model_source_bodies_read'])
    def test_blank_review_fails_before_any_training_source_integrity(self):
        self.f.check('begin_scoring')
        path=self.root/'reviewer1.csv';form=pd.read_csv(path);form['judgment_positive_negative_unknown']='';form.to_csv(path,index=False)
        (self.root/'training_labels.csv').unlink();(self.root/'train/train0.sol').unlink()
        out=p.admission_preflight(self.root,self.f.binding_path,self.f.digest,self.root/'release.json',self.f.profile)
        self.assertFalse(out['admission_artifacts_consistent']);self.assertIn('reviewer1.csv',out['blockers'][0])
    def test_inference_gate_false_blocks_even_schema_complete_protocol(self):
        path=self.root/'inference_policy.json';policy=json.loads(path.read_text());policy['external_ap_confirmatory_uncertainty']=False;write_json(path,policy)
        # Rebind policy into a coherent fictional anchor: rejection must be scientific policy, not only a stale hash.
        self.f.artifacts['inference_policy']=ref(self.root,path)
        self.f.protocol['hashes']['inference_policy']=self.f.artifacts['inference_policy']['sha256']
        write_json(self.root/'protocol.json',self.f.protocol);self.f.artifacts['protocol']=ref(self.root,self.root/'protocol.json')
        self.f.binding['artifacts']=self.f.artifacts;write_json(self.f.binding_path,self.f.binding);self.f.digest=p.sha(self.f.binding_path)
        out=self.f.check('begin_scoring');self.assertFalse(out['phase_integrity_pass']);self.assertIn('inference_policy_blocks',out['blockers'][0])
    def test_missing_static_comparator_receipt_cannot_improve_domain(self):
        receipt=json.loads((self.root/'run_receipt.json').read_text());receipt['static_runs']=[];write_json(self.root/'run_receipt.json',receipt)
        event=json.loads((self.root/'scores_sealed.json').read_text());event['artifacts']['run_receipt']=ref(self.root,self.root/'run_receipt.json');self.f.replace_event(3,event)
        self.assertFalse(self.f.check()['phase_integrity_pass'])
    def test_key_counts_are_checked_before_initial_review_admission(self):
        key=self.f.key.copy();key['N_h']=99;key.to_csv(self.root/'sample_key.csv',index=False)
        self.f.binding['artifacts']['sample_key']=ref(self.root,self.root/'sample_key.csv')
        with self.assertRaisesRegex(p.IntegrityError,'sample_key_counts'):
            p.bind_sources(self.root,self.f.binding,self.f.profile)
    def test_duplicate_dependency_cannot_satisfy_inventory_count(self):
        inventory=json.loads((self.root/'toolchain_inventory.json').read_text());inventory['dependency_artifacts']*=2
        profile=p.Profile(2,2,4,2,1,1,2,True)
        with self.assertRaisesRegex(p.IntegrityError,'duplicate_dependency'):
            p.bind_toolchain(self.root,inventory,profile)
    def test_compiler_versions_must_equal_bound_planner_set(self):
        inventory=json.loads((self.root/'toolchain_inventory.json').read_text());inventory['executables'][0]['version']='0.7.0'
        with self.assertRaisesRegex(p.IntegrityError,'compiler_versions'):
            p.bind_toolchain(self.root,inventory,self.f.profile)
    def test_failed_fit_keeps_full_failure_rows_without_invented_model(self):
        receipt=json.loads((self.root/'run_receipt.json').read_text());fit=receipt['fitted_states'][0]
        statepath=self.root/fit['state_artifact']['path'];state=json.loads(statepath.read_text())
        log=self.root/'fictional_fit_failure.json';write_json(log,{'status':'model_error','reason':'fictional unit-test failure'})
        state.update(fit_status='failed',fitted_object=None,failure_log=ref(self.root,log));write_json(statepath,state)
        fit['state_artifact']=ref(self.root,statepath);write_json(self.root/'run_receipt.json',receipt)
        selected=self.f.scores.job_id==fit['job_id'];self.f.scores['score']=self.f.scores.score.astype(object)
        self.f.scores.loc[selected,['execution_status','status','score']]=['model_error','model_error',''];self.rebind_scores()
        out=self.f.check();self.assertTrue(out['phase_integrity_pass'],out)
    def test_coherently_resealed_wrong_training_members_still_rejected(self):
        receipt=json.loads((self.root/'run_receipt.json').read_text());fit=receipt['fitted_states'][0]
        statepath=self.root/fit['state_artifact']['path'];state=json.loads(statepath.read_text());state['training_node_ids']=['external-node','1'];write_json(statepath,state)
        fit['state_artifact']=ref(self.root,statepath);write_json(self.root/'run_receipt.json',receipt);self.rebind_scores()
        out=self.f.check();self.assertFalse(out['phase_integrity_pass']);self.assertIn('training_members_changed',out['blockers'][0])
    def test_checker_is_read_only(self):
        self.f.check();before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        out=p.check(self.root,self.f.binding_path,self.f.digest,'analyze',self.root/'release.json',self.f.profile)
        self.assertTrue(out['phase_integrity_pass']);self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

class StrictGateTests(unittest.TestCase):
    def test_legacy_fail_open_counterexample_rejected(self):
        legacy_path=HERE.parent/'validate_gate.py';spec=importlib.util.spec_from_file_location('legacy_gate_counterexample',legacy_path);legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
        forged={'status':'frozen_before_human_judgments_and_scores','probability_audit':{'reviewer_1_name':'same fictional name','reviewer_2_name':'same fictional name'},'model_fitting_allowed':False,'external_scoring_allowed':False}
        self.assertEqual(legacy.blockers(forged,HERE,'score'),[])
        out=g.blockers(forged,'begin_scoring');self.assertIn('freeze_prerequisite_set_missing_or_changed',out);self.assertIn('required_hash_binding_set_missing_or_changed',out);self.assertIn('permission_closed:model_fitting_allowed',out)
    def test_current_real_draft_is_closed(self):
        current=json.loads((HERE.parent/'protocol_B_draft.json').read_text());self.assertTrue(g.blockers(current,'begin_scoring'))
    def test_missing_each_required_map_and_false_permissions_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=Fixture(Path(temp));good=fixture.protocol
            for field in ['freeze_prerequisites','score_requirements','hashes']:
                changed=dict(good);changed.pop(field);self.assertTrue(g.blockers(changed,'begin_scoring'),field)
            for field in ['model_fitting_allowed','external_scoring_allowed']:
                changed=dict(good);changed[field]=False;self.assertIn('permission_closed:'+field,g.blockers(changed,'begin_scoring'))
    def test_normalized_same_reviewer_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Fixture(Path(temp));d=dict(f.protocol);d['reviewers']=[{'reviewer_id':'Ａlice','display_name':'Person1'},{'reviewer_id':' alice ','display_name':'Person2'}]
            self.assertIn('distinct_nonempty_reviewer_id_required',g.blockers(d))

if __name__=='__main__':unittest.main()
