"""NEW 2026-10-28 read-only audit comparison; no report/model generation.

The original archive and all reproduced outputs are inputs only. An optional
new comparison receipt uses exclusive creation. This is not an original receipt
and makes no claim about unrecovered original reports or their metadata.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent
REPORTING=HERE.parent
EXPECTED_ARCHIVE_SHA256='2d463a36e9933f2d5fe588750869bf9c0c424f6740d25a2aabbaf4c175d3892e'
EXPECTED_MEMBER_SHA256='044243fa44bb70f496629d6d9b0210b7ee291dff2806fbb93790415513baa15d'
EXPECTED_MEMBER='synthetic_check_20261026_v1/engine_audit_baseline_reentrancy.json'
EXPECTED_MEMBER_BYTES=20804725
MAX_DIFFERENCES=20

def digest(data):return hashlib.sha256(data).hexdigest()
def require(condition,message):
    if not condition:raise ValueError(message)

def strict_json(data):
    def unique_object(pairs):
        out={}
        for key,value in pairs:
            if key in out:raise ValueError('Duplicate JSON key: '+key)
            out[key]=value
        return out
    def reject_constant(value):raise ValueError('Non-finite JSON number: '+value)
    return json.loads(data,object_pairs_hook=unique_object,parse_constant=reject_constant)

def brief(value):
    if isinstance(value,dict):return {'kind':'object','keys':len(value)}
    if isinstance(value,list):return {'kind':'array','length':len(value)}
    if isinstance(value,str):return value[:160]+('...' if len(value)>160 else '')
    return value

def bounded_differences(left,right,limit=MAX_DIFFERENCES):
    """Return first bounded differences in deterministic JSON-pointer order.

    JSON numbers compare numerically; booleans are distinct from numbers.
    Object key order is immaterial. Array order remains material.
    """
    differences=[]
    def add(path,reason,a=None,b=None):
        differences.append({'json_pointer':path or '', 'reason':reason,
                            'original':brief(a),'reproduced':brief(b)})
    def child(path,key):return path+'/'+str(key).replace('~','~0').replace('/','~1')
    def walk(a,b,path):
        if len(differences)>limit:return
        number_a=isinstance(a,(int,float)) and not isinstance(a,bool)
        number_b=isinstance(b,(int,float)) and not isinstance(b,bool)
        if type(a) is not type(b) and not (number_a and number_b):
            add(path,'JSON_type_mismatch',a,b);return
        if isinstance(a,dict):
            for key in sorted(set(a)|set(b)):
                if len(differences)>limit:return
                if key not in a:add(child(path,key),'missing_in_original',None,b[key])
                elif key not in b:add(child(path,key),'missing_in_reproduction',a[key],None)
                else:walk(a[key],b[key],child(path,key))
        elif isinstance(a,list):
            if len(a)!=len(b):add(path,'array_length_mismatch',a,b)
            for index,(av,bv) in enumerate(zip(a,b)):
                if len(differences)>limit:return
                walk(av,bv,child(path,index))
        elif a!=b:add(path,'value_mismatch',a,b)
    walk(left,right,'')
    return differences[:limit],len(differences)>limit

def compare():
    archive=REPORTING/'synthetic_engine_audit_20261026.zip'
    reproduced=REPORTING/'recovered_check_20261028_v1/engine_audit_baseline_reentrancy.json'
    plan=HERE/'PLAN_BEFORE_EXECUTION.json'
    receipt=REPORTING/'recovered_check_20261028_v1/receipt.json'
    archive_bytes=archive.read_bytes()
    require(digest(archive_bytes)==EXPECTED_ARCHIVE_SHA256,'Original archive digest mismatch')
    with ZipFile(archive) as zipped:
        require(zipped.namelist()==[EXPECTED_MEMBER],'Unexpected original archive membership')
        info=zipped.getinfo(EXPECTED_MEMBER)
        require(info.file_size==EXPECTED_MEMBER_BYTES,'Unexpected original member size')
        original_bytes=zipped.read(EXPECTED_MEMBER)
    require(digest(original_bytes)==EXPECTED_MEMBER_SHA256,'Original member digest mismatch')
    reproduced_bytes=reproduced.read_bytes()
    plan_bytes=plan.read_bytes();receipt_bytes=receipt.read_bytes()
    plan_data=strict_json(plan_bytes);receipt_data=strict_json(receipt_bytes)
    require(receipt_data['status']=='complete_fictional_reports_only','Reproduced run incomplete')
    require(receipt_data['output_hashes'][reproduced.name]==digest(reproduced_bytes),'Reproduced member differs from its new receipt')
    require(all(plan_data['source_hashes'].get(path)==sha for path,sha in receipt_data['source_hashes'].items()),'New run source bindings differ from pre-execution plan')
    original_json=strict_json(original_bytes);reproduced_json=strict_json(reproduced_bytes)
    differences,truncated=bounded_differences(original_json,reproduced_json)
    return {'schema':'new_reporting_audit_comparison_20261028_v1',
      'comparison_created_utc':datetime.now(timezone.utc).isoformat(),
      'comparison_is_original_20261026_receipt':False,
      'purpose':'NEW read-only comparison of the recovered original audit with the newly reproduced audit',
      'original':{'archive':str(archive.relative_to(REPORTING)),'archive_bytes':len(archive_bytes),
        'archive_sha256':digest(archive_bytes),'matches_recorded_archive_sha256':True,
        'member':EXPECTED_MEMBER,'member_bytes':len(original_bytes),'member_sha256':digest(original_bytes),
        'matches_recorded_member_sha256':True},
      'reproduced':{'member':str(reproduced.relative_to(REPORTING)),'member_bytes':len(reproduced_bytes),
        'member_sha256':digest(reproduced_bytes),'new_run_receipt':str(receipt.relative_to(REPORTING)),
        'new_run_receipt_sha256':digest(receipt_bytes),'pre_execution_plan':str(plan.relative_to(REPORTING)),
        'pre_execution_plan_sha256':digest(plan_bytes),'source_hashes':receipt_data['source_hashes']},
      'exact_bytes_equal':original_bytes==reproduced_bytes,'JSON_semantically_equal':not differences,
      'JSON_equality_definition':'same object keys and scalar values, ordered arrays, numeric equality without equating booleans to numbers',
      'first_differences':differences,'difference_path_limit':MAX_DIFFERENCES,
      'additional_differences_not_enumerated':truncated,
      'unrecovered_original_report_outputs_compared':False,
      'unrecovered_original_receipts_recreated':False,
      'scope_limit':'An audit match does not establish byte equality of any other original report, timing, metadata or receipt not recovered.',
      'models_tests_or_report_generation_executed':False,'input_files_modified':False,
      'comparison_utility_sha256':digest(Path(__file__).read_bytes())}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,help='Optional NEW comparison JSON; existing paths are refused')
    args=parser.parse_args();result=compare()
    if args.out:
        with args.out.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    else:print(json.dumps(result,indent=2,allow_nan=False))
