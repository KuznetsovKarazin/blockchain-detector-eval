"""Reproducible development-only fixed-test comparison using historical C2 groups.

No external data are scored. DAppSCAN y=0 means no published finding, not safe.
The historical clone partition is held fixed; its LSH candidate recall is not
certified. The full 7080-object project/clone graph is retained before restriction.

python papers/security_evaluation/code/fixed_t_development.py prepare --out RUN
python papers/security_evaluation/code/fixed_t_development.py run --out RUN
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from bal.data.contracts import load_all, label_files
from bal.features.contract_features import raw_text, strip_comments

MODES = ('other_files_unrestricted', 'project_disjoint', 'clone_disjoint',
         'joint_project_clone_disjoint')
HISTORY = 'results/contracts/c2_20261024_004314'
SOURCE_FILES = ('papers/security_evaluation/code/fixed_t_development.py',
                'src/bal/data/contracts.py', 'src/bal/features/contract_features.py')
SELECTION_SALT = 'security-fixed-t-development-v1'


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def hash_order(paths, salt):
    return sorted(paths, key=lambda x: (hashlib.sha256((salt + '|' + x).encode()).hexdigest(), x))


def joint_groups(frame):
    """Full transitive bipartite union; do not call on a restricted cohort."""
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for g, c in zip(frame.group, frame.comp):
        a, b = find(('project', str(g))), find(('clone', str(c)))
        if a != b:
            parent[b] = a
    roots = [find(('project', str(x))) for x in frame.group]
    # Stable public names from the minimum source path of each component.
    minima = {}
    for p, r in zip(frame.path, roots):
        minima[r] = min(p, minima.get(r, p))
    return pd.Series(['joint:' + hashlib.sha256(minima[r].encode()).hexdigest()[:20]
                      for r in roots], index=frame.index)


def check_partition_equivalence(a, b):
    d = pd.DataFrame({'a': np.asarray(a), 'b': np.asarray(b)})
    return bool((d.groupby('a').b.nunique() == 1).all() and
                (d.groupby('b').a.nunique() == 1).all())


def training_pools(population, test):
    """Regime exclusions on original full-population grouping metadata."""
    other = population[~population.file_id.isin(test.file_id)]
    pools = {
        MODES[0]: other,
        MODES[1]: other[~other.group.isin(test.group)],
        MODES[2]: other[~other.comp.isin(test.comp)],
        MODES[3]: other[~other.joint_id.isin(test.joint_id)],
    }
    assert not any(set(p.file_id) & set(test.file_id) for p in pools.values())
    assert not set(pools[MODES[3]].joint_id) & set(test.joint_id)
    return pools


def matched_training(pools, cls, seed):
    """Exact class-count matching; class labels here are declared proxy labels."""
    counts = {label: min(int((p[cls] == label).sum()) for p in pools.values())
              for label in (0, 1)}
    if min(counts.values()) == 0:
        return {}, counts
    out = {}
    for mode, pool in pools.items():
        selected = []
        for label, n in counts.items():
            rank = hash_order(pool.loc[pool[cls] == label, 'path'].tolist(),
                              f'{SELECTION_SALT}|train|{seed}|{cls}|{label}')
            selected.extend(rank[:n])
        out[mode] = pool[pool.path.isin(selected)].sort_values('file_id').copy()
    assert len({len(p) for p in out.values()}) == 1
    assert len({int(p[cls].sum()) for p in out.values()}) == 1
    return out, counts


def workload(y, score, fraction):
    """Expected TP and attainable range under uniform permutation at a tie."""
    y, score = np.asarray(y), np.asarray(score)
    n = len(y)
    k = min(n, max(1, math.ceil(fraction * n)))
    cutoff = np.sort(score)[-k]
    above, tie = score > cutoff, score == cutoff
    slots = k - int(above.sum())
    tie_pos = int(y[tie].sum())
    tie_n = int(tie.sum())
    base = int(y[above].sum())
    expected = base + slots * tie_pos / tie_n
    low = base + max(0, slots - (tie_n - tie_pos))
    high = base + min(slots, tie_pos)
    total_pos = int(y.sum())
    return {'review_fraction': fraction, 'k': k, 'tp_expected': expected,
            'tp_min': low, 'tp_max': high, 'precision_expected': expected / k,
            'recall_expected': expected / total_pos if total_pos else None,
            'tie_size': tie_n, 'slots_from_tie': slots}


def load_population():
    full = load_all().reset_index(drop=True)
    hist = pd.read_parquet(ROOT / HISTORY / 'groups.parquet')
    full['file_id'] = np.arange(len(full))
    for field in ('file_id', 'dataset', 'path', 'group'):
        if not np.array_equal(full[field].to_numpy(), hist[field].to_numpy()):
            raise ValueError(f'Current pinned loader differs from historical groups in {field}')
    full['comp'] = hist.comp.to_numpy()
    full['safe_group'] = hist.safe_group.to_numpy()
    full['joint_id'] = joint_groups(full)
    if not check_partition_equivalence(full.joint_id, full.safe_group):
        raise ValueError('Reconstructed full transitive graph differs from saved safe groups')
    return full


def composition(frame, mode):
    import re
    rows = []
    clean = frame.source.map(strip_comments)
    lengths = clean.map(lambda x: sum(bool(line.strip()) for line in x.splitlines()))
    pragma = clean.map(lambda x: ';'.join(re.findall(r'pragma\s+solidity\s+([^;]+)', x)) or 'missing')
    # These are screen flags, never asserted library provenance or compiler resolution.
    lib = clean.str.contains(r'\blibrary\s+[A-Za-z_]', regex=True)
    path_lib = frame.path.str.contains(r'(?i)(openzeppelin|safemath|/lib/|/libraries/)', regex=True)
    base = {'population': mode, 'n': len(frame), 'projects': int(frame.group.nunique()),
            'clone_components': int(frame.comp.nunique()), 'joint_components': int(frame.joint_id.nunique()),
            'nonempty_lines_median': float(lengths.median()) if len(frame) else None,
            'nonempty_lines_q25': float(lengths.quantile(.25)) if len(frame) else None,
            'nonempty_lines_q75': float(lengths.quantile(.75)) if len(frame) else None,
            'library_declaration_screen_n': int(lib.sum()), 'library_path_screen_n': int(path_lib.sum()),
            'library_origin_status': 'unverified_screen_only',
            'any_swc_annotation_n': int((frame.sb_category == 'labelled').sum())}
    rows.append(base)
    return base, [{'population': mode, 'compiler_range_literal': k, 'n': int(v)}
                  for k, v in pragma.value_counts().items()]


def prepare(out):
    if out.exists():
        raise FileExistsError(f'Refusing to overwrite run directory {out}')
    out.mkdir(parents=True)
    started = utc()
    config = {
        'schema': 'security_fixed_t_development_v1', 'status': 'development_only_not_confirmatory',
        'created_utc': started, 'class': 'reentrancy', 'seed': 0,
        'source_population': 'All historical C2 7080 rows for graph; DAppSCAN 6587 rows for training/test',
        'clone_partition': f'{HISTORY}/groups.parquet; normalized-token LSH candidates + verified Jaccard >=0.8',
        'joint_partition': 'full transitive project union clone graph before all restrictions',
        'test_selection': {'population': 'largest DAppSCAN joint component; size descending then joint ID',
                           'fraction': .2, 'rounding': 'ceil', 'ranking': 'sha256(salt + "|" + path), then path',
                           'salt': SELECTION_SALT, 'uses_labels_or_scores': False},
        'training': {'regimes': list(MODES), 'count_matching': 'minimum per binary proxy label over all four pools',
                     'ranking': 'shared deterministic SHA256 path rank within proxy class; seed=0',
                     'infeasible_rule': 'any matched class count zero; do not relax components',
                     'tuning_budget': 0},
        'representation': {'type': 'raw_text from historical contract_features.py',
                           'tfidf': {'token_pattern': r'\S+', 'ngram_range': [1, 3], 'min_df': 2,
                                     'max_features': 50000, 'sublinear_tf': True, 'lowercase': False},
                           'scaler': 'StandardScaler(with_mean=False), fit on training only'},
        'model': {'type': 'LogisticRegression', 'C': 1., 'max_iter': 3000,
                  'class_weight': 'balanced', 'random_state': 0, 'solver': 'lbfgs', 'tol': 1e-4},
        'metrics': {'ap': 'sklearn.average_precision_score', 'budgets': [.05, .1, .2],
                    'budget_rounding': 'ceil(fraction * all test files)',
                    'ties': 'uniform permutation within exact-score boundary tie; expectation and attainable TP range',
                    'label_semantics': 'DAppSCAN proxy finding vs no published finding; not verified vulnerabilities/negatives'},
        'uncertainty': 'No confidence interval: selected test lies in one joint component',
        'external_scoring': False, 'repeat_stopping': 'one seed, one class, all four regimes; no score-based selection',
    }
    dump(out / 'pilot_config.json', config)
    config_hash = sha256(out / 'pilot_config.json')
    snapshot = out / 'code_snapshot'
    for name in SOURCE_FILES:
        dest = snapshot / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
    full = load_population()
    pop = full[full.dataset == 'dappscan'].copy()
    biggest = pop.groupby('joint_id').size().sort_values(ascending=False, kind='stable').index[0]
    component = pop[pop.joint_id == biggest]
    ranked = hash_order(component.path.tolist(), SELECTION_SALT)
    chosen = ranked[:math.ceil(len(ranked) * .2)]
    test = pop[pop.path.isin(chosen)].sort_values('file_id')
    pools = training_pools(pop, test)
    matched, counts = matched_training(pools, config['class'], config['seed'])
    if not matched:
        dump(out / 'manifest.json', {'status': 'infeasible', 'created_utc': started, 'config_sha256': config_hash,
                                    'matched_counts': counts, 'external_scores_computed': False})
        return
    # File hashes and partitions are original metadata, no third-party labels/source.
    pubcols = ['file_id', 'dataset', 'path', 'group', 'comp', 'joint_id']
    inventory = full[pubcols].copy()
    inventory['file_sha256'] = [sha256(ROOT / p) for p in inventory.path]
    inventory.to_csv(out / 'source_inventory.csv', index=False)
    membership = [test[pubcols].assign(role='test', regime='common_test')]
    for mode, train in matched.items():
        membership.append(train[pubcols].assign(role='train', regime=mode))
    pd.concat(membership, ignore_index=True).to_csv(out / 'memberships.csv', index=False)
    feasibility = []
    alternatives = [('fixed_hash20_largest_joint', test), ('whole_largest_joint', component)]
    assignments = pd.read_parquet(ROOT / HISTORY / 'assignments.parquet')
    old = assignments[(assignments.dataset == 'dappscan') & (assignments.cls == 'reentrancy') &
                      (assignments.protocol == 'random') & (assignments.seed == 0)]
    for fold in sorted(old.fold.unique()):
        alternatives.append((f'historical_random_seed0_fold{fold}', pop[pop.file_id.isin(old.loc[old.fold == fold, 'file_id'])]))
    for name, alt in alternatives:
        apools = training_pools(pop, alt)
        amatched, acounts = matched_training(apools, config['class'], 0)
        equal = len({tuple(sorted(p.file_id)) for p in apools.values()}) == 1
        for mode, p in apools.items():
            feasibility.append({'test_design': name, 'regime': mode, 'n_test': len(alt),
                                'test_positive_proxy': int(alt.reentrancy.sum()),
                                'test_joint_components': alt.joint_id.nunique(), 'n_pool': len(p),
                                'pool_positive_proxy': int(p.reentrancy.sum()),
                                'matched_n': sum(acounts.values()), 'matched_positive_proxy': acounts[1],
                                'status': 'feasible' if amatched else 'infeasible',
                                'all_raw_pools_identical': equal})
    pd.DataFrame(feasibility).to_csv(out / 'feasibility.csv', index=False)
    comps, pragmas = [], []
    for name, data in [('full_dappscan', pop), ('largest_joint', component), ('common_test', test),
                       *[(f'pool:{k}', p) for k, p in pools.items()],
                       *[(f'train:{k}', p) for k, p in matched.items()]]:
        c, p = composition(data, name)
        comps.append(c); pragmas.extend(p)
    pd.DataFrame(comps).to_csv(out / 'composition.csv', index=False)
    pd.DataFrame(pragmas).to_csv(out / 'compiler_ranges.csv', index=False)
    label_inputs = {str(p): sha256(p) for p in label_files()}
    dump(out / 'label_input_hashes.json', label_inputs)
    repo_commits = {x: subprocess.check_output(['git', '-C', str(ROOT / 'data/raw' / x), 'rev-parse', 'HEAD'], text=True).strip()
                    for x in ('smartbugs-curated', 'SolidiFI-benchmark', 'DAppSCAN')}
    env = {'python': sys.version, 'platform': platform.platform(),
           'packages': {m: importlib.metadata.version(m) for m in ('numpy', 'pandas', 'scipy', 'scikit-learn', 'pyarrow', 'threadpoolctl')},
           'logical_cpu_count': os.cpu_count(), 'thread_limit': 1}
    dump(out / 'environment.json', env)
    labelhash = hashlib.sha256(full[config['class']].to_numpy(dtype=np.int8).tobytes()).hexdigest()
    manifest = {'schema': 'security_fixed_t_run_v1', 'status': 'prepared_no_scores', 'started_utc': started,
                'prepared_utc': utc(), 'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'git_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
                'source_snapshots': {n: sha256(snapshot / n) for n in SOURCE_FILES},
                'input_files': {f'{HISTORY}/groups.parquet': sha256(ROOT / HISTORY / 'groups.parquet'),
                                f'{HISTORY}/assignments.parquet': sha256(ROOT / HISTORY / 'assignments.parquet')},
                'data_commits': repo_commits, 'config_sha256': config_hash,
                'membership_sha256': sha256(out / 'memberships.csv'), 'source_inventory_sha256': sha256(out / 'source_inventory.csv'),
                'label_inputs_sha256': sha256(out / 'label_input_hashes.json'), 'proxy_labels_sha256_int8_full_order': labelhash,
                'full_graph_n': len(full), 'dappscan_n': len(pop), 'selected_component_n': len(component),
                'test_n': len(test), 'test_positive_proxy': int(test.reentrancy.sum()),
                'test_coverage_of_dappscan': len(test) / len(pop), 'test_joint_components': int(test.joint_id.nunique()),
                'matched_training_n': sum(counts.values()), 'matched_training_positive_proxy': counts[1],
                'external_scores_computed': False,
                'limitations': ['One development test from one joint component; no population inference',
                                'Proxy labels are not confirmed negative/positive adjudications',
                                'Historical clone grouping uses probabilistic LSH candidate discovery',
                                'Equal size and proxy positives do not equalize all training composition',
                                'Library fields are screening heuristics, not verified origins']}
    dump(out / 'manifest.json', manifest)
    print(json.dumps({k: manifest[k] for k in ('status', 'test_n', 'test_positive_proxy', 'matched_training_n', 'matched_training_positive_proxy')}))


def run(out):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import average_precision_score
    from threadpoolctl import threadpool_limits
    started = time.perf_counter()
    manifest = json.loads((out / 'manifest.json').read_text())
    if manifest['status'] != 'prepared_no_scores':
        raise ValueError('Only a prepared, never-scored directory can be run')
    config = json.loads((out / 'pilot_config.json').read_text())
    for file, key in [('pilot_config.json', 'config_sha256'), ('memberships.csv', 'membership_sha256'),
                      ('source_inventory.csv', 'source_inventory_sha256'), ('label_input_hashes.json', 'label_inputs_sha256')]:
        if sha256(out / file) != manifest[key]:
            raise ValueError(f'Frozen file changed: {file}')
    for name, digest in manifest['source_snapshots'].items():
        if sha256(ROOT / name) != digest or sha256(out / 'code_snapshot' / name) != digest:
            raise ValueError(f'Code changed after preparation: {name}')
    for p, h in manifest['input_files'].items():
        if sha256(ROOT / p) != h:
            raise ValueError(f'Historical input changed: {p}')
    for p, h in json.loads((out / 'label_input_hashes.json').read_text()).items():
        if sha256(ROOT / p) != h:
            raise ValueError(f'Label input changed: {p}')
    for r in pd.read_csv(out / 'source_inventory.csv').itertuples():
        if sha256(ROOT / r.path) != r.file_sha256:
            raise ValueError(f'Source input changed: {r.path}')
    full = load_population()
    cls = config['class']
    if hashlib.sha256(full[cls].to_numpy(dtype=np.int8).tobytes()).hexdigest() != manifest['proxy_labels_sha256_int8_full_order']:
        raise ValueError('Proxy label vector changed')
    members = pd.read_csv(out / 'memberships.csv')
    test_ids = members.loc[members.role == 'test', 'file_id'].tolist()
    test = full.set_index('file_id').loc[test_ids]
    txt_test = test.source.map(raw_text)
    manifest['status'] = 'running'
    manifest['scoring_started_utc'] = utc()
    dump(out / 'manifest.json', manifest)
    metrics, budgets, predictions = [], [], []
    with threadpool_limits(limits=1):
        for mode in MODES:
            t0 = time.perf_counter()
            train_ids = members.loc[(members.role == 'train') & (members.regime == mode), 'file_id'].tolist()
            train = full.set_index('file_id').loc[train_ids]
            assert not set(train_ids) & set(test_ids)
            if mode == MODES[3]:
                assert not set(train.joint_id) & set(test.joint_id)
            params = dict(config['representation']['tfidf'])
            params['ngram_range'] = tuple(params['ngram_range'])
            vectorizer = TfidfVectorizer(**params)
            A = vectorizer.fit_transform(train.source.map(raw_text))
            B = vectorizer.transform(txt_test)
            scaler = StandardScaler(with_mean=False)
            A = scaler.fit_transform(A); B = scaler.transform(B)
            model = LogisticRegression(**{k: v for k, v in config['model'].items() if k != 'type'})
            model.fit(A, train[cls].to_numpy())
            score = model.predict_proba(B)[:, 1]
            elapsed = time.perf_counter() - t0
            y = test[cls].to_numpy()
            metrics.append({'regime': mode, 'class': cls, 'seed': config['seed'], 'n_train': len(train),
                            'positive_proxy_train': int(train[cls].sum()), 'n_test': len(test),
                            'positive_proxy_test': int(y.sum()), 'prevalence_proxy': float(y.mean()),
                            'ap_proxy': float(average_precision_score(y, score)), 'coverage': 1.,
                            'fit_and_score_seconds': elapsed, 'vocabulary_size': len(vectorizer.vocabulary_),
                            'iterations': int(model.n_iter_[0]), 'converged': bool(model.n_iter_[0] < config['model']['max_iter']),
                            'process_peak_rss_mib_cumulative': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024})
            for fraction in config['metrics']['budgets']:
                budgets.append({'regime': mode, **workload(y, score, fraction)})
            predictions.append(pd.DataFrame({'file_id': test_ids, 'regime': mode, 'score': score}))
            print(json.dumps(metrics[-1]), flush=True)
    pd.DataFrame(metrics).to_csv(out / 'pilot_metrics.csv', index=False)
    pd.DataFrame(budgets).to_csv(out / 'workload_metrics.csv', index=False)
    pd.concat(predictions).to_csv(out / 'predictions.csv', index=False)
    manifest.update(status='complete_development_only', finished_utc=utc(),
                    total_validation_and_scoring_seconds=time.perf_counter() - started,
                    process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                    all_models_converged=all(x['converged'] for x in metrics),
                    output_hashes={p.name: sha256(p) for p in (out / 'pilot_metrics.csv', out / 'workload_metrics.csv', out / 'predictions.csv')})
    manifest['artifact_bytes_before_final_manifest'] = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    dump(out / 'manifest.json', manifest)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('prepare', 'run'))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    os.chdir(ROOT)
    (prepare if args.action == 'prepare' else run)(args.out)


if __name__ == '__main__':
    main()
