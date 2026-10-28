"""Create a new source-frozen fictional reporting receipt; no real data options."""
import argparse,hashlib,importlib.metadata,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import reporting as r
from synthetic_inputs import fixture

HERE=Path(__file__).resolve().parent;B=HERE.parent
SOURCES=['reporting_v1/reporting.py','reporting_v1/run_synthetic.py','reporting_v1/synthetic_inputs.py',
 'reporting_v1/test_reporting.py','reporting_v1/README.md','reporting_v1/conftest.py',
 'performance_v2/performance.py','performance_v1/performance.py','performance_v1/synthetic_inputs.py',
 'review_estimators.py','ap_bounds_v1/ap_bounds.py','INFERENCE_AMENDMENT_DRAFT_20261026.md','INFERENCE_GATE_20261026.json',
 'PROTOCOL_B.md','protocol_B_draft.json']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,obj):
    with path.open('x') as stream:json.dump(obj,stream,separators=(',',':'),allow_nan=False);stream.write('\n')
def checked_hashes():return {name:sha(B/name) for name in SOURCES}

def run(out):
    if out.exists():raise FileExistsError('Use a new directory; preserve all previous observations')
    out.mkdir(parents=True)
    config={'schema':'fictional_reporting_design_v1','purpose':'synthetic_in_memory_inactive_reporting_amendment',
      'classes':list(r.CLASSES),'files':12,'selected_per_class':4,'total_selected_cases':8,
      'primary_vectors_per_class':13,'raw_LR_contrasts_per_domain':12,'broad_slither_secondary':True,
      'review_fractions':[.05,.1,.2],'replicates':2000,'seed':20261026,'alpha':.05,
      'scenarios':['baseline','mixed_failures','unknown_outside_common'],
      'exploratory_runs':['baseline:reentrancy'],'others_primary_only':True,
      'actual_inputs_allowed':False,'amendment_adopted':False,'prospective_actual_study_freeze':False,
      'created_utc':datetime.now(timezone.utc).isoformat()}
    source_hashes=checked_hashes()
    for name in SOURCES:
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((B/name).read_bytes())
        if sha(target)!=source_hashes[name]:raise ValueError('Source changed during snapshot')
    write(out/'design_before_reports.json',config)
    write(out/'prepared_receipt.json',{'source_hashes':source_hashes,'config_sha256':sha(out/'design_before_reports.json'),
      'python':sys.version,'packages':{name:importlib.metadata.version(name) for name in ['numpy','pandas','scipy','scikit-learn']},
      'synthetic_reports_computed':0,'actual_labels_or_scores_opened':False})
    start=time.perf_counter();rows=[]
    for scenario in config['scenarios']:
        for cls in r.CLASSES:
            data,key=fixture(12,4,target_class=cls,broad=True)
            if scenario=='mixed_failures':
                change=data[-1].path.eq('synthetic://file_0000')&data[-1].job_id.eq(f'pattern_rf:{cls}:0')
                data[-1].loc[change,['status','execution_status']]='model_error';data[-1].loc[change,'score']=np.nan
                change=data[-1].path.eq('synthetic://file_0005')&data[-1].method.eq('slither')
                data[-1].loc[change,['status','execution_status']]='compile_error';data[-1].loc[change,'score']=np.nan
            elif scenario=='unknown_outside_common':
                case=key[key['class'].eq(cls)].iloc[0]
                data[5].loc[data[5].case_id.eq(case.case_id),'adjudicated_judgment']='unknown'
                change=data[-1].path.eq(case.path)&data[-1].job_id.eq(f'raw_tfidf_lr:{cls}:0')
                data[-1].loc[change,['status','execution_status']]='timeout';data[-1].loc[change,'score']=np.nan
            exploratory=f'{scenario}:{cls}' in config['exploratory_runs']
            result=r.report_class(*data,cls,case_manifest=key,expected_files=12,expected_sample_cases=8,synthetic_fixture=True,
              review_fractions=config['review_fractions'],replicates=config['replicates'],seed=config['seed'],alpha=config['alpha'],include_exploratory=exploratory)
            audit=result.pop('engine_audit')
            if audit is not None:
                filename=f'engine_audit_{scenario}_{cls}.json';write(out/filename,audit)
                result['engine_audit_artifact']={'filename':filename,'sha256':sha(out/filename),'raw_all_pairs_per_domain':78,
                  'purpose':'complete unchanged exploratory engine output, not primary inference'}
            filename=f'report_{scenario}_{cls}.json';write(out/filename,result)
            ds=result['primary']['domains']
            rows.append({'scenario':scenario,'class':cls,'primary_vectors':len(result['primary_inventory']),
              'common_success_n':ds['common_success']['population_n'],'contrast_counts':{name:len(d['raw_LR_reference_contrasts']) for name,d in ds.items()},
              'full_HT_status':ds['full_frame_pipeline']['reference_positive_total']['status'],
              'common_HT_status':ds['common_success']['reference_positive_total']['status'],'exploratory':exploratory,
              'report_sha256':sha(out/filename)})
    if checked_hashes()!=source_hashes:raise ValueError('Source or inactive policy changed during reports')
    receipt={'schema':'fictional_reporting_receipt_v1','status':'complete_fictional_reports_only','source_hashes':source_hashes,
      'config_sha256':sha(out/'design_before_reports.json'),'reports':rows,'wall_seconds':time.perf_counter()-start,
      'output_hashes':{p.name:sha(p) for p in out.glob('*.json')},'actual_human_judgments_created':0,'actual_labels_or_scores_opened':False,
      'model_fits_or_tool_calls':0,'amendment_adopted':False,'current_inference_gate_changed':False,
      'prospective_actual_study_freeze':False,'completed_utc':datetime.now(timezone.utc).isoformat()}
    write(out/'receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'reports':len(rows),'wall_seconds':receipt['wall_seconds'],'actual_operations':0}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
