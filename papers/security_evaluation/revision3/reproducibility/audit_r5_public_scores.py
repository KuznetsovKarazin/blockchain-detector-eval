#!/usr/bin/env python3
"""Independent rational metric replay of R5; no sklearn or model fitting.

Requires labels locally reconstructed from pinned upstream annotations. Checks
all planned score vectors and all primary/nested frame AP and review counts.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rows(path):
    opener = gzip.open if path.name.endswith('.gz') else open
    with opener(path, 'rt', newline='') as stream:
        return list(csv.DictReader(stream))

def calculate(ids, scores, labels):
    groups = {}
    positive = 0
    for i in ids:
        score = scores[i]
        n, k = groups.get(score, (0, 0))
        y = labels[i]['reentrancy']
        positive += y
        groups[score] = n + 1, k + y
    if not positive:
        raise ValueError('Undefined AP requires an explicit separate report')
    budgets = {f: len(ids) * f // 100 for f in (5, 10, 20)}
    yields = {f: Fraction(0) for f in budgets}
    minimum = dict.fromkeys(budgets, 0)
    maximum = dict.fromkeys(budgets, 0)
    ap = Fraction(0)
    seen = tp = 0
    for score in sorted(groups, reverse=True):
        n, k = groups[score]
        for f, budget in budgets.items():
            slots = max(0, min(n, budget - seen))
            yields[f] += Fraction(k * slots, n)
            minimum[f] += max(0, slots - (n - k))
            maximum[f] += min(slots, k)
        seen += n
        tp += k
        if k:
            ap += Fraction(k * tp, positive * seen)
    result = {'ap': float(ap)}
    for f in budgets:
        result.update({f'budget_{f}': budgets[f], f'findings_{f}': float(yields[f]),
                       f'findings_min_{f}': minimum[f], f'findings_max_{f}': maximum[f],
                       f'precision_{f}': float(yields[f] / budgets[f]),
                       f'recall_{f}': float(yields[f] / positive)})
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError('Use a new audit receipt')
    started = time.perf_counter()
    run = args.run.resolve()
    complete = json.loads((run / 'COMPLETE.json').read_text())
    analysis = json.loads((run / 'ANALYSIS_COMPLETE.json').read_text())
    freeze = json.loads((run / 'FREEZE_BEFORE_FITTING.json').read_text())
    plan = json.loads((run / 'PLAN_BEFORE_FITTING.json').read_text())
    assert complete['physical_fits_attempted'] == 852 and complete['failed'] == 0
    assert sha(run / 'FREEZE_BEFORE_FITTING.json') == complete['freeze_sha256']
    assert sha(run / 'COMPLETE.json') == analysis['complete_sha256']
    for path, expected in freeze['prepared_files'].items():
        assert sha(run / path) == expected, path
    for path, expected in freeze['source_hashes'].items():
        assert sha(run / 'code_snapshot' / path) == expected, path
    for path, expected in analysis['outputs'].items():
        assert sha(run / 'analysis' / path) == expected, path
    labels = {int(k): v for k, v in json.loads((run / 'labels.json').read_text()).items()}
    frames = json.loads((run / 'evaluation_frames.json').read_text())
    memberships = json.loads((run / 'membership_ids.json').read_text())
    primary = frames['giant_primary']
    assert len(primary) == 5408 and sum(labels[i]['reentrancy'] for i in primary) == 83
    reported = rows(run / 'analysis/per_fit_frame_metrics.csv.gz')
    reference = {(r['job_id'], r['frame']): r for r in reported}
    assert len(reference) == len(reported) == 852 * len(frames)
    maximum_error = 0.0
    checked = values = artifact_hashes = 0
    warnings = Counter()
    convergence = 0
    for job in plan['jobs']:
        jid = job['job_id']
        folder = run / 'fits' / jid
        assert sha(folder / 'result.json') == complete['result_hashes'][jid]
        result = json.loads((folder / 'result.json').read_text())
        assert result['status'] == 'ok'
        for path, expected in result['artifact_hashes'].items():
            assert sha(folder / path) == expected, (jid, path)
            artifact_hashes += 1
        pred = rows(folder / 'predictions.csv.gz')
        assert [int(r['file_id']) for r in pred] == primary
        assert all(r['status'] == 'ok' and math.isfinite(float(r['score'])) for r in pred)
        scores = {int(r['file_id']): float(r['score']) for r in pred}
        train = memberships[job['membership']]
        assert len(train) == 708 and sum(labels[i]['reentrancy'] for i in train) == 24
        assert not set(train) & set(primary)
        for frame, ids in frames.items():
            calculated = calculate(ids, scores, labels)
            saved = reference[(jid, frame)]
            for field, value in calculated.items():
                error = abs(value - float(saved[field]))
                if error > 1e-12:
                    raise ValueError((jid, frame, field, value, saved[field], error))
                maximum_error = max(maximum_error, error)
                values += 1
            checked += 1
        resource = json.loads((folder / 'resources.json').read_text())
        warnings.update(resource['warnings'])
        convergence += bool(resource['convergence_warning'])
    receipt = {'schema': 'article1_r5_independent_public_score_replay_v1', 'status': 'pass',
               'script_sha256': sha(Path(__file__)), 'complete_sha256': sha(run / 'COMPLETE.json'),
               'analysis_complete_sha256': sha(run / 'ANALYSIS_COMPLETE.json'),
               'physical_prediction_vectors': len(plan['jobs']), 'primary_prediction_values': len(plan['jobs']) * len(primary),
               'evaluation_frames': len(frames), 'AP_frame_cells': checked,
               'numeric_values_checked': values, 'artifact_hashes_checked': artifact_hashes,
               'maximum_absolute_difference': maximum_error,
               'metric_method': 'Fraction arithmetic on independently grouped equal-score values. AP, expected yields, min/max tie yields, precision and recall. No sklearn or producer metric function called.',
               'warnings': dict(warnings), 'convergence_warning_fits': convergence,
               'seconds': time.perf_counter() - started, 'new_model_fits': 0,
               'scope': 'Conditional historical-population reproduction; nested frames are not independent families.'}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
