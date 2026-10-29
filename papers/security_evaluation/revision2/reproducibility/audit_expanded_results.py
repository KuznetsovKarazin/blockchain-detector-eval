"""Independent post-run score arithmetic with rational tied-group calculations."""
import argparse
from collections import Counter
import csv
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();repo=a.repo.resolve();run=repo/'papers/security_evaluation/revision2/model_link/expanded_contrast_20261028_v1'
    design=json.loads((Path(__file__).parent/'EXPANDED_CONTRAST_DESIGN_AUDIT.json').read_text())
    freeze=json.loads((run/'FREEZE_BEFORE_FITTING.json').read_text());complete=json.loads((run/'COMPLETE.json').read_text())
    assert sha(run/'FREEZE_BEFORE_FITTING.json')==complete['freeze_sha256']==design['freeze_sha256']
    for p,h in freeze['prepared_files'].items():assert sha(run/p)==h
    for p,h in freeze['source_hashes'].items():assert sha(repo/p)==sha(run/'code_snapshot'/p)==h
    jobs=json.loads((run/'config.json').read_text())['jobs'];lookup={j['job_id']:j for j in jobs}
    labels={int(k):v for k,v in json.loads((run/'labels.json').read_text()).items()}
    logical=list(csv.DictReader((run/'logical_results.csv').open()));assert sha(run/'logical_results.csv')==complete['summary_sha256']
    assert [j['job_id'] for j in jobs]==[x['job_id'] for x in logical]
    assert {p.name for p in (run/'fits').iterdir() if p.is_dir()}==set(lookup)
    assert len(jobs)==120 and complete['logical']==120 and complete['physical']==72
    warnings=Counter();physical=reused=failed=artifacts=convergence=0;max_error=0.;verified=[]
    for j,row in zip(jobs,logical):
        folder=run/'fits'/j['job_id'];res=json.loads((folder/'result.json').read_text())
        assert sha(folder/'result.json')==complete['result_hashes'][j['job_id']]
        start=json.loads((folder/'started.json').read_text());assert start['job']==j and start['freeze_sha256']==design['freeze_sha256']
        assert res['physical_fit']==(j['reuse_from'] is None) and res['reuse_from']==j['reuse_from']
        for p,h in res['artifacts'].items():assert sha(folder/p)==h;artifacts+=1
        if res['status']!='ok':failed+=1;continue
        pred=list(csv.DictReader((folder/'predictions.csv').open()));assert [int(x['file_id']) for x in pred]==j['test_ids']
        assert all(x['status']=='ok' and math.isfinite(float(x['score'])) for x in pred)
        grouped={}
        for x in pred:
            score=float(x['score']);n,k=grouped.get(score,(0,0));grouped[score]=(n+1,k+labels[int(x['file_id'])]['reentrancy'])
        assert sum(n for n,k in grouped.values())==1082 and sum(k for n,k in grouped.values())==21
        tp=n_seen=0;ap_value=Fraction(0);yield_by_budget={b:Fraction(0) for b in (54,108,216)}
        for score in sorted(grouped,reverse=True):
            n,k=grouped[score]
            for budget in yield_by_budget:
                slots=min(n,max(0,budget-n_seen));yield_by_budget[budget]+=Fraction(k*slots,n)
            n_seen+=n;tp+=k;ap_value+=Fraction(k*tp,21*n_seen)
        calc={'ap_proxy':float(ap_value),**{f'expected_findings_{b}':float(v) for b,v in yield_by_budget.items()}}
        metric=json.loads((folder/'metrics.json').read_text())
        for name,value in calc.items():
            error=max(abs(value-metric[name]),abs(value-float(row[name])))
            assert error<=1e-12,(j['job_id'],name,error);max_error=max(max_error,error)
        resources=json.loads((folder/'resources.json').read_text())
        if j['reuse_from']:
            p=lookup[j['reuse_from']]
            assert all(j[k]==p[k] for k in ['train_ids','test_ids','seed','method'])
            assert sha(folder/'predictions.csv')==sha(run/'fits'/j['reuse_from']/'predictions.csv')
            assert resources['physical_fit'] is False and resources['total_seconds']==0.;reused+=1
        else:
            physical+=1;warnings.update(resources.get('warnings',[]));convergence+=int(resources.get('convergence_warning',False))
        verified.append({'job_id':j['job_id'],**calc})
    assert physical==72 and reused==48 and failed==complete['failed']==0
    assert not list(run.rglob('*.joblib'))
    result={'schema':'expanded_contrast_independent_postrun_audit_v1','status':'pass','script_sha256':sha(Path(__file__)),
      'design_audit_sha256':sha(Path(__file__).parent/'EXPANDED_CONTRAST_DESIGN_AUDIT.json'),'complete_sha256':sha(run/'COMPLETE.json'),
      'logical_predictions_checked':len(verified),'physical_fits':physical,'reused_logical_evaluations':reused,'failed':failed,
      'per_fit_artifact_hashes_checked':artifacts,'independent_metrics':len(verified)*4,'max_absolute_error':max_error,
      'metric_method':'Fraction arithmetic over equal-score groups; no sklearn or producer metric function called.',
      'physical_warning_counts':dict(warnings),'convergence_warning_fits':convergence,'model_binaries_expected_and_present':False,
      'scope':'Completed configured historical-test diagnostic, not an external assessment or independent-family causal estimate.',
      'new_fits_by_this_audit':0,'source_and_configuration_match_frozen_hashes_at_postrun':True}
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
