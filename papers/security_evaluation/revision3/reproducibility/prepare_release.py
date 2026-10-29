#!/usr/bin/env python3
"""Prepare a reviewable release tree; never call remote services.

The tree starts from the exact public checkpoint. Newly authored evidence is
copied without upstream corpora, package binaries or row-level annotations.
Original local scientific files are never modified by this script.
"""
from __future__ import annotations
import argparse
import csv
import gzip
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess

BASE_COMMIT = '9dd44597d9dcb29caf31e0dbaebdcceab4185aff'
BASE = Path('papers/security_evaluation')
ROW_LABELS = {'reentrancy', 'unchecked', 'reentrancy_proxy', 'unchecked_proxy',
              'y_true', 'label', 'target'}
EDITORIAL_NAMES = {
    'REVIEW_ASSESSMENT_RU.md', 'START_HERE_RU.txt', 'build_private_package.py',
    'FINAL_R4_VERIFICATION.json', 'REVIEW_FINDINGS_RU.md', 'REVIEW_FINDINGS.md',
    'REVIEW_AND_INSERTIONS.md', 'MANUSCRIPT_INSERTIONS_EN.md', 'ENGLISH_INSERTIONS.md',
    'TABLES_FOR_R4.md', 'REPORT_RU.md', 'WORD_LINK_CHECK.json',
    'PUBLICATION_CAPABILITIES.json', 'R4_FINAL_REVIEW.json',
    'READY_INSERTIONS_EN.md', 'RESULTS_RU.md',
    'build_docx.py', 'R5_GRAPH_MANUSCRIPT_QA.md', 'R5_GRAPH_MANUSCRIPT_QA.json',
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--restored', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    repo, out = args.repo.resolve(), args.out.resolve()
    if out.exists():
        raise FileExistsError('A fresh isolated staging path is required')
    out.mkdir(parents=True)
    entries = subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-r', '-z', BASE_COMMIT])
    records, omitted, transformations = [], [], []
    existing = set()
    for entry in entries.split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, kind, blob = meta.decode().split()
        path = Path(name.decode())
        if kind != 'blob' or mode == '120000':
            raise ValueError(f'Unexpected public tree entry: {path}')
        data = subprocess.check_output(['git', '-C', str(repo), 'cat-file', 'blob', blob])
        dest = out / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        if mode == '100755':
            dest.chmod(0o755)
        existing.add(path.as_posix())
    candidates = {}
    for directory in [repo / BASE / 'revision2', repo / BASE / 'revision3',
                      repo / BASE / 'manuscript']:
        for source in directory.rglob('*'):
            if source.is_file() and not source.is_symlink():
                candidates[source.relative_to(repo).as_posix()] = source
    # The recovered original gzip files and NEW canonical NPZ have disjoint paths.
    for source in args.restored.rglob('*'):
        if source.is_file() and source.relative_to(args.restored).parts[0] == 'papers':
            candidates[source.relative_to(args.restored).as_posix()] = source
    # Previously blocked distribution consists solely of authored synthetic cases.
    publication = repo / BASE / 'revision1/recovery_20261028/publication_payload/MANIFEST.json'
    for row in json.loads(publication.read_text())['members']:
        source = repo / row['path']
        if sha(source.read_bytes()) != row['sha256']:
            raise ValueError(f'Changed authored fixture evidence: {source}')
        candidates[row['path']] = source
    engine = BASE / 'revision1/external_protocol/reporting_v1/recovered_check_20261028_v1/engine_audit_baseline_reentrancy.json'
    if (repo / engine).is_file():
        candidates[engine.as_posix()] = repo / engine
    for name, source in sorted(candidates.items()):
        parts = Path(name).parts
        if name not in existing and source.name.startswith('private_'):
            omitted.append({'path': name, 'reason': 'explicitly private editorial material', 'sha256': sha(source.read_bytes())})
            continue
        if name not in existing and 'graph_checks' in parts and any(term in source.name for term in ('MANUSCRIPT', 'RELEASE_AUDIT', 'PUBLICATION_AUDIT')):
            omitted.append({'path': name, 'reason': 'private manuscript or release-review coordination notes', 'sha256': sha(source.read_bytes())})
            continue
        if name not in existing and 'manuscript' in parts:
            manuscript_source = source.name in {'DRAFT_REVISION4.md', 'SUPPLEMENT_REVISION4.md',
                                               'DRAFT_REVISION5.md', 'SUPPLEMENT_REVISION5.md'}
            if 'revision5' in parts:
                manuscript_source = source.name in {
                    'main.tex', 'supplement.tex', 'references.bib', 'main.md', 'supplement.md',
                    'elsarticle.cls', 'elsarticle-num.bst', 'elsarticle.dtx', 'elsarticle.ins',
                    'manifest.txt', 'Makefile', 'README_SOURCE.txt', 'citation_map.json',
                    'funding_statement.txt',
                    'main.pdf', 'supplement.pdf',
                } or source.name.startswith('figure') and source.suffix in {'.pdf', '.png', '.svg'}
            manuscript_figure = any(p.startswith('figures_revision') for p in parts) and source.suffix in {'.png', '.pdf', '.svg', '.csv', '.json', '.py', '.md'}
            if not (manuscript_source or manuscript_figure):
                omitted.append({'path': name, 'reason': 'not an explicitly selected public manuscript or figure', 'sha256': sha(source.read_bytes())})
                continue
        if name not in existing and 'journal_literature' in parts and source.suffix == '.md' and not source.name.startswith('REFERENCES'):
            omitted.append({'path': name, 'reason': 'journal-planning/editorial notes', 'sha256': sha(source.read_bytes())})
            continue
        public_converter = name == (BASE / 'revision3/manuscript_notes/build_latex.py').as_posix()
        if name not in existing and (source.name in EDITORIAL_NAMES or 'manuscript_notes' in parts and not public_converter):
            omitted.append({'path': name, 'reason': 'private editorial or publication-preparation material', 'sha256': sha(source.read_bytes())})
            continue
        if '__pycache__' in parts or source.suffix in {'.pyc', '.whl', '.joblib'}:
            omitted.append({'path': name, 'reason': 'cache or third-party/runtime/model binary', 'sha256': sha(source.read_bytes())})
            continue
        if source.name == 'labels.json' or 'source_snapshot' in parts and source.suffix == '.sol':
            omitted.append({'path': name, 'reason': 'upstream source or row-level annotation; fetch and reconstruct locally', 'sha256': sha(source.read_bytes())})
            continue
        data = source.read_bytes()
        if (source.suffix == '.csv' or source.name.endswith('.csv.gz')) and name not in existing:
            compressed = source.name.endswith('.gz')
            text = (gzip.decompress(data) if compressed else data).decode('utf-8')
            reader = csv.DictReader(io.StringIO(text))
            fields = reader.fieldnames or []
            removed = [field for field in fields if field in ROW_LABELS]
            if removed:
                rows = list(reader)
                public_fields = [field for field in fields if field not in removed]
                stream = io.StringIO(newline='')
                writer = csv.DictWriter(stream, fieldnames=public_fields, lineterminator='\n', extrasaction='ignore')
                writer.writeheader()
                writer.writerows(rows)
                data = stream.getvalue().encode()
                if compressed:
                    buffer = io.BytesIO()
                    with gzip.GzipFile(filename='', mode='wb', fileobj=buffer, mtime=0) as binary:
                        binary.write(data)
                    data = buffer.getvalue()
                transformations.append({'path': name, 'original_sha256': sha(source.read_bytes()),
                                        'public_sha256': sha(data), 'removed_columns': removed,
                                        'original_columns': fields,
                                        'reason': 'Do not redistribute row-level DAppSCAN annotations'})
        destination = out / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    # Persist the explicit distinction between a public projection and originals.
    release = out / BASE / 'revision3/reproducibility'
    release.mkdir(parents=True, exist_ok=True)
    (release / 'PUBLIC_PROJECTION.json').write_text(json.dumps({
        'schema': 'article1_public_evidence_projection_v1',
        'base_public_commit': BASE_COMMIT,
        'omitted_files': omitted,
        'transformed_files': transformations,
        'original_frozen_manifests_retained': True,
        'instruction': 'Original manifests refer to original scientific bytes. Reconstruct omitted labels and transformed tables from pinned annotations before validating those original hashes.',
    }, indent=2) + '\n')
    # These overrides apply only to this article release tree/branch, not main.
    metadata = json.loads((repo / BASE / 'revision3/reproducibility/zenodo_metadata.json').read_text())
    (out / '.zenodo.json').write_text(json.dumps(metadata, indent=2) + '\n')
    shutil.copyfile(repo / BASE / 'revision3/reproducibility/CITATION.cff', out / 'CITATION.cff')
    article_readme = out / BASE / 'README.md'
    old_text = article_readme.read_text()
    article_readme.write_text(
        '# Article 1 — revision 5 reproducibility release\n\n'
        'For the current manuscript, release contents and executable reproduction commands, see '
        '[the current release guide](revision3/reproducibility/README.md). '
        'That guide supersedes the availability limitations in the dated checkpoint below. '
        'The release supplies the original recovered gzip files, separately identified canonical NPZ arrays, '
        'new graph/model evidence and local annotation reconstruction scripts. '
        'No upstream raw corpus or per-file annotation values are distributed.\n\n'
        '---\n\nHistorical checkpoint retained for provenance:\n\n' + old_text)
    root_readme = out / 'README.md'
    if root_readme.exists():
        root_readme.write_text('> **Article 1 release branch:** [Current reproducibility package and manuscript guide]'
                              '(papers/security_evaluation/revision3/reproducibility/README.md). '
                              'The broader project README below is preserved.\n\n' + root_readme.read_text())
    for path in sorted(out.rglob('*')):
        if path.is_file():
            data = path.read_bytes()
            records.append({'path': path.relative_to(out).as_posix(), 'bytes': len(data), 'sha256': sha(data)})
    manifest = {'schema': 'article1_public_release_manifest_v1',
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'base_public_commit': BASE_COMMIT,
                'status': 'prepared locally; NOT published',
                'manifest_excludes_itself': True, 'files': records}
    (out / 'ARTICLE1_RELEASE_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'staged': str(out), 'files': len(records), 'bytes': sum(r['bytes'] for r in records),
                      'omitted': len(omitted), 'transformed': len(transformations)}))

if __name__ == '__main__':
    main()
