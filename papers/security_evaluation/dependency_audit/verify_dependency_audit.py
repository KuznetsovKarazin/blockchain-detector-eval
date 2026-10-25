#!/usr/bin/env python3
"""Independent connected-component and training-partition verification."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from run_dependency_audit import ROOT,THRESHOLDS,sha,dump,load_all

def main():
    ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);a=ap.parse_args()
    config=json.loads((a.run/'config_before_graph.json').read_text());summary=json.loads((a.run/'summary.json').read_text())
    assert sha((a.run/'config_before_graph.json').read_bytes())==summary['config_sha256']
    for path,digest in config['source_hashes'].items():assert sha((a.run/'executed_source'/path).read_bytes())==digest
    n=pd.read_csv(a.run/'nodes.csv');e=pd.read_csv(a.run/'edges.csv');m=pd.read_csv(a.run/'memberships.csv')
    assert len(n)==24131 and np.array_equal(n.node_id,np.arange(len(n)))
    assert np.array_equal(n.node_id,m.node_id) and n.candidate_test.sum()==1998 and n.historical_train.sum()==7080
    assert not n[['scope','path']].duplicated().any()
    historical_manifest=ROOT/'results/contracts/c2_20261024_004314/groups.parquet'
    prior=pd.read_parquet(historical_manifest).set_index('path')
    old=n[n.historical_train].set_index('path')
    assert set(old.index)==set(prior.index)
    assert old.loc[prior.index,'dataset'].equals(prior.dataset)
    assert old.loc[prior.index,'project_id'].equals(prior['group'])
    labels=load_all().set_index('path');reports=[]
    metrics=pd.read_csv(a.run/'training_feasibility.csv')
    for policy in ['base','address_expanded']:
        for t in THRESHOLDS:
            name=f'{policy}_{int(t*100):03d}';use=e[e.jaccard.isna()|e.jaccard.ge(t)]
            if policy=='base':use=use[~use.address_expanded_only]
            adj=coo_matrix((np.ones(len(use),dtype=np.int8),(use.left,use.right)),shape=(len(n),len(n))).tocsr()
            nc,comp=connected_components(adj,directed=False)
            minimum=pd.Series(n.node_id.to_numpy()).groupby(comp).transform('min').to_numpy()
            assert np.array_equal(minimum,m[name].to_numpy()),name
            target=set(m.loc[n.candidate_test,name]);train=n[n.historical_train]
            manifest=pd.read_csv(a.run/f'training_exclusion_{name}.csv').set_index('node_id').loc[train.node_id]
            expected=m.loc[train.index,name].isin(target).to_numpy()
            assert np.array_equal(expected,manifest.connected_to_candidate)
            bad=train.normalization_status.ne('ok').to_numpy()
            assert np.array_equal(bad,manifest.scan_error)
            assert np.array_equal(~expected&~bad,manifest.usable_training)
            retained=manifest[manifest.usable_training]
            assert not set(retained.component)&target
            for dataset in ['all','dappscan','solidifi','smartbugs']:
                subset=retained if dataset=='all' else retained[retained.dataset==dataset]
                for cls in ['reentrancy','unchecked']:
                    row=metrics[(metrics.grouping==policy)&(metrics.threshold==t)&(metrics.dataset==dataset)&(metrics['class']==cls)].iloc[0]
                    assert row.after_files==len(subset)
                    assert row.after_proxy_positive_files==int(labels.loc[subset.path,cls].sum())
            reports.append({'graph':name,'scipy_components':nc,'exact_membership_partition_match':True,
                            'retained_train':len(retained),'train_test_component_intersection':0,'aggregate_positive_counts_match':True})
    dump(a.run/'independent_verification.json',{'schema':'dependency_graph_independent_verification_v1','verifier_sha256':sha(Path(__file__).read_bytes()),
       'method':'scipy undirected connected_components, compared canonical minimum-node partitions; independent train-label joins',
       'graphs':reports,'source_snapshots_match':True,'historical_paths_datasets_projects_match_original_C2_all7080':True,
       'historical_manifest_sha256':sha(historical_manifest.read_bytes()),'status':'pass'})
    print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
