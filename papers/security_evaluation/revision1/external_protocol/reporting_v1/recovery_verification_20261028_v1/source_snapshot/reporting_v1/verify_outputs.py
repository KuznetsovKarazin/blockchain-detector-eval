"""Read-only verification of the fictional reporting run; no corpus inputs."""
import argparse,hashlib,json,math
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)

def verify(folder):
    root=Path(__file__).resolve().parents[1]
    receipt=json.loads((folder/'receipt.json').read_text());design=json.loads((folder/'design_before_reports.json').read_text())
    require(receipt['status']=='complete_fictional_reports_only','Incomplete fictional run')
    require(not receipt['actual_labels_or_scores_opened'] and receipt['model_fits_or_tool_calls']==0 and not receipt['amendment_adopted'],'Unexpected actual operation or release')
    for name,digest in receipt['source_hashes'].items():
        require(sha(root/name)==digest and sha(folder/'source_snapshot'/name)==digest,'Source mismatch: '+name)
    for name,digest in receipt['output_hashes'].items():require(sha(folder/name)==digest,'Output mismatch: '+name)
    checks=[]
    for row in receipt['reports']:
        report=json.loads((folder/f"report_{row['scenario']}_{row['class']}.json").read_text())
        require(len(report['primary_inventory'])==13 and len(report['primary']['coverage'])==13,'Primary inventory')
        require(report['policy']['amendment_active'] is False,'Inactive policy')
        for domain in report['primary']['domains'].values():
            require(len(domain['raw_LR_reference_contrasts'])==12 and len(domain['vectors'])==13,'Contrast or vector count')
            total=domain['reference_positive_total'];require(total['confidence_interval'] is None,'Primary interval leak')
            for vector in domain['vectors'].values():
                for q in vector['workload']:
                    require(q['review_count_requested']==math.floor(q['review_fraction']*domain['population_n']),'Budget rounding')
                    require(q['review_count_filled']+q['unfilled_budget']==q['review_count_requested'],'Unfilled budget')
                    require(q['positive_yield']['confidence_interval'] is None,'Primary interval leak')
                    require(q['positive_yield']['logical_population_bounds']['upper']<=q['review_count_filled']+1e-10,'Logical bound exceeds physical capacity')
        domains=report['primary']['domains']
        if row['scenario']=='baseline':
            require(domains['full_frame_pipeline']['reference_positive_total']['point']['estimate']==6,'Known fictional HT total')
            require(math.isclose(domains['full_frame_pipeline']['reference_positive_total']['point']['design_variance_estimate'],12,rel_tol=0,abs_tol=1e-12),'Known fictional HT variance')
        if row['scenario']=='unknown_outside_common':
            require(domains['full_frame_pipeline']['reference_positive_total']['point'] is None,'Unknown silently given full-domain point')
            require(domains['common_success']['reference_positive_total']['point'] is not None,'Outside unknown incorrectly suppresses common domain')
        if row['exploratory']:
            reference=report['engine_audit_artifact'];audit=json.loads((folder/reference['filename']).read_text())['raw_output']
            require(sha(folder/reference['filename'])==reference['sha256'],'Audit binding')
            require(audit['bootstrap']['replicates']==2000 and audit['bootstrap']['seed']==20261026,'Frozen exploratory design')
            require(all(len(d['paired_differences'])==78 for d in audit['domains'].values()),'Raw engine pairs lost')
        else:require(report['exploratory'] is None and 'engine_audit_artifact' not in report,'Unexpected bootstrap path')
        checks.append({'scenario':row['scenario'],'class':row['class'],'passed':True})
    return {'schema':'fictional_reporting_output_verification_v1','passed':True,'reports':checks,
      'source_files_checked':len(receipt['source_hashes']),'output_hashes_checked':len(receipt['output_hashes']),
      'actual_inputs_opened':False,'model_or_tool_operations':0,'source_sha256':sha(Path(__file__))}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True)
    print(json.dumps(verify(parser.parse_args().folder),indent=2))
