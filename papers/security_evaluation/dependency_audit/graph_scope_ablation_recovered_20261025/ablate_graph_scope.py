#!/usr/bin/env python3
"""Separate observed grouping, exhaustive grouping, and source-scope expansion.

Uses complete previously computed lexical edges; no source rescoring or models.
Regenerates group-star links on each selected population, avoiding lost anchors.
"""
import argparse,hashlib,json,shutil,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from run_dependency_audit import ROOT,load_all,sha,dump,csvout

def rebuild(nodes,edges,selected):
    selected=set(selected)
    lexical=edges[(edges.edge_type=='normalized_shingle')&edges.jaccard.ge(.8)&edges.left.isin(selected)&edges.right.isin(selected)]
    left=lexical.left.astype(int).tolist();right=lexical.right.astype(int).tolist();counts={'normalized_shingle':len(left)}
    sub=nodes.loc[nodes.node_id.isin(selected)]
    for field,kind,scope in [('project_id','upstream_project','upstream'),('identifier_key','candidate_identifier','external'),('file_sha256','identical_raw_source',None)]:
        d=sub if scope is None else sub[sub.scope==scope]
        d=d[d[field].notna()&d[field].ne('')];count=0
        for _,g in d.groupby(field,sort=True):
            ids=sorted(g.node_id)
            for j in ids[1:]:left.append(ids[0]);right.append(j);count+=1
        counts[kind]=count
    adjacency=coo_matrix((np.ones(len(left),np.int8),(left,right)),shape=(len(nodes),len(nodes))).tocsr()
    _,component=connected_components(adjacency,directed=False)
    canonical=pd.Series(nodes.node_id.to_numpy()).groupby(component).transform('min').to_numpy()
    # Unselected isolates cannot join selected files; only selected nodes are
    # retained in the canonical projection and scope-level node count.
    return pd.Series(canonical,index=nodes.path),counts

