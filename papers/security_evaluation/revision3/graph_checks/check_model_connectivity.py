#!/usr/bin/env python3
"""Read-only audit of frozen membership connectivity; fits and scores are not read."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'papers/security_evaluation'
RUN = BASE / 'revision3/model_link/run_20261029_v1'
PROJECTION = BASE / 'dependency_audit/graph_scope_ablation_recovered_20261025/historical_projection.csv'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
memberships = read(RUN / 'membership_ids.json')
frames = read(RUN / 'evaluation_frames.json')
pools = read(RUN / 'pool_ids.json')
labels = read(RUN / 'labels.json')
with PROJECTION.open() as stream:
    projection = {int(r['file_id']): r for r in csv.DictReader(stream) if r['dataset'] == 'dappscan'}
giant = set(frames['giant_primary'])
B, C = set(pools['B']), set(pools['C'])
linked = B - C
assert len(giant) == 5408 and len(linked) == 471
pos = lambda ids: sum(labels[str(i)]['reentrancy'] for i in ids)
assert pos(giant) == 83 and pos(linked) == 7
rows = []
frame_rows = []
for name, ids in memberships.items():
    train = set(ids)
    assert len(ids) == len(train) == 708 and pos(train) == 24
    assert train <= B and not train & giant
    row = {'membership': name, 'training_n': len(train), 'training_positive': pos(train),
           'linked_training_n': len(train & linked), 'linked_training_positive': pos(train & linked),
           'safe_training_n': len(train & C), 'safe_training_positive': pos(train & C),
           'linked_retention': len(train & linked) / len(linked),
           'linked_fraction_of_training': len(train & linked) / len(train)}
    for tag, col in [('B', 'B_historical_legacy'), ('C', 'C_uncapped_reference_legacy')]:
        train_components = {projection[i][col] for i in train}
        connected = {i for i in giant if projection[i][col] in train_components}
        row[f'{tag}_connected_giant_n'] = len(connected)
        row[f'{tag}_connected_giant_positive'] = pos(connected)
        assert not connected if tag == 'B' else len(connected) == (5408 if train & linked else 0)
    c_train_components = {projection[j]['C_uncapped_reference_legacy'] for j in train}
    for frame, frame_ids in frames.items():
        test = set(frame_ids)
        test_components = {projection[i]['C_uncapped_reference_legacy'] for i in test}
        connected_training = {i for i in train if projection[i]['C_uncapped_reference_legacy'] in test_components}
        connected_test = {i for i in test if projection[i]['C_uncapped_reference_legacy'] in c_train_components}
        assert connected_training == train & linked
        assert len(connected_test) == (len(test) if train & linked else 0)
        frame_rows.append({'membership': name, 'frame': frame, 'test_n': len(test),
                           'test_positive': pos(test), 'C_connected_test_n': len(connected_test),
                           'C_connected_test_positive': pos(connected_test),
                           'C_connected_training_n': len(connected_training),
                           'C_connected_training_positive': pos(connected_training)})
    rows.append(row)
assert len(rows) == 71 and len(frame_rows) == 852
for filename, data in [('model_membership_connectivity.csv', rows), ('model_frame_connectivity.csv', frame_rows)]:
    with (HERE / filename).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)
counts = Counter(r['C_connected_giant_n'] for r in rows)
assert counts == {0: 1, 5408: 70}
result = {'status': 'PASS', 'created_utc': datetime.now(timezone.utc).isoformat(),
          'script_sha256': sha(Path(__file__)),
          'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [PROJECTION] + [RUN/n for n in ['membership_ids.json','evaluation_frames.json','pool_ids.json','labels.json','FREEZE_BEFORE_FITTING.json']]},
          'memberships_checked': len(rows), 'membership_frame_combinations_checked': len(frame_rows),
          'B_disjoint_all_memberships': True, 'C_disjoint_memberships': ['C_full'],
          'C_all_giant_connected_memberships': 70,
          'interpretation': 'Positive dose changes linked training exposure; all giant test files are already C-connected at every positive dose. Dose is retention of the 471 linked B-minus-C files, not fraction of connected test files and not fraction of training files.',
          'score_or_fit_files_read': 0}
(HERE / 'MODEL_CONNECTIVITY_REVIEW.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'input_sha256'}, indent=2))
