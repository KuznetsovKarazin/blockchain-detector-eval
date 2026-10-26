"""Prepare the separate quarantined-identity census evidence locally only."""
import argparse,hashlib,json,shutil
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
    private=(ROOT/a.private).resolve();out=private/'identity_evidence'
    if out.exists() or a.receipt.exists():raise FileExistsError('Do not overwrite existing evidence')
    out.mkdir(parents=True)
    key=pd.read_csv(private/'quarantined_identity_key.csv',keep_default_na=False)
    meta=pd.read_csv(ROOT/'papers/security_evaluation/external_audit/source_audit_full_20261025/candidate_source_metadata.csv',keep_default_na=False)
    csvpath=ROOT/'data/raw/salzano/csvs/sample_of_interest.csv';raw=pd.read_csv(csvpath,keep_default_na=False)
    receipts=[]
    for r in key.itertuples():
        d=out/r.identity_case_id;d.mkdir()
        m=meta[(meta.source_id==r.source_id)&(meta.contract_id==r.contract_id)]
        assert len(m)==1
        src=ROOT/'data/raw/salzano'/m.iloc[0].path;shutil.copy2(src,d/'source.sol')
        original=raw[(raw.label==r.source_id)&(raw.contract==r.contract_id)].to_dict('records')
        # Case-insensitive alternatives are evidence candidates, never an automatic fix.
        alternatives=raw[(raw.label==r.source_id)&(raw.contract.str.lower()==r.contract_id.lower())].to_dict('records')
        record={'identity_case_id':r.identity_case_id,'source_metadata':m.iloc[0].to_dict(),'issue':r._asdict(),
                'exact_original_annotation_rows':original,'case_insensitive_annotation_candidates':alternatives,
                'proposed_correction':None,'identity_resolved':False,'cohort_reentry_allowed':False,
                'note':'Identity audit may reveal source labels; it is separate from blinded probability-case assessment.'}
        (d/'evidence.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
        receipts.append({'identity_case_id':r.identity_case_id,'source_sha256':sha(d/'source.sol'),'private_evidence_sha256':sha(d/'evidence.json'),'human_decision_present':False})
    result={'schema':'quarantined_identity_evidence_receipt_v1','identity_cases':len(receipts),'existing_quarantine_preserved':True,'cohort_reentry_allowed':False,'raw_annotations_publicly_redistributed':False,'source_csv_sha256':sha(csvpath),'code_sha256':sha(Path(__file__)),'private_evidence_root':str(a.private/'identity_evidence'),'cases':receipts}
    a.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['identity_cases','existing_quarantine_preserved','cohort_reentry_allowed']}))
if __name__=='__main__':main()
