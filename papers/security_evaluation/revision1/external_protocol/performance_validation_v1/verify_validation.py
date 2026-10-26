"""Independent scalar AP, ordered bootstrap support, and sample-count checks."""
import hashlib
import itertools
import json
import math
from collections import Counter
from fractions import Fraction
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
RUN=HERE/'run_20261026_v1'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def uid(key):return hashlib.sha256(json.dumps(key,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def scalar_ap(y,s,w):
    total=math.fsum(weight for target,weight in zip(y,w) if target==1)
    if total==0:return None
    pieces=[]
    for target,score,weight in zip(y,s,w):
        if target!=1:continue
        denominator=math.fsum(v for z,v in zip(s,w) if z>=score)
        numerator=math.fsum(v for outcome,z,v in zip(y,s,w) if z>=score and outcome==1)
        pieces.append(weight*numerator/denominator)
    return math.fsum(pieces)/total


def main():
    manifest=json.loads((RUN/'manifest.json').read_text())
    config=json.loads((RUN/'design_before_results.json').read_text())
    assert manifest['config_sha256']==sha(RUN/'design_before_results.json')
    assert config['frozen_utc']<manifest['started_utc']<manifest['finished_utc']
    for p,h in manifest['output_hashes'].items():assert sha(RUN/p)==h
    checkpoints=json.loads((RUN/'checkpoints.json').read_text())
    for p,h in checkpoints['files'].items():assert sha(RUN/p)==h
    configurations={}
    scalar_checks=support_sequences=0
    for path in sorted((RUN/'configurations').glob('*.json')):
        item=json.loads(path.read_text());key=item['key'];assert uid(key)==path.stem
        configurations[path.stem]=item
        design,strata,y,scores=key;lookup={name:(N,n) for name,N,n in design}
        weights=[lookup[h][0]/lookup[h][1] for h in strata]
        point=scalar_ap(y,scores,weights)
        assert (point is None and item['point'] is None) or math.isclose(point,item['point'],rel_tol=1e-12,abs_tol=1e-12)
        rows=np.asarray(item['bootstrap_support_weights'])
        computed=[]
        for row,value in zip(rows,item['support_production_ap_values']):
            actual=scalar_ap(y,scores,row)
            assert (actual is None and value is None) or math.isclose(actual,value,rel_tol=1e-12,abs_tol=1e-12)
            computed.append(actual);scalar_checks+=1
        # Enumerate ordered draws, independently of multinomial compositions.
        group_options=[]
        for name,N,n in design:
            ids=[i for i,h in enumerate(strata) if h==name]
            if N==n:options=[np.ones(n)]
            else:
                options=[];scale=math.sqrt(1-n/N)
                for draw in itertools.product(range(n),repeat=n-1):
                    counts=[draw.count(i) for i in range(n)]
                    options.append(np.array([(N/n)*(1-scale+scale*n/(n-1)*m) for m in counts]))
            group_options.append((ids,options))
        matched=Counter()
        for selected in itertools.product(*(options for _,options in group_options)):
            row=np.empty(len(strata))
            for (ids,_),values in zip(group_options,selected):row[ids]=values
            candidates=np.flatnonzero(np.all(np.isclose(rows,row,rtol=1e-13,atol=1e-13),axis=1))
            assert len(candidates)==1
            matched[int(candidates[0])]+=1;support_sequences+=1
        assert [matched[i] for i in range(len(rows))]==item['support_multiplicities']
        assert sum(matched.values())==item['support_denominator']
        if point is not None:
            endpoints=[]
            for target in (Fraction(1,40),Fraction(39,40)):
                cumulative=0
                for value,multiple in sorted(zip(item['support_production_ap_values'],item['support_multiplicities'])):
                    cumulative+=multiple
                    if Fraction(cumulative,item['support_denominator'])>=target:
                        endpoints.append(value);break
            assert endpoints==item['methods']['exact_support']['interval']
    table=pd.read_csv(RUN/'summary.csv').set_index(['scenario','method'])
    enumerated=0;summary_checks=0
    for case in config['scenarios']:
        saved=json.loads((RUN/'scenarios'/f"{case['id']}.json").read_text())
        truth=scalar_ap(case['y'],case['scores'],[1]*case['N'])
        assert (truth is None and saved['true_population_ap'] is None) or math.isclose(truth,saved['true_population_ap'],abs_tol=1e-12)
        h_of={unit:h['id'] for h in case['strata'] for unit in h['units']}
        d=[[h['id'],len(h['units']),h['n']] for h in case['strata']]
        counts=Counter()
        for selected in itertools.product(*(itertools.combinations(h['units'],h['n']) for h in case['strata'])):
            ids=sorted(itertools.chain.from_iterable(selected));levels=sorted({case['scores'][i] for i in ids})
            key=(tuple(tuple(x) for x in d),tuple(h_of[i] for i in ids),tuple(case['y'][i] for i in ids),
                 tuple(levels.index(case['scores'][i]) for i in ids))
            counts[key]+=1;enumerated+=1
        actual={uid(key):number for key,number in counts.items()}
        expected={row['configuration_id']:row['sample_count'] for row in saved['distribution']}
        assert actual==expected and sum(actual.values())==case['sample_states']
        for row in saved['summary']:
            issued=covered=0;width=0.
            for key,count in actual.items():
                ci=configurations[key]['methods'][row['method']]['interval']
                if ci is not None:
                    issued+=count;width+=count*(ci[1]-ci[0])
                    covered+=count*int(ci[0]-1e-12<=truth<=ci[1]+1e-12)
            assert issued==row['issued_sample_states']
            if truth is not None:
                assert covered==row['covered_sample_states']
                assert math.isclose(covered/case['sample_states'],row['unconditional_issued_and_covering_probability'],abs_tol=1e-14)
            if issued:
                assert math.isclose(covered/issued,row['coverage_conditional_on_issued'],abs_tol=1e-14)
                assert math.isclose(width/issued,row['mean_width_conditional_on_issued'],abs_tol=1e-12)
            csv=table.loc[(case['id'],row['method'])]
            assert int(csv.issued_sample_states)==issued
            summary_checks+=1
    assert enumerated==795934 and summary_checks==236
    analytic={'scenario':'N20_srs4_blocks5_one_top','all_samples':math.comb(20,4),
        'positive_included_samples':math.comb(19,3),'singleton_top_tie_samples':math.comb(15,3),
        'covered_samples':math.comb(19,3)-math.comb(15,3),
        'conditional_coverage_fraction':'514/969','unconditional_issued_covering_fraction':'514/4845',
        'reason':'If positive is sampled without any other top-tie member, every positive-weight replicate ranks it alone at the top: AP=1 and CI=[1,1], while true AP=1/5.'}
    target=table.loc[(analytic['scenario'],'exact_support')]
    assert target.covered_sample_states==analytic['covered_samples']
    result={'schema':'independent_synthetic_ap_validation_audit_v1','status':'pass',
        'auditor_sha256':sha(__file__),'design_sha256':sha(RUN/'design_before_results.json'),
        'configuration_files_checked':len(configurations),'scalar_weighted_ap_checks':scalar_checks,
        'ordered_bootstrap_sequences_checked':support_sequences,'all_sampling_states_reenumerated':enumerated,
        'summary_rows_recomputed':summary_checks,'checkpoint_file_hashes_checked':len(checkpoints['files']),
        'analytical_counterexample':analytic,'no_real_labels_scores_or_sources_used':True,
        'actual_external_design_coverage_estimated':False}
    destination=HERE/'INDEPENDENT_VERIFICATION.json';assert not destination.exists()
    destination.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
