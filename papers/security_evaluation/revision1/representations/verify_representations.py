#!/usr/bin/env python3
"""Independent checks of persisted representation graphs; no model scoring."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


class Union:
    def __init__(self,n):
        self.parent=list(range(n))
    def root(self,i):
        while self.parent[i]!=i:
            self.parent[i]=self.parent[self.parent[i]]
            i=self.parent[i]
        return i
    def join(self,a,b):
        a,b=self.root(a),self.root(b)
        if a!=b:
            self.parent[max(a,b)]=min(a,b)


def partition_equal(a,b):
    forward,back={},{}
    for x,y in zip(a,b):
        if x in forward and forward[x]!=y:return False
        if y in back and back[y]!=x:return False
        forward[x]=y;back[y]=x
    return True


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True)
    args=ap.parse_args();run=args.run.resolve()
    root=Path(__file__).resolve().parents[4]
    config=json.loads((run/'config_before_outputs.json').read_text())
    nodes=pd.read_csv(run/'nodes_unchanged.csv',keep_default_na=False)
    structural=pd.read_csv(run/'structural_edges_unchanged.csv',keep_default_na=False)
    metadata=pd.read_csv(run/'representation_metadata.csv',keep_default_na=False)
    assert len(nodes)==24131 and len(metadata)==24131
    assert np.array_equal(nodes.node_id,np.arange(24131))
    checks=[]
    for variant_index,variant in enumerate(config['variants']):
        folder=run/variant;edge=np.load(folder/'lexical_edges.npz')
        left,right,inter,size=[edge[k] for k in ('left','right','intersection','node_shingle_sizes')]
        assert np.all(left<right) and np.all(size[left]>0) and np.all(size[right]>0)
        jac=inter/(size[left]+size[right]-inter);con=inter/np.minimum(size[left],size[right])
        assert np.all(con>=jac)
        membership=pd.read_csv(folder/'memberships.csv.gz')
        assert np.array_equal(membership.node_id,nodes.node_id)
        assert np.array_equal(membership.informative_representation,size>0)
        assert np.array_equal(metadata[variant+'_informative'],size>0)
        counts=pd.read_csv(folder/'edge_counts.csv')
        for metric,similarity in [('jaccard',jac),('containment',con)]:
            for t in config['thresholds']:
                selected=similarity>=t
                observed=counts.loc[(counts.metric==metric)&(counts.threshold==t),'lexical_pairs'].item()
                assert observed==int(selected.sum())
                for policy in config['graph_policies']:
                    col=f'{metric}_{policy}_{int(round(t*100)):03d}'
                    labels=membership[col].to_numpy()
                    assert np.all(labels[left[selected]]==labels[right[selected]])
                    s=structural if policy=='address_expanded' else structural[~structural.address_expanded_only]
                    assert np.all(labels[s.left.to_numpy()]==labels[s.right.to_numpy()])
                    # Raising the threshold must refine the component partition.
                    higher=[v for v in config['thresholds'] if v>t]
                    if higher:
                        hcol=f'{metric}_{policy}_{int(round(higher[0]*100)):03d}'
                        pair=pd.DataFrame({'high':membership[hcol],'low':labels})
                        assert (pair.groupby('high').low.nunique()==1).all()
            # An independent Python union-find checks the primary 0.8 graph.
            selected=similarity>=.8
            u=Union(len(nodes))
            for a,b in zip(structural.left,structural.right):u.join(int(a),int(b))
            for a,b in zip(left[selected],right[selected]):u.join(int(a),int(b))
            roots=[u.root(i) for i in range(len(nodes))]
            assert partition_equal(roots,membership[f'{metric}_address_expanded_080'])
        # Verify a fixed sample using literal token tuples, not hash digests.
        streams=[]
        with gzip.open(root/config['private_stream_cache']/'streams.jsonl.gz','rt') as f:
            for line in f:streams.append(json.loads(line)[variant_index])
        sample=np.random.default_rng(20261025).choice(len(left),size=min(100,len(left)),replace=False)
        def shingles(i):
            tokens=streams[i].split()
            return {tuple(tokens[j:j+5]) for j in range(max(1,len(tokens)-4))}
        for idx in sample:
            a,b=shingles(left[idx]),shingles(right[idx])
            assert len(a)==size[left[idx]] and len(b)==size[right[idx]]
            assert len(a&b)==inter[idx]
        check={'variant':variant,'all_edge_endpoints_connected':True,
               'threshold_refinement':True,'primary_graphs_independently_reconstructed':2,
               'literal_shingle_pairs_verified':len(sample),'empty_nodes_have_no_lexical_edges':True}
        if variant=='corrected_file_normalized':
            baseline=pd.read_csv(root/'papers/security_evaluation/dependency_audit/string_aware_recovered_20261025/edges.csv',keep_default_na=False,low_memory=False)
            old=baseline[baseline.edge_type=='normalized_shingle']
            expected=set(zip(old.left,old.right))
            actual=set(zip(left[jac>=.7],right[jac>=.7]))
            missing=expected-actual
            # The frozen current policy omits every empty lexical stream. The
            # prior graph used one shared empty shingle, creating empty-empty
            # edges. Attribute that policy difference explicitly; nothing else
            # is permitted to disappear from the matched corrected baseline.
            assert not actual-expected
            assert all(size[a]==0 and size[b]==0 for a,b in missing)
            assert actual=={(a,b) for a,b in expected if size[a]>0 and size[b]>0}
            check['nonempty_corrected_baseline_edges_identical']=len(actual)
            check['legacy_empty_empty_lexical_edges_omitted']=len(missing)
            old_members=pd.read_csv(root/'papers/security_evaluation/dependency_audit/string_aware_recovered_20261025/memberships.csv')
            check['prior_baseline_partition_at_080_unchanged']=partition_equal(old_members.address_expanded_080,
                                                                             membership.jaccard_address_expanded_080)
        checks.append(check)
        print(json.dumps(check),flush=True)
    result={'status':'pass','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'config_sha256':hashlib.sha256((run/'config_before_outputs.json').read_bytes()).hexdigest(),
            'checks':checks,'independence_claim':'None; verified persisted lexical graph calculations only'}
    (run/'independent_verification.json').write_text(json.dumps(result,indent=2)+'\n')
