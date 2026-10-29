#!/usr/bin/env python3
"""Prepare small Git changes and one hash-pinned public evidence release asset.

No external writes. Previously public files stay in Git; larger new files and
all new per-fit records move into an asset restored at their original paths.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from verify_public_projection import check as check_public_projection

BASE_COMMIT = '9dd44597d9dcb29caf31e0dbaebdcceab4185aff'
VERSION = 'article1-r5-2026-10-29'
DESCRIPTOR = 'papers/security_evaluation/revision3/reproducibility/EVIDENCE_ASSET.json'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def gitblob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def inventory(tree):
    records = []
    for path in sorted(tree.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Symlink in release tree: {path}')
        if not path.is_file() or path.name == 'ARTICLE1_RELEASE_MANIFEST.json':
            continue
        relative = path.relative_to(tree)
        if relative.parts[0] in {'.git', 'data', 'reproduction'}:
            raise ValueError(f'Local/raw input in release tree: {relative}')
        data = path.read_bytes()
        records.append({'path': relative.as_posix(), 'bytes': len(data), 'sha256': sha(data)})
    return records

def main():
    ap = argparse.ArgumentParser()
    for name in ['tree', 'repo', 'transport', 'receipts', 'asset']:
        ap.add_argument('--' + name, type=Path, required=True)
    args = ap.parse_args()
    tree, transport = args.tree.resolve(), args.transport.resolve()
    if transport.exists() or args.asset.exists():
        raise FileExistsError('Fresh transport and asset destinations required')
    public_projection_check = check_public_projection(tree)
    run = tree / 'papers/security_evaluation/revision3/model_link/run_20261029_v1'
    for name in ['COMPLETE.json', 'ANALYSIS_COMPLETE.json']:
        if not (run / name).is_file():
            raise ValueError(f'R5 incomplete: {name}')
    complete = json.loads((run / 'COMPLETE.json').read_text())
    if complete['physical_fits_attempted'] != 852 or complete['failed']:
        raise ValueError('Complete disclosed R5 results required')
    base = {}
    raw = subprocess.check_output(['git', '-C', str(args.repo), 'ls-tree', '-r', '-z', BASE_COMMIT])
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, kind, blob = meta.decode().split()
        base[name.decode()] = {'mode': mode, 'type': kind, 'sha': blob}
    records = inventory(tree)
    payload = [r for r in records if r['path'] not in base and
               (r['bytes'] > 128 * 1024 or 'fits' in Path(r['path']).parts or
                Path(r['path']).suffix in {'.gz', '.npz', '.zip'})]
    payload_names = {r['path'] for r in payload}
    inner = {'schema': 'article1_public_evidence_asset_v1', 'version': VERSION,
             'raw_third_party_corpora_or_restricted_annotations_included': False, 'files': payload}
    args.asset.parent.mkdir(parents=True, exist_ok=True)
    inner_bytes = (json.dumps(inner, indent=2) + '\n').encode()
    with zipfile.ZipFile(args.asset, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for row in payload:
            z.write(tree / row['path'], arcname=row['path'])
        z.writestr('EVIDENCE_CONTENTS.json', inner_bytes)
    with zipfile.ZipFile(args.asset) as z:
        assert z.testzip() is None and len(z.namelist()) == len(payload) + 1
        for row in payload:
            data = z.read(row['path'])
            assert len(data) == row['bytes'] and sha(data) == row['sha256']
    descriptor = {'schema': 'article1_versioned_public_evidence_asset_v1', 'version': VERSION,
                  'archive_name': args.asset.name, 'archive_bytes': args.asset.stat().st_size,
                  'archive_sha256': sha(args.asset.read_bytes()),
                  'download_url': f'https://github.com/KuznetsovKarazin/blockchain-detector-eval/releases/download/{VERSION}/{args.asset.name}',
                  'restore_instruction': 'Run fetch_release_evidence.py before verify_release_manifest.py and scientific replay commands.',
                  'inventory_sha256': sha(inner_bytes), 'files_count': len(payload),
                  'expanded_bytes': sum(r['bytes'] for r in payload)}
    (tree / DESCRIPTOR).write_text(json.dumps(descriptor, indent=2) + '\n')
    records = inventory(tree)
    manifest_parts = []
    groups, group = [], []
    for row in records:
        if group and len(json.dumps(group + [row], indent=2).encode()) > 96 * 1024:
            groups.append(group)
            group = []
        group.append(row)
    if group:
        groups.append(group)
    for index, group in enumerate(groups):
        name = f'papers/security_evaluation/revision3/reproducibility/manifest_parts/part{index:03d}.json'
        path = tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(group, indent=2) + '\n').encode()
        path.write_bytes(data)
        manifest_parts.append({'path': name, 'bytes': len(data), 'sha256': sha(data), 'files': len(group)})
    manifest = {'schema': 'article1_public_release_manifest_v2',
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'base_public_commit': BASE_COMMIT, 'version': VERSION,
                'distribution': 'Git plus hash-pinned release evidence asset restored at original relative paths',
                'evidence_asset_sha256': descriptor['archive_sha256'],
                'manifest_excludes_itself_and_its_indexed_parts': True,
                'file_count': len(records), 'file_bytes': sum(r['bytes'] for r in records),
                'manifest_parts': manifest_parts}
    manifest_path = tree / 'ARTICLE1_RELEASE_MANIFEST.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    transport.mkdir(parents=True)
    all_paths = [r['path'] for r in records] + [r['path'] for r in manifest_parts] + [manifest_path.name]
    git_paths = set(all_paths) - payload_names
    for name in git_paths:
        destination = transport / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tree / name, destination)
    if set(base) - git_paths:
        raise ValueError('Unexpected removal of a previously public file')
    changes = []
    for name in sorted(git_paths):
        path = transport / name
        data = path.read_bytes()
        blob = gitblob(data)
        mode = '100755' if path.stat().st_mode & 0o111 else '100644'
        if name not in base or blob != base[name]['sha'] or mode != base[name]['mode']:
            changes.append({'path': name, 'mode': mode, 'type': 'blob', 'sha': blob,
                            'bytes': len(data), 'sha256': sha(data)})
    args.receipts.mkdir(parents=True, exist_ok=True)
    plan = {'schema': 'article1_exact_git_publication_plan_v1',
            'repository': 'KuznetsovKarazin/blockchain-detector-eval',
            'branch': 'paper/security-evaluation', 'expected_parent_sha': BASE_COMMIT,
            'base_tree_sha': subprocess.check_output(['git', '-C', str(args.repo), 'rev-parse', BASE_COMMIT + '^{tree}'], text=True).strip(),
            'tag_proposal': VERSION, 'mark_latest_general_project_release': False,
            'tree_directory': str(transport), 'manifest_sha256': sha(manifest_path.read_bytes()),
            'commit_message': 'Release Article 1 revision 5 reproducibility evidence and portable checks',
            'new_or_changed_files': changes, 'deletions': [],
            'release_asset': {k: v for k, v in descriptor.items() if k != 'files'},
            'remote_writes_performed': False}
    (args.receipts / 'PUBLICATION_PLAN.json').write_text(json.dumps(plan, indent=2) + '\n')
    receipt = {'status': 'pass', 'full_restored_files': len(all_paths),
               'public_projection_check': public_projection_check,
               'new_or_changed_git_files': len(changes), 'new_or_changed_git_bytes': sum(x['bytes'] for x in changes),
               'largest_git_change_bytes': max(x['bytes'] for x in changes),
               'evidence_asset_files': len(payload), 'evidence_asset_expanded_bytes': sum(r['bytes'] for r in payload),
               'manifest_sha256': plan['manifest_sha256'], 'asset': str(args.asset),
               'asset_bytes': descriptor['archive_bytes'], 'asset_sha256': descriptor['archive_sha256'],
               'every_asset_member_crc_size_sha256_verified': True, 'remote_writes': False}
    (args.receipts / 'PACKAGE_VERIFICATION.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
