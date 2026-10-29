"""Post-review ordered-stream controls using unchanged archived source hashes."""
from pathlib import Path
import hashlib,json,sys,time
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
REP=ROOT/'papers/security_evaluation/revision1/representations/run_20261025_v1'
INPUTS=[REP/'representation_metadata.csv',REP/'nodes_unchanged.csv',REP/'structural_edges_unchanged.csv']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def stats(labels,ids):
 c=np.unique(labels[ids],return_counts=True)[1]
 return dict(files=len(ids),components=len(c),giant_files=int(c.max()),giant_fraction=float(c.max()/len(ids)))
def links(values,valid):
 first={};a=[];b=[]
 for i in np.flatnonzero(valid):
  v=values[i]
  if not v:continue
  if v in first:a.append(first[v]);b.append(i)
  else:first[v]=i
 return a,b

def main():
 out=HERE/'metadata_run_20261028_v1';out.mkdir(exist_ok=False)
 plan={'schema':'post_review_metadata_controls_v1','planned_utc':pd.Timestamp.now(tz='UTC').isoformat(),'inputs':{str(p.relative_to(ROOT)):sha(p) for p in INPUTS},'source_sha256':sha(Path(__file__)),'no_source_retokenization':True,'no_labels_or_predictions_used':True,'cohorts':['historical7080','dappscan21457','upstream21950','combined24131'],'relations':['project_raw','project_raw_ordered_normalized_nonempty','project_raw_ordered_preserved_nonempty'],'empty_policy':'suppress lexical links; retain all graph nodes and provenance/raw-identity links','interpretation':'Preserved streams retain identifiers/numbers but inherit TOKEN_RE; not comment/whitespace-only canonicalization and not Jaccard1.0 shingle-set equality','coverage_decomposition':'classify unchanged original per-file metadata, no rerun and no imputation'}
 dump(out/'PLAN_BEFORE_COMPUTE.json',plan)
 start=time.perf_counter();meta=pd.read_csv(INPUTS[0],keep_default_na=False);nodes=pd.read_csv(INPUTS[1],keep_default_na=False);n=len(nodes)
 assert np.array_equal(meta.node_id,nodes.node_id) and np.array_equal(nodes.node_id,np.arange(n))
 assert np.array_equal(meta.file_sha256,nodes.file_sha256)
 dapp=nodes.dataset.eq('dappscan').to_numpy();hist=nodes.historical_train.to_numpy(bool);ext=nodes.candidate_test.to_numpy(bool)
 rows=[];members=[]
 cohorts={'historical7080':hist,'dappscan21457':dapp,'upstream21950':nodes.scope.eq('upstream').to_numpy(),'combined24131':np.ones(n,bool)}
 for cname,selected in cohorts.items():
  a=[];b=[]
  for col,valid in [('project_id',selected & nodes.scope.eq('upstream').to_numpy()),('identifier_key',selected & nodes.scope.eq('external').to_numpy()),('file_sha256',selected)]:
   x,y=links(nodes[col].to_numpy(),valid);a+=x;b+=y
  for relation,variant in [('project_raw',None),('project_raw_ordered_normalized_nonempty','corrected_file_normalized'),('project_raw_ordered_preserved_nonempty','corrected_file_preserved')]:
   x=[];y=[]
   if variant:x,y=links(meta[variant+'_sha256'].to_numpy(),selected & meta[variant+'_informative'].to_numpy(bool))
   _,cp=connected_components(csr_matrix((np.ones(len(a)+len(x),np.int8),(a+x,b+y)),shape=(n,n)),directed=False)
   ids=np.flatnonzero(selected & dapp);r={'cohort':cname,'relation':relation,**stats(cp,ids)}
   if cname=='combined24131':r['external_graph_retained_historical']=int((hist & dapp & ~np.isin(cp,cp[ext])).sum())
   rows.append(r)
   members.append(pd.DataFrame({'cohort':cname,'relation':relation,'node_id':np.flatnonzero(selected),'component':cp[selected]}))
 pd.DataFrame(rows).to_csv(out/'ordered_equality_concentration.csv',index=False)
 pd.concat(members).to_csv(out/'ordered_equality_memberships.csv.gz',index=False,compression='gzip')
 coverage=[]
 for population,selected in [('dappscan21457',dapp),('combined24131',np.ones(n,bool))]:
  q=meta.loc[selected];full=q.corrected_file_normalized_informative.to_numpy(bool);masked=q.library_interface_masked_normalized_informative.to_numpy(bool);error=q.structural_scan_error.ne('').to_numpy();removed=pd.to_numeric(q.removed_unit_count,errors='coerce').fillna(0).to_numpy()>0
  categories={'already_full_empty':~full,'newly_unavailable_scan_error':full & ~masked & error,'newly_unavailable_no_residual_code':full & ~masked & ~error,'still_informative_masked_declarations':masked & removed,'still_informative_no_masked_declarations':masked & ~removed}
  assert sum(int(v.sum()) for v in categories.values())==len(q)
  for c,v in categories.items():coverage.append({'population':population,'category':c,'files':int(v.sum()),'fraction':float(v.mean())})
 pd.DataFrame(coverage).to_csv(out/'masking_coverage_decomposition.csv',index=False)
 dump(out/'RESULT.json',{'status':'complete_metadata_only','plan_sha256':sha(out/'PLAN_BEFORE_COMPUTE.json'),'seconds':time.perf_counter()-start,'outputs':{p.name:sha(p) for p in out.iterdir() if p.name!='RESULT.json'}})
 print(pd.DataFrame(rows).to_string(index=False));print(pd.DataFrame(coverage).to_string(index=False))
if __name__=='__main__':main()
