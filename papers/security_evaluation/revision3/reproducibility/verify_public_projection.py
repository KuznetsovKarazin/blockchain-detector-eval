#!/usr/bin/env python3
"""Reject restricted annotations and any changed public table before packaging."""
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

def check(tree):
    path = tree / 'papers/security_evaluation/revision3/reproducibility/PUBLIC_PROJECTION.json'
    projection = json.loads(path.read_text())
    checked = []
    for row in projection['transformed_files']:
        actual = tree / row['path']
        data = actual.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != row['public_sha256']:
            raise ValueError(f'Public projection changed or locally materialized: {row["path"]}')
        plain = gzip.decompress(data) if actual.name.endswith('.gz') else data
        fields = next(csv.reader(io.StringIO(plain.decode())))
        if set(fields) & set(row['removed_columns']):
            raise ValueError(f'Withheld label column present: {row["path"]}')
        checked.append({'path': row['path'], 'sha256': digest})
    for row in projection['omitted_files']:
        if (tree / row['path']).exists():
            raise ValueError(f'Omitted/private file present: {row["path"]}')
    if (tree / 'data/raw').exists():
        raise ValueError('Raw-data directory present in public package')
    return {'status': 'pass', 'public_table_hashes': checked,
            'omitted_paths_confirmed_absent': len(projection['omitted_files']),
            'raw_data_directory_absent': True}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tree', type=Path, default=Path(__file__).resolve().parents[4])
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    result = check(args.tree.resolve())
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
