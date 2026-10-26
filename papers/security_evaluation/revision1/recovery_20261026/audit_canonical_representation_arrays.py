#!/usr/bin/env python3
"""Read-only independent full ZIP/NPY schema and graph-content audit.

Does not import the packaging or graph-generation implementation. It accounts
for every archive byte, decodes NPY headers explicitly, and compares each fresh
replay edge by binary-search lookup rather than the packager's permutation.
"""
from __future__ import annotations
import ast
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import zipfile
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PACKAGE = HERE/'representation_edges_v1'
KEYS = ('left','right','intersection','node_shingle_sizes')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def archive_schema(data, expected_arrays):
    """Reject extra entries, bytes, comments, headers, object arrays and trailers."""
    arrays, metadata = {}, []
    assert data.startswith(b'PK\x03\x04')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        assert [x.filename for x in entries] == [k+'.npy' for k in KEYS]
        assert len({x.filename for x in entries}) == 4 and archive.comment == b''
        next_offset = 0
        for key, entry in zip(KEYS, entries):
            assert entry.header_offset == next_offset
            assert entry.flag_bits == 0 and entry.compress_type == zipfile.ZIP_DEFLATED
            assert entry.extra == b'' and entry.comment == b'' and not entry.is_dir()
            assert entry.date_time == (1980,1,1,0,0,0)
            assert entry.create_system == 3 and entry.external_attr == 0o100600 << 16
            assert 0 < entry.file_size <= 64*1024*1024
            local = struct.unpack_from('<4s5H3I2H', data, next_offset)
            signature, version, flags, method, mtime, mdate, crc, compressed, size, name_length, extra_length = local
            assert signature == b'PK\x03\x04' and version == 20
            assert flags == 0 and method == 8 and mtime == 0 and mdate == 33
            assert crc == entry.CRC and compressed == entry.compress_size and size == entry.file_size
            assert extra_length == 0
            start = next_offset + 30
            assert data[start:start+name_length] == (key+'.npy').encode('ascii')
            start += name_length
            decompressor = zlib.decompressobj(-15)
            payload = decompressor.decompress(data[start:start+compressed]) + decompressor.flush()
            assert decompressor.eof and not decompressor.unused_data and not decompressor.unconsumed_tail
            assert payload == archive.read(entry) and len(payload) == size
            next_offset = start+compressed
            assert payload[:8] == b'\x93NUMPY\x01\x00'
            header_length = struct.unpack_from('<H',payload,8)[0]
            offset = 10+header_length
            header = payload[10:offset]
            shape = expected_arrays[key]['shape']
            assert len(shape) == 1 and type(shape[0]) is int and shape[0] > 0
            canonical_header = ("{'descr': '<i4', 'fortran_order': False, 'shape': ("+str(shape[0])+",), }").encode('ascii')
            assert header.startswith(canonical_header) and header.endswith(b'\n')
            assert set(header[len(canonical_header):-1]) <= {32}
            decoded = ast.literal_eval(header.decode('ascii').strip())
            assert decoded == {'descr':'<i4','fortran_order':False,'shape':(shape[0],)}
            assert offset % 64 == 0
            raw = payload[offset:]
            assert len(raw) == 4*shape[0] and offset+len(raw) == len(payload)
            assert expected_arrays[key]['dtype'] == '<i4'
            assert digest(raw) == expected_arrays[key]['raw_little_endian_sha256']
            arrays[key] = np.frombuffer(raw,dtype='<i4').copy()
            metadata.append({'name':key,'shape':shape,'dtype':'<i4','raw_bytes':len(raw),
                'sha256':digest(raw),'minimum':int(arrays[key].min()),'maximum':int(arrays[key].max()),
                'npy_header_exact_fixed_schema':True,'no_trailing_npy_bytes':True})
        assert next_offset == archive.start_dir
        directory_start = next_offset
        for key, entry in zip(KEYS,entries):
            central = struct.unpack_from('<4s6H3I5H2I',data,next_offset)
            (sig,made,needed,flags,method,mtime,mdate,crc,compressed,size,name_length,
             extra_length,comment_length,disk,internal,external,local_offset) = central
            assert sig == b'PK\x01\x02' and made == (3 << 8) | 20 and needed == 20
            assert flags == 0 and method == 8 and mtime == 0 and mdate == 33
            assert (crc,compressed,size) == (entry.CRC,entry.compress_size,entry.file_size)
            assert extra_length == comment_length == disk == internal == 0
            assert external == entry.external_attr and local_offset == entry.header_offset
            next_offset += 46
            assert data[next_offset:next_offset+name_length] == (key+'.npy').encode('ascii')
            next_offset += name_length
        eocd = struct.unpack_from('<4s4H2IH',data,next_offset)
        assert eocd == (b'PK\x05\x06',0,0,4,4,next_offset-directory_start,directory_start,0)
        assert next_offset+22 == len(data), 'Unexpected ZIP prefix, gap or trailing payload'
    with np.load(io.BytesIO(data),allow_pickle=False) as numpy_loaded:
        assert tuple(numpy_loaded.files) == KEYS
        for key in KEYS:
            assert numpy_loaded[key].dtype.str == '<i4' and numpy_loaded[key].ndim == 1
            assert not numpy_loaded[key].dtype.hasobject
            assert np.array_equal(numpy_loaded[key],arrays[key])
    return arrays,metadata


