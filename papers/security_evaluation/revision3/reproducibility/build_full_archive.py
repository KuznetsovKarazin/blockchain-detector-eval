#!/usr/bin/env python3
"""Build a single self-contained public code/evidence archive for Zenodo.

The input is the fully restored PUBLIC tree, before annotation materialization.
The asset ZIP is not nested again: its scientific files already occupy their
original paths. Only files indexed by the public manifest are included.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from verify_public_projection import check as check_public_projection

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tree', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    public_projection_check = check_public_projection(args.tree.resolve())
    index_path = args.tree / 'ARTICLE1_RELEASE_MANIFEST.json'
    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes)
    records = []
    for part in index['manifest_parts']:
        data = (args.tree / part['path']).read_bytes()
        assert len(data) == part['bytes'] and sha(data) == part['sha256']
        records.extend(json.loads(data))
    assert len(records) == index['file_count']
    records += [{k: p[k] for k in ['path', 'bytes', 'sha256']} for p in index['manifest_parts']]
    records.append({'path': index_path.name, 'bytes': len(index_bytes), 'sha256': sha(index_bytes)})
    assert len(records) == len({r['path'] for r in records})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in records:
            path = Path(row['path'])
            assert not path.is_absolute() and '..' not in path.parts and path.parts[0] not in {'data', '.git', 'reproduction'}
            data = (args.tree / path).read_bytes()
            assert len(data) == row['bytes'] and sha(data) == row['sha256'], row['path']
            archive.writestr(row['path'], data)
    with zipfile.ZipFile(args.out) as archive:
        assert archive.testzip() is None and len(archive.namelist()) == len(records)
        for row in records:
            data = archive.read(row['path'])
            assert len(data) == row['bytes'] and sha(data) == row['sha256']
    receipt = {'schema': 'article1_full_public_reproducibility_archive_v1', 'status': 'pass',
               'public_projection_check': public_projection_check,
               'archive': str(args.out), 'bytes': args.out.stat().st_size,
               'sha256': sha(args.out.read_bytes()), 'files': len(records),
               'manifest_sha256': sha(index_bytes), 'all_crc_size_sha256_verified': True,
               'raw_third_party_corpora_or_restricted_annotation_values_included': False,
               'nested_duplicate_evidence_asset': False, 'public_or_remote_writes': False}
    args.out.with_suffix('.verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
