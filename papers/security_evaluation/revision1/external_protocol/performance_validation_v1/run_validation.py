#!/usr/bin/env python3
"""Prespecified fully synthetic exact-sampling AP diagnostic; no real data I/O."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import pandas as pd
import scipy
import sklearn

HERE=Path(__file__).resolve().parent
PROTOCOL=HERE.parent
EXPECTED_V1='b5bdd17f6e90b0456b03ca64a5d528e53927437a9d72cfef0d9d962316e46d9b'
SEEDS=(2026102601,2026102602,2026102603)
B=2000
ALPHA=.05
TOL=1e-12


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def encoded(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def dump(p,x):
    p=Path(p);temp=p.with_name(p.name+'.tmp')
    temp.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n');temp.replace(p)
def identifier(x):return hashlib.sha256(encoded(x).encode()).hexdigest()


def scenarios():
    result=[]
    patterns={'one_top':[0],'one_middle':[9],'one_bottom':[19],'one_oversampled':[16],
              'two_spread':[1,18],'half_alternating':list(range(0,20,2))}
    for pattern,positive in patterns.items():
        for score_type in ('unique','blocks5','all_tied'):
            for design in ('srs4','unequal2x2','census'):
                result.append(make_case(20,positive,pattern,score_type,design))
    result.extend(make_case(20,[],'no_positive','unique',d) for d in ('srs4','census'))
    result.extend(make_case(50,[i],name,'unique','srs4') for i,name in
                  [(0,'one_top'),(24,'one_middle'),(49,'one_bottom')])
    assert len(result)==59
    return result


def make_case(N,positive,pattern,score_type,design):
    scores=list(range(N,0,-1)) if score_type=='unique' else (
        [(N-1-i)//5 for i in range(N)] if score_type=='blocks5' else [0]*N)
    if design=='unequal2x2':
        minority={1,6,11,16}
        strata=[{'id':'A','units':[i for i in range(N) if i not in minority],'n':2},
                {'id':'B','units':sorted(minority),'n':2}]
    else:strata=[{'id':'A','units':list(range(N)),'n':N if design=='census' else 4}]
    total=math.prod(math.comb(len(h['units']),h['n']) for h in strata)
    return {'id':f'N{N}_{design}_{score_type}_{pattern}','N':N,'pattern':pattern,
            'design':design,'score_type':score_type,'y':[int(i in positive) for i in range(N)],
            'scores':scores,'strata':strata,'sample_states':total}


def prepare(out):
    out.mkdir(parents=True,exist_ok=False)
    assert sha(PROTOCOL/'performance_v1/performance.py')==EXPECTED_V1
    sources={'driver':Path(__file__),'design':HERE/'DESIGN.md',
             'performance_v1':PROTOCOL/'performance_v1/performance.py',
             'review_estimators':PROTOCOL/'review_estimators.py'}
    snap=out/'source_before';(snap/'external_protocol/performance_v1').mkdir(parents=True)
    for name,path in sources.items():
        target=(snap/'external_protocol/performance_v1/performance.py' if name=='performance_v1' else
                snap/'external_protocol/review_estimators.py' if name=='review_estimators' else snap/path.name)
        shutil.copy2(path,target)
    cases=scenarios();assert sum(c['sample_states'] for c in cases)==795934
    config={'schema':'synthetic_finite_population_ap_validation_v1','frozen_utc':utc(),
        'sources':{k:{'path':str(p),'sha256':sha(p)} for k,p in sources.items()},
        'scenarios':cases,'scenario_count':59,'total_exact_sample_states':795934,
        'bootstrap_replicates':B,'bootstrap_seeds':list(SEEDS),'alpha':ALPHA,'comparison_tolerance':TOL,
        'exact_bootstrap_quantile':'discrete inverse CDF, smallest value with cumulative probability>=q',
        'monte_carlo_quantile':'unchanged v1 numpy.quantile default linear convention',
        'oracle_rule':'first positive configuration per(N,design,score_type), all2000 replicates, first seed',
        'synthetic_only':True,'real_project_data_read':False,'external_gate_modified':False,
        'environment':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,
                       'scipy':scipy.__version__,'sklearn':sklearn.__version__}}
    dump(out/'design_before_results.json',config)
    dump(out/'manifest.json',{'status':'frozen_no_results','config_sha256':sha(out/'design_before_results.json')})
    print(json.dumps({'frozen':sha(out/'design_before_results.json'),'scenarios':59,'sample_states':795934}),flush=True)


def independent_true_ap(y,scores):
    y=np.asarray(y,dtype=int);scores=np.asarray(scores)
    if y.sum()==0:return None
    order=np.argsort(-scores,kind='stable');sy=y[order];ss=scores[order]
    ends=np.flatnonzero(np.r_[ss[:-1]!=ss[1:],True]);tp=np.cumsum(sy)[ends]
    return float(np.sum(np.diff(np.r_[0,tp])*tp/(ends+1))/y.sum())


def key_for(case,units):
    unit_stratum={i:h['id'] for h in case['strata'] for i in h['units']}
    selected_scores=[case['scores'][i] for i in units]
    ranks={score:j for j,score in enumerate(sorted(set(selected_scores)))}
    return (tuple((h['id'],len(h['units']),h['n']) for h in case['strata']),
            tuple(unit_stratum[i] for i in units),tuple(case['y'][i] for i in units),
            tuple(ranks[score] for score in selected_scores))


def sample_distribution(case):
    choices=[list(itertools.combinations(h['units'],h['n'])) for h in case['strata']]
    grouped=Counter()
    # This is exact enumeration, not a random sample of the sample space.
    for parts in itertools.product(*choices):
        units=sorted(itertools.chain.from_iterable(parts))
        grouped[key_for(case,units)]+=1
    assert sum(grouped.values())==case['sample_states']
    return grouped


def frames(key):
    designs,strata,y,scores=key
    allocation=pd.DataFrame([{'source_id':h,'class':'synthetic_target','label_status':'fictional',
                             'N_h':N,'n_h':n} for h,N,n in designs])
    by_id={h:(N,n) for h,N,n in designs};rows=[]
    for i,h in enumerate(strata):
        N,n=by_id[h]
        rows.append({'case_id':f'fictional_unit_{i:03d}','source_id':h,'class':'synthetic_target',
            'label_status':'fictional','N_h':N,'n_h':n,'inclusion_probability':n/N,'design_weight':N/n})
    return pd.DataFrame(rows),allocation,np.asarray(y,float),np.asarray(scores,float)


def compositions(total,parts):
    if parts==1:yield (total,)
    else:
        for first in range(total+1):
            for rest in compositions(total-first,parts-1):yield (first,)+rest


def support(key):
    designs,strata,_,_=key;groups=[]
    for h,N,n in designs:
        ids=np.flatnonzero(np.asarray(strata)==h)
        if n==N:options=[(np.ones(n),1)];denominator=1
        else:
            f=n/N;s=math.sqrt(1-f);baseline=f/(1+s);options=[]
            for counts in compositions(n-1,n):
                coefficient=math.factorial(n-1)//math.prod(math.factorial(c) for c in counts)
                weights=(N/n)*(baseline+s*n/(n-1)*np.asarray(counts))
                options.append((weights,coefficient))
            denominator=n**(n-1)
        groups.append((ids,options,denominator))
    denominator=math.prod(g[2] for g in groups);weights=[];multiplicities=[]
    for selected in itertools.product(*(g[1] for g in groups)):
        row=np.empty(len(strata));multiple=1
        for (ids,_,_),(values,coefficient) in zip(groups,selected):
            row[ids]=values;multiple*=coefficient
        weights.append(row);multiplicities.append(multiple)
    assert sum(multiplicities)==denominator
    assert len(weights)<=20 and denominator<=64
    return np.asarray(weights),multiplicities,denominator


def evaluate_configuration(key,production):
    sample,allocation,y,scores=frames(key);weights=sample.design_weight.to_numpy(float)
    vectors,multiplicities,denominator=support(key)
    census=bool((allocation.N_h==allocation.n_h).all())
    evaluated=production.ap_interval(y,scores,weights,vectors if len(vectors)>1 else np.repeat(vectors,2,axis=0),
                                     alpha=ALPHA,census=census)
    point=evaluated['point'];values=evaluated['replicate_values'][:len(vectors)]
    if point is None:
        values=[None]*len(vectors)
        methods={'exact_support':{'interval':None,'invalid_fraction':1.0,'status':evaluated['status']}}
    else:
        assert len(values)==len(vectors) and all(v is not None for v in values)
        ordered=np.sort(np.repeat(np.asarray(values),multiplicities))
        exact=[point,point] if census else [float(ordered[math.ceil(q*denominator)-1]) for q in (.025,.975)]
        methods={'exact_support':{'interval':exact,'invalid_fraction':0.0,'status':evaluated['status']}}
    lookup={v.tobytes():value for v,value in zip(vectors,values)}
    for seed in SEEDS:
        reps=production.rao_wu_weights(sample,allocation,replicates=B,seed=seed)
        assert all(row.tobytes() in lookup for row in reps)
        if point is None:
            interval=None;invalid=1.0
        else:
            replicate_ap=np.asarray([lookup[row.tobytes()] for row in reps])
            assert np.isfinite(replicate_ap).all()
            interval=[point,point] if census else list(map(float,np.quantile(replicate_ap,[.025,.975])))
            invalid=0.0
        methods[f'mc_seed_{seed}']={'interval':interval,'invalid_fraction':invalid,'status':evaluated['status']}
    return {'key':key,'point':point,'sample_positive_count':int(y.sum()),'census':census,
            'bootstrap_support_weights':vectors.tolist(),'support_multiplicities':multiplicities,
            'support_denominator':denominator,'support_production_ap_values':values,'methods':methods}


def direct_oracle(key,cached,production):
    sample,allocation,y,scores=frames(key)
    reps=production.rao_wu_weights(sample,allocation,replicates=B,seed=SEEDS[0])
    actual=production.ap_interval(y,scores,sample.design_weight.to_numpy(float),reps,ALPHA,census=cached['census'])
    expected=cached['methods'][f'mc_seed_{SEEDS[0]}']
    assert actual['point']==cached['point']
    assert actual['interval']==expected['interval']
    assert actual['invalid_replicates']/B==expected['invalid_fraction']
    return {'production_interval_matches_support_lookup':True,'replicates':B,'seed':SEEDS[0],
            'point':actual['point'],'status':actual['status'],'interval':actual['interval']}


def aggregate(case,true_ap,rows,method):
    total=case['sample_states'];issued=covered=below=above=zero=0
    width=invalid=bias=square_error=0.0
    for row in rows:
        count=row['sample_count'];value=row['configuration'];point=value['point']
        result=value['methods'][method];interval=result['interval'];invalid+=count*result['invalid_fraction']
        if interval is None:continue
        assert true_ap is not None
        lo,hi=interval;issued+=count;width+=count*(hi-lo);zero+=count*int(hi-lo<=TOL)
        covered+=count*int(lo-TOL<=true_ap<=hi+TOL)
        below+=count*int(hi<true_ap-TOL);above+=count*int(lo>true_ap+TOL)
        bias+=count*(point-true_ap);square_error+=count*(point-true_ap)**2
    return {'scenario':case['id'],'N':case['N'],'K':sum(case['y']),'prevalence':sum(case['y'])/case['N'],
        'design':case['design'],'score_type':case['score_type'],'pattern':case['pattern'],'method':method,
        'true_population_ap':true_ap,'exact_sample_states':total,'issued_sample_states':issued,
        'covered_sample_states':covered if true_ap is not None else None,
        'interval_issuance_probability':issued/total,'undefined_or_unissued_probability':1-issued/total,
        'unconditional_issued_and_covering_probability':covered/total if true_ap is not None else None,
        'coverage_conditional_on_issued':covered/issued if issued else None,
        'mean_width_conditional_on_issued':width/issued if issued else None,
        'zero_width_fraction_conditional_on_issued':zero/issued if issued else None,
        'invalid_replicate_fraction_all_samples':invalid/total,
        'invalid_replicate_fraction_positive_samples':0.0 if issued else None,
        'interval_below_truth_probability':below/total if true_ap is not None else None,
        'interval_above_truth_probability':above/total if true_ap is not None else None,
        'point_bias_conditional_on_defined':bias/issued if issued else None,
        'point_rmse_conditional_on_defined':math.sqrt(square_error/issued) if issued else None}


def run(out):
    manifest=json.loads((out/'manifest.json').read_text())
    assert sha(out/'design_before_results.json')==manifest['config_sha256']
    config=json.loads((out/'design_before_results.json').read_text())
    for row in config['sources'].values():assert sha(row['path'])==row['sha256']
    assert config['bootstrap_replicates']==B and config['bootstrap_seeds']==list(SEEDS)
    spec=importlib.util.spec_from_file_location('immutable_performance_v1',out/'source_before/external_protocol/performance_v1/performance.py')
    production=importlib.util.module_from_spec(spec);spec.loader.exec_module(production)
    assert sha(out/'source_before/external_protocol/performance_v1/performance.py')==EXPECTED_V1
    cache_dir=out/'configurations';scenario_dir=out/'scenarios';cache_dir.mkdir(exist_ok=True);scenario_dir.mkdir(exist_ok=True)
    checkpoint_path=out/'checkpoints.json'
    checkpoint=json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {'files':{},'oracles':{}}
    for p,h in checkpoint['files'].items():assert sha(out/p)==h
    manifest.update(status='running_synthetic_only',started_utc=manifest.get('started_utc',utc()));dump(out/'manifest.json',manifest)
    started=time.monotonic();summary=[]
    for case in config['scenarios']:
        output=scenario_dir/(case['id']+'.json')
        if output.exists():
            assert str(output.relative_to(out)) in checkpoint['files']
            summary.extend(json.loads(output.read_text())['summary']);continue
        truth=independent_true_ap(case['y'],case['scores'])
        other=production.weighted_ap(case['y'],case['scores'],np.ones(case['N']))
        assert (truth is None and other is None) or math.isclose(truth,other,rel_tol=1e-14,abs_tol=1e-14)
        grouped=sample_distribution(case);rows=[];oracle_key=f"N{case['N']}_{case['design']}_{case['score_type']}"
        for key,count in sorted(grouped.items()):
            uid=identifier(key);path=cache_dir/(uid+'.json')
            if path.exists():
                assert str(path.relative_to(out)) in checkpoint['files']
                value=json.loads(path.read_text());assert identifier(value['key'])==uid
            else:
                value=evaluate_configuration(key,production);dump(path,value)
                checkpoint['files'][str(path.relative_to(out))]=sha(path);dump(checkpoint_path,checkpoint)
            if value['point'] is not None and oracle_key not in checkpoint['oracles']:
                checkpoint['oracles'][oracle_key]={'configuration_id':uid,**direct_oracle(key,value,production)}
                dump(checkpoint_path,checkpoint)
            rows.append({'configuration_id':uid,'sample_count':count,'probability':count/case['sample_states'],
                         'configuration':value})
        methods=('exact_support',)+tuple(f'mc_seed_{s}' for s in SEEDS)
        case_summary=[aggregate(case,truth,rows,method) for method in methods]
        dump(output,{'scenario':case,'true_population_ap':truth,'configuration_count':len(grouped),
            'distribution':[{'configuration_id':r['configuration_id'],'sample_count':r['sample_count'],
                             'probability':r['probability']} for r in rows],'summary':case_summary})
        checkpoint['files'][str(output.relative_to(out))]=sha(output);dump(checkpoint_path,checkpoint)
        summary.extend(case_summary)
        exact=case_summary[0]
        print(json.dumps({'case':case['id'],'states':case['sample_states'],'configurations':len(grouped),
            'true_ap':truth,'issuance':exact['interval_issuance_probability'],
            'conditional_coverage':exact['coverage_conditional_on_issued'],
            'unconditional_issued_covered':exact['unconditional_issued_and_covering_probability']}),flush=True)
    pd.DataFrame(summary).to_csv(out/'summary.csv',index=False)
    dump(out/'production_oracle_checks.json',checkpoint['oracles'])
    assert len(summary)==59*4
    manifest.update(status='complete_synthetic_finite_population_diagnostic',finished_utc=utc(),
        scenario_count=59,exact_sample_states=795934,configuration_count=len(list(cache_dir.glob('*.json'))),
        direct_production_oracles=len(checkpoint['oracles']),runtime_seconds_this_invocation=time.monotonic()-started,
        output_hashes={'summary.csv':sha(out/'summary.csv'),'checkpoints.json':sha(checkpoint_path),
                       'production_oracle_checks.json':sha(out/'production_oracle_checks.json')},
        real_project_labels_or_scores_used=False,new_external_scores=0,v1_modified=False)
    dump(out/'manifest.json',manifest)
    print(json.dumps({'status':manifest['status'],'configurations':manifest['configuration_count']}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.action=='prepare':prepare(args.out.resolve())
    else:run(args.out.resolve())