def main():
    manifest_path = PACKAGE/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    config_path = PACKAGE/'packaging_config_before_outputs.json'
    assert sha(config_path) == manifest['packaging_config_sha256']
    config = json.loads(config_path.read_text())
    assert sha(HERE/'package_representation_edges.py') == config['script_sha256']
    assert sha(HERE/'REPRESENTATION_RECOVERY.json') == config['recovery_receipt_sha256']
    assert sha(HERE/'REPRESENTATION_INDEPENDENT_CHECK.json') == config['independent_verification_sha256']
    assert len(manifest['entries']) == 6
    assert len({r['variant'] for r in manifest['entries']}) == 6
    actual_paths = {p.resolve() for p in PACKAGE.rglob('*.npz')}
    declared_paths = {(ROOT/r['new_canonical_path']).resolve() for r in manifest['entries']}
    assert actual_paths == declared_paths and len(actual_paths) == 6
    reports=[]
    for record in manifest['entries']:
        path = ROOT/record['new_canonical_path']
        assert path.is_relative_to(PACKAGE) and not path.is_symlink()
        data = path.read_bytes()
        assert digest(data) == record['new_canonical_npz_sha256'] and len(data) == record['byte_size']
        arrays,metadata = archive_schema(data,record['arrays'])
        left,right,inter,sizes = [arrays[key] for key in KEYS]
        n,m = len(sizes),len(left)
        assert n == 24131 == record['nodes'] and m == record['saved_pairs']
        assert len(right) == len(inter) == m
        assert all(np.all(a>=0) for a in arrays.values())
        assert np.all(left<right) and np.all(right<n)
        assert np.all(inter>0) and np.all(sizes[left]>0) and np.all(sizes[right]>0)
        assert np.all(inter<=np.minimum(sizes[left],sizes[right]))
        assert np.all(inter/np.minimum(sizes[left],sizes[right])>=.7)
        codes=left.astype(np.int64)*n+right.astype(np.int64)
        assert np.all(np.diff(codes)>0), 'Not strict lexicographic unique node pairs'
        assert digest(b''.join(arrays[k].tobytes() for k in KEYS)) == record['new_canonical_array_bytes_sha256']
        source=ROOT/record['fresh_replay_path']
        assert sha(source) == record['fresh_replay_npz_sha256']
        with np.load(source,allow_pickle=False) as replay:
            assert tuple(replay.files) == KEYS
            for k in KEYS:
                assert replay[k].dtype.str == '<i4' and replay[k].ndim == 1
            assert np.array_equal(sizes,replay['node_shingle_sizes'])
            lookup = np.searchsorted(codes,replay['left'].astype(np.int64)*n+replay['right'].astype(np.int64))
            assert len(lookup)==m and np.all(lookup<m) and len(np.unique(lookup))==m
            for key in KEYS[:3]:
                assert np.array_equal(arrays[key][lookup],replay[key])
        assert not (ROOT/record['original_missing_path']).exists()
        original_summary=json.loads((ROOT/record['original_missing_path']).with_name('summary.json').read_text())
        assert original_summary['output_hashes']['lexical_edges.npz']==record['original_lost_npz_sha256']
        assert record['original_full_unordered_edge_identity_established'] is False
        for prior in record['identical_reported_result_lineage']:
            assert sha(ROOT/prior['path'])==prior['sha256']
        reports.append({'variant':record['variant'],'archive_path':record['new_canonical_path'],
            'archive_sha256':digest(data),'archive_bytes':len(data),'nodes':n,'edge_rows':m,'arrays':metadata,
            'all_zip_and_npy_bytes_accounted_for':True,'zip_entries_exactly_four_numeric_arrays':True,
            'no_archive_comments_extra_fields_hidden_entries_or_trailers':True,
            'no_object_string_or_pickle_arrays':True,'np_load_allow_pickle':False,
            'all_rows_nonnegative_in_bounds_aligned_unique_lexsorted':True,
            'all_intersections_positive_and_bounded_by_both_set_sizes':True,
            'all_containment_candidates_at_least_070':True,
            'complete_row_bijection_against_fresh_replay':True,'node_sizes_equal_fresh_replay':True,
            'surviving_result_lineage_hashes_valid':True,'original_missing_archive_still_absent':True})
    result={'schema':'independent_full_canonical_npz_schema_content_audit_v1','status':'pass',
        'auditor_source_sha256':sha(__file__),'manifest_sha256':sha(manifest_path),
        'packaging_config_sha256':sha(config_path),'archives_checked':6,'arrays_checked':24,
        'archive_bytes_fully_accounted_for':sum(x['archive_bytes'] for x in reports),
        'edge_rows_exhaustively_checked':sum(x['edge_rows'] for x in reports),
        'checks':reports,'declared_reported_partitions':120,'declared_identical_result_csvs':20,
        'content_conclusion':'Only integer derived graph records and the fixed ZIP/NPY schema metadata; no source-body, private-key, label, score or arbitrary text payload fields/entries',
        'independence':'Separate byte parser and graph-record lookup; does not import packaging or generation functions; automated code audit, not human vulnerability adjudication',
        'historical_identity_limit':'Original six NPZ archives are lost. This verifies the new package against its fresh replay, not complete unordered identity with the historical originals.',
        'no_upload_or_publication_performed':True,'no_model_scoring_or_human_judgments_created':True}
    destination=HERE/'CANONICAL_NPZ_SCHEMA_AUDIT.json'
    assert not destination.exists(), 'Preserve previous audit receipts'
    destination.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ['status','archives_checked','arrays_checked','archive_bytes_fully_accounted_for','edge_rows_exhaustively_checked','manifest_sha256']},indent=2))


if __name__=='__main__':
    main()
