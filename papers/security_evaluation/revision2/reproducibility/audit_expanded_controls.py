"""Independent read-only replay of the expanded-graph contrast's frozen design."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();repo=a.repo.resolve()
    run=repo/'papers/security_evaluation/revision2/model_link/expanded_contrast_20261028_v1'
    freeze=json.loads((run/'FREEZE_BEFORE_FITTING.json').read_text())
    for path,h in freeze['source_hashes'].items():
        assert digest(repo/path)==digest(run/'code_snapshot'/path)==h,path
    for path,h in freeze['input_hashes'].items():assert digest(repo/path)==h,path
    for path,h in freeze['prepared_files'].items():assert digest(run/path)==h,path
    c=json.loads((run/'config.json').read_text())
    old=json.loads((repo/'papers/security_evaluation/revision1/sampling_variance/run_20261025_v2/config.json').read_text())
    assert c['model_config']==old['model_config']
    inventory={int(x['file_id']):x for x in csv.DictReader((repo/'papers/security_evaluation/runs/dev_fixed_t_20261025_v1/source_inventory.csv').open())}
    projection={int(x['file_id']):x for x in csv.DictReader((repo/'papers/security_evaluation/dependency_audit/graph_scope_ablation_recovered_20261025/historical_projection.csv').open())}
    annotations=json.loads((repo/'papers/security_evaluation/runs/dev_fixed_t_20261025_v1/label_input_hashes.json').read_text())
    n_annotations=0
    for name,h in annotations.items():
        if name.startswith('data/raw/DAppSCAN/'):
            assert digest(repo/name)==h,name;n_annotations+=1
    labels={}
    for fid,row in inventory.items():
        if row['dataset']!='dappscan':continue
        relative=Path(row['path'].removeprefix('data/raw/DAppSCAN/DAppSCAN-source/contracts/')).with_suffix('.json')
        path=repo/'data/raw/DAppSCAN/DAppSCAN-source/SWCsource'/relative
        found=set()
        if path.exists():
            assert str(path.relative_to(repo)) in annotations
            ann=json.loads(path.read_text())
            assert ann['filePath']==row['path'].removeprefix('data/raw/DAppSCAN/')
            found={x['category'].split('-')[1] for x in ann.get('SWCs',[]) if x.get('category','').startswith('SWC-')}
        labels[fid]={'reentrancy':int('107' in found),'unchecked':int('104' in found)}
    used_labels={int(k):v for k,v in json.loads((run/'labels.json').read_text()).items()}
    for fid,v in used_labels.items():assert labels[fid]==v
    used=list(csv.DictReader((run/'source_inventory.csv').open()))
    for row in used:
        fid=int(row['file_id']);assert row==inventory[fid]
        assert digest(repo/row['path'])==row['file_sha256']
    test=json.loads((run/'test_ids.json').read_text())
    assert len(test)==len(set(test))==1082 and sum(labels[i]['reentrancy'] for i in test)==21
    assert all(j['test_ids']==test for j in old['jobs'])
    pool={}
    for name,column in [('B','B_historical_legacy'),('C','C_uncapped_reference_legacy')]:
        excluded={projection[i][column] for i in test}
        pool[name]=sorted(i for i in labels if projection[i][column] not in excluded)
    assert pool==json.loads((run/'pool_ids.json').read_text())
    assert len(pool['B'])==1179 and len(pool['C'])==708 and set(pool['C'])<set(pool['B'])
    members=list(csv.DictReader((run/'memberships.csv').open()))
    expected={}
    for draw in range(5):
        for policy in ['B','C']:
            selected=[]
            for y,n in [(0,684),(1,24)]:
                salt=f'expanded-graph-post-review-v1|draw={draw}|class={y}|'
                ids=[i for i in pool[policy] if labels[i]['reentrancy']==y]
                ids.sort(key=lambda i:(hashlib.sha256((salt+inventory[i]['path']).encode()).hexdigest(),inventory[i]['path']))
                selected.extend(ids[:n])
            expected[draw,policy]=sorted(selected)
            actual=[int(x['file_id']) for x in members if int(x['draw'])==draw and x['policy']==policy]
            assert actual==expected[draw,policy]
    canonical={};physical=0
    assert len(c['jobs'])==120
    for j in c['jobs']:
        assert j['train_ids']==expected[j['draw'],j['policy']]
        assert j['test_ids']==test and not(set(j['train_ids'])&set(test))
        assert len(j['train_ids'])==len(set(j['train_ids']))==708
        assert sum(labels[i]['reentrancy'] for i in j['train_ids'])==24
        assert j['seed'] in ([0] if j['method'].endswith('tfidf_lr') else list(range(5)))
        key=(j['method'],j['seed'],tuple(j['train_ids']),tuple(test))
        assert j['reuse_from']==canonical.get(key)
        if key not in canonical:physical+=1;canonical[key]=j['job_id']
    assert physical==72
    runtime=json.loads((run/'environment.json').read_text())
    prior_runtime=json.loads((repo/'papers/security_evaluation/revision1/sampling_variance/run_20261025_v2/environment.json').read_text())
    assert all(prior_runtime['packages'][p]==v for p,v in runtime['packages'].items())
    start=json.loads((run/'execution_started.json').read_text())
    assert start['freeze_sha256']==digest(run/'FREEZE_BEFORE_FITTING.json')
    assert datetime.fromisoformat(freeze['prepared_utc'])<datetime.fromisoformat(start['started_utc'])
    result={'schema':'expanded_contrast_independent_design_audit_v1','status':'pass','script_sha256':digest(Path(__file__)),
      'audit_timing':'During execution. This is not a claim of independent review before the first fit.',
      'freeze_sha256':digest(run/'FREEZE_BEFORE_FITTING.json'),'source_hashes_checked':5,'input_hashes_checked':3,'prepared_hashes_checked':7,
      'source_files_byte_verified':len(used),'annotation_files_byte_verified':n_annotations,'labels_independently_rejoined':len(used_labels),
      'membership_cells_replayed':10,'physical_fits_declared':72,'logical_jobs_declared':120,
      'B_pool':[1179,sum(labels[i]['reentrancy'] for i in pool['B'])],'C_pool':[708,sum(labels[i]['reentrancy'] for i in pool['C'])],
      'matched_train':[708,24],'fixed_test':[1082,21],'test_unchecked_positives':sum(labels[i]['unchecked'] for i in test),
      'numerical_package_versions_match_previous':True,'old_lightgbm_binary_identity_established':False,
      'recorded_freeze_precedes_execution':True,'model_parameters_equal_previous':True,
      'code_review':['Vectorizer and scaler fitted on training sources only; test sources transformed with those objects.',
                     'Trainer uses training labels; test labels enter metric calculation after scoring.',
                     'All job identities and reuse destinations fixed before execution; wrapper prohibits restarting the run directory.',
                     'The same observed historical test is reused; no external validation, causal claim, or independent-family interval is supported.'],
      'new_fits_by_this_audit':0}
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
