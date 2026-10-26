#!/usr/bin/env python3
"""Independent saved-graph and boundary-window checks for the segmented control."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from verify_representations import Union, partition_equal


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);args=ap.parse_args()
    root=Path(__file__).resolve().parents[4];run=args.run.resolve()
    config=json.loads((run/'config_before_outputs.json').read_text());n=24131
    for path, expected in config['code_hashes'].items():
        assert hashlib.sha256((run/'executed_source'/path).read_bytes()).hexdigest()==expected
    common_hashes={name:hashlib.sha256((run/name).read_bytes()).hexdigest() for name in
                   ['boundary_diagnostics.csv','nodes_unchanged.csv','structural_edges_unchanged.csv',
                    'training_label_input_hashes.json','manifest.json']}
    nodes=pd.read_csv(run/'nodes_unchanged.csv',keep_default_na=False)
    structural=pd.read_csv(run/'structural_edges_unchanged.csv',keep_default_na=False)
    diag=pd.read_csv(run/'boundary_diagnostics.csv',keep_default_na=False)
    original=root/config['original_run']
    assert len(nodes)==n and np.array_equal(nodes.node_id,np.arange(n))
    assert int(nodes.candidate_test.sum())==1998
    assert hashlib.sha256((run/'nodes_unchanged.csv').read_bytes()).hexdigest()==hashlib.sha256((original/'nodes_unchanged.csv').read_bytes()).hexdigest()
    results=[]
    for vi,variant in enumerate(config['variants']):
        folder=run/variant;z=np.load(folder/'lexical_edges.npz')
        a,b,inter,size=[z[k] for k in ['left','right','intersection','node_shingle_sizes']]
        assert np.all(a<b) and np.all(size[a]>0) and np.all(size[b]>0)
        d=diag[diag.representation==variant].sort_values('node_id')
        assert np.array_equal(d.node_id,np.arange(n)) and np.array_equal(d.segmented_shingles,size)
        assert np.all(d.segmented_shingles<=d.concatenated_shingles)
        assert np.array_equal(d.concatenated_shingles-d.segmented_shingles,d.boundary_only_unique_shingles_removed)
        membership=pd.read_csv(folder/'memberships.csv.gz')
        assert np.array_equal(membership.informative_representation,size>0)
        counts=pd.read_csv(folder/'edge_counts.csv')
        for metric,similarity in [('jaccard',inter/(size[a]+size[b]-inter)),('containment',inter/np.minimum(size[a],size[b]))]:
            for t in config['thresholds']:
                take=similarity>=t
                assert counts.loc[(counts.metric==metric)&(counts.threshold==t),'lexical_pairs'].item()==int(take.sum())
                for policy in config['graph_policies']:
                    col=f'{metric}_{policy}_{int(round(t*100)):03d}';group=membership[col].to_numpy()
                    assert np.all(group[a[take]]==group[b[take]])
                    s=structural if policy=='address_expanded' else structural[~structural.address_expanded_only]
                    assert np.all(group[s.left.to_numpy()]==group[s.right.to_numpy()])
                    higher=[x for x in config['thresholds'] if x>t]
                    if higher:
                        h=membership[f'{metric}_{policy}_{int(round(higher[0]*100)):03d}']
                        frame=pd.DataFrame({'higher':h,'lower':group})
                        assert (frame.groupby('higher').lower.nunique()==1).all()
            u=Union(n)
            for left,right in zip(structural.left,structural.right):u.join(int(left),int(right))
            for left,right in zip(a[similarity>=.8],b[similarity>=.8]):u.join(int(left),int(right))
            assert partition_equal([u.root(i) for i in range(n)],membership[f'{metric}_address_expanded_080'])
        # Reconstruct valid windows directly from flattened tokens + segment IDs,
        # independently of the generator's per-segment shingle implementation.
        segments=[]
        with gzip.open(root/config['private_cache']/'segments.jsonl.gz','rt') as f:
            for line in f:segments.append(json.loads(line)[vi])
        cache={}
        def literal_windows(node):
            if node in cache:return cache[node]
            tokens=[];ids=[]
            for sid,segment in enumerate(segments[node]):
                current=segment.split();tokens.extend(current);ids.extend([sid]*len(current))
            result=set()
            if tokens:
                for j in range(max(1,len(tokens)-4)):
                    end=min(j+5,len(tokens))
                    if len(set(ids[j:end]))==1:result.add(tuple(tokens[j:end]))
            cache[node]=result;return result
        sample=np.random.default_rng(20261025).choice(len(a),size=min(100,len(a)),replace=False)
        for idx in sample:
            left,right=literal_windows(int(a[idx])),literal_windows(int(b[idx]))
            assert len(left)==size[a[idx]] and len(right)==size[b[idx]] and len(left&right)==inter[idx]
        results.append({'variant':variant,'all_graph_edges_connected':True,'threshold_refinement':True,
                        'independent_primary_union_find_graphs':2,'independent_literal_segment_pairs_checked':len(sample),
                        'node_shingle_counts_match_diagnostics':True,'empty_nodes_have_no_lexical_edges':True})
        print(json.dumps(results[-1]),flush=True)
    result={'status':'pass','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'config_sha256':hashlib.sha256((run/'config_before_outputs.json').read_bytes()).hexdigest(),
            'common_output_sha256':common_hashes,'executed_source_snapshots_match_config':True,
            'checks':results,'claim':'Persisted lexical graph calculations verified; semantic independence unestablished'}
    (run/'independent_verification.json').write_text(json.dumps(result,indent=2)+'\n')
