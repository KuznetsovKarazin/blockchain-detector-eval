import numpy as np
import pandas as pd
from run_mechanism import group_stars,partition,weighted_cuts,contract_projects

def test_removed_anchor_does_not_remove_equivalence():
    n=pd.DataFrame({'node_id':[0,1,2],'scope':['upstream']*3,'project_id':['p']*3}).set_index('node_id',drop=False)
    left,right=group_stars(n,np.array([1,2]),'project_id')
    assert list(zip(left,right))==[(1,2)]
    assert partition(3,np.array([1,2]),left,right)[1]==partition(3,np.array([1,2]),left,right)[2]

def test_weighted_cuts_chain():
    a,b=weighted_cuts({0:{1},1:{0,2},2:{1}},{0:4,1:10,2:6})
    assert a==[dict(vertex=1,component_dapp_files=20,removed_project_dapp_files=10,remaining_pieces=2,separated_dapp_files=4,disconnected_dapp_pairs=24)]
    assert sorted(x['smaller_side_dapp_files'] for x in b)==[4,6]

def test_triangle_has_no_star_articulations():
    a,b=weighted_cuts({0:{1,2},1:{0,2},2:{0,1}},{0:4,1:10,2:6})
    assert not a and not b

def test_raw_equivalence_contracts_to_clique():
    n=pd.DataFrame({'node_id':[0,1,2],'scope':['upstream']*3,'project_id':['a','b','c'],'identifier_key':['x']*3,'file_sha256':['same']*3,'dataset':['dappscan']*3}).set_index('node_id',drop=False)
    adj,weights,*_=contract_projects(n,np.array([0,1,2]),pd.DataFrame(columns=['left','right','jaccard']),.8)
    assert all(len(x)==2 for x in adj.values())
    assert weighted_cuts(adj,weights)==([],[])

def test_zero_weight_connector_can_be_articulation():
    a,_=weighted_cuts({0:{1},1:{0,2},2:{1}},{0:4,1:0,2:6})
    assert a[0]['separated_dapp_files']==4

def test_disconnected_components_keep_local_weights():
    a,b=weighted_cuts({0:{1},1:{0},2:set()},{0:2,1:3,2:100})
    assert not a and b[0]['component_dapp_files']==5
