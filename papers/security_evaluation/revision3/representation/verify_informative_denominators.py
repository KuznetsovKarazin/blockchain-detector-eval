"""Recompute R5 denominator controls from immutable R4 graph memberships.

Every calculation projects existing full-graph component assignments. No vertices,
links, graphs, source representations, labels, or model outputs are changed.
"""
from __future__ import annotations
import csv
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REP = ROOT / 'papers/security_evaluation/revision1/representations/run_20261025_v1'
R4 = ROOT / 'papers/security_evaluation/revision2/representation_controls/pair_run_20261028_v1'
FLAVORS = ('normalized', 'preserved')
CASES = ('full_080', 'full_080_mask_availability_only', 'masked_080')
POLICIES = ('base', 'address_expanded')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_csv(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', newline='') as stream:
        return list(csv.DictReader(stream))

def yes(value):
    if value not in ('True', 'False'):
        raise ValueError(f'Unrecognized Boolean: {value!r}')
    return value == 'True'

def table_write(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def main():
    out = HERE / 'informative_denominator_v1'
    out.mkdir(exist_ok=False)
    inputs = [REP / 'nodes_unchanged.csv', REP / 'representation_metadata.csv',
              R4 / 'graph_controls.csv', R4 / 'memberships.csv.gz',
              R4 / 'PLAN_BEFORE_COMPUTE.json', R4 / 'RESULT.json']
    plan = {
        'schema': 'r5_fixed_informative_denominator_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_sha256': sha(Path(__file__)),
        'inputs': {str(path.relative_to(ROOT)): sha(path) for path in inputs},
        'immutable_inputs': 'R4 graph memberships and metadata; no graph recomputation',
        'all_dappscan_denominator': 21457,
        'common_informative_definition': 'DAppSCAN nodes with informative masked normalized AND masked preserved representations; assert the two flags select identical nodes',
        'common_informative_expected_denominator': 15399,
        'cases': list(CASES),
        'flavors': list(FLAVORS),
        'policies': list(POLICIES),
        'main_table_policy': 'address_expanded',
        'projection_definition': 'Find largest projected component after counting only denominator-selected nodes, retaining original full-graph paths. Also separately count selected nodes inside the all-DAppSCAN giant and verify whether it remains the same largest component.',
        'explicit_exclusion': 'Not an induced informative-node graph; unavailable nodes and their structural paths remain in the graph.',
        'no_labels_or_models': True,
    }
    (out / 'PLAN_BEFORE_COMPUTE.json').write_text(json.dumps(plan, indent=2) + '\n')
    nodes, meta, saved, members = [read_csv(path) for path in inputs[:4]]
    node_map = {int(row['node_id']): row for row in nodes}
    meta_map = {int(row['node_id']): row for row in meta}
    member_map = {int(row['node_id']): row for row in members}
    assert len(nodes) == len(node_map) == 24131
    assert set(node_map) == set(meta_map) == set(member_map)
    assert all(node_map[i]['file_sha256'] == meta_map[i]['file_sha256'] for i in node_map)
    dapp = {i for i, row in node_map.items() if row['dataset'] == 'dappscan'}
    masks = [{i for i in dapp if yes(meta_map[i][f'library_interface_masked_{flavor}_informative'])}
             for flavor in FLAVORS]
    assert masks[0] == masks[1]
    common = masks[0]
    assert len(dapp) == 21457 and len(common) == 15399
    full_sets = [{i for i in dapp if yes(meta_map[i][f'corrected_file_{flavor}_informative'])}
                 for flavor in FLAVORS]
    assert full_sets[0] == full_sets[1] and len(full_sets[0]) == 21451
    assert common <= full_sets[0]
    saved_map = {(row['flavor'], row['policy'], row['case']): row for row in saved}
    rows = []
    for flavor in FLAVORS:
        for policy in POLICIES:
            for case in CASES:
                name = f'{flavor}_{policy}_{case}'
                all_count = Counter(int(member_map[i][name]) for i in dapp)
                common_count = Counter(int(member_map[i][name]) for i in common)
                full_count = Counter(int(member_map[i][name]) for i in full_sets[0])
                all_max = max(all_count.values())
                all_giants = sorted(k for k, value in all_count.items() if value == all_max)
                assert len(all_giants) == 1
                giant = all_giants[0]
                common_max = max(common_count.values())
                common_giants = sorted(k for k, value in common_count.items() if value == common_max)
                assert common_giants == [giant]
                existing = saved_map[(flavor, policy, case)]
                assert all_max == int(existing['dapp_giant_files'])
                assert common_max == int(existing['dapp_giant_mask_informative'])
                assert all_max - common_max == int(existing['dapp_giant_mask_unavailable'])
                # Separate direct Boolean accumulation, independent of Counter grouping.
                assert common_max == sum(int(member_map[i][name]) == giant for i in common)
                assert all_max == sum(int(member_map[i][name]) == giant for i in dapp)
                rows.append({
                    'flavor': flavor, 'policy': policy, 'case': case,
                    'all_dappscan_nodes': len(dapp),
                    'largest_all_dappscan_component': all_max,
                    'all_dappscan_fraction': all_max / len(dapp),
                    'common_informative_nodes': len(common),
                    'largest_common_informative_projection': common_max,
                    'common_informative_fraction': common_max / len(common),
                    'common_unavailable_nodes': len(dapp - common),
                    'unavailable_nodes_in_all_dappscan_giant': all_max - common_max,
                    'same_unique_giant_component': True,
                    'full_file_informative_nodes': len(full_sets[0]),
                    'full_file_informative_in_giant': full_count[giant],
                })
    table_write(out / 'all_policy_denominators.csv', rows)
    main_rows = [row for row in rows if row['policy'] == 'address_expanded']
    table_write(out / 'main_table_denominators.csv', main_rows)
    table_write(out / 'common_informative_node_ids.csv', [{'node_id': i} for i in sorted(common)])
    index = {(r['flavor'], r['policy'], r['case']): r for r in rows}
    for flavor in FLAVORS:
        for case in CASES:
            for field in ['largest_all_dappscan_component', 'largest_common_informative_projection']:
                assert index[(flavor, 'base', case)][field] == index[(flavor, 'address_expanded', case)][field]
    checks = {
        'status': 'passed',
        'planned_input_hashes_unchanged': all(sha(ROOT / p) == v for p, v in plan['inputs'].items()),
        'graph_projections_checked': len(rows),
        'main_table_rows': len(main_rows),
        'common_mask_identical_across_flavors': True,
        'same_unique_giant_in_full_and_common_projections_for_every_row': True,
        'saved_R4_counts_reproduced_every_row': True,
        'independent_counter_vs_boolean_sums_every_row': True,
        'same_aggregates_base_and_address_expanded': True,
        'R4_inputs_modified': False,
        'output_sha256': {p.name: sha(p) for p in out.iterdir() if p.is_file()},
    }
    assert checks['planned_input_hashes_unchanged']
    (out / 'CHECKS.json').write_text(json.dumps(checks, indent=2) + '\n')
    for row in main_rows:
        print(f"{row['flavor']} {row['case']}: {row['largest_all_dappscan_component']}/21457={row['all_dappscan_fraction']:.8%}; {row['largest_common_informative_projection']}/15399={row['common_informative_fraction']:.8%}")

if __name__ == '__main__':
    main()
