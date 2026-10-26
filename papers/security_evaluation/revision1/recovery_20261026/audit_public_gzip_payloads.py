"""Inspect every decompressed field before publishing recovered graph-result tables."""
from pathlib import Path
import csv,gzip,hashlib,json,re
ROOT=Path(__file__).resolve().parents[4]
REV=ROOT/'papers/security_evaluation/revision1'
rows=list(csv.DictReader((ROOT/'papers/security_evaluation/dependency_audit/legacy_recovered_20261025/nodes.csv').open(newline='')))
nodes={r['node_id']:r for r in rows}
projects={'project:'+r['project_id'] if r['scope']=='upstream' else 'external:'+r['identifier_key'] for r in rows}
enums={'normalization':{'legacy','string_aware'},'cohort':{'historical_7080','full_dappscan_21457','full_upstream_21950','full_combined_24131'},'variant':{'project_raw_equality','project_normalized_stream_with_empty','project_normalized_stream_nonempty'},'regime':{'clone_disjoint','common_test','joint_project_clone_disjoint','other_files_unrestricted','project_disjoint'},'role':{'train','test'},'semantic_review':{'not_reviewed'}}
boolean={'any_library_or_interface_declaration','exclusively_library_or_interface_declarations','known_utility_or_standard_filename','informative_representation'}
fixednumeric={'node_id','component','left_vertex','right_vertex','lexical_file_pairs','raw_hash_groups','max_jaccard','example_left_node_id','example_right_node_id','seed','rank','draw','file_id','library_declarations','interface_declarations','contract_declarations','line_count'}
fieldpattern=re.compile(r'(project_only|clone_only|joint)_(070|075|080|085|090|092|094|095|096|097|098|099|100)|(?:jaccard|containment)_(?:base|address_expanded)_(?:070|080|090|095|099)')
number=re.compile(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?')
audit=[]
for item in json.loads((REV/'publication_omissions.json').read_text())['omitted']:
 p=ROOT/item['path']
 if p.suffix!='.gz' or not p.exists():continue
 b=p.read_bytes();gitsha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();assert gitsha==item['git_blob_sha']
 count=0
 with gzip.open(p,'rt',newline='') as f:
  reader=csv.DictReader(f);fields=reader.fieldnames
  for row in reader:
   assert None not in row and all(v is not None for v in row.values())
   for k,v in row.items():
    if k in enums:assert v in enums[k],(p,k,v)
    elif k in boolean:assert v in {'True','False'},(p,k,v)
    elif k in {'path','dataset','file_sha256'}:assert v==nodes[row['node_id']][k],(p,k)
    elif k=='draw' and v=='-1':assert row['regime']=='common_test' and row['role']=='test'
    elif k in {'left_project','right_project'}:assert v in projects,(p,k,v)
    else:
     assert k in fixednumeric or fieldpattern.fullmatch(k),(p,k)
     assert number.fullmatch(v),(p,k,v)
   count+=1
 audit.append({'path':item['path'],'git_blob_sha':gitsha,'sha256':hashlib.sha256(b).hexdigest(),'compressed_bytes':len(b),'rows_inspected':count,'fields':fields,'all_decompressed_fields_checked':True,'content':'Numeric graph/sample results, fixed category enums, or metadata matched exactly to the pinned public source manifest; no source-code bodies, private contract text, reviewer keys, or human judgments.'})
out=REV/'recovery_20261026/PUBLIC_GZIP_CONTENT_AUDIT.json'
out.write_text(json.dumps({'status':'pass','files':audit,'inspection':'every decompressed row and field; exact original Git blob hash required'},indent=2)+'\n')
print(json.dumps({'status':'pass','files':len(audit),'rows':sum(x['rows_inspected'] for x in audit),'bytes':sum(x['compressed_bytes'] for x in audit)}))
