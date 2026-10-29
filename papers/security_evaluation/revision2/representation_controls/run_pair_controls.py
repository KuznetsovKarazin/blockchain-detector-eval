"""Post-review Jaccard=1 and masking-availability graph controls on replay NPZ."""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
REP=ROOT/'papers/security_evaluation/revision1/representations/run_20261025_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def canon(cp):
 c=np.full(len(cp),len(cp),dtype=np.int32);np.minimum.at(c,cp,np.arange(len(cp)));return c[cp]
def independent(n,a,b):
 parent=np.arange(n,dtype=np.int32);size=np.ones(n,dtype=np.int32)
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for u,v in zip(a,b):
  u,v=find(u),find(v)
  if u==v:continue
  if size[u]<size[v]:u,v=v,u
  parent[v]=u;size[u]+=size[v]
 return canon(np.array([find(i) for i in range(n)]))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--archive-root',type=Path,required=True);args=ap.parse_args()
 edgebase=args.archive_root/'papers/security_evaluation/revision1/recovery_20261026/representation_edges_v1'
 names=['corrected_file_normalized','corrected_file_preserved','library_interface_masked_normalized','library_interface_masked_preserved']
 inputs=[REP/'representation_metadata.csv',REP/'nodes_unchanged.csv',REP/'structural_edges_unchanged.csv',edgebase/'manifest.json']+[edgebase/x/'lexical_edges.npz' for x in names]
 out=HERE/'pair_run_20261028_v1';out.mkdir(exist_ok=False)
 plan={'schema':'post_review_pair_controls_v1','planned_utc':pd.Timestamp.now(tz='UTC').isoformat(),'inputs':{str(p):sha(p) for p in inputs},'source_sha256':sha(Path(__file__)),'lineage':'New canonical edge arrays from independently verified source replay; not byte-identical lost original archives and not proven complete historical edge-list identity. New controls conditional on this replay.','population':'All24131 original nodes, project/rawidentity/candidateidentifier policies unchanged; DAppSCAN21457 projection denominator unchanged.','policies':['base','address_expanded'],'cases':['full_080','full_100','full_080_mask_availability_only','masked_080'],'availability_control':'Keep full-file lexical edges only if BOTH endpoints have informative masked representation; leave every node and every structural edge untouched.','exact_threshold_predicate':'5*intersection >=4*(leftsize+rightsize-intersection) at0.8; leftsize==rightsize==intersection at1.0','no_labels_or_models':True,'decomposition':'Two-step, fixed-order descriptive contrast. Masking may add as well as remove edges; not an additive causal attribution.'}
 dump(out/'PLAN_BEFORE_COMPUTE.json',plan);start=time.perf_counter()
 nodes=pd.read_csv(inputs[1],keep_default_na=False);meta=pd.read_csv(inputs[0],keep_default_na=False);struct=pd.read_csv(inputs[2],keep_default_na=False)
 n=len(nodes);dapp=nodes.dataset.eq('dappscan').to_numpy();hist=nodes.historical_train.to_numpy(bool)&dapp;test=nodes.candidate_test.to_numpy(bool)
 assert np.array_equal(nodes.node_id,meta.node_id)
 rows=[];members={'node_id':nodes.node_id};edgechanges=[]
 for flavor in ['normalized','preserved']:
  full=np.load(edgebase/f'corrected_file_{flavor}/lexical_edges.npz',allow_pickle=False);mask=np.load(edgebase/f'library_interface_masked_{flavor}/lexical_edges.npz',allow_pickle=False)
  a,b,k,s=[full[x].astype(np.int64) for x in ('left','right','intersection','node_shingle_sizes')];ma,mb,mk,ms=[mask[x].astype(np.int64) for x in ('left','right','intersection','node_shingle_sizes')]
  informative=meta[f'library_interface_masked_{flavor}_informative'].to_numpy(bool);fullinformative=meta[f'corrected_file_{flavor}_informative'].to_numpy(bool)
  assert np.array_equal(s>0,fullinformative) and np.array_equal(ms>0,informative)
  full08=5*k>=4*(s[a]+s[b]-k);exact=(k==s[a])&(k==s[b]);mask08=5*mk>=4*(ms[ma]+ms[mb]-mk);avail=full08&informative[a]&informative[b]
  fullpairs=set((a[full08]*n+b[full08]).tolist());avpairs=set((a[avail]*n+b[avail]).tolist());maskpairs=set((ma[mask08]*n+mb[mask08]).tolist())
  edgechanges.append({'flavor':flavor,'full_080_pairs':len(fullpairs),'availability_only_pairs':len(avpairs),'masked_080_pairs':len(maskpairs),'availability_removed':len(fullpairs-avpairs),'mask_added_vs_availability':len(maskpairs-avpairs),'mask_removed_vs_availability':len(avpairs-maskpairs)})
  cases={'full_080':(a[full08],b[full08]),'full_100':(a[exact],b[exact]),'full_080_mask_availability_only':(a[avail],b[avail]),'masked_080':(ma[mask08],mb[mask08])}
  for policy in ['base','address_expanded']:
   st=struct if policy=='address_expanded' else struct.loc[~struct.address_expanded_only]
   for case,(la,lb) in cases.items():
    left=np.concatenate([la,st.left]);right=np.concatenate([lb,st.right])
    _,cp=connected_components(csr_matrix((np.ones(len(left),np.int8),(left,right)),shape=(n,n)),directed=False)
    cp=canon(cp);assert np.array_equal(cp,independent(n,left,right))
    key=f'{flavor}_{policy}_{case}';members[key]=cp
    uniq,counts=np.unique(cp[dapp],return_counts=True);giant=uniq[np.argmax(counts)];retained=hist&~np.isin(cp,cp[test]);r={'flavor':flavor,'policy':policy,'case':case,'lexical_pairs':len(la),'dapp_files':int(dapp.sum()),'dapp_components':len(counts),'dapp_giant_files':int(counts.max()),'dapp_giant_fraction':float(counts.max()/dapp.sum()),'dapp_giant_mask_informative':int((dapp&(cp==giant)&informative).sum()),'dapp_giant_mask_unavailable':int((dapp&(cp==giant)&~informative).sum()),'historical_retained':int(retained.sum()),'historical_retained_mask_informative':int((retained&informative).sum())};rows.append(r)
 pd.DataFrame(rows).to_csv(out/'graph_controls.csv',index=False);pd.DataFrame(edgechanges).to_csv(out/'mask_edge_changes.csv',index=False);pd.DataFrame(members).to_csv(out/'memberships.csv.gz',index=False,compression='gzip')
 dump(out/'RESULT.json',{'status':'complete','independent_union_find_graph_checks':len(rows),'plan_sha256':sha(out/'PLAN_BEFORE_COMPUTE.json'),'seconds':time.perf_counter()-start,'outputs':{p.name:sha(p) for p in out.iterdir() if p.name!='RESULT.json'}})
 print(pd.DataFrame(rows).query("policy=='address_expanded'").to_string(index=False));print(pd.DataFrame(edgechanges).to_string(index=False))
if __name__=='__main__':main()
