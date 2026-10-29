#!/usr/bin/env python3
"""Fetch only the pinned source/annotation trees and verify scientific inputs.

This does not redistribute upstream code or annotations. Existing modified or
unexpected checkouts are refused. No models or graph outputs are overwritten.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
PIN = '66a56619c44770e05c2db600fa6468115ff0dcd5'
UPSTREAM = 'https://github.com/InPlusLab/DAppSCAN.git'
SPARSE = ['DAppSCAN-source/contracts', 'DAppSCAN-source/SWCsource']

def git(dst, *args):
    return subprocess.check_output(['git', '-C', str(dst), *args], text=True).strip()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(root):
    dst = root / 'data/raw/DAppSCAN'
    if git(dst, 'rev-parse', 'HEAD') != PIN:
        raise ValueError('Wrong DAppSCAN commit')
    if git(dst, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Modified tracked DAppSCAN input')
    nodes = root / 'papers/security_evaluation/revision1/representations/run_20261025_v1/nodes_unchanged.csv'
    count = size = 0
    with nodes.open(newline='') as stream:
        for row in csv.DictReader(stream):
            if row['dataset'] != 'dappscan':
                continue
            path = root / row['path']
            if sha(path) != row['file_sha256']:
                raise ValueError(f'Source hash mismatch: {row["path"]}')
            count += 1
            size += path.stat().st_size
    pins = json.loads((root / 'papers/security_evaluation/runs/dev_fixed_t_20261025_v1/label_input_hashes.json').read_text())
    labels = {p: h for p, h in pins.items() if p.startswith('data/raw/DAppSCAN/')}
    for path, digest in labels.items():
        if sha(root / path) != digest:
            raise ValueError(f'Annotation hash mismatch: {path}')
    if (count, size, len(labels)) != (21457, 107970249, 948):
        raise ValueError('Unexpected pinned inventory')
    return {'pinned_commit': PIN, 'source_files': count, 'source_bytes': size,
            'annotation_files': len(labels), 'all_sha256_verified': True}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    dst = ROOT / 'data/raw/DAppSCAN'
    if not args.verify_only:
        if dst.exists():
            if not (dst / '.git').exists() or git(dst, 'rev-parse', 'HEAD') != PIN:
                raise ValueError('Refuse existing non-pinned checkout; use a fresh destination')
            if git(dst, 'status', '--porcelain', '--untracked-files=no'):
                raise ValueError('Refuse modified checkout')
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'init', '-q', str(dst)], check=True)
            subprocess.run(['git', '-C', str(dst), 'remote', 'add', 'origin', UPSTREAM], check=True)
            env = dict(os.environ, GIT_LFS_SKIP_SMUDGE='1')
            subprocess.run(['git', '-C', str(dst), 'fetch', '--depth', '1', '--filter=blob:none', 'origin', PIN], check=True, env=env)
            subprocess.run(['git', '-C', str(dst), 'sparse-checkout', 'init', '--cone'], check=True)
            subprocess.run(['git', '-C', str(dst), 'sparse-checkout', 'set', *SPARSE], check=True)
            subprocess.run(['git', '-C', str(dst), 'checkout', '--detach', PIN], check=True, env=env)
    result = verify(ROOT)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