def main():
    p=argparse.ArgumentParser();p.add_argument('--legacy',type=Path,required=True);p.add_argument('--corrected',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--bundle',type=Path,action='append',required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    graph=ROOT/'results/contracts/c2_20261024_004314/groups.parquet';observed=pd.read_parquet(graph)
    nodes=pd.read_csv(a.legacy/'nodes.csv',keep_default_na=False);cnodes=pd.read_csv(a.corrected/'nodes.csv',keep_default_na=False)
    assert nodes.path.equals(cnodes.path) and nodes.file_sha256.equals(cnodes.file_sha256)
    inputs=[graph,a.legacy/'nodes.csv',a.legacy/'edges.csv',a.legacy/'memberships.csv',a.corrected/'nodes.csv',a.corrected/'edges.csv',a.corrected/'memberships.csv']
    inputs += [b/'selected_memberships.csv.gz' for b in a.bundle]
    config={'schema':'graph_scope_ablation_v1','threshold':.8,'normalizations':['legacy','string_aware'],
      'scope_A':'observed original7080 safe_group, historical LSH/CRC32 and recorded provenance limits',
      'scope_B':'exhaustive edges on the same historical7080 files',
      'scope_C':'exhaustive edges on uncapped21950 upstream files',
      'scope_D':'exhaustive edges on all24131 upstream plus external files',
      'grouping_policy':'base: project, identical raw bytes, candidate identifiers; regenerate stars within each selected population',
      'lexical_policy':'induce complete normalized-shingle edge list at0.8; no model scoring',
      'interpretation':'A→B bundles grouping algorithm/representation/provenance differences, not isolated causal LSH effect; B→C and C→D isolate added nodes and incident relations under fixed lexical rule',
      'inputs':{str(x):sha(x.read_bytes()) for x in inputs},'script_sha256':sha(Path(__file__).read_bytes()),'no_model_scoring':True}
    dump(a.out/'config_before_compute.json',config);shutil.copy2(Path(__file__),a.out/'ablate_graph_scope.py')
    hist=set(observed.path);assert set(nodes.loc[nodes.historical_train,'path'])==hist
    source=load_all().set_index('path');dapp=observed[observed.dataset=='dappscan'];assert len(dapp)==6587
    a_partition=observed.groupby('safe_group').file_id.transform('min')
    projections={'A_observed':pd.Series(a_partition.to_numpy(),index=observed.path)};edge_counts=[]
    scopes={'B_historical':set(nodes.loc[nodes.historical_train,'node_id']),
            'C_uncapped_reference':set(nodes.loc[nodes.scope=='upstream','node_id']),
            'D_with_candidate':set(nodes.node_id)}
    for label,run in [('legacy',a.legacy),('string_aware',a.corrected)]:
        e=pd.read_csv(run/'edges.csv');n=pd.read_csv(run/'nodes.csv',keep_default_na=False)
        for scope,ids in scopes.items():
            partition,ec=rebuild(n,e,ids);name=f'{scope}_{label}';projections[name]=partition.loc[observed.path]
            edge_counts.append({'graph':name,'population_nodes':len(ids),**ec})
        saved=pd.read_csv(run/'memberships.csv').set_index('path').base_080
        assert projections[f'D_with_candidate_{label}'].equals(saved.loc[observed.path].rename(None))
        for old,new in [('B_historical','C_uncapped_reference'),('C_uncapped_reference','D_with_candidate')]:
            pairs=pd.DataFrame({'old':projections[f'{old}_{label}'],'new':projections[f'{new}_{label}']})
            assert pairs.groupby('old')['new'].nunique().max()==1
    out=observed[['file_id','dataset','path']].copy()
    for name,partition in projections.items():out[name]=partition.loc[out.path].to_numpy()
    out.to_csv(a.out/'historical_projection.csv',index=False);csvout(a.out/'edge_counts.csv',edge_counts)
    concentrations=[];results=[];bundle_results=[];transitions=[]
    for name,partition in projections.items():
        dp=partition.loc[dapp.path];sizes=dp.value_counts()
        concentrations.append({'graph':name,'historical_dapp_files':len(dp),'components_in_dapp_projection':len(sizes),
          'largest_component_files':int(sizes.max()),'largest_component_fraction':float(sizes.max()/len(dp)),
          'effective_component_count':float(len(dp)**2/(sizes.pow(2).sum()))})
        for b in a.bundle:
            members=pd.read_csv(b/'selected_memberships.csv.gz');test=members[members.role=='test'];paths=test.path.tolist();assert len(paths)==1062 and len(set(paths))==1062
            tc=set(partition.loc[paths]);eligible=dapp[~partition.loc[dapp.path].isin(tc).to_numpy()].path.tolist()
            tsizes=partition.loc[paths].value_counts()
            for cls in ['reentrancy','unchecked']:
                positives=int(source.loc[eligible,cls].sum());positive_paths=source.loc[eligible].query(f'{cls}==1').index
                results.append({'test_id':test.test_id.iloc[0],'graph':name,'class':cls,'test_files':len(paths),
                  'test_components':len(tsizes),'largest_test_component_files':int(tsizes.max()),'largest_test_component_fraction':float(tsizes.max()/len(paths)),
                  'joint_raw_train_files':len(eligible),'joint_proxy_positive_files':positives,'joint_proxy_zero_files':len(eligible)-positives,
                  'joint_train_components':partition.loc[eligible].nunique(),'joint_positive_components':partition.loc[positive_paths].nunique()})
            tr=members[(members.role=='train')&(members.regime=='joint_project_clone_disjoint')]
            for (cls,seed),g in tr.groupby(['class','seed']):
                conflict=partition.loc[g.path].isin(tc)
                bundle_results.append({'test_id':test.test_id.iloc[0],'graph':name,'class':cls,'sampling_seed':int(seed),'selected_joint_train_files':len(g),
                  'selected_joint_train_connected_to_test':int(conflict.sum()),'selected_joint_train_retained_fraction':float((~conflict).mean())})
    for label in ['legacy','string_aware']:
        for old,new in [('A_observed',f'B_historical_{label}'),(f'B_historical_{label}',f'C_uncapped_reference_{label}'),(f'C_uncapped_reference_{label}',f'D_with_candidate_{label}')]:
            q=pd.DataFrame({'old':projections[old].loc[dapp.path],'new':projections[new].loc[dapp.path]})
            transitions.append({'from':old,'to':new,'old_components':q.old.nunique(),'new_components':q.new.nunique(),
               'old_components_split_across_new':int((q.groupby('old')['new'].nunique()>1).sum()),
               'new_components_merging_multiple_old':int((q.groupby('new')['old'].nunique()>1).sum())})
    csvout(a.out/'component_concentration.csv',concentrations);csvout(a.out/'fixed_test_feasibility.csv',results)
    csvout(a.out/'selected_bundle_retention.csv',bundle_results);csvout(a.out/'partition_transitions.csv',transitions)
    dump(a.out/'summary.json',{'schema':'graph_scope_ablation_results_v1','status':'complete_no_model_scores','config_sha256':sha((a.out/'config_before_compute.json').read_bytes()),
      'full_D_graph_matches_saved_memberships':True,'B_C_D_projected_coarsening_check':'pass','star_links_regenerated_on_each_population':True,
      'runtime_seconds':time.monotonic()-start,'graphs':len(projections),'fixed_test_cases':len(a.bundle),'concentrations':concentrations,'fixed_test_results':results})
    print(pd.DataFrame(results)[['test_id','graph','class','joint_raw_train_files','joint_proxy_positive_files','joint_proxy_zero_files']].to_string(index=False))
if __name__=='__main__':main()
