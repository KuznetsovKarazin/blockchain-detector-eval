#!/usr/bin/env python3
"""Verify recovered ignored sources against existing frozen metadata only."""
from pathlib import Path
import gc
import hashlib
import json
import subprocess
import sys
from datetime import datetime,timezone
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'src'))
from bal.data.contracts import load_all,label_files

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def git(path,*args):return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()

def run():
    assert Path.cwd()==ROOT
    original=ROOT/'papers/security_evaluation/revision1/representations/run_20261025_v1'
    config=json.loads((original/'config_before_outputs.json').read_text())
    repositories={}
    for name,record in config['upstream_pins'].items():
        source=ROOT/'data/raw'/name
        head=git(source,'rev-parse','HEAD');status=git(source,'status','--porcelain')
        assert head==record['commit'] and not status,(name,head,status)
        repositories[name]={'commit':head,'git_tree':git(source,'rev-parse','HEAD^{tree}'),'clean':True}
    for name,expected in config['input_hashes'].items():assert sha(ROOT/name)==expected,name
    nodes=pd.read_csv(ROOT/'papers/security_evaluation/dependency_audit/string_aware_recovered_20261025/nodes.csv',keep_default_na=False)
    assert len(nodes)==24131 and nodes.node_id.tolist()==list(range(24131)) and nodes.candidate_test.sum()==1998
    source_bytes=0
    for row in nodes.itertuples():
        path=ROOT/('data/raw/salzano/'+row.path if row.scope=='external' else row.path)
        assert sha(path)==row.file_sha256,row.path
        assert path.stat().st_size==row.source_bytes,row.path
        source_bytes+=path.stat().st_size
    print('24131 raw source hashes and byte lengths match',flush=True)
    labels=json.loads((original/'training_label_input_hashes.json').read_text())
    assert [str(path) for path in label_files()]==list(labels)
    for name,expected in labels.items():assert sha(ROOT/name)==expected,name
    full=load_all(max_unlabelled_per_project=None)
    upstream=nodes[nodes.scope=='upstream']
    assert len(full)==21950 and full.path.tolist()==upstream.path.tolist()
    assert full.dataset.tolist()==upstream.dataset.tolist() and full.group.tolist()==upstream.project_id.tolist()
    full_order_hash=hashlib.sha256(('\n'.join(full.path)+'\n').encode()).hexdigest()
    del full;gc.collect()
    historical=load_all()
    inventory_path=ROOT/'papers/security_evaluation/runs/dev_fixed_t_20261025_v1/source_inventory.csv'
    inventory=pd.read_csv(inventory_path,keep_default_na=False)
    assert len(historical)==len(inventory)==7080 and inventory.file_id.tolist()==list(range(7080))
    for column in ['path','dataset','group']:assert historical[column].tolist()==inventory[column].tolist(),column
    assert set(historical.path)==set(nodes.loc[nodes.historical_train,'path'])
    source_map=dict(zip(nodes.path,nodes.file_sha256))
    assert inventory.file_sha256.tolist()==[source_map[path] for path in historical.path]
    # Labels are reproduced through the unchanged committed loader and all
    # annotation input byte hashes have been checked, with ordering preserved.
    historical_order_hash=hashlib.sha256(('\n'.join(historical.path)+'\n').encode()).hexdigest()
    receipt={'status':'pass','verified_utc':datetime.now(timezone.utc).isoformat(),
             'checkpoint_commit':git(ROOT,'rev-parse','HEAD'),'script_sha256':sha(Path(__file__)),
             'raw_repository_states':repositories,'frozen_graph_input_hashes':config['input_hashes'],
             'source_hashes_verified':24131,'source_bytes_verified_sum':source_bytes,
             'external_source_records':2181,'full_upstream_records':21950,
             'full_upstream_path_order_matches_frozen_nodes':True,'full_upstream_order_sha256_newline_paths':full_order_hash,
             'historical_records':7080,'historical_dappscan_records':int(historical.dataset.eq('dappscan').sum()),
             'historical_path_dataset_project_order_matches_frozen_inventory':True,
             'historical_order_sha256_newline_paths':historical_order_hash,
             'historical_inventory_sha256':sha(inventory_path),'historical_source_hashes_match':True,
             'historical_membership_matches_frozen_node_flags':True,'candidate_test_records':1998,
             'annotation_files_verified':len(labels),'annotation_manifest_sha256':sha(original/'training_label_input_hashes.json'),
             'loader_sha256':sha(ROOT/'src/bal/data/contracts.py'),'models_or_graphs_recomputed':False,
             'frozen_output_overwritten':False}
    dest=Path(__file__).with_name('INPUT_VERIFICATION.json')
    dest.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':run()
