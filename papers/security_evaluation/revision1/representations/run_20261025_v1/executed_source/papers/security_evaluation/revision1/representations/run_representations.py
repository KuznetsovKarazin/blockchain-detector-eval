#!/usr/bin/env python3
"""Unscored full-population lexical representation and dependency sensitivity."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import gzip
import hashlib
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import scipy
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from structural_lexical import (ROOT, mask_library_interface_blocks, lexical_stream,
                                StructuralScanError, SolidityScanError, scan_comments)
from bal.data.contracts import load_all, label_files

HERE = Path(__file__).resolve().parent
BASE = ROOT / 'papers/security_evaluation/dependency_audit/string_aware_recovered_20261025'
VARIANTS = ('corrected_file_normalized', 'corrected_file_preserved',
            'library_interface_masked_normalized', 'library_interface_masked_preserved')
THRESHOLDS = (.7, .8, .9, .95, .99)
PINS = {'DAppSCAN':'66a56619c44770e05c2db600fa6468115ff0dcd5',
        'smartbugs-curated':'230e649123477eff332742a59a1c7cc6dc286cab',
        'SolidiFI-benchmark':'4b0573e1b3f7031396de6f48f7f3e7380222ad3a',
        'salzano':'da079440bf2cf4fd803c864ef29aeea8a3da50c3'}
CODE = (Path(__file__), HERE / 'structural_lexical.py',
        ROOT / 'papers/security_evaluation/normalization_audit/solidity_scanner.py',
        ROOT / 'src/bal/features/contract_features.py', ROOT / 'src/bal/data/contracts.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def prepare(out, cache):
    out.mkdir(parents=True, exist_ok=False)
    cache.mkdir(parents=True, exist_ok=False)
    assert git(ROOT, 'check-ignore', str(cache.relative_to(ROOT))) == str(cache.relative_to(ROOT))
    pins = {}
    for name, expected in PINS.items():
        repo = ROOT / 'data/raw' / name
        observed = git(repo, 'rev-parse', 'HEAD')
        clean = not git(repo, 'status', '--porcelain')
        assert observed == expected and clean
        pins[name] = {'commit': observed, 'clean': clean}
    source_hashes = {}
    for path in CODE:
        relative = path.relative_to(ROOT)
        target = out / 'executed_source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        source_hashes[str(relative)] = sha(path)
    config = {
        'schema': 'revision1_representation_sensitivity_v1', 'frozen_utc': utc(),
        'repo_head': git(ROOT, 'rev-parse', 'HEAD'), 'source_hashes': source_hashes,
        'input_hashes': {str((BASE / name).relative_to(ROOT)): sha(BASE / name) for name in ('nodes.csv','edges.csv')},
        'upstream_pins': pins, 'variants': VARIANTS, 'thresholds': THRESHOLDS,
        'population': 'all24131 original node IDs, no pre-graph cohort restriction',
        'candidate_test': 'original diagnostic1998 candidate_test flags, not final external eligibility',
        'shingles': 'token5gram sets represented by BLAKE2b128; exhaustive sparse intersection',
        'preserved_variant': 'same historical TOKEN_RE; no identifier or numeric replacement; quotes still omitted by that regex',
        'masked_variant': 'blank balanced top-level library/interface declaration blocks after string-aware comment handling; no compiler AST or verified library provenance',
        'empty_policy': 'directive-only residual or empty lexical stream has no lexical shingles; node and all known structural edges remain',
        'parse_error_policy': 'masked representations unavailable; no lexical shingles; retain structural edges and report uncertainty/coverage',
        'jaccard': 'intersection/(size_left+size_right-intersection)',
        'containment': 'max of directed inclusion fractions = intersection/min(size_left,size_right); undirected edge if either direction reaches threshold',
        'graph_policies': ['base','address_expanded'],
        'structural_edges': 'reuse all pre-existing project/candidate-identifier/raw-identity edges; address_expanded additionally keeps original syntactic-address edges',
        'membership_inference': 'representation-defined components only, never semantic or verified independent families',
        'private_stream_cache': str(cache.relative_to(ROOT)),
        'max_saved_lexical_pairs': 20000000,
        'resource_failure': 'record incomplete and stop; never silently prune similarity edges',
        'no_model_scoring': True, 'no_external_labels_read': True,
        'training_label_use': 'historical proxy counts only, not model selection or external labels',
        'environment': {'python': sys.version, 'numpy': np.__version__, 'pandas': pd.__version__, 'scipy': scipy.__version__},
    }
    dump(out / 'config_before_outputs.json', config)
    dump(out / 'manifest.json', {'status': 'prepared_no_outputs', 'config_sha256': sha(out / 'config_before_outputs.json')})
    print(json.dumps({'config_sha256': sha(out / 'config_before_outputs.json'), 'records': 24131}), flush=True)


def load_private_streams(cache, index):
    result = []
    with gzip.open(cache / 'streams.jsonl.gz', 'rt') as stream:
        for line in stream:
            result.append(json.loads(line)[index])
    return result


def preprocess(out, cache, nodes):
    rows = []
    with gzip.open(cache / 'streams.jsonl.gz', 'wt', compresslevel=1) as store:
        for count, row in enumerate(nodes.itertuples()):
            path = ROOT / ('data/raw/salzano/' + row.path if row.scope == 'external' else row.path)
            raw = path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == row.file_sha256
            source = raw.decode('utf-8', errors='replace')
            cleaned = scan_comments(source).text
            base_norm, base_preserve = lexical_stream(cleaned), lexical_stream(cleaned, True)
            assert hashlib.sha256(base_norm.encode()).hexdigest() == row.normalized_sha256
            error = ''
            try:
                masked = mask_library_interface_blocks(source)
                mask_norm = lexical_stream(masked.text) if masked.informative else None
                mask_preserve = lexical_stream(masked.text, True) if masked.informative else None
                types = Counter(u['kind'] for u in masked.units)
                information = {'library_units': types['library'], 'interface_units': types['interface'],
                               'contract_units': types['contract'], 'removed_unit_count': masked.removed_unit_count,
                               'masked_informative': masked.informative,
                               'remaining_structural_tokens': masked.remaining_structural_token_count,
                               'masked_characters': sum(u['end']-u['start'] for u in masked.units if u['kind'] in ('library','interface'))}
            except (StructuralScanError, SolidityScanError) as exc:
                error = str(exc)
                mask_norm = mask_preserve = None
                information = {'library_units': '', 'interface_units': '', 'contract_units': '',
                               'removed_unit_count': '', 'masked_informative': False,
                               'remaining_structural_tokens': '', 'masked_characters': ''}
            streams = [base_norm or None, base_preserve or None, mask_norm or None, mask_preserve or None]
            store.write(json.dumps(streams) + '\n')
            result = {'node_id': row.node_id, 'scope': row.scope, 'dataset': row.dataset, 'path': row.path,
                      'file_sha256': row.file_sha256, 'structural_scan_error': error,
                      'masked_unavailable_reason': 'structural_scan_error' if error else ('directive_only_or_no_residual_code' if mask_norm is None else ''), **information}
            for name, text in zip(VARIANTS, streams):
                result[name + '_sha256'] = hashlib.sha256(text.encode()).hexdigest() if text is not None else ''
                result[name + '_token_count'] = len(text.split()) if text is not None else 0
                result[name + '_informative'] = text is not None
            rows.append(result)
            if count % 5000 == 0:
                print(f'preprocessed {count+1}/{len(nodes)}', flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(out / 'representation_metadata.csv', index=False)
    summaries = []
    for (scope, dataset), group in frame.groupby(['scope','dataset']):
        for variant in VARIANTS:
            informative = group[variant + '_informative']
            summaries.append({'scope':scope, 'dataset':dataset, 'representation':variant,
                              'files':len(group), 'informative_files':int(informative.sum()),
                              'unavailable_files':int((~informative).sum()),
                              'structural_scan_error_files':int((group.structural_scan_error != '').sum()),
                              'files_with_removed_library_or_interface':int((pd.to_numeric(group.removed_unit_count, errors='coerce') > 0).sum())})
    pd.DataFrame(summaries).to_csv(out / 'coverage.csv', index=False)
    return frame


def concentration(labels, ids):
    _, counts = np.unique(labels[ids], return_counts=True)
    n = len(ids)
    return {'files':n, 'components':len(counts), 'largest_component_files':int(counts.max()) if n else 0,
            'largest_component_share':float(counts.max()/n) if n else None,
            'effective_components_inverse_hhi':float(n*n/np.square(counts.astype(float)).sum()) if n else None}


def graph_variant(out, cache, variant_index, nodes, structure, training_labels, config):
    start = time.perf_counter()
    variant = VARIANTS[variant_index]
    folder = out / variant
    folder.mkdir()
    texts = load_private_streams(cache, variant_index)
    vocab, indices, indptr = {}, [], [0]
    for text in texts:
        tokens = text.split() if text is not None else []
        shingles = set() if not tokens else {hashlib.blake2b(' '.join(tokens[j:j+5]).encode(),digest_size=16).digest()
                                           for j in range(max(1,len(tokens)-4))}
        for token in shingles:
            if token not in vocab:
                vocab[token] = len(vocab)
            indices.append(vocab[token])
        indptr.append(len(indices))
    n = len(texts)
    X = csr_matrix((np.ones(len(indices),np.int32), np.asarray(indices), np.asarray(indptr)), shape=(n,len(vocab)))
    sizes = np.diff(X.indptr)
    del texts, vocab, indices, indptr
    gc.collect()
    left, right, intersections = [], [], []
    count = 0
    for first in range(0,n,100):
        product = (X[first:first+100] @ X.T).tocoo()
        a, b = product.row + first, product.col
        keep = (a < b)
        a, b, inter = a[keep], b[keep], product.data[keep]
        contain = inter / np.minimum(sizes[a],sizes[b])
        keep = contain >= min(THRESHOLDS)
        left.append(a[keep].astype(np.int32)); right.append(b[keep].astype(np.int32)); intersections.append(inter[keep].astype(np.int32))
        count += int(keep.sum())
        if count > config['max_saved_lexical_pairs']:
            dump(folder / 'INCOMPLETE.json', {'status':'resource_edge_limit_exceeded_no_graph_claim', 'observed_pairs':count})
            raise RuntimeError('Frozen lexical-pair limit exceeded; no pruning allowed')
        if first % 5000 == 0:
            print(f'{variant} pairs {min(first+100,n)}/{n}: {count}',flush=True)
    a, b, inter = np.concatenate(left), np.concatenate(right), np.concatenate(intersections)
    del X, left, right, intersections, product
    gc.collect()
    np.savez_compressed(folder / 'lexical_edges.npz', left=a, right=b, intersection=inter, node_shingle_sizes=sizes)
    jaccard = inter / (sizes[a]+sizes[b]-inter)
    containment = inter / np.minimum(sizes[a],sizes[b])
    informative = sizes > 0
    membership = pd.DataFrame({'node_id':nodes.node_id, 'informative_representation':informative})
    metrics, training, edge_counts = [], [], []
    historical = nodes.historical_train.to_numpy(bool)
    test = nodes.candidate_test.to_numpy(bool)
    dapp = nodes.dataset.to_numpy() == 'dappscan'
    populations = {'all24131':np.arange(n), 'full_dappscan':np.flatnonzero(dapp),
                   'historical_dappscan':np.flatnonzero(historical & dapp), 'diagnostic_candidate1998':np.flatnonzero(test)}
    for metric, similarity in [('jaccard',jaccard),('containment',containment)]:
        for threshold in THRESHOLDS:
            selected = similarity >= threshold
            edge_counts.append({'representation':variant, 'metric':metric, 'threshold':threshold, 'lexical_pairs':int(selected.sum())})
            for policy in ('base','address_expanded'):
                structural = structure if policy == 'address_expanded' else structure[~structure.address_expanded_only]
                row = np.concatenate([a[selected],structural.left.to_numpy(np.int32)])
                col = np.concatenate([b[selected],structural.right.to_numpy(np.int32)])
                adjacency = csr_matrix((np.ones(len(row),np.int8),(row,col)),shape=(n,n))
                _, labels = connected_components(adjacency,directed=False,return_labels=True)
                name = f'{metric}_{policy}_{int(round(threshold*100)):03d}'
                membership[name] = labels
                for population, ids in populations.items():
                    metrics.append({'representation':variant,'metric':metric,'policy':policy,'threshold':threshold,
                                    'population':population,'informative_files':int(informative[ids].sum()), **concentration(labels,ids)})
                connected = np.isin(labels,np.unique(labels[test]))
                retained_graph = historical & ~connected
                retained_informative = retained_graph & informative
                assert not set(labels[retained_informative]) & set(labels[test])
                for population, mask in [('all_historical',historical),('historical_dappscan',historical & dapp)]:
                    after = retained_informative & mask
                    data = {'representation':variant,'metric':metric,'policy':policy,'threshold':threshold,
                            'training_population':population,'before_files':int(mask.sum()),
                            'retained_by_graph':int((retained_graph & mask).sum()),'retained_with_informative_representation':int(after.sum()),
                            'excluded_connected_to_test':int((mask & connected).sum()),
                            'retained_but_representation_unavailable':int((retained_graph & mask & ~informative).sum()),
                            'candidate_test_files':int(test.sum()),'candidate_informative_files':int((test & informative).sum())}
                    for cls in ('reentrancy','unchecked'):
                        y=training_labels[cls]
                        data[cls+'_proxy_positive_retained']=int(y[after].sum())
                        data[cls+'_proxy_positive_components']=len(np.unique(labels[after & (y==1)]))
                    training.append(data)
    membership.to_csv(folder / 'memberships.csv.gz',index=False,compression='gzip')
    pd.DataFrame(metrics).to_csv(folder / 'component_concentration.csv',index=False)
    pd.DataFrame(training).to_csv(folder / 'training_feasibility.csv',index=False)
    pd.DataFrame(edge_counts).to_csv(folder / 'edge_counts.csv',index=False)
    # Containment >= Jaccard for every pair; its edges must be supersets.
    assert np.all(containment >= jaccard)
    dump(folder / 'summary.json', {'representation':variant,'nodes':n,'informative_nodes':int(informative.sum()),
                                  'unavailable_nodes':int((~informative).sum()),'pairs_containment_ge_070':len(a),
                                  'pair_definition':'undirected edge when either directed containment reaches threshold',
                                  'runtime_seconds':time.perf_counter()-start,
                                  'peak_rss_mib_cumulative':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                                  'no_model_scoring':True,
                                  'output_hashes':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}})
    del a,b,inter,jaccard,containment,membership
    gc.collect()
    print(f'completed {variant}',flush=True)


def run(out):
    start=time.perf_counter()
    manifest=json.loads((out/'manifest.json').read_text())
    assert manifest['status']=='prepared_no_outputs'
    assert sha(out/'config_before_outputs.json')==manifest['config_sha256']
    config=json.loads((out/'config_before_outputs.json').read_text())
    for section in ('source_hashes','input_hashes'):
        for path,digest in config[section].items():
            assert sha(ROOT/path)==digest,path
    nodes=pd.read_csv(BASE/'nodes.csv',keep_default_na=False)
    assert np.array_equal(nodes.node_id,np.arange(24131)) and int(nodes.candidate_test.sum())==1998
    edges=pd.read_csv(BASE/'edges.csv',keep_default_na=False)
    structure=edges[edges.edge_type!='normalized_shingle'].copy()
    structure.to_csv(out/'structural_edges_unchanged.csv',index=False)
    # Node population/identity provenance stays identical; no source labels copied.
    nodes.to_csv(out/'nodes_unchanged.csv',index=False)
    cache=ROOT/config['private_stream_cache']
    manifest.update(status='running',started_utc=utc());dump(out/'manifest.json',manifest)
    preprocess(out,cache,nodes)
    historical=load_all().set_index('path')
    labelmap={cls:np.array([int(historical.loc[r.path,cls]) if r.historical_train else -1 for r in nodes.itertuples()])
              for cls in ('reentrancy','unchecked')}
    dump(out/'training_label_input_hashes.json',{str(p):sha(p) for p in label_files()})
    del historical
    for index in range(len(VARIANTS)):
        graph_variant(out,cache,index,nodes,structure,labelmap,config)
    manifest.update(status='complete_unscored_representation_sensitivity',finished_utc=utc(),
                    runtime_seconds=time.perf_counter()-start,
                    peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                    no_model_scoring=True,no_external_labels_read=True,
                    common_output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='manifest.json'})
    dump(out/'manifest.json',manifest)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--cache',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':
        if not args.cache:
            parser.error('--cache is required for prepare')
        prepare(args.out,args.cache.resolve())
    else:
        run(args.out)
