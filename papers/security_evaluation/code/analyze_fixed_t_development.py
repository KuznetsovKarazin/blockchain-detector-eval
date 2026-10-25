"""Post-pilot floor-budget reanalysis and two-class metadata feasibility.

This script does not fit models. The pilot originally froze ceil budget rounding;
floor-budget results are an explicitly post-hoc reanalysis of unchanged scores.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixed_t_development as dev
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation_metrics import evaluate_workload


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pilot', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); os.chdir(dev.ROOT)
    if a.out.exists():
        raise FileExistsError(a.out)
    a.out.mkdir(parents=True)
    manifest = json.loads((a.pilot / 'manifest.json').read_text())
    if manifest['status'] != 'complete_development_only':
        raise ValueError('Pilot must be complete')
    for name, h in manifest['output_hashes'].items():
        assert dev.sha256(a.pilot / name) == h
    for name, h in manifest['source_snapshots'].items():
        assert dev.sha256(dev.ROOT / name) == h
    used_files = ['papers/security_evaluation/code/analyze_fixed_t_development.py',
                  'papers/security_evaluation/evaluation_metrics.py', *manifest['source_snapshots']]
    for name in used_files:
        dest = a.out / 'code_snapshot' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dev.ROOT / name, dest)
    analysis = {'schema': 'fixed_t_posthoc_metadata_and_budget_v1', 'started_utc': dev.utc(),
                'status': 'running', 'source_pilot': str(a.pilot),
                'purpose': 'Metadata-only class feasibility; post-hoc floor-budget reanalysis of existing predictions',
                'budget_amendment': 'Original pilot used ceil; floor policy was aligned after pilot scores became available. Original files unchanged.',
                'external_scores_computed': False, 'models_fitted': 0,
                'input_hashes': {'predictions.csv': dev.sha256(a.pilot / 'predictions.csv'),
                                 'memberships.csv': dev.sha256(a.pilot / 'memberships.csv')},
                'code_hashes': {n: dev.sha256(dev.ROOT / n) for n in used_files}}
    dev.dump(a.out / 'analysis_manifest.json', analysis)
    full = dev.load_population(); pop = full[full.dataset == 'dappscan']
    members = pd.read_csv(a.pilot / 'memberships.csv')
    fixed_test = pop[pop.file_id.isin(members.loc[members.role == 'test', 'file_id'])]
    historical = pd.read_parquet(dev.ROOT / dev.HISTORY / 'assignments.parquet')
    rows = []
    for cls in ('reentrancy', 'unchecked'):
        alts = [('fixed_hash20_largest_joint', fixed_test)]
        hist = historical[(historical.dataset == 'dappscan') & (historical.cls == cls) &
                          (historical.protocol == 'random') & (historical.seed == 0)]
        for fold in sorted(hist.fold.unique()):
            alts.append((f'historical_random_seed0_fold{fold}', pop[pop.file_id.isin(hist.loc[hist.fold == fold, 'file_id'])]))
        for name, test in alts:
            pools = dev.training_pools(pop, test)
            matched, counts = dev.matched_training(pools, cls, 0)
            for mode, pool in pools.items():
                rows.append({'class': cls, 'test_design': name, 'regime': mode,
                             'n_test': len(test), 'positive_proxy_test': int(test[cls].sum()),
                             'test_joint_components': int(test.joint_id.nunique()),
                             'n_pool': len(pool), 'positive_proxy_pool': int(pool[cls].sum()),
                             'matched_n': sum(counts.values()), 'matched_positive_proxy': counts[1],
                             'status': 'feasible' if matched else 'infeasible'})
    pd.DataFrame(rows).to_csv(a.out / 'class_feasibility.csv', index=False)
    preds = pd.read_csv(a.pilot / 'predictions.csv', float_precision='round_trip')
    scores, workload_rows, summaries = {}, [], []
    for mode, sub in preds.groupby('regime', sort=False):
        labels = full.set_index('file_id').loc[sub.file_id, 'reentrancy'].to_numpy()
        result = evaluate_workload(labels, sub.score.to_numpy(), label_regime='proxy',
                                   label_provenance='DAppSCAN published SWC-107 finding or no published finding')
        scores[mode] = result
        summaries.append({'regime': mode, 'ap_proxy': result['ranking_ap'],
                          'trapezoidal_pr_area_proxy': result['ranking_trapezoidal_pr_area'],
                          'coverage': result['scoring_coverage'], 'label_regime': 'proxy'})
        workload_rows.extend({'regime': mode, **r} for r in result['budgets'])
    dev.dump(a.out / 'floor_metrics.json', scores)
    pd.DataFrame(workload_rows).to_csv(a.out / 'floor_workload.csv', index=False)
    pd.DataFrame(summaries).to_csv(a.out / 'ranking_reanalysis.csv', index=False)
    old = pd.read_csv(a.pilot / 'pilot_metrics.csv').set_index('regime')
    assert all(abs(r['ap_proxy'] - old.loc[r['regime'], 'ap_proxy']) < 1e-13 for r in summaries)
    analysis.update(status='complete', finished_utc=dev.utc(),
                    output_hashes={name: dev.sha256(a.out / name) for name in
                                   ('class_feasibility.csv', 'floor_metrics.json', 'floor_workload.csv', 'ranking_reanalysis.csv')})
    dev.dump(a.out / 'analysis_manifest.json', analysis)
    print(pd.DataFrame(rows).query("test_design == 'fixed_hash20_largest_joint'").to_string(index=False))


if __name__ == '__main__':
    main()
