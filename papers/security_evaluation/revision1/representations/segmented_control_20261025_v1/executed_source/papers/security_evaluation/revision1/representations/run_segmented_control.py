#!/usr/bin/env python3
"""Post hoc implementation control: forbid shingles crossing removed blocks."""
from __future__ import annotations
import argparse
from collections import Counter
import gc
import gzip
import hashlib
import json
from pathlib import Path
import resource
import shutil
import sys
import time
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from structural_lexical import ROOT, mask_library_interface_blocks, lexical_stream
from run_representations import sha, dump, utc, concentration, THRESHOLDS
from bal.data.contracts import load_all, label_files

HERE=Path(__file__).resolve().parent
VARIANTS=('library_interface_segmented_normalized','library_interface_segmented_preserved')
OLD=('library_interface_masked_normalized','library_interface_masked_preserved')


def segment_shingles(segments):
    """Subset of full-stream windows wholly contained in a retained segment.

    Do not create a short shingle for each small segment. The original single
    short-file window is retained only when the whole file has fewer than five
    tokens and all its tokens belong to one segment.
    """
    token_segments=[x.split() for x in segments if x.split()]
    total=sum(len(x) for x in token_segments)
    if total<5:
        return {tuple(token_segments[0])} if len(token_segments)==1 else set()
    return {tuple(t[j:j+5]) for t in token_segments for j in range(max(0,len(t)-4))}


def retained_segments(source, preserve):
    masked=mask_library_interface_blocks(source)
    if not masked.informative:return []
    spans=sorted((u['start'],u['end']) for u in masked.units if u['kind'] in ('library','interface'))
    result=[];start=0
    for left,right in spans:
        result.append(lexical_stream(masked.text[start:left],preserve))
        start=right
    result.append(lexical_stream(masked.text[start:],preserve))
    return result


def prepare(out, original, cache):
    out.mkdir(parents=True,exist_ok=False);cache.mkdir(parents=True,exist_ok=False)
    config_old=json.loads((original/'config_before_outputs.json').read_text())
    code=[Path(__file__),HERE/'structural_lexical.py',HERE/'run_representations.py',
          ROOT/'papers/security_evaluation/normalization_audit/solidity_scanner.py',
          ROOT/'src/bal/features/contract_features.py',ROOT/'src/bal/data/contracts.py']
    hashes={}
    for p in code:
        rel=p.relative_to(ROOT);dest=out/'executed_source'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,dest);hashes[str(rel)]=sha(p)
    config={'schema':'posthoc_segment_boundary_control_v1','frozen_utc':utc(),
            'status':'posthoc_implementation_control_frozen_before_control_outputs_not_preregistered',
            'reason':'Masking deletion concatenates nonadjacent retained token regions; quantify and remove boundary-spanning windows',
            'original_run':str(original.relative_to(ROOT)),
            'original_config_sha256':sha(original/'config_before_outputs.json'),
            'original_metadata_sha256':sha(original/'representation_metadata.csv'),
            'original_private_cache':config_old['private_stream_cache'],
            'original_private_cache_sha256':sha(ROOT/config_old['private_stream_cache']/'streams.jsonl.gz'),
            'private_cache':str(cache.relative_to(ROOT)), 'code_hashes':hashes,
            'variants':VARIANTS,'thresholds':THRESHOLDS,'population_nodes':24131,'candidate_test_files':1998,
            'segmentation':'Keep only original concatenated-stream windows wholly contained in one retained segment; no new short-segment windows',
            'short_file_rule':'For fewer than5 total tokens retain original short-file window only if all tokens in one segment',
            'graph_policies':['base','address_expanded'],'node_identity_structural_edges':'unchanged from original four-variant run',
            'empty_rule':'zero surviving shingles means no lexical edges and unavailable informative training; structural node remains',
            'metrics':['jaccard','containment_max_directed'],'no_model_scoring':True,'no_external_labels_read':True,
            'max_saved_lexical_pairs':20000000}
    dump(out/'config_before_outputs.json',config)
    dump(out/'manifest.json',{'status':'prepared_no_control_outputs','config_sha256':sha(out/'config_before_outputs.json')})
    print(json.dumps({'config_sha256':sha(out/'config_before_outputs.json')}),flush=True)


