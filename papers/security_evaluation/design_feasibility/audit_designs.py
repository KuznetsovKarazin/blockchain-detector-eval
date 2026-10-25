"""Metadata-only development fixed-T feasibility and explicit bundle export.

Candidate designs are label blind. All source labels are proxy findings. No
models or prior model scores are read. The candidate list and operational count
screens are saved before enumeration; these screens are not a power calculation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'papers/security_evaluation/code'))
import fixed_t_development as dev

CLASSES = ('reentrancy', 'unchecked')
SEEDS = (0, 1, 2, 3, 4)
SALT = 'security-design-feasibility-after-pilot-v1'
SOURCE_FILES = ('papers/security_evaluation/design_feasibility/audit_designs.py',
                *dev.SOURCE_FILES)


def concentration(ids):
    """Inverse-Simpson concentration summary, not a statistical sample size."""
    counts = pd.Series(ids, dtype=object).value_counts().to_numpy(dtype=float)
    total = counts.sum()
    return {'n_components': len(counts),
            'largest_component_fraction': float(counts.max() / total) if total else None,
            'inverse_simpson_component_count': float(total**2 / np.square(counts).sum()) if total else None}


def sample_files(frame, fraction, seed, scope):
    ranked = dev.hash_order(frame.path.tolist(), f'{SALT}|{scope}|{seed}')
    selected = set(ranked[:math.ceil(len(ranked) * fraction)])
    return frame[frame.path.isin(selected)].sort_values('file_id')


def sample_whole_components(frame, fraction, seed):
    keys = sorted(frame.joint_id.unique())
    ranked = dev.hash_order(keys, f'{SALT}|outside_whole_components|{seed}')
    selected = ranked[:math.ceil(len(keys) * fraction)]
    return frame[frame.joint_id.isin(selected)].sort_values('file_id')


def specifications():
    rows = []
    for scope, fractions in [('full', [.01, .02, .05, .1, .2]),
                             ('giant', [.01, .02, .05, .1, .2]),
                             ('outside', [.1, .2, .5, .75, .9, 1.0]),
                             ('outside_whole_components', [.1, .2, .5])]:
        for fraction in fractions:
            for seed in SEEDS:
                rows.append({'test_id': f'{scope}_p{fraction*100:g}_seed{seed}',
                             'scope': scope, 'fraction': fraction, 'design_seed': seed})
    return rows


def candidate_tests(pop, specs):
    component_sizes = pop.groupby('joint_id').size()
    largest = sorted(component_sizes.index, key=lambda k: (-component_sizes[k], k))[0]
    scopes = {'full': pop, 'giant': pop[pop.joint_id == largest],
              'outside': pop[pop.joint_id != largest]}
    out = {}
    for spec in specs:
        if spec['scope'] == 'outside_whole_components':
            test = sample_whole_components(scopes['outside'], spec['fraction'], spec['design_seed'])
        else:
            test = sample_files(scopes[spec['scope']], spec['fraction'], spec['design_seed'], spec['scope'])
        out[spec['test_id']] = test
    return out, largest


def assess_design(pop, test, giant):
    pools = dev.training_pools(pop, test)
    ids = {mode: set(p.file_id) for mode, p in pools.items()}
    common = set.intersection(*ids.values())
    any_pool = set.union(*ids.values())
    unres, joint = ids[dev.MODES[0]], ids[dev.MODES[3]]
    c = concentration(test.joint_id)
    summary = {'n_test': len(test), 'test_coverage_full_population': len(test) / len(pop),
               'test_giant_fraction': float((test.joint_id == giant).mean()),
               'test_components': c['n_components'],
               'test_largest_component_fraction': c['largest_component_fraction'],
               'test_inverse_simpson_components': c['inverse_simpson_component_count'],
               'distinct_raw_training_pools': len({tuple(sorted(v)) for v in ids.values()}),
               'all_pools_identical': len(common) == len(any_pool),
               'unrestricted_joint_removed_n': len(unres - joint),
               'unrestricted_joint_removed_fraction': len(unres - joint) / len(unres) if unres else None}
    details = []
    computational, count_screen, positive_dispersion = True, True, True
    for cls in CLASSES:
        matches, counts = dev.matched_training(pools, cls, 0)
        npos = int(test[cls].sum())
        pos_c = concentration(test.loc[test[cls] == 1, 'joint_id'])
        summary[f'{cls}_test_positive_proxy'] = npos
        summary[f'{cls}_positive_test_components'] = pos_c['n_components']
        summary[f'{cls}_positive_inverse_simpson_components'] = pos_c['inverse_simpson_component_count']
        summary[f'{cls}_matched_train_n'] = sum(counts.values())
        summary[f'{cls}_matched_train_positive_proxy'] = counts[1]
        computational &= bool(matches) and npos > 0 and npos < len(test)
        count_screen &= npos >= 20 and counts[1] >= 20 and sum(counts.values()) >= 500
        positive_dispersion &= pos_c['n_components'] >= 5 and (pos_c['inverse_simpson_component_count'] or 0) >= 3
        for mode, pool in pools.items():
            details.append({'class': cls, 'regime': mode, 'n_pool': len(pool),
                            'positive_proxy_pool': int(pool[cls].sum()),
                            'matched_n': sum(counts.values()), 'matched_positive_proxy': counts[1],
                            'train_joint_components': int(pool.joint_id.nunique()),
                            'status': 'computable' if matches and npos > 0 and npos < len(test) else 'infeasible'})
    summary['computationally_feasible_both_classes'] = bool(computational)
    summary['count_screen_both_classes'] = bool(count_screen)
    summary['dispersion_screen'] = bool(c['n_components'] >= 10 and
                                        (c['inverse_simpson_component_count'] or 0) >= 5 and
                                        (c['largest_component_fraction'] or 0) <= .5 and positive_dispersion)
    summary['nontrivial_restriction_contrast'] = bool(summary['distinct_raw_training_pools'] > 1)
    summary['all_operational_screens_pass'] = bool(computational and count_screen and summary['dispersion_screen'] and summary['nontrivial_restriction_contrast'])
    return summary, details


def write_input_provenance(out, full):
    cols = ['file_id', 'dataset', 'path', 'group', 'comp', 'joint_id']
    inventory = full[cols].copy()
    inventory['file_sha256'] = [dev.sha256(ROOT / p) for p in inventory.path]
    inventory.to_csv(out / 'source_inventory.csv', index=False)
    dev.dump(out / 'label_input_hashes.json', {str(p): dev.sha256(p) for p in dev.label_files()})
    for name in SOURCE_FILES:
        dest = out / 'code_snapshot' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
    return {'data_commits': {x: subprocess.check_output(['git', '-C', str(ROOT/'data/raw'/x), 'rev-parse', 'HEAD'], text=True).strip()
                             for x in ('smartbugs-curated', 'SolidiFI-benchmark', 'DAppSCAN')},
            'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'code_hashes': {n: dev.sha256(ROOT / n) for n in SOURCE_FILES},
            'graph_source': dev.HISTORY + '/groups.parquet',
            'graph_source_sha256': dev.sha256(ROOT / dev.HISTORY / 'groups.parquet'),
            'full_graph_n': len(full),
            'proxy_label_hashes_full_order_int8': {c: hashlib.sha256(full[c].to_numpy(dtype=np.int8).tobytes()).hexdigest() for c in CLASSES}}


def audit(out):
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    specs = specifications()
    config = {'schema': 'fixed_t_design_feasibility_v1', 'purpose': 'development_after_observed_pilot',
              'created_utc': dev.utc(), 'seed_list': list(SEEDS), 'selection_salt': SALT,
              'candidate_specs': specs, 'test_selection_uses_labels': False,
              'test_selection_uses_model_scores': False,
              'count_screens': {'test_positive_proxy_per_class_min': 20,
                                'matched_training_positive_proxy_per_class_min': 20, 'matched_training_n_min': 500},
              'dispersion_screens': {'test_components_min': 10, 'test_inverse_simpson_components_min': 5,
                                     'largest_test_component_fraction_max': .5,
                                     'positive_components_per_class_min': 5,
                                     'positive_inverse_simpson_components_per_class_min': 3},
              'screen_interpretation': 'Operational feasibility checks, not statistical power or sufficient evidence for a paper',
              'model_scores_read': False, 'external_scoring_allowed': False,
              'clone_graph': 'Full original 7080-row C2 observed partition at threshold0.8; capped DAppSCAN 6587 rows; additional external graph pending',
              'population_change': 'outside designs exclude the giant component from test; all development DAppSCAN stays eligible training subject to regime',
              'repeated_tests': 'Five overlapping deterministic samples are not independent studies or independent uncertainty draws'}
    dev.dump(out / 'audit_config.json', config)
    full = dev.load_population()
    assert full.file_id.is_unique and full.path.is_unique
    pop = full[full.dataset == 'dappscan']
    tests, giant = candidate_tests(pop, specs)
    summaries, detail_rows, assignments = [], [], []
    for spec in specs:
        test = tests[spec['test_id']]
        summary, detail = assess_design(pop, test, giant)
        summaries.append({**spec, **summary})
        detail_rows.extend({'test_id': spec['test_id'], **x} for x in detail)
        assignments.extend({'test_id': spec['test_id'], 'file_id': int(i)} for i in test.file_id)
    table = pd.DataFrame(summaries)
    table.to_csv(out / 'design_summary.csv', index=False)
    pd.DataFrame(detail_rows).to_csv(out / 'class_pool_feasibility.csv', index=False)
    pd.DataFrame(assignments).to_csv(out / 'candidate_tests.csv', index=False)
    overlap = []
    for (scope, fraction), group in table.groupby(['scope','fraction']):
        ids = group.test_id.tolist()
        for i, a in enumerate(ids):
            for b in ids[i+1:]:
                A, B = set(tests[a].file_id), set(tests[b].file_id)
                overlap.append({'test_a': a, 'test_b': b, 'intersection_n': len(A&B), 'jaccard': len(A&B)/len(A|B)})
    pd.DataFrame(overlap).to_csv(out / 'replicate_test_overlap.csv', index=False)
    provenance = write_input_provenance(out, full)
    files = ['audit_config.json', 'design_summary.csv', 'class_pool_feasibility.csv', 'candidate_tests.csv',
             'replicate_test_overlap.csv', 'source_inventory.csv', 'label_input_hashes.json']
    manifest = {'schema': 'security_development_design_bundle_v1', 'purpose': 'development_only',
                'status': 'metadata_audit_complete_selection_pending', 'created_utc': config['created_utc'], 'finished_utc': dev.utc(),
                'external_scoring_allowed': False, 'train_allowed': False, 'models_fitted': 0,
                'reason_training_blocked': 'A documented design selection decision is required; operational screens are not a main-protocol freeze.',
                'selected_test_ids': [], 'candidate_n': len(table), 'all_screens_pass_n': int(table.all_operational_screens_pass.sum()),
                'hashes': {f: dev.sha256(out/f) for f in files}, **provenance}
    dev.dump(out / 'design_manifest.json', manifest)
    print(table.groupby(['scope','fraction']).agg(n=('test_id','size'),
          count_pass=('count_screen_both_classes','sum'),all_pass=('all_operational_screens_pass','sum'),
          train_min=('reentrancy_matched_train_n','min'),train_max=('reentrancy_matched_train_n','max'),
          re_test_min=('reentrancy_test_positive_proxy','min'),re_test_max=('reentrancy_test_positive_proxy','max'),
          un_test_min=('unchecked_test_positive_proxy','min'),un_test_max=('unchecked_test_positive_proxy','max')).to_string())


def export_bundle(audit_dir, out, selected, decision):
    """Authorised development selection only; records the decision verbatim.

    A passed operational screen is required. The bundle is not an external-test
    freeze. Root may make this routine scientific choice within user authority.
    """
    if out.exists():
        raise FileExistsError(out)
    manifest = json.loads((audit_dir/'design_manifest.json').read_text())
    for f, h in manifest['hashes'].items():
        assert dev.sha256(audit_dir/f) == h, f
    if not decision.strip():
        raise ValueError('Document why these development designs are selected')
    summary = pd.read_csv(audit_dir/'design_summary.csv').set_index('test_id')
    for test_id in selected:
        if test_id not in summary.index or not bool(summary.loc[test_id,'all_operational_screens_pass']):
            raise ValueError(f'{test_id}: does not pass declared operational screens; do not silently relax')
    for source_name, digest in manifest['code_hashes'].items():
        if source_name != 'papers/security_evaluation/design_feasibility/audit_designs.py':
            assert dev.sha256(ROOT/source_name) == digest, source_name
    for source in pd.read_csv(audit_dir/'source_inventory.csv').itertuples():
        assert dev.sha256(ROOT/source.path) == source.file_sha256, source.path
    for source_name, digest in json.loads((audit_dir/'label_input_hashes.json').read_text()).items():
        assert dev.sha256(ROOT/source_name) == digest, source_name
    full = dev.load_population(); pop = full[full.dataset=='dappscan']
    for cls, digest in manifest['proxy_label_hashes_full_order_int8'].items():
        assert hashlib.sha256(full[cls].to_numpy(dtype=np.int8).tobytes()).hexdigest() == digest, cls
    candidate = pd.read_csv(audit_dir/'candidate_tests.csv')
    rows = []
    cols = ['file_id','path','group','comp','joint_id']
    for test_id in selected:
        test = pop[pop.file_id.isin(candidate.loc[candidate.test_id==test_id,'file_id'])].sort_values('file_id')
        pools = dev.training_pools(pop,test)
        common_test=test[cols].copy()
        common_test['test_id']=test_id;common_test['class']='*';common_test['seed']=-1
        common_test['regime']='common_test';common_test['role']='test';rows.append(common_test)
        for cls in CLASSES:
            for seed in SEEDS:
                matched,_ = dev.matched_training(pools,cls,seed)
                for regime, train in matched.items():
                    for role, part in [('train',train)]:
                        block=part[cols].copy()
                        block['test_id']=test_id;block['class']=cls;block['seed']=seed;block['regime']=regime;block['role']=role
                        rows.append(block)
    out.mkdir(parents=True)
    columns=['test_id','class','seed','regime','role',*cols]
    pd.concat(rows,ignore_index=True)[columns].to_csv(out/'selected_memberships.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    for f in ['source_inventory.csv','label_input_hashes.json','audit_config.json','design_summary.csv']:
        shutil.copy2(audit_dir/f,out/f)
    dest=out/'code_snapshot'/'audit_designs.py';dest.parent.mkdir(parents=True);shutil.copy2(Path(__file__),dest)
    bundle={**{k:manifest[k] for k in ['schema','purpose','data_commits','graph_source','graph_source_sha256','full_graph_n','proxy_label_hashes_full_order_int8']},
            'created_utc':dev.utc(),'status':'selected_development_bundle', 'train_allowed':True,'external_scoring_allowed':False,
            'selected_test_ids':selected,'membership_file':'selected_memberships.csv.gz','selection_decision':decision,'source_audit_manifest_sha256':dev.sha256(audit_dir/'design_manifest.json'),
            'selection_source_audit':str(audit_dir),'training_seeds':list(SEEDS),
            'candidate_membership_uses_labels':False,'selection_uses_proxy_label_counts':True,
            'selection_uses_model_scores':False,
            'export_code_sha256':dev.sha256(Path(__file__)),
            'hashes':{f:dev.sha256(out/f) for f in ['selected_memberships.csv.gz','source_inventory.csv','label_input_hashes.json','audit_config.json','design_summary.csv']},
            'limitations':['Post-pilot development design, not untouched confirmation','Outside-giant designs represent a changed test population',
                           'Operational screens are not power calculations','Repeated tests overlap and are not independent studies']}
    dev.dump(out/'design_manifest.json',bundle)
    print(json.dumps({'selected_test_ids':selected,'train_allowed':True,'rows':sum(len(x) for x in rows)}))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['audit','export'])
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--audit-dir',type=Path)
    p.add_argument('--select',nargs='+')
    p.add_argument('--decision',default='')
    a=p.parse_args();os.chdir(ROOT)
    if a.action=='audit':audit(a.out)
    else:
        if not a.audit_dir or not a.select:p.error('export requires --audit-dir and --select')
        export_bundle(a.audit_dir,a.out,a.select,a.decision)


if __name__=='__main__':main()
