"""Metadata design tests: label blindness, concentration and trivial contrasts."""
import importlib.util
from pathlib import Path
import pandas as pd

PATH=Path(__file__).resolve().parents[1]/'papers/security_evaluation/design_feasibility/audit_designs.py'
spec=importlib.util.spec_from_file_location('audit_designs',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def frame():
    d=pd.DataFrame({'file_id':range(8),'path':[f'{i}.sol' for i in range(8)],
                    'group':['A','B','B','C','D','D','E','E'],'comp':[1,1,2,2,3,4,5,6],
                    'reentrancy':[1,1,0,0,1,0,1,0],'unchecked':[0,1,0,1,0,1,0,1]})
    d['joint_id']=m.dev.joint_groups(d)
    return d


def test_selection_label_blind_and_input_order_invariant():
    d=frame();a=m.sample_files(d,.5,2,'full').file_id.tolist()
    d.reentrancy=1-d.reentrancy;d.unchecked=1-d.unchecked
    b=m.sample_files(d.sample(frac=1,random_state=8),.5,2,'full').file_id.tolist()
    assert a==b


def test_component_concentration_distinguishes_raw_number_and_dominance():
    x=m.concentration(['giant']*90+[f'g{i}' for i in range(10)])
    assert x['n_components']==11 and x['largest_component_fraction']==.9
    assert 1<x['inverse_simpson_component_count']<1.24
    assert m.concentration(['A','B','C','D'])['inverse_simpson_component_count']==4


def test_entire_joint_component_makes_all_pools_identical():
    d=frame();giant=d.iloc[0].joint_id;t=d[d.joint_id==giant]
    summary,_=m.assess_design(d,t,giant)
    assert summary['all_pools_identical']
    assert not summary['nontrivial_restriction_contrast']
    assert not summary['all_operational_screens_pass']


def test_partial_component_retains_transitive_exclusion():
    d=frame();giant=d.iloc[0].joint_id;t=d.iloc[[0,1]]
    summary,details=m.assess_design(d,t,giant)
    assert summary['unrestricted_joint_removed_n']==2
    assert summary['test_components']==1
    assert not summary['dispersion_screen']
    assert all(x['n_pool']==4 for x in details if x['regime']=='joint_project_clone_disjoint')


def test_whole_component_selection_never_splits_component():
    d=frame();sel=m.sample_whole_components(d,.5,0)
    for joint in sel.joint_id.unique():
        assert set(sel[sel.joint_id==joint].file_id)==set(d[d.joint_id==joint].file_id)


def test_candidate_list_fixed_and_contains_95_labelblind_designs():
    specs=m.specifications()
    assert len(specs)==95 and len({x['test_id'] for x in specs})==95
    assert {x['design_seed'] for x in specs}==set(range(5))
