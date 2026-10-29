#!/usr/bin/env python3
"""Replay immutable graph programs into fresh output folders and compare tables.

No frozen source is edited. Only each imported program's output directory is
redirected; the new plan records the actual original source bytes and inputs.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'papers/security_evaluation'
SCENARIOS = {
    'labelblind': ('revision2/graph_mechanics/analyze_mechanics.py', 'run_20261028_v1',
                  ['all_test_feasibility.csv', 'eligibility_loss_decomposition.csv',
                   'labelblind_test_memberships.csv', 'outside_population_witness_summary.csv']),
    'project-prefix': ('revision2/graph_mechanics/project_coverage.py', 'project_coverage_20261028_v1',
                       ['whole_project_curves.csv', 'whole_project_rankings.csv', 'file_vs_project_sampling.csv']),
    'metadata': ('revision2/representation_controls/run_metadata_controls.py', 'metadata_run_20261028_v1',
                 ['ordered_equality_concentration.csv', 'masking_coverage_decomposition.csv', 'ordered_equality_memberships.csv.gz']),
    'pairs': ('revision2/representation_controls/run_pair_controls.py', 'pair_run_20261028_v1',
              ['graph_controls.csv', 'mask_edge_changes.csv', 'memberships.csv.gz']),
    'equality': ('revision2/representation_controls/run_trivia_control.py', 'trivia_run_20261028_v1',
                 ['source_verified_canonical_hashes.csv', 'exact_equality_concentration.csv', 'memberships.csv.gz']),
    'informative-denominators': ('revision3/representation/verify_informative_denominators.py', 'informative_denominator_v1',
                                ['all_policy_denominators.csv', 'main_table_denominators.csv', 'common_informative_node_ids.csv']),
    'structural-baselines': ('revision3/representation/verify_structural_baselines.py', 'structural_baselines_v1',
                            ['structural_denominators.csv']),
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('scenario', choices=SCENARIOS)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError('Choose a fresh output folder')
    # Some original programs record source paths relative to the repo.
    out.relative_to(ROOT)
    out.mkdir(parents=True)
    relative, child, tables = SCENARIOS[args.scenario]
    source = BASE / relative
    original = source.parent / child
    sys.path.insert(0, str(source.parent))
    spec = importlib.util.spec_from_file_location('article1_replay_program', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_hash = sha(source)
    if args.scenario in {'labelblind', 'project-prefix'}:
        module.OUT = out
        module.plan()
        module.run()
    else:
        module.HERE = out
        if args.scenario == 'equality':
            for name in ['trivia_only.py', 'test_trivia_only.py']:
                shutil.copyfile(source.parent / name, out / name)
        old_argv = sys.argv
        try:
            sys.argv = [str(source)] + (['--archive-root', str(ROOT)] if args.scenario == 'pairs' else [])
            module.main()
        finally:
            sys.argv = old_argv
    import pandas as pd
    checked = []
    for name in tables:
        expected = pd.read_csv(original / name, keep_default_na=False)
        actual = pd.read_csv(out / child / name, keep_default_na=False)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-12, atol=1e-12)
        checked.append({'table': name, 'rows': len(actual), 'columns': len(actual.columns),
                        'saved_sha256': sha(original / name), 'replayed_sha256': sha(out / child / name)})
    assert sha(source) == original_hash
    result = {'schema': 'article1_portable_graph_replay_v1', 'scenario': args.scenario,
              'status': 'pass', 'finished_utc': datetime.now(timezone.utc).isoformat(),
              'scientific_source_sha256': original_hash, 'scientific_source_changed': False,
              'comparison': 'All cells, row order and columns; numeric tolerance 1e-12. Compressed gzip byte identity is not required because gzip embeds timestamps.',
              'tables': checked, 'new_model_fits': 0}
    (out / 'REPLAY_CHECK.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
