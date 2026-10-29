"""Fresh source-verified exact lexical equality control on all DAppSCAN files."""
from pathlib import Path
import hashlib,json,time,subprocess,shutil
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from trivia_only import canonical_bytes,SolidityScanError
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
REP=ROOT/'papers/security_evaluation/revision1/representations/run_20261025_v1'
PIN='66a56619c44770e05c2db600fa6468115ff0dcd5'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def main():
 out=HERE/'trivia_run_20261028_v1';out.mkdir(exist_ok=False)
 source=ROOT/'data/raw/DAppSCAN';assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==PIN
 scripts=[Path(__file__),HERE/'trivia_only.py',HERE/'test_trivia_only.py',ROOT/'papers/security_evaluation/normalization_audit/solidity_scanner.py']
 plan={'schema':'post_review_trivia_only_exact_control_v1','planned_utc':pd.Timestamp.now(tz='UTC').isoformat(),'upstream_pin':PIN,'inputs':{str(p.relative_to(ROOT)):sha(p) for p in [REP/'nodes_unchanged.csv',REP/'representation_metadata.csv']},'code':{str(p.relative_to(ROOT)):sha(p) for p in scripts},'population':'Exactly21457DAppSCANnodes; build on DAppSCAN-only cohort to match original raw/ordered equalitycontrols; no externalcandidate or otherreference nodes','canonicalization':'string-aware comment removal then maximal identifier/number/operator lexemes, atomic quoted and directlyprefixedhex/unicode literals, individual remaining punctuation; whitespace omitted BETWEENtokens; JSONtokenarray preservesboundaries and literals; identifiers,numericspellings,quotes,punctuationunchanged','license_handling':'remove license header onlywheninsidecomment; retain anylicense-like literal','empty_policy':'no equalityedges for emptytokenlist; retain node/project/rawidentitylinks','scanner_failures':'explicit unavailable, no fallback','not_a_semantic_or_compiler_equivalence_claim':True,'no_labels_or_models':True}
 dump(out/'PLAN_BEFORE_COMPUTE.json',plan)
 for p in scripts:shutil.copy2(p,out/p.name)
 start=time.perf_counter();nodes=pd.read_csv(REP/'nodes_unchanged.csv',keep_default_na=False);nodes=nodes.loc[nodes.dataset.eq('dappscan')].copy().reset_index(drop=True);assert len(nodes)==21457
 expected=nodes.file_sha256.to_numpy();records=[];seen={};unique={};collisions=0
 for i,row in enumerate(nodes.itertuples()):
  raw=(ROOT/row.path).read_bytes();assert hashlib.sha256(raw).hexdigest()==expected[i],row.path
  source=raw.decode('utf-8',errors='surrogateescape');error=''
  try:data=canonical_bytes(source);digest=hashlib.sha256(data).hexdigest();informative=data!=b'[]'
  except SolidityScanError as exc:data=None;digest='';informative=False;error=str(exc)
  if informative:
   if digest in unique:assert unique[digest]==data
   else:unique[digest]=data
  records.append({'node_id':row.node_id,'path':row.path,'file_sha256':row.file_sha256,'trivia_tokens_sha256':digest,'informative':informative,'scan_error':error})
  if (i+1)%5000==0:print(f'verified and scanned {i+1}/21457',flush=True)
 info=pd.DataFrame(records);info.to_csv(out/'source_verified_canonical_hashes.csv',index=False)
 rows=[];members={'node_id':nodes.node_id};old=pd.read_csv(REP/'representation_metadata.csv',keep_default_na=False).set_index('node_id').loc[nodes.node_id]
 for relation,values in [('project_raw',None),('project_raw_trivia_only_nonempty',info.trivia_tokens_sha256.where(info.informative,'')),('project_raw_old_preserved_nonempty',old.corrected_file_preserved_sha256),('project_raw_normalized_nonempty',old.corrected_file_normalized_sha256)]:
  a=[];b=[]
  for valueset in [nodes.project_id,nodes.file_sha256]+([] if values is None else [values]):
   first={}
   for i,v in enumerate(valueset):
    if not v:continue
    if v in first:a.append(first[v]);b.append(i)
    else:first[v]=i
  _,cp=connected_components(csr_matrix((np.ones(len(a),np.int8),(a,b)),shape=(len(nodes),len(nodes))),directed=False)
  counts=np.unique(cp,return_counts=True)[1];rows.append({'relation':relation,'files':len(nodes),'components':len(counts),'giant_files':int(counts.max()),'giant_fraction':float(counts.max()/len(nodes))});members[relation]=cp
 pd.DataFrame(rows).to_csv(out/'exact_equality_concentration.csv',index=False);pd.DataFrame(members).to_csv(out/'memberships.csv.gz',index=False,compression='gzip')
 dump(out/'RESULT.json',{'status':'complete','source_hash_checks':len(nodes),'source_scan_failures':int(info.scan_error.ne('').sum()),'empty_streams':int((~info.informative & info.scan_error.eq('')).sum()),'canonical_hash_group_bytes_checked':True,'plan_sha256':sha(out/'PLAN_BEFORE_COMPUTE.json'),'seconds':time.perf_counter()-start,'outputs':{p.name:sha(p) for p in out.iterdir() if p.name!='RESULT.json'}})
 print(pd.DataFrame(rows).to_string(index=False))
if __name__=='__main__':main()
