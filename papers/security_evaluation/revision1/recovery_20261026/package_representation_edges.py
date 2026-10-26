#!/usr/bin/env python3
"""Package new, verified edge reproductions; never restore a lost original NPZ.

Sorting is a pure permutation of (left,right,intersection) rows. Node shingle
sizes are indexed by node and are never permuted. ZIP metadata is deterministic.
No raw Solidity, labels, model scores, upload or Git mutation is performed.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
REP = ROOT / 'papers/security_evaluation/revision1/representations'
KEYS = ('left', 'right', 'intersection', 'node_shingle_sizes')
ROW_KEYS = KEYS[:3]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p, value):
    Path(p).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def archive_bytes(arrays):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for key in KEYS:
            data = io.BytesIO()
            np.lib.format.write_array(data, arrays[key], version=(1, 0), allow_pickle=False)
            entry = zipfile.ZipInfo(key+'.npy', date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o100600 << 16
            entry.extra = b''
            entry.comment = b''
            archive.writestr(entry, data.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def main():
    replay = Path(sys.argv[1]).resolve()
    assert replay.is_relative_to(ROOT/'data/derived')
    output = HERE/'representation_edges_v1'
    output.mkdir(exist_ok=False)
    receipt = json.loads((HERE/'REPRESENTATION_RECOVERY.json').read_text())
    verification = json.loads((HERE/'REPRESENTATION_INDEPENDENT_CHECK.json').read_text())
    assert receipt['status'] == 'complete' and verification['status'] == 'pass'
    assert receipt['artifacts_matching_both_original_hashes'] == 6
    assert sha(replay/'recovery_config_before_compute.json') == receipt['recovery_configuration_sha256']
    config = {'schema':'canonical_representation_edge_packaging_v1',
        'scientific_status':'new independently verified computational reproduction; not historical edge-array recovery',
        'script_sha256':sha(__file__), 'replay_root':str(replay.relative_to(ROOT)),
        'replay_configuration_sha256':receipt['recovery_configuration_sha256'],
        'recovery_receipt_sha256':sha(HERE/'REPRESENTATION_RECOVERY.json'),
        'independent_verification_sha256':sha(HERE/'REPRESENTATION_INDEPENDENT_CHECK.json'),
        'row_order':'ascending (left,right); same permutation for left,right,intersection',
        'node_vector':'node_shingle_sizes stays in node_id order0..24130',
        'array_encoding':'one-dimensional little-endian int32; NumPy .npy version1.0; no pickle',
        'zip_encoding':{'entry_order':[k+'.npy' for k in KEYS], 'timestamp':[1980,1,1,0,0,0],
                        'compression':'deflate', 'compression_level':9, 'create_system':3,
                        'external_attr':0o100600 << 16, 'extra':'', 'comment':''},
        'environment':{'python':sys.version, 'numpy':np.__version__, 'zlib_compiled':zlib.ZLIB_VERSION,
                       'zlib_runtime':zlib.ZLIB_RUNTIME_VERSION},
        'no_model_scoring':True, 'no_upload':True, 'no_git_mutation':True}
    dump(output/'packaging_config_before_outputs.json',config)
    entries = []
    for kind, oldname in [('primary','run_20261025_v1'), ('segmented','segmented_control_20261025_v1')]:
        frozen = REP/oldname
        original_config = json.loads((frozen/'config_before_outputs.json').read_text())
        for variant in original_config['variants']:
            source = replay/kind/variant/'lexical_edges.npz'
            lost = frozen/variant/'lexical_edges.npz'
            assert not lost.exists(), 'Do not replace or reinterpret a historical archive'
            relative = str(lost.relative_to(ROOT))
            prior = next(x for x in receipt['comparisons'] if x['original_path'] == relative)
            assert sha(source) == prior['actual_sha256']
            assert prior['sha256_match'] is False and prior['git_blob_match'] is False
            with np.load(source, allow_pickle=False) as stored:
                assert tuple(stored.files) == KEYS
                arrays = {k:stored[k].copy() for k in KEYS}
            for a in arrays.values():
                assert a.ndim == 1 and a.dtype.kind == 'i' and a.dtype.itemsize == 4
            left,right,intersection,size = [arrays[k] for k in KEYS]
            n = len(size)
            assert n == 24131 and len(left) == len(right) == len(intersection)
            assert np.all(size >= 0)
            assert np.all((left >= 0) & (left < right) & (right < n))
            assert np.all((intersection > 0) & (intersection <= np.minimum(size[left], size[right])))
            assert np.all(intersection / np.minimum(size[left], size[right]) >= .7)
            order = np.lexsort((right,left))
            ordered = {k:np.asarray(arrays[k][order], dtype='<i4') for k in ROW_KEYS}
            ordered['node_shingle_sizes'] = np.asarray(size, dtype='<i4')
            pairs = ordered['left'].astype(np.int64)*n+ordered['right']
            assert np.all(pairs[1:] > pairs[:-1]), 'Duplicate or unsorted node pair'
            inverse = np.empty_like(order)
            inverse[order] = np.arange(len(order))
            for key in ROW_KEYS:
                assert np.array_equal(ordered[key][inverse], arrays[key])
            assert np.array_equal(ordered['node_shingle_sizes'], size)
            canonical_data = hashlib.sha256()
            for key in KEYS:
                canonical_data.update(ordered[key].tobytes())
            previous_canonical = receipt['new_canonical_graphs'][kind+'/'+variant]['canonical_sha256']
            assert canonical_data.hexdigest() == previous_canonical
            payload = archive_bytes(ordered)
            assert payload == archive_bytes(ordered), 'Archive encoding not deterministic'
            folder = output/variant
            folder.mkdir()
            target = folder/'lexical_edges.npz'
            with target.open('xb') as f:
                f.write(payload)
            with np.load(target, allow_pickle=False) as reloaded:
                assert tuple(reloaded.files) == KEYS
                for key in KEYS:
                    assert reloaded[key].dtype.str == '<i4'
                    assert np.array_equal(reloaded[key],ordered[key])
                for key in ROW_KEYS:
                    assert np.array_equal(reloaded[key][inverse], arrays[key])
            lineage = []
            for comparison in receipt['comparisons']:
                if Path(comparison['original_path']).parent == lost.parent.relative_to(ROOT) and comparison['original_path'] != relative:
                    original = ROOT/comparison['original_path']
                    assert comparison['sha256_match'] and sha(original) == comparison['expected_sha256']
                    lineage.append({'path':comparison['original_path'],'sha256':comparison['expected_sha256']})
            assert len(lineage) == (4 if kind == 'primary' else 5)
            entries.append({'variant':variant,'nodes':n,'saved_pairs':len(order),
                'original_missing_path':relative,'original_lost_npz_sha256':prior['expected_sha256'],
                'original_lost_git_blob_sha1':prior['expected_git_blob_sha1'],
                'original_frozen_config_path':str((frozen/'config_before_outputs.json').relative_to(ROOT)),
                'original_frozen_config_sha256':sha(frozen/'config_before_outputs.json'),
                'fresh_replay_path':str(source.relative_to(ROOT)), 'fresh_replay_npz_sha256':sha(source),
                'new_canonical_path':str(target.relative_to(ROOT)), 'new_canonical_npz_sha256':sha(target),
                'new_canonical_array_bytes_sha256':canonical_data.hexdigest(),
                'byte_size':len(payload),'duplicates':0,'sorting':'strictly increasing left*24131+right',
                'full_unordered_row_identity_with_fresh_replay':True,'node_vector_identical_to_fresh_replay':True,
                'original_full_unordered_edge_identity_established':False,
                'identical_reported_result_lineage':lineage,
                'arrays':{k:{'dtype':ordered[k].dtype.str,'shape':list(ordered[k].shape),
                             'raw_little_endian_sha256':hashlib.sha256(ordered[k].tobytes()).hexdigest()} for k in KEYS}})
    assert len(entries) == 6
    dump(output/'manifest.json',{'schema':'canonical_representation_reproduction_package_v1','status':'complete_verified_local_package',
        'packaging_config_sha256':sha(output/'packaging_config_before_outputs.json'),
        'entries':entries,'reported_component_partitions_preserved':120,'existing_result_csvs_byte_identical':20,
        'independent_validation':{'union_find_primary_reconstructions':12,'literal_shingle_pair_checks':600,
            'receipt_path':str((HERE/'REPRESENTATION_INDEPENDENT_CHECK.json').relative_to(ROOT)),
            'receipt_sha256':sha(HERE/'REPRESENTATION_INDEPENDENT_CHECK.json'),
            'transfer_to_sorted_archive':'Every complete row and node size is unchanged, so existing predicate checks apply'},
        'claim':'New independently verified computational reproduction; original complete unordered edge-list identity cannot be proved from surviving artifacts',
        'no_model_scoring':True,'no_upload':True,'no_git_mutation':True})
    print(json.dumps({'archives':len(entries),'bytes':sum(x['byte_size'] for x in entries),
        'full_unordered_identity_with_fresh_replay':True,'original_full_edge_identity_established':False}),flush=True)


if __name__ == '__main__':
    main()
