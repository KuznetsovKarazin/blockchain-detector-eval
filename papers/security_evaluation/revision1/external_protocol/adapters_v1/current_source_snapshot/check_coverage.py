"""Read-only fixed-manifest feature preprocessing; no vocabulary/model fit.

Only metadata and hashes are written. The external provisional labels, private
review keys, human answers and model scores are never opened by this command.
"""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import time

import numpy as np
import pandas as pd

from adapters import ROOT, SourceRecord, prepare, REPRESENTATIONS

PINS = {'DAppSCAN':'66a56619c44770e05c2db600fa6468115ff0dcd5',
        'salzano':'da079440bf2cf4fd803c864ef29aeea8a3da50c3',
        'smartbugs-curated':'230e649123477eff332742a59a1c7cc6dc286cab',
        'SolidiFI-benchmark':'4b0573e1b3f7031396de6f48f7f3e7380222ad3a'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def load_verified_records(packet, root=ROOT):
    """Require original public hashes, fixed membership/roles and source bytes."""
    for name, digest in json.loads((packet/'public_file_hashes.json').read_text()).items():
        if sha(packet/name) != digest:
            raise ValueError('Frozen packet hash changed: '+name)
    train = pd.read_csv(packet/'training_manifest.csv', keep_default_na=False)
    test = pd.read_csv(packet/'external_cohort_manifest.csv', keep_default_na=False)
    if len(train)!=691 or len(test)!=1998 or set(train.component)&set(test.address_expanded_080):
        raise ValueError('Fixed membership/graph separation mismatch')
    if not train.path.is_unique or not test.path.is_unique or not pd.concat([train.node_id,test.node_id]).is_unique:
        raise ValueError('Duplicate source identity')
    records = []
    inventory = []
    for role, frame in [('train',train),('external',test)]:
        for row in frame.itertuples():
            path = root/row.path if role=='train' else root/'data/raw/salzano'/row.path
            if not path.resolve().is_relative_to((root/'data/raw').resolve()):
                raise ValueError('Source path outside pinned input trees')
            data = path.read_bytes()
            expected = row.file_sha256 if role=='train' else row.file_hash
            if hashlib.sha256(data).hexdigest()!=expected:
                raise ValueError('Source byte hash changed: '+str(path))
            records.append(SourceRecord(str(row.node_id),role,data))
            inventory.append(dict(sample_id=str(row.node_id),role=role,path=row.path,source_sha256=expected))
    return records, inventory


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--packet',type=Path,default=ROOT/'papers/security_evaluation/revision1/external_protocol/packet_probability_20261025_v1')
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();start=time.monotonic()
    if args.out.exists():raise FileExistsError('A new output directory is required')
    base=Path(__file__).parent
    plan=json.loads((base/'adapter_plan.json').read_text())
    for name,digest in plan['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Predeclared adapter source changed: '+name)
    for name,digest in plan['input_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Predeclared adapter input changed: '+name)
    pins={}
    for name,pin in PINS.items():
        path=ROOT/'data/raw'/name
        head=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        clean=not subprocess.check_output(['git','-C',str(path),'status','--porcelain'],text=True).strip()
        if head!=pin or not clean:raise ValueError('Upstream pin/tree changed: '+name)
        pins[name]=dict(commit=head,clean=clean)
    records,inventory=load_verified_records(args.packet)
    args.out.mkdir(parents=True)
    shutil.copy2(base/'adapter_plan.json',args.out/'plan_before_preprocessing.json')
    snapshot=args.out/'source_snapshot';snapshot.mkdir()
    for name in plan['source_sha256']:
        source=ROOT/name
        shutil.copy2(source,snapshot/source.name)
    rows=[]
    for representation in REPRESENTATIONS:
        prepared=prepare(records,representation)
        for item in prepared.coverage:
            row=dict(item,representation=representation)
            index=row['matrix_row']
            if index is not None:
                vector=prepared.patterns[index] if representation=='pattern43' else prepared.texts[index].encode()
                raw=vector.tobytes() if isinstance(vector,np.ndarray) else vector
                row['representation_sha256']=hashlib.sha256(raw).hexdigest()
                row['finite_pattern_values']=bool(np.isfinite(vector).all()) if representation=='pattern43' else None
            rows.append(row)
    coverage=pd.DataFrame(rows)
    coverage=coverage.merge(pd.DataFrame(inventory)[['sample_id','role','path']],on=['sample_id','role'],validate='many_to_one')
    coverage.to_csv(args.out/'preprocessing_coverage.csv',index=False)
    summary=dict(schema='external_B_adapter_coverage_v1',scope='preprocessing only; no learned vocabulary/scaler/classifier fitted on real inputs',
                 input_files=len(records),representations=list(REPRESENTATIONS),
                 coverage=coverage.groupby(['role','representation','preprocessing_status']).size().rename('files').reset_index().to_dict('records'),
                 pattern_missing_pragma=coverage[coverage.representation=='pattern43'].groupby('role').pragma_version_missing.sum().astype(int).to_dict(),
                 upstream_pins=pins,packet_sha256=sha(args.packet/'packet_manifest.json'),adapter_plan_sha256=sha(base/'adapter_plan.json'),
                 output_sha256={'preprocessing_coverage.csv':sha(args.out/'preprocessing_coverage.csv')},
                 environment=dict(python=platform.python_version(),packages={n:importlib.metadata.version(n) for n in ['numpy','pandas','scipy','scikit-learn']}),
                 elapsed_seconds=time.monotonic()-start,peak_ram_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                 training_labels_read=False,external_source_annotations_read=False,human_judgments_read=False,
                 real_training_vocabularies_fitted=0,external_vocabularies_fitted=0,model_fits_or_predictions=0,
                 toolchain_execution=False,protocol_freeze_performed=False)
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary))

if __name__=='__main__':main()
