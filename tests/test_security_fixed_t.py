"""Validity tests for full transitive exclusion, matching, and tied workload."""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

PATH = Path(__file__).resolve().parents[1] / 'papers/security_evaluation/code/fixed_t_development.py'
spec = importlib.util.spec_from_file_location('fixed_t_development', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    # A--clone1--B--clone2--C; C must be excluded from joint T=A despite
    # neither its direct project nor its clone matching T's file.
    d = pd.DataFrame({'file_id': range(8), 'path': [f'{i}.sol' for i in range(8)],
                      'group': ['A', 'B', 'B', 'C', 'D', 'D', 'E', 'E'],
                      'comp': [1, 1, 2, 2, 3, 4, 5, 6],
                      'reentrancy': [1, 1, 0, 0, 1, 0, 1, 0]})
    d['joint_id'] = m.joint_groups(d)
    return d


def test_transitive_joint_exclusion_is_stronger_than_direct_neighbors():
    d = fixture(); t = d.iloc[[0]]; p = m.training_pools(d, t)
    assert 3 in p['project_disjoint'].file_id.to_list()
    assert 3 in p['clone_disjoint'].file_id.to_list()
    assert set(p['joint_project_clone_disjoint'].file_id) == {4, 5, 6, 7}
    assert all(0 not in x.file_id.to_list() for x in p.values())


def test_matching_preserves_exact_counts_and_joint_exclusion():
    d = fixture(); t = d.iloc[[0]]
    matched, counts = m.matched_training(m.training_pools(d, t), 'reentrancy', 0)
    assert counts == {0: 2, 1: 2}
    assert all(len(p) == 4 and p.reentrancy.sum() == 2 for p in matched.values())
    assert not set(matched['joint_project_clone_disjoint'].joint_id) & set(t.joint_id)


def test_infeasible_no_positive_is_not_silently_relaxed():
    d = fixture(); d.loc[d.file_id >= 4, 'reentrancy'] = 0
    matched, counts = m.matched_training(m.training_pools(d, d.iloc[[0]]), 'reentrancy', 0)
    assert matched == {} and counts[1] == 0


def test_hash_selection_does_not_depend_on_labels_or_row_order():
    d = fixture(); expected = m.hash_order(d.path.tolist(), m.SELECTION_SALT)
    d.reentrancy = 1 - d.reentrancy
    assert m.hash_order(d.sample(frac=1, random_state=33).path.tolist(), m.SELECTION_SALT) == expected


def test_tie_expectation_and_range_are_permutation_invariant():
    y = np.array([1, 0, 1, 0]); s = np.ones(4)
    result = m.workload(y, s, .5)
    assert result['tp_expected'] == 1 and result['tp_min'] == 0 and result['tp_max'] == 2
    assert result['precision_expected'] == .5 and result['recall_expected'] == .5
    assert m.workload(y[::-1], s, .5) == result


def test_partition_equivalence_and_bridge_detection():
    assert m.check_partition_equivalence(['A', 'A', 'B'], [0, 0, 1])
    assert not m.check_partition_equivalence(['A', 'A', 'B'], [0, 1, 1])
