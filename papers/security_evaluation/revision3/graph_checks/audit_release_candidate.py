#!/usr/bin/env python3
"""Read-only release content/lineage audit. Does not evaluate model scores."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, csv, gzip, hashlib, json, subprocess

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tree', type=Path, required=True)
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    tree = args.tree.resolve()
    base = tree / 'papers/security_evaluation'
    rel = base / 'revision3/reproducibility'
    index_path = tree / 'ARTICLE1_RELEASE_MANIFEST.json'
    index = json.loads(index_path.read_text())
    manifest = []
    for part in index['manifest_parts']:
        path = tree / part['path']
        assert path.stat().st_size == part['bytes'] and sha(path) == part['sha256']
        records = json.loads(path.read_text()); assert len(records) == part['files']
        manifest.extend(records)
    assert len(manifest) == index['file_count']
    discrepancies = []
    for row in manifest:
        path = tree / row['path']
        if not path.is_file():
            discrepancies.append({'path': row['path'], 'issue': 'missing'}); continue
        actual = sha(path)
        if actual != row['sha256'] or path.stat().st_size != row['bytes']:
            discrepancies.append({'path': row['path'], 'issue': 'manifest byte mismatch',
                                  'expected_sha256': row['sha256'], 'actual_sha256': actual,
                                  'actual_bytes': path.stat().st_size})
    projection = json.loads((rel / 'PUBLIC_PROJECTION.json').read_text())
    transformed = []
    for row in projection['transformed_files']:
        path = tree / row['path']
        actual = sha(path)
        transformed.append({'path': row['path'], 'matches_public_projection': actual == row['public_sha256'],
                            'actual_sha256': actual, 'expected_public_sha256': row['public_sha256'],
                            'matches_restricted_original': actual == row['original_sha256']})
    old = set(subprocess.check_output(['git', '-C', str(args.repo), 'ls-tree', '-r', '--name-only', index['base_public_commit']], text=True).splitlines())
    forbidden_headers = {'reentrancy','unchecked','reentrancy_proxy','unchecked_proxy','y_true','label','target'}
    csv_issues, new_sources, omitted_present, editorial_present = [], [], [], []
    for row in projection['omitted_files']:
        if row['path'].endswith('/labels.json') and (tree / row['path']).exists(): omitted_present.append(row['path'])
    for path in tree.rglob('*'):
        if not path.is_file(): continue
        name = path.relative_to(tree).as_posix()
        if name in old: continue
        if path.suffix == '.sol' or name.startswith('data/raw/'): new_sources.append(name)
        if 'graph_checks' in path.parts and 'MANUSCRIPT' in path.name.upper(): editorial_present.append(name)
        if path.suffix == '.csv' or path.name.endswith('.csv.gz'):
            opener = gzip.open if path.name.endswith('.gz') else open
            with opener(path, 'rt', newline='') as stream: fields = next(csv.reader(stream), [])
            restricted = sorted(forbidden_headers & set(fields))
            if restricted: csv_issues.append({'path': name, 'columns': restricted})
    lineage = json.loads((rel / 'GRAPH_LINEAGE.json').read_text())
    original = lineage['original_gzip_files']; canonical = lineage['new_canonical_npz']; lost = lineage['lost_original_npz']
    assert len(original) == 23 and len(canonical) == 6 and len(lost) == 6
    for row in original:
        data = (tree / row['path']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['sha256']
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == row['git_blob_sha1']
    for row in canonical:
        assert sha(tree / row['path']) == row['sha256']
        assert row['original_full_unordered_edge_identity_established'] is False
    assert not any((tree / row['path']).exists() for row in lost)
    # Check every explicit frozen graph input; private recovery-root prefixes are
    # mapped only to their declared original repository-relative archive paths.
    plans = [base/'revision2/graph_mechanics/PLAN_BEFORE_COMPUTATION.json',
             base/'revision2/graph_mechanics/PROJECT_COVERAGE_PLAN_BEFORE_COMPUTATION.json']
    plans += sorted((base/'revision2/representation_controls').glob('*/PLAN_BEFORE_COMPUTE.json'))
    plans += sorted((base/'revision3/representation').glob('*/PLAN_BEFORE_COMPUTE.json'))
    input_checks, raw_inputs, input_issues = [], [], []
    for plan_path in plans:
        plan = json.loads(plan_path.read_text())
        for name, digest in plan.get('inputs', {}).items():
            if name.startswith('data/raw/'):
                raw_inputs.append(name); continue
            name = name[name.index('papers/security_evaluation/'):] if 'papers/security_evaluation/' in name else name
            p = tree / name
            if not p.is_file(): input_issues.append({'plan': str(plan_path.relative_to(tree)), 'path': name, 'issue': 'missing'}); continue
            actual = sha(p)
            if actual != digest: input_issues.append({'plan': str(plan_path.relative_to(tree)), 'path': name, 'issue': 'input hash mismatch'})
            input_checks.append(name)
    blockers = bool(discrepancies or csv_issues or omitted_present or new_sources or editorial_present or input_issues)
    result = {'status': 'BLOCKED' if blockers else 'PASS', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'candidate_tree': str(tree), 'release_index_sha256': sha(index_path),
              'manifest_parts_checked': len(index['manifest_parts']), 'manifest_files_checked': len(manifest),
              'manifest_discrepancies': discrepancies, 'public_projection_checks': transformed,
              'new_per_file_annotation_columns': csv_issues, 'omitted_label_json_present': omitted_present,
              'new_raw_source_files': new_sources, 'private_editorial_files_present': editorial_present,
              'original_gzip_hash_and_git_blob_checks': len(original), 'canonical_npz_hash_checks': len(canonical),
              'lost_original_npz_paths_remain_absent': len(lost),
              'graph_plans_checked': len(plans), 'graph_input_occurrences_checked': len(input_checks),
              'graph_input_issues': input_issues, 'raw_input_occurrences_correctly_external': len(raw_inputs),
              'scope': 'Content/dependency/lineage inspection only; no model metric recalculation, model fitting, source download, publication or candidate writes.'}
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status','manifest_files_checked','manifest_discrepancies','new_per_file_annotation_columns','private_editorial_files_present','graph_input_issues','original_gzip_hash_and_git_blob_checks','canonical_npz_hash_checks']}, indent=2))

if __name__ == '__main__': main()