def preprocess(out,config,nodes):
    original=ROOT/config['original_run'];meta=pd.read_csv(original/'representation_metadata.csv',keep_default_na=False)
    rows=[];cache=ROOT/config['private_cache']
    with gzip.open(ROOT/config['original_private_cache']/'streams.jsonl.gz','rt') as src,gzip.open(cache/'segments.jsonl.gz','wt',compresslevel=1) as dest:
        for node,record,line in zip(nodes.itertuples(),meta.itertuples(),src):
            old=json.loads(line);all_segments=[]
            source=None
            if record.library_interface_masked_normalized_informative and int(record.removed_unit_count)>0:
                path=ROOT/('data/raw/salzano/'+node.path if node.scope=='external' else node.path)
                raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==node.file_sha256
                source=raw.decode('utf-8',errors='replace')
            for index in range(2):
                text=old[index+2]
                segments=retained_segments(source,bool(index)) if source is not None else ([text] if text else [])
                tokens=[t for s in segments for t in s.split()]
                assert tokens==(text.split() if text else [])
                old_set={tuple(tokens[j:j+5]) for j in range(max(1,len(tokens)-4))} if tokens else set()
                new_set=segment_shingles(segments)
                assert new_set<=old_set
                labels=[i for i,s in enumerate(segments) for _ in s.split()]
                crossing=sum(labels[j]!=labels[min(j+4,len(labels)-1)] for j in range(max(1,len(labels)-4))) if labels else 0
                rows.append({'node_id':node.node_id,'scope':node.scope,'dataset':node.dataset,'path':node.path,
                             'representation':VARIANTS[index],'concatenated_shingles':len(old_set),'segmented_shingles':len(new_set),
                             'boundary_spanning_window_occurrences':crossing,
                             'boundary_only_unique_shingles_removed':len(old_set-new_set),
                             'informative_segments':sum(bool(s.split()) for s in segments),'segmented_informative':bool(new_set)})
                all_segments.append(segments)
            dest.write(json.dumps(all_segments)+'\n')
    pd.DataFrame(rows).to_csv(out/'boundary_diagnostics.csv',index=False)


def graph(out,config,nodes,struct,labels,index):
    started=time.perf_counter();variant=VARIANTS[index];folder=out/variant;folder.mkdir()
    vocab={};indices=[];indptr=[0]
    with gzip.open(ROOT/config['private_cache']/'segments.jsonl.gz','rt') as f:
        for line in f:
            tuples=segment_shingles(json.loads(line)[index])
            for t in tuples:
                digest=hashlib.blake2b(' '.join(t).encode(),digest_size=16).digest()
                if digest not in vocab:vocab[digest]=len(vocab)
                indices.append(vocab[digest])
            indptr.append(len(indices))
    n=len(nodes);X=csr_matrix((np.ones(len(indices),np.int32),indices,indptr),shape=(n,len(vocab)));size=np.diff(X.indptr)
    del vocab,indices,indptr;gc.collect();left=[];right=[];intersection=[];count=0
    for first in range(0,n,100):
        z=(X[first:first+100]@X.T).tocoo();a=z.row+first;b=z.col;keep=a<b
        a,b,inter=a[keep],b[keep],z.data[keep];keep=inter/np.minimum(size[a],size[b])>=.7
        left.append(a[keep].astype(np.int32));right.append(b[keep].astype(np.int32));intersection.append(inter[keep].astype(np.int32))
        count+=int(keep.sum());assert count<=config['max_saved_lexical_pairs']
        if first%10000==0:print(variant,first,count,flush=True)
    a,b,inter=np.concatenate(left),np.concatenate(right),np.concatenate(intersection)
    del X,left,right,intersection,z;gc.collect()
    np.savez_compressed(folder/'lexical_edges.npz',left=a,right=b,intersection=inter,node_shingle_sizes=size)
    metrics={'jaccard':inter/(size[a]+size[b]-inter),'containment':inter/np.minimum(size[a],size[b])}
    members=pd.DataFrame({'node_id':nodes.node_id,'informative_representation':size>0})
    concentration_rows=[];training_rows=[];edge_rows=[];changes=[]
    old=np.load(ROOT/config['original_run']/OLD[index]/'lexical_edges.npz');oa,ob,oi,osize=[old[k] for k in ['left','right','intersection','node_shingle_sizes']]
    old_metrics={'jaccard':oi/(osize[oa]+osize[ob]-oi),'containment':oi/np.minimum(osize[oa],osize[ob])}
    historical=nodes.historical_train.to_numpy(bool);test=nodes.candidate_test.to_numpy(bool);dapp=nodes.dataset.to_numpy()=='dappscan'
    populations={'all24131':np.arange(n),'full_dappscan':np.flatnonzero(dapp),'historical_dappscan':np.flatnonzero(historical&dapp),'diagnostic_candidate1998':np.flatnonzero(test)}
    for metric,similarity in metrics.items():
        for t in THRESHOLDS:
            selected=similarity>=t;edge_rows.append({'representation':variant,'metric':metric,'threshold':t,'lexical_pairs':int(selected.sum())})
            # Encode unordered node pairs as unique integers to compare complete
            # edge sets, including denominator-induced additions after removal.
            new_codes=np.sort(a[selected].astype(np.int64)*n+b[selected]);old_selected=old_metrics[metric]>=t
            old_codes=np.sort(oa[old_selected].astype(np.int64)*n+ob[old_selected])
            changes.append({'representation':variant,'metric':metric,'threshold':t,'old_edges':len(old_codes),'new_edges':len(new_codes),
                            'edges_added':len(np.setdiff1d(new_codes,old_codes,assume_unique=True)),
                            'edges_removed':len(np.setdiff1d(old_codes,new_codes,assume_unique=True))})
            for policy in ('base','address_expanded'):
                structural=struct if policy=='address_expanded' else struct[~struct.address_expanded_only]
                row=np.concatenate([a[selected],structural.left.to_numpy(np.int32)]);col=np.concatenate([b[selected],structural.right.to_numpy(np.int32)])
                adjacency=csr_matrix((np.ones(len(row),np.int8),(row,col)),shape=(n,n))
                _,groups=connected_components(adjacency,directed=False)
                members[f'{metric}_{policy}_{int(round(t*100)):03d}']=groups
                for population,ids in populations.items():
                    concentration_rows.append({'representation':variant,'metric':metric,'policy':policy,'threshold':t,'population':population,
                                               'informative_files':int((size[ids]>0).sum()),**concentration(groups,ids)})
                connected=np.isin(groups,np.unique(groups[test]));retained=historical&~connected;usable=retained&(size>0)
                assert not set(groups[usable])&set(groups[test])
                for population,mask in [('all_historical',historical),('historical_dappscan',historical&dapp)]:
                    after=usable&mask
                    row={'representation':variant,'metric':metric,'policy':policy,'threshold':t,'training_population':population,
                         'before_files':int(mask.sum()),'retained_by_graph':int((retained&mask).sum()),
                         'retained_with_informative_representation':int(after.sum()),'excluded_connected_to_test':int((mask&connected).sum()),
                         'retained_but_representation_unavailable':int((retained&mask&(size==0)).sum()),
                         'candidate_test_files':int(test.sum()),'candidate_informative_files':int((test&(size>0)).sum())}
                    for cls in ('reentrancy','unchecked'):
                        y=labels[cls];row[cls+'_proxy_positive_retained']=int(y[after].sum());row[cls+'_proxy_positive_components']=len(np.unique(groups[after&(y==1)]))
                    training_rows.append(row)
    members.to_csv(folder/'memberships.csv.gz',index=False,compression='gzip')
    for name,rows in [('component_concentration',concentration_rows),('training_feasibility',training_rows),('edge_counts',edge_rows),('edge_changes_from_concatenated',changes)]:
        pd.DataFrame(rows).to_csv(folder/(name+'.csv'),index=False)
    dump(folder/'summary.json',{'status':'complete_posthoc_unscored_control','nodes':n,'informative_nodes':int((size>0).sum()),
                              'runtime_seconds':time.perf_counter()-started,'output_hashes':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}})


