#!/usr/bin/env python3
"""Fetch the pinned public release asset and safely restore its original paths."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import stat
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def restore(archive, descriptor):
    if archive.stat().st_size != descriptor['archive_bytes'] or sha(archive) != descriptor['archive_sha256']:
        raise ValueError('Evidence archive size/SHA-256 mismatch')
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.namelist()) != len(set(bundle.namelist())):
            raise ValueError('Duplicate archive member')
        inner_bytes = bundle.read('EVIDENCE_CONTENTS.json')
        if hashlib.sha256(inner_bytes).hexdigest() != descriptor['inventory_sha256']:
            raise ValueError('Internal evidence inventory hash differs')
        inner = json.loads(inner_bytes)
        expected = {r['path']: r for r in inner['files']}
        if len(expected) != len(inner['files']) or len(expected) != descriptor['files_count']:
            raise ValueError('Duplicate or incomplete evidence inventory')
        if set(bundle.namelist()) != set(expected) | {'EVIDENCE_CONTENTS.json'}:
            raise ValueError('Archive and descriptor inventories differ')
        # Validate all paths, content and existing files before any write.
        for name, row in expected.items():
            path = Path(name)
            info = bundle.getinfo(name)
            if path.is_absolute() or '..' in path.parts or path.parts[0] in {'.git', 'data'}:
                raise ValueError(f'Unsafe evidence path: {name}')
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f'Unexpected archive symlink: {name}')
            if info.file_size != row['bytes']:
                raise ValueError(f'Unexpected expanded size: {name}')
            data = bundle.read(name)
            if hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError(f'Evidence content hash mismatch: {name}')
            target = ROOT / path
            if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != ROOT.parent):
                raise ValueError(f'Symlink in destination: {name}')
            if target.exists() and (not target.is_file() or sha(target) != row['sha256']):
                raise ValueError(f'Refuse differing existing scientific file: {name}')
        for name in expected:
            target = ROOT / name
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(name))
    return len(expected)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--archive', type=Path, help='Already downloaded public asset (optional)')
    ap.add_argument('--receipt', type=Path, default=Path('reproduction/evidence_restore.json'))
    args = ap.parse_args()
    descriptor = json.loads((HERE / 'EVIDENCE_ASSET.json').read_text())
    if args.archive:
        count = restore(args.archive.resolve(), descriptor)
    else:
        # The URL is pinned to a versioned public release and a verified SHA-256.
        with tempfile.TemporaryDirectory(prefix='article1-evidence-') as temp:
            path = Path(temp) / descriptor['archive_name']
            request = urllib.request.Request(descriptor['download_url'], headers={'User-Agent': 'article1-reproduction'})
            with urllib.request.urlopen(request) as response, path.open('wb') as stream:
                while block := response.read(1024 * 1024):
                    stream.write(block)
            count = restore(path, descriptor)
    receipt = {'status': 'pass', 'restored_or_verified_files': count,
               'archive_sha256': descriptor['archive_sha256'],
               'original_paths_restored': True, 'raw_third_party_corpora_or_restricted_annotations_included': False}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
