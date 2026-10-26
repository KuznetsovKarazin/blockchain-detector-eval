"""Package audited derived outputs for the author's private recovery copy.

This does not upload or publish anything and never reads source bodies or keys.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    recovery = repo / 'papers/security_evaluation/revision1/recovery_20261026'
    omission = repo / 'papers/security_evaluation/revision1/publication_omissions.json'
    gz_entries = [x for x in json.loads(omission.read_text())['omitted'] if x['path'].endswith('.gz')]
    npz = sorted((recovery / 'representation_edges_v1').glob('*/lexical_edges.npz'))
    if len(gz_entries) != 23 or len(npz) != 6:
        raise ValueError('Unexpected recovery output inventory')
    for record in gz_entries:
        data = (repo / record['path']).read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if actual != record['git_blob_sha']:
            raise ValueError('Recovered gzip differs from original: ' + record['path'])
    for name in ['PUBLIC_GZIP_CONTENT_AUDIT.json', 'CANONICAL_NPZ_SCHEMA_AUDIT.json']:
        if json.loads((recovery / name).read_text())['status'] != 'pass':
            raise ValueError('Content audit did not pass')
    paths = [repo / x['path'] for x in gz_entries] + npz + [omission]
    paths += [recovery / x for x in [
        'PUBLIC_GZIP_CONTENT_AUDIT.json', 'CANONICAL_NPZ_SCHEMA_AUDIT.json',
        'CANONICAL_NPZ_SCHEMA_AUDIT.md', 'REPRESENTATION_RECOVERY.md',
        'REPRESENTATION_RECOVERY.json', 'REPRESENTATION_INDEPENDENT_CHECK.json',
        'GRAPH_MECHANISM_RECOVERY.md', 'SAMPLING_RECOVERY.md',
    ]]
    paths += sorted((recovery / 'representation_edges_v1').glob('*.json'))
    content = {str(p.relative_to(repo)): p.read_bytes() for p in paths}
    content['README.txt'] = (
        'Author recovery copy, 26 October 2026. Not a public deposit.\n'
        'Contains 23 byte-exact recovered gzip outputs and six NEW canonical NPZ outputs.\n'
        'The six original NPZ byte streams remain unavailable. New outputs have distinct paths.\n'
        'All 120 representation partitions and 20 tables reproduce; full original edge identity is unproved.\n'
        'Only audited derived graph metadata is included. No third-party source bodies, copied annotation\n'
        'keys, human judgments, model labels/scores, signed contracts or credentials are included.\n'
        'Publication review still blocks public compressed output upload. This private copy does not\n'
        'resolve that block and must not be linked from the public repository as a public deposit.\n'
        'Extract relative to a copy of the article repository; never overwrite original NPZ paths.\n'
    ).encode()
    index = {'schema': 'author_private_recovery_bundle_v1', 'files': [
        {'path': name, 'bytes': len(data), 'sha256': digest(data)}
        for name, data in sorted(content.items())]}
    content['BUNDLE_CONTENTS.json'] = (json.dumps(index, indent=2) + '\n').encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(content.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 26, 0, 0, 0))
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(args.output) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(content):
            raise ValueError('Archive inventory or CRC failure')
        for name, data in content.items():
            if archive.read(name) != data:
                raise ValueError('Archive roundtrip mismatch: ' + name)
    receipt = {'schema': 'author_private_recovery_bundle_receipt_v1',
               'filename': args.output.name, 'bytes': args.output.stat().st_size,
               'sha256': digest(args.output.read_bytes()), 'files': len(content),
               'byte_exact_gzip_paths': 23, 'new_canonical_npz_paths': 6,
               'public_deposit': False, 'roundtrip_verified': True}
    (recovery / 'PRIVATE_BUNDLE_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
