"""Restore identical audit bytes for the NEW 28 October reproduction.

The public archive's member retains its original 26 October path. This copies
only its verified bytes to the new run path; no old run receipt is recreated.
"""
import hashlib,json,zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
ARCHIVE=ROOT/'synthetic_engine_audit_20261026.zip'
MEMBER='synthetic_check_20261026_v1/engine_audit_baseline_reentrancy.json'
TARGET=ROOT/'recovered_check_20261028_v1/engine_audit_baseline_reentrancy.json'
ARCHIVE_SHA='2d463a36e9933f2d5fe588750869bf9c0c424f6740d25a2aabbaf4c175d3892e'
MEMBER_SHA='044243fa44bb70f496629d6d9b0210b7ee291dff2806fbb93790415513baa15d'

def restore():
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()!=ARCHIVE_SHA:raise ValueError('Archive checksum mismatch')
    with zipfile.ZipFile(ARCHIVE) as archive:data=archive.read(MEMBER)
    if len(data)!=20804725 or hashlib.sha256(data).hexdigest()!=MEMBER_SHA:raise ValueError('Audit member checksum mismatch')
    existed=TARGET.exists()
    if existed:
        if TARGET.read_bytes()!=data:raise ValueError('Existing destination differs; no overwrite permitted')
    else:
        TARGET.parent.mkdir(parents=True,exist_ok=True)
        with TARGET.open('xb') as stream:stream.write(data)
    return {'status':'already_present_identical' if existed else 'restored_identical_bytes',
      'sha256':MEMBER_SHA,'bytes':len(data),'destination':str(TARGET),
      'new_report_generation':False,'old_run_receipt_recreated':False}

if __name__=='__main__':print(json.dumps(restore(),indent=2))
