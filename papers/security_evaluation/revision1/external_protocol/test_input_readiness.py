"""Verify saved read-only readiness receipts, without invoking any model or tool."""
import hashlib,json
from pathlib import Path
import pandas as pd
BASE=Path(__file__).parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def test_frozen_packet_and_readiness_receipts_are_intact():
    packet=BASE/'packet_probability_20261025_v1';out=BASE/'input_readiness_20261025_v1'
    for name,want in json.loads((packet/'public_file_hashes.json').read_text()).items():assert sha(packet/name)==want
    receipt=json.loads((out/'summary.json').read_text())
    for name,want in receipt['output_sha256'].items():assert sha(out/name)==want
    for path,want in receipt['source_sha256'].items():assert sha(out/'source_snapshot'/Path(path).name)==want
    assert receipt['models_fitted']==receipt['vocabularies_fitted']==0
    assert not receipt['compiler_or_slither_executed']
    assert not receipt['training_labels_read'] and not receipt['model_scores_read'] and not receipt['human_judgments_read']


def test_readiness_is_not_compile_or_model_coverage():
    out=BASE/'input_readiness_20261025_v1';rows=pd.read_csv(out/'input_readiness.csv');plans=pd.read_csv(out/'compiler_plans.csv')
    assert rows.groupby('cohort').size().to_dict()=={'external':1998,'train':691}
    assert set(rows.lexical_readiness)=={'lexical_ready'}
    assert not plans.executed.any() and not plans.outside_pragma.any()
    external=plans.loc[plans.cohort=='external']
    assert external.status.value_counts().to_dict()=={'compile_plan_ready_not_executed':1968,'missing_pragma':23,'unsupported_constraint':4,'no_compatible_catalog_release':3}
    assert not {'label','y','score','prediction','judgment'}.intersection(rows.columns)
