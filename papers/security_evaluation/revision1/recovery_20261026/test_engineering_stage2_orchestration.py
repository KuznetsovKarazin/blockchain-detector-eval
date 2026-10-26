"""Independent adversarial assertions on fictional artifact trees only.

The owner's Fixture is reused solely to construct internally consistent toy
files. Mutation targets and expected failures below were selected independently.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

BASE=Path(__file__).parents[1]/'external_protocol/orchestration_v1'
sys.path.insert(0,str(BASE))
spec=importlib.util.spec_from_file_location('independent_toy_fixture',BASE/'test_preflight.py')
toy=importlib.util.module_from_spec(spec);sys.modules[spec.name]=toy;spec.loader.exec_module(toy)
p,g=toy.p,toy.g


def rebind_protocol(f):
    toy.write_json(f.root/'protocol.json',f.protocol)
    f.artifacts['protocol']=toy.ref(f.root,f.root/'protocol.json')
    f.binding['artifacts']=f.artifacts
    toy.write_json(f.binding_path,f.binding);f.digest=p.sha(f.binding_path)


def rebind_scores(f):
    f.scores.to_csv(f.root/'scores.csv',index=False)
    receipt=json.loads((f.root/'run_receipt.json').read_text())
    receipt['scores_sha256']=p.sha(f.root/'scores.csv')
    toy.write_json(f.root/'run_receipt.json',receipt)
    event=json.loads((f.root/'scores_sealed.json').read_text())
    event['artifacts']={'scores':toy.ref(f.root,f.root/'scores.csv'),
                        'run_receipt':toy.ref(f.root,f.root/'run_receipt.json')}
    f.replace_event(3,event)


def test_each_named_freeze_condition_is_required_not_implicitly_vacuous(tmp_path):
    f=toy.Fixture(tmp_path)
    assert not g.blockers(f.protocol,'begin_scoring')
    for name in g.FREEZE_KEYS:
        changed=copy.deepcopy(f.protocol);del changed['freeze_prerequisites'][name]
        assert 'freeze_prerequisite_set_missing_or_changed' in g.blockers(changed,'begin_scoring')


def test_every_transitive_code_hash_binding_is_mandatory(tmp_path):
    f=toy.Fixture(tmp_path)
    for role in ('solidity_scanner','contract_features','legacy_compiler_catalog','model_worker','toolchain_provisioner'):
        changed=copy.deepcopy(f.protocol);del changed['hashes']['code.'+role]
        assert 'required_hash_binding_set_missing_or_changed' in g.blockers(changed,'begin_scoring')


@pytest.mark.parametrize('phase', ('score','begin-review','EXECUTE','',None))
def test_unknown_or_legacy_phase_spelling_is_never_accepted(tmp_path,phase):
    f=toy.Fixture(tmp_path)
    assert g.blockers(f.protocol,phase)==['unknown_phase']


def test_closed_draft_rejected_before_any_private_key_or_source_read(tmp_path,monkeypatch):
    f=toy.Fixture(tmp_path);f.protocol['status']='draft_not_registered_not_frozen';rebind_protocol(f)
    f.check('begin_scoring')  # materialize only the fictional three-event release
    forbidden={'training_labels.csv','source_labels.csv','sample_key.csv','reviewer1.csv','reviewer2.csv','adjudication.csv'}
    real_artifact=p.artifact;seen=[]
    def checked(root,ref):
        name=Path(ref['path']).name;seen.append(name)
        if name in forbidden:raise AssertionError('Private artifact accessed before draft rejection: '+name)
        return real_artifact(root,ref)
    monkeypatch.setattr(p,'artifact',checked)
    out=p.admission_preflight(f.root,f.binding_path,f.digest,f.root/'release.json',f.profile)
    assert not out['admission_artifacts_consistent']
    assert 'protocol_gate' in out['blockers'][0] and not (set(seen)&forbidden)


def test_false_inference_policy_blocks_even_a_coherent_rebound_anchor(tmp_path,monkeypatch):
    f=toy.Fixture(tmp_path)
    policy=json.loads((f.root/'inference_policy.json').read_text());policy['external_ap_confirmatory_uncertainty']=False
    toy.write_json(f.root/'inference_policy.json',policy)
    f.artifacts['inference_policy']=toy.ref(f.root,f.root/'inference_policy.json')
    f.protocol['hashes']['inference_policy']=f.artifacts['inference_policy']['sha256'];rebind_protocol(f)
    monkeypatch.setattr(p,'csv',lambda path: (_ for _ in ()).throw(AssertionError('CSV read before blocked inference policy')))
    out=p.admission_preflight(f.root,f.binding_path,f.digest,f.root/'release.json',f.profile)
    assert not out['admission_artifacts_consistent'] and 'inference_policy_blocks' in out['blockers'][0]


def test_production_cannot_attest_fake_live_validator_copies(tmp_path):
    f=toy.Fixture(tmp_path);f.binding['synthetic_fixture']=False
    toy.write_json(f.binding_path,f.binding);f.digest=p.sha(f.binding_path)
    with pytest.raises(p.IntegrityError,match='live_validator_code_differs'):
        p.header(f.root,f.binding_path,f.digest,'setup',p.Profile())


def test_source_or_artifact_symlink_cannot_escape_binding_root(tmp_path):
    root=tmp_path/'allowed';root.mkdir();outside=tmp_path/'outside';outside.write_text('fictional')
    (root/'link').symlink_to(outside)
    with pytest.raises(p.IntegrityError,match='escapes'):
        p.artifact(root,{'path':'link','sha256':p.sha(outside)})


def test_partial_static_receipt_cannot_satisfy_complete_score_release(tmp_path):
    f=toy.Fixture(tmp_path)
    f.scores=f.scores[~f.scores.job_id.eq('slither:unchecked:0')].copy();rebind_scores(f)
    out=f.check()
    assert not out['phase_integrity_pass'] and 'score_job_set' in out['blockers'][0]


def test_raw_preprocessing_failure_cannot_be_relabelled_success(tmp_path):
    f=toy.Fixture(tmp_path)
    f.scores.loc[0,['execution_status','status','score']]=['scanner_error','ok',0.]
    rebind_scores(f);out=f.check()
    assert not out['phase_integrity_pass'] and 'score_status_mapping_changed' in out['blockers'][0]


def test_identity_bound_training_labels_cannot_be_permuted(tmp_path):
    f=toy.Fixture(tmp_path)
    labels=f.training_labels.iloc[::-1].copy();labels.to_csv(f.root/'training_labels.csv',index=False)
    f.binding['artifacts']['training_labels']=toy.ref(f.root,f.root/'training_labels.csv')
    with pytest.raises(p.IntegrityError,match='training_label_identity_or_order'):
        p.bind_sources(f.root,f.binding,f.profile)


def test_static_scan_before_reference_seal_is_rejected_after_hash_rebinding(tmp_path):
    f=toy.Fixture(tmp_path)
    receipt=json.loads((f.root/'run_receipt.json').read_text())
    receipt['static_runs'][0]['scan_started_utc']='2026-01-02T00:00:00+00:00'
    toy.write_json(f.root/'run_receipt.json',receipt)
    event=json.loads((f.root/'scores_sealed.json').read_text());event['artifacts']['run_receipt']=toy.ref(f.root,f.root/'run_receipt.json')
    f.replace_event(3,event);out=f.check()
    assert not out['phase_integrity_pass'] and 'static_analysis_before_adjudication' in out['blockers'][0]


def test_fitted_state_membership_substitution_fails_with_valid_artifact_hashes(tmp_path):
    f=toy.Fixture(tmp_path)
    receipt=json.loads((f.root/'run_receipt.json').read_text());fit=receipt['fitted_states'][0]
    state_path=f.root/fit['state_artifact']['path'];state=json.loads(state_path.read_text())
    state['training_node_ids']=['99','100'];toy.write_json(state_path,state)
    fit['state_artifact']=toy.ref(f.root,state_path);toy.write_json(f.root/'run_receipt.json',receipt)
    event=json.loads((f.root/'scores_sealed.json').read_text());event['artifacts']['run_receipt']=toy.ref(f.root,f.root/'run_receipt.json')
    f.replace_event(3,event);out=f.check()
    assert not out['phase_integrity_pass'] and 'training_members_changed' in out['blockers'][0]


def test_human_completion_cannot_be_replaced_with_only_provenance_flags(tmp_path):
    f=toy.Fixture(tmp_path)
    form=f.forms[0].copy();form['judgment_positive_negative_unknown']=''
    form.to_csv(f.root/'reviewer1.csv',index=False)
    event=json.loads((f.root/'initial_reviews_sealed.json').read_text())
    event['artifacts']['reviewer_1']=toy.ref(f.root,f.root/'reviewer1.csv')
    f.replace_event(1,event)
    # Rebind later chain link so the intended judgment check, not a stale link,
    # determines failure.
    adjud_event=json.loads((f.root/'adjudication_sealed.json').read_text())
    adjud_event['previous_event_sha256']=f.events[1]['sha256'];f.replace_event(2,adjud_event)
    f.check('begin_scoring')
    out=p.admission_preflight(f.root,f.binding_path,f.digest,f.root/'release.json',f.profile)
    assert not out['admission_artifacts_consistent'] and 'blank_or_invalid' in out['blockers'][0]