def run(out):
    started=time.perf_counter();manifest=json.loads((out/'manifest.json').read_text());assert manifest['status']=='prepared_no_control_outputs'
    assert sha(out/'config_before_outputs.json')==manifest['config_sha256'];config=json.loads((out/'config_before_outputs.json').read_text())
    for p,h in config['code_hashes'].items():assert sha(ROOT/p)==h
    original=ROOT/config['original_run'];assert sha(original/'config_before_outputs.json')==config['original_config_sha256']
    assert sha(original/'representation_metadata.csv')==config['original_metadata_sha256']
    assert sha(ROOT/config['original_private_cache']/'streams.jsonl.gz')==config['original_private_cache_sha256']
    nodes=pd.read_csv(original/'nodes_unchanged.csv',keep_default_na=False);struct=pd.read_csv(original/'structural_edges_unchanged.csv',keep_default_na=False)
    assert len(nodes)==24131 and int(nodes.candidate_test.sum())==1998
    shutil.copy2(original/'nodes_unchanged.csv',out/'nodes_unchanged.csv');shutil.copy2(original/'structural_edges_unchanged.csv',out/'structural_edges_unchanged.csv')
    manifest.update(status='running',started_utc=utc());dump(out/'manifest.json',manifest)
    preprocess(out,config,nodes)
    train=load_all().set_index('path');labels={c:np.array([int(train.loc[r.path,c]) if r.historical_train else -1 for r in nodes.itertuples()]) for c in ('reentrancy','unchecked')}
    dump(out/'training_label_input_hashes.json',{str(p):sha(p) for p in label_files()});del train
    for index in range(2):graph(out,config,nodes,struct,labels,index)
    manifest.update(status='complete_posthoc_unscored_control',finished_utc=utc(),runtime_seconds=time.perf_counter()-started,
                    peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,no_model_scoring=True)
    dump(out/'manifest.json',manifest)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['prepare','run']);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--original',type=Path);ap.add_argument('--cache',type=Path);args=ap.parse_args()
    if args.action=='prepare':prepare(args.out,args.original.resolve(),args.cache.resolve())
    else:run(args.out)
