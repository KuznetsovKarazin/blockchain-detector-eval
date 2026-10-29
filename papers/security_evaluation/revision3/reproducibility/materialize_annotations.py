#!/usr/bin/env python3
"""Reconstruct withheld annotation projections locally and require original hashes.

Run only in a local checkout. The public release deliberately omits upstream
annotation values. This restores scientific files for checksum/metric audits;
it never contacts a publishing service or changes frozen manifests.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--receipt', type=Path, required=True)
    args = ap.parse_args()
    import pandas as pd
    code = ROOT / 'papers/security_evaluation/revision2/model_link/analyze.py'
    spec = importlib.util.spec_from_file_location('article1_label_mapping', code)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inventory = pd.read_csv(module.PILOT / 'source_inventory.csv')
    labels, count = module.read_labels(inventory, ROOT / 'data/raw/DAppSCAN')
    projection = json.loads((HERE / 'PUBLIC_PROJECTION.json').read_text())
    prepared = []
    for record in projection['omitted_files']:
        path = ROOT / record['path']
        if path.name != 'labels.json':
            continue
        rows = pd.read_csv(path.parent / 'source_inventory.csv')
        values = {str(int(i)): labels[int(i)] for i in rows.file_id}
        data = (json.dumps(values, indent=2) + '\n').encode()
        if digest(data) != record['sha256']:
            raise ValueError(f'Reconstructed labels differ from frozen bytes: {record["path"]}')
        prepared.append((path, data, record['sha256']))
    for record in projection['transformed_files']:
        path = ROOT / record['path']
        raw = path.read_bytes()
        if digest(raw) == record['original_sha256']:
            prepared.append((path, raw, record['original_sha256']))
            continue
        if digest(raw) != record['public_sha256']:
            raise ValueError(f'Unexpected edited public table: {record["path"]}')
        compressed = path.name.endswith('.csv.gz')
        plain = gzip.decompress(raw) if compressed else raw
        rows = list(csv.DictReader(io.StringIO(plain.decode())))
        for row in rows:
            values = labels[int(row['file_id'])]
            for field in record['removed_columns']:
                key = field.removesuffix('_proxy')
                if key not in values:
                    raise ValueError(f'Undeclared annotation column: {field}')
                row[field] = str(values[key])
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=record['original_columns'], lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        data = stream.getvalue().encode()
        if compressed:
            buffer = io.BytesIO()
            with gzip.GzipFile(filename='', mode='wb', fileobj=buffer, mtime=0) as binary:
                binary.write(data)
            data = buffer.getvalue()
        if digest(data) != record['original_sha256']:
            raise ValueError(f'Reconstructed table differs from frozen bytes: {record["path"]}')
        prepared.append((path, data, record['original_sha256']))
    for path, data, expected in prepared:
        if path.exists() and path.name == 'labels.json' and digest(path.read_bytes()) != expected:
            raise ValueError(f'Refuse changed existing labels: {path}')
    for path, data, expected in prepared:
        if path.exists() and digest(path.read_bytes()) == expected:
            continue
        # Atomic replacement deliberately breaks any pre-existing hardlink.
        # A local reconstruction must never change a separate public snapshot.
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.annotation-', delete=False) as stream:
            stream.write(data)
            temporary = Path(stream.name)
        os.replace(temporary, path)
    result = {'schema': 'article1_local_annotation_materialization_v1',
              'status': 'pass', 'verified_upstream_annotation_files': count,
              'restored': [{'path': str(p.relative_to(ROOT)), 'sha256': h} for p, _, h in prepared],
              'public_or_remote_writes': False}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
