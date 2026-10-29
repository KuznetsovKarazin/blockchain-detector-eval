#!/usr/bin/env python3
"""Verify the public release before locally materializing restricted labels."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

def main():
    manifest = json.loads((ROOT / 'ARTICLE1_RELEASE_MANIFEST.json').read_text())
    entries = manifest.get('files', [])
    if 'manifest_parts' in manifest:
        for part in manifest['manifest_parts']:
            path = Path(part['path'])
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe manifest part path')
            data = (ROOT / path).read_bytes()
            if len(data) != part['bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
                raise ValueError(f'Manifest part hash mismatch: {path}')
            rows = json.loads(data)
            if len(rows) != part['files']:
                raise ValueError('Incorrect manifest part count')
            entries.extend(rows)
        if len(entries) != manifest['file_count']:
            raise ValueError('Incorrect complete manifest count')
    paths = set()
    total = 0
    for row in entries:
        path = Path(row['path'])
        if path.is_absolute() or '..' in path.parts or row['path'] in paths:
            raise ValueError('Unsafe or duplicate manifest path')
        paths.add(row['path'])
        actual = ROOT / path
        if actual.is_symlink():
            raise ValueError(f'Unexpected symlink: {path}')
        data = actual.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError(f'Public release bytes changed: {path}')
        total += len(data)
    print(json.dumps({'status': 'pass', 'files': len(paths), 'bytes': total,
                      'scope': 'Distributed files only; run before annotation materialization.'}))

if __name__ == '__main__':
    main()
