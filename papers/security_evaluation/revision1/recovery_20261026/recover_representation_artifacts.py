#!/usr/bin/env python3
"""Fresh local recomputation from unchanged frozen representation functions.

Never modify a surviving result. Restore missing paths only after matching both
the original SHA256 and Git blob SHA1. No models, scores, uploads or publications.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import scipy

ROOT = Path(__file__).resolve().parents[4]
REP = ROOT / 'papers/security_evaluation/revision1/representations'
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(REP))
import run_representations as primary
import run_segmented_control as segmented


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def blob(p):
    b = Path(p).read_bytes()
    return hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest()


def dump(p, obj):
    Path(p).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def check(mapping):
    checked = []
    for name, expected in mapping.items():
        p = ROOT / name
        assert sha(p) == expected, name
        checked.append({'path': name, 'sha256': expected})
    return checked


def restore(candidate, old, expected, omitted):
    relative = str(old.relative_to(ROOT))
    row = {'original_path': relative, 'candidate': str(candidate.relative_to(ROOT)),
           'expected_sha256': expected, 'actual_sha256': sha(candidate),
           'expected_git_blob_sha1': omitted.get(relative), 'actual_git_blob_sha1': blob(candidate),
           'restored': False}
    row['sha256_match'] = row['actual_sha256'] == expected
    row['git_blob_match'] = row['actual_git_blob_sha1'] == omitted.get(relative)
    if relative in omitted and row['sha256_match'] and row['git_blob_match']:
        if old.exists():
            assert sha(old) == expected and blob(old) == omitted[relative]
        else:
            with old.open('xb') as f:
                f.write(candidate.read_bytes())
            row['restored'] = True
    return row


def historical_gzip(candidate, expected, manifest, destination):
    """Reconstruct only the header time; accept solely an exact full-file hash."""
    data = bytearray(candidate.read_bytes())
    assert data[:2] == b'\x1f\x8b'
    start = int(datetime.fromisoformat(manifest['started_utc']).timestamp()) - 2
    end = int(datetime.fromisoformat(manifest['finished_utc']).timestamp()) + 2
    for timestamp in range(start, end + 1):
        data[4:8] = struct.pack('<I', timestamp)
        if hashlib.sha256(data).hexdigest() == expected:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as f:
                f.write(data)
            assert gzip.decompress(data) == gzip.decompress(candidate.read_bytes())
            return destination, timestamp
    return candidate, None


def compare_variant(out, original, name, omitted, results):
    old = original / name
    new = out / name
    summary = json.loads((old / 'summary.json').read_text())
    manifest = json.loads((original / 'manifest.json').read_text())
    for filename, expected in summary['output_hashes'].items():
        candidate = new / filename
        if filename == 'memberships.csv.gz':
            candidate, timestamp = historical_gzip(candidate, expected, manifest,
                out / 'exact_candidates' / name / filename)
        else:
            timestamp = None
        row = restore(candidate, old / filename, expected, omitted)
        row['gzip_historical_mtime'] = timestamp
        if (old / filename).exists() and filename not in ('lexical_edges.npz', 'memberships.csv.gz'):
            assert row['sha256_match'], (name, filename)
        results.append(row)
    edge = np.load(new / 'lexical_edges.npz')
    order = np.lexsort((edge['right'], edge['left']))
    canonical = hashlib.sha256()
    for key in ('left', 'right', 'intersection'):
        canonical.update(np.asarray(edge[key][order], dtype='<i4').tobytes())
    canonical.update(np.asarray(edge['node_shingle_sizes'], dtype='<i4').tobytes())
    dump(new / 'canonical_graph_recovery.json', {
        'schema': 'sorted_edges_and_node_sizes_little_endian_int32_v1',
        'array_order': ['left', 'right', 'intersection', 'node_shingle_sizes'],
        'canonical_sha256': canonical.hexdigest(), 'edges': len(order),
        'purpose': 'New recovery provenance only; no original canonical edge digest survives for comparison'})
    dump(out.parent / 'recovery_comparisons.json', results)


def main():
    out = Path(sys.argv[1]).resolve()
    assert out.is_relative_to(ROOT / 'data/derived')
    out.mkdir(parents=True, exist_ok=False)
    assert subprocess.check_output(['git', '-C', str(ROOT), 'check-ignore', str(out)], text=True).strip()
    old = REP / 'run_20261025_v1'
    oldseg = REP / 'segmented_control_20261025_v1'
    config = json.loads((old / 'config_before_outputs.json').read_text())
    configseg = json.loads((oldseg / 'config_before_outputs.json').read_text())
    checked = check(config['source_hashes']) + check(config['input_hashes']) + check(configseg['code_hashes'])
    for p, expected in config['source_hashes'].items():
        assert sha(old / 'executed_source' / p) == expected
    for p, expected in configseg['code_hashes'].items():
        assert sha(oldseg / 'executed_source' / p) == expected
    for name, pin in config['upstream_pins'].items():
        repo = ROOT / 'data/raw' / name
        assert primary.git(repo, 'rev-parse', 'HEAD') == pin['commit']
        assert not primary.git(repo, 'status', '--porcelain')
    environment = {'python': sys.version, 'numpy': np.__version__, 'pandas': pd.__version__, 'scipy': scipy.__version__}
    assert environment == config['environment']
    omissions = json.loads((ROOT / 'papers/security_evaluation/revision1/publication_omissions.json').read_text())
    omitted = {x['path']: x['git_blob_sha'] for x in omissions['omitted']}
    fresh = out / 'primary'
    freshseg = out / 'segmented'
    cache = out / 'streams'
    segcache = out / 'segments'
    for folder in (fresh, freshseg, cache, segcache):
        folder.mkdir()
    dump(out / 'recovery_config_before_compute.json', {
        'schema': 'representation_recovery_v1', 'utc': datetime.now(timezone.utc).isoformat(),
        'wrapper_sha256': sha(__file__), 'checked_inputs_and_sources': checked, 'environment': environment,
        'original_config_sha256': sha(old / 'config_before_outputs.json'),
        'original_segmented_config_sha256': sha(oldseg / 'config_before_outputs.json'),
        'pythonhashseed_recovery': os.environ.get('PYTHONHASHSEED'),
        'original_pythonhashseed': 'not recorded; row-order identity cannot be assumed',
        'changes': ['Call unchanged preprocessing and graph functions in new directories',
                    'Redirect runtime private caches and segmented parent graph to fresh recovery outputs',
                    'Reconstruct historical gzip header time only when the full original SHA256 matches'],
        'no_model_scoring': True, 'no_upload': True})
    shutil.copy2(__file__, out / 'executed_recovery_wrapper.py')
    nodes = pd.read_csv(primary.BASE / 'nodes.csv', keep_default_na=False)
    edges = pd.read_csv(primary.BASE / 'edges.csv', keep_default_na=False)
    structure = edges[edges.edge_type != 'normalized_shingle'].copy()
    nodes.to_csv(fresh / 'nodes_unchanged.csv', index=False)
    structure.to_csv(fresh / 'structural_edges_unchanged.csv', index=False)
    for name in ('nodes_unchanged.csv', 'structural_edges_unchanged.csv'):
        assert sha(fresh / name) == sha(old / name)
        shutil.copy2(fresh / name, freshseg / name)
    primary.preprocess(fresh, cache, nodes)
    for name in ('representation_metadata.csv', 'coverage.csv'):
        assert sha(fresh / name) == sha(old / name)
    train = primary.load_all().set_index('path')
    labels = {c: np.array([int(train.loc[r.path, c]) if r.historical_train else -1 for r in nodes.itertuples()])
              for c in ('reentrancy', 'unchecked')}
    for p, expected in json.loads((old / 'training_label_input_hashes.json').read_text()).items():
        assert sha(p) == expected
    del train
    results = []
    for index, name in enumerate(primary.VARIANTS):
        primary.graph_variant(fresh, cache, index, nodes, structure, labels, config)
        compare_variant(fresh, old, name, omitted, results)
    runtime = dict(configseg)
    runtime.update(original_run=str(fresh.relative_to(ROOT)), original_private_cache=str(cache.relative_to(ROOT)),
                   private_cache=str(segcache.relative_to(ROOT)))
    segmented.preprocess(freshseg, runtime, nodes)
    assert sha(freshseg / 'boundary_diagnostics.csv') == sha(oldseg / 'boundary_diagnostics.csv')
    for index, name in enumerate(segmented.VARIANTS):
        segmented.graph(freshseg, runtime, nodes, structure, labels, index)
        compare_variant(freshseg, oldseg, name, omitted, results)
    missing = [r for r in results if r['original_path'] in omitted]
    dump(out / 'recovery_result.json', {'status': 'complete', 'comparisons': results,
         'missing_artifacts_checked': len(missing), 'artifacts_matching_both_original_hashes': sum(r['sha256_match'] and r['git_blob_match'] for r in missing),
         'restored': sum(r['restored'] for r in missing), 'no_model_scoring': True,
         'caveat': 'If NPZ hash differs, matching aggregate tables and memberships does not by itself prove original full edge-list equality'})
    print(json.dumps({'complete': True, 'restored': sum(r['restored'] for r in missing)}), flush=True)


if __name__ == '__main__':
    main()
