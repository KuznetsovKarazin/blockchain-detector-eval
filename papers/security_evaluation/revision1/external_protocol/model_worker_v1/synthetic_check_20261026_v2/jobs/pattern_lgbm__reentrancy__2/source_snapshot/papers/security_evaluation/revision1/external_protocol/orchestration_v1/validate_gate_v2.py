"""Strict prospective-protocol schema gate; never executes a research action.

Legacy draft/snapshots are not modified. Frozen v2 declarations define required
release evidence, rather than falsely recording completed human review at freeze.
Names/IDs and hashes are integrity metadata, not authentication of real people.
"""
import argparse
import json
from pathlib import Path
import unicodedata

SCHEMA='external_validation_protocol_B_frozen_v2'
PHASES=('setup','begin_review','initial_reviews','adjudication','begin_scoring','analyze')
FREEZE_KEYS={'named_independent_human_reviewers','feature_adapters_and_regression_tests_complete',
'compiler_inventory_and_policy_tests_complete','survey_weighted_performance_and_interval_tests_complete',
'class_mapping_semantic_signoff','human_review_protocol_signed_off',
'external_population_and_train_hashes_verified','sampling_packet_prepared_before_judgments_or_scores'}
SCORE_KEYS={'protocol_frozen_before_human_judgments_and_scores','both_initial_human_review_sets_complete_and_sealed',
'adjudication_complete_with_unknowns_retained','source_and_configuration_hashes_unchanged'}
RELEASE_ORDER=['protocol_frozen','initial_reviews_sealed','adjudication_sealed','scores_sealed']
ARTIFACT_ROLES={'protocol','training_manifest','training_labels','test_manifest','source_labels','sample_key','allocation','method_config','toolchain_inventory','inference_policy'}
CODE_ROLES={'integrity_preflight','validate_gate_v2','adapters','feature_definitions','performance','performance_dependency','review_estimators','compiler_policy','toolchain_verifier','solidity_scanner','contract_features','legacy_compiler_catalog','toolchain_provisioner','model_worker'}


def normalized_identity(value):
    if not isinstance(value,str):return ''
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())


def blockers(protocol,phase='begin_scoring'):
    """Schema/condition declarations only; artifact and release checks are separate."""
    bad=[]
    if phase not in PHASES:return ['unknown_phase']
    if not isinstance(protocol,dict):return ['protocol_not_object']
    if protocol.get('schema')!=SCHEMA:bad.append('unrecognized_or_legacy_protocol_schema')
    if protocol.get('status')!='frozen_before_human_judgments_and_scores':bad.append('protocol_not_frozen')
    if not isinstance(protocol.get('protocol_id'),str) or not protocol.get('protocol_id','').strip():bad.append('missing_protocol_id')
    freeze=protocol.get('freeze_prerequisites')
    if not isinstance(freeze,dict) or set(freeze)!=FREEZE_KEYS:bad.append('freeze_prerequisite_set_missing_or_changed')
    elif any(value is not True for value in freeze.values()):bad.append('freeze_prerequisites_not_satisfied')
    score=protocol.get('score_requirements')
    if not isinstance(score,dict) or set(score)!=SCORE_KEYS:bad.append('score_requirement_set_missing_or_changed')
    elif any(value!='required_sealed_evidence' for value in score.values()):bad.append('score_requirements_must_require_evidence')
    hashes=protocol.get('hashes')
    wanted=(ARTIFACT_ROLES-{'protocol'})|{'code.'+key for key in CODE_ROLES}
    if not isinstance(hashes,dict) or set(hashes)!=wanted:bad.append('required_hash_binding_set_missing_or_changed')
    elif any(not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value) for value in hashes.values()):bad.append('invalid_sha256_binding')
    if protocol.get('release_order')!=RELEASE_ORDER:bad.append('human_before_fit_score_order_changed')
    if protocol.get('classes')!=['reentrancy','unchecked']:bad.append('class_set_changed')
    reviewers=protocol.get('reviewers')
    if not isinstance(reviewers,list) or len(reviewers)!=2 or any(not isinstance(r,dict) or set(r)!={'reviewer_id','display_name'} for r in reviewers):bad.append('two_reviewer_records_required')
    else:
        for field in ['reviewer_id','display_name']:
            values=[normalized_identity(r[field]) for r in reviewers]
            if not all(values) or len(set(values))!=2:bad.append('distinct_nonempty_'+field+'_required')
    for key in ['model_fitting_allowed','external_scoring_allowed']:
        if not isinstance(protocol.get(key),bool):bad.append('missing_permission:'+key)
        elif phase in ('begin_scoring','analyze') and protocol[key] is not True:bad.append('permission_closed:'+key)
    return sorted(set(bad))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--protocol',type=Path,required=True)
    ap.add_argument('--phase',choices=PHASES,default='begin_scoring');args=ap.parse_args()
    try:bad=blockers(json.loads(args.protocol.read_text()),args.phase)
    except (OSError,ValueError,TypeError) as exc:bad=['invalid_protocol:'+str(exc)]
    # A schema check alone is NEVER sufficient to approve any execution.
    print(json.dumps({'schema_conditions_pass':not bad,'blockers':bad,'artifact_release_preflight_required':True,
                      'execution_authorized':False,'human_identity_authenticated':False,'operations_executed':0},indent=2))
    return 2 if bad else 0
if __name__=='__main__':raise SystemExit(main())
