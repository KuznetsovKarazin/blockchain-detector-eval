"""Independent combinatorial check of one prespecified synthetic AP scenario.

No estimator module, project source, model, or human reference is imported.
"""
import hashlib
import itertools
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
SCENARIO=HERE.parent/'external_protocol/performance_validation_v1/run_20261026_v1/scenarios/N20_srs4_blocks5_one_top.json'


def main():
    out=HERE/'rare_positive_ap_counterexample_verification.json'
    if out.exists():raise FileExistsError('Do not overwrite this identified independent check')
    record=json.loads(SCENARIO.read_text());case=record['scenario']
    if case['y']!=[1]+[0]*19 or case['scores']!=[3]*5+[2]*5+[1]*5+[0]*5:
        raise ValueError('Synthetic scenario differs from the reviewed analytic example')
    total=math.comb(20,4);included=math.comb(19,3);no_tied_negative=math.comb(15,3)
    truth=1/5;scale=math.sqrt(1-4/20);baseline=1-scale;increment=scale*4/3
    rows=[];covered=0
    for t in range(4):
        # Given the unique positive is sampled, t of its four tied negatives
        # and 3-t of the fifteen lower-score negatives accompany it.
        count=math.comb(4,t)*math.comb(15,3-t)
        values=[]
        for draws in itertools.product(range(4),repeat=3):
            weights=[baseline+increment*draws.count(i) for i in range(4)]
            # Only one positive: AP is precision of its top score group.
            values.append(weights[0]/sum(weights[:t+1]))
        values.sort();interval=[values[math.ceil(.025*64)-1],values[math.ceil(.975*64)-1]]
        covers=interval[0]-1e-12<=truth<=interval[1]+1e-12
        covered+=count*int(covers)
        rows.append(dict(sampled_tied_negatives=t,positive_included_sample_states=count,
                         exact_bootstrap_ordered_states=64,interval=interval,covers_population_AP=covers))
    expected=next(row for row in record['summary'] if row['method']=='exact_support')
    actual=dict(exact_sample_states=total,issued_sample_states=included,covered_sample_states=covered,
                coverage_conditional_on_issued=covered/included,
                unconditional_issued_and_covering_probability=covered/total)
    for key,value in actual.items():
        if not math.isclose(value,expected[key],rel_tol=0,abs_tol=1e-12):raise ValueError('Independent count mismatch: '+key)
    if covered!=included-no_tied_negative:raise ValueError('Analytic miss-event is not the exact failure set')
    result=dict(status='pass',synthetic_only=True,source_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                scenario_sha256=hashlib.sha256(SCENARIO.read_bytes()).hexdigest(),
                derivation='Conditional on positive selection, no sampled tied negative has probability C(15,3)/C(19,3); it forces every AP=1 although population AP=1/5.',
                true_population_AP=truth,forced_miss_sample_states=no_tied_negative,
                forced_miss_fraction_conditional=no_tied_negative/included,**actual,
                conditional_cases=rows,estimator_code_imported=False,real_data_read=False)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
