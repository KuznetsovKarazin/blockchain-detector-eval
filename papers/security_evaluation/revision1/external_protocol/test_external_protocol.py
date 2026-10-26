"""Tests of actual sampling design properties and protocol fail-closed behavior."""
import importlib.util
from pathlib import Path
import pandas as pd
import numpy as np
BASE=Path(__file__).parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,BASE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=load('build_packet');gate=load('validate_gate')

def frame():
    rows=[]
    for source,cls,status,n in [('A','reentrancy',m.POS,7),('B','unchecked',m.POS,30),('B','unchecked','unknown_source_status',80),('A','reentrancy','no_finding',50)]:
        rows.extend({'source_id':source,'class':cls,'label_status':status,'path':source+cls+status+str(i)} for i in range(n))
    return pd.DataFrame(rows)

def test_allocation_census_probabilities_and_fixed_budget():
    d=frame();a=m.allocate(d,n=60)
    assert a.n_h.sum()==60 and (a.n_h<=a.N_h).all() and (a.n_h>=2).all()
    census=a[(a.source_id=='A')&(a.label_status==m.POS)].iloc[0]
    assert census.n_h==7 and census.inclusion_probability==1
    assert np.allclose(a.design_weight*a.inclusion_probability,1)

def test_sample_is_order_invariant_no_replacement_and_each_stratum_exact():
    d=frame();a=m.allocate(d,n=60);x=m.sample_cases(d,a);y=m.sample_cases(d.sample(frac=1,random_state=55),a)
    assert x[['case_id','path']].equals(y[['case_id','path']])
    assert not x[['path','class']].duplicated().any()
    n=x.groupby(m.STRATA).size();want=a.set_index(m.STRATA).n_h
    assert n.equals(want)

def test_estimator_recovers_constant_outcomes_despite_oversampling():
    d=frame();a=m.allocate(d,n=60);sample=m.sample_cases(d,a)
    # Constant finite-population y=1 must estimate exactly N under HT.
    assert abs(sample.design_weight.sum()-len(d))<1e-9

def test_gate_missing_frozen_state_and_humans_is_closed():
    p={'hashes':{},'freeze_prerequisites':{'packet':True},'probability_audit':{},'status':'draft'}
    b=gate.blockers(p,BASE,'score')
    assert 'protocol_not_prospectively_frozen' in b and 'missing:reviewer_1_name' in b
