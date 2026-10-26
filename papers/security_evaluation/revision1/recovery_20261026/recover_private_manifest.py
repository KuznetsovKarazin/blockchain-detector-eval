#!/usr/bin/env python3
"""Recover ignored annotation-derived input using the committed audit prefix.

No graph computation, model fitting, external scoring or frozen-output writes.
The extracted prefix is the exact original main body before loading training.
"""
from pathlib import Path
import ast
import hashlib
import json
import runpy
import shutil
import sys

ROOT=Path(__file__).resolve().parents[4]
SCRIPT=ROOT/'papers/security_evaluation/external_audit/audit_external_sources.py'
EXPECTED='72fceb79cacca51253eabdb7e3ed26a54e7863f4b5be4430071ef9b14d5d0236'
RECOVERY=ROOT/'data/derived/recovery_20261026/source_prefix'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run():
    if Path.cwd()!=ROOT:raise RuntimeError('Run from repository root to retain relative path serialization')
    code=SCRIPT.read_text();tree=ast.parse(code)
    main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    stop=next(i for i,node in enumerate(main.body) if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='train' for t in node.targets))
    # Execute the literal committed source statements through source/label parsing;
    # stop before load_all(), sparse similarity, grouping, or review selection.
    prefix=ast.fix_missing_locations(ast.Module(body=main.body[:stop],type_ignores=[]))
    namespace=runpy.run_path(str(SCRIPT))
    old_argv=sys.argv
    try:
        sys.argv=[str(SCRIPT),'--out',str((RECOVERY/'metadata').relative_to(ROOT)),
                  '--private-out',str((RECOVERY/'private').relative_to(ROOT)),'--full-upstream']
        exec(compile(prefix,str(SCRIPT),'exec'),namespace)
    finally:sys.argv=old_argv
    source=RECOVERY/'private/provisional_label_manifest.csv'
    namespace['write_csv'](source,namespace['labels'])
    namespace['write_json'](RECOVERY/'private/source_annotation_reconciliation.json',namespace['private_details'])
    assert sha(source)==EXPECTED,('label manifest mismatch',sha(source))
    import pandas as pd
    frozen=ROOT/'papers/security_evaluation/external_audit/source_audit_full_20261025/candidate_source_metadata.csv'
    meta=pd.read_csv(frozen,keep_default_na=False)
    generated=namespace['external']
    assert len(generated)==len(meta)==2181
    for row,record in zip(meta.itertuples(),generated):
        for key in ['path','source_id','file_hash','normalized_hash','reconciliation']:
            assert getattr(row,key)==record[key],(row.path,key)
    restored=[]
    for dirname in ['security_external_full_20261025','security_external_recovered_20261025']:
        dest=ROOT/'data/derived'/dirname/'provisional_label_manifest.csv'
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert sha(dest)==EXPECTED
        else:shutil.copyfile(source,dest)
        restored.append(str(dest.relative_to(ROOT)))
    receipt={'status':'exact_hash_recovery','generator':str(SCRIPT.relative_to(ROOT)),
             'generator_sha256':sha(SCRIPT),'executed_prefix_ends_before':'train = load_all(...)',
             'annotation_csv_sha256':sha(ROOT/'data/raw/salzano/csvs/sample_of_interest.csv'),
             'provisional_label_manifest_sha256':EXPECTED,'restored_paths':restored,
             'source_records':len(generated),'label_rows':len(namespace['labels']),
             'frozen_candidate_order_and_identity_match':True,'raw_annotations_in_public_outputs':False}
    target=Path(__file__).with_name('PRIVATE_MANIFEST_RECOVERY.json')
    target.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':run()
