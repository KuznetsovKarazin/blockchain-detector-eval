#!/usr/bin/env python3
"""Full transitive graph and training restrictions; no model fitting/scoring."""
import argparse, collections, csv, hashlib, importlib.util, json, re, resource, shutil, subprocess, sys, time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
import scipy
from scipy.sparse import csr_matrix

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from bal.data.contracts import load_all,label_files
from bal.features.contract_features import normalised_text
THRESHOLDS=(.7,.8,.9)
PINS={'DAppSCAN':'66a56619c44770e05c2db600fa6468115ff0dcd5','smartbugs-curated':'230e649123477eff332742a59a1c7cc6dc286cab','SolidiFI-benchmark':'4b0573e1b3f7031396de6f48f7f3e7380222ad3a','salzano':'da079440bf2cf4fd803c864ef29aeea8a3da50c3'}
SOURCES={'smartbugs_results':'sb_results_contracts','smartbugs_curated':'smartbugs_curated','zeus_safe':'zeus_safe_contracts','zeus_vulnerable':'zeus_vulnerable_contracts'}
def sha(b):return hashlib.sha256(b).hexdigest()
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args]).decode().strip()
def json_default(o):
    if isinstance(o,np.integer):return int(o)
    if isinstance(o,np.floating):return float(o)
    raise TypeError(type(o).__name__)
def dump(p,o):p.write_text(json.dumps(o,indent=2,default=json_default)+'\n')
def csvout(p,rows,fields=None):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
class UF:
    def __init__(self,n):self.p=list(range(n))
    def find(self,a):
        while a!=self.p[a]:self.p[a]=self.p[self.p[a]];a=self.p[a]
        return a
    def join(self,a,b):
        a,b=self.find(a),self.find(b)
        if a!=b:self.p[max(a,b)]=min(a,b)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--normalization',choices=['legacy','string_aware'],required=True)
    ap.add_argument('--scanner',type=Path);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--candidate-audit',type=Path,default=Path('papers/security_evaluation/external_audit/source_audit_full_20261025'))
    ap.add_argument('--private-labels',type=Path,default=Path('data/derived/security_external_full_20261025/provisional_label_manifest.csv'))
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False);start=time.monotonic();started=datetime.now(timezone.utc).isoformat()
    normalizer=normalised_text;scanner_errors=()
    code=[Path(__file__),ROOT/'src/bal/data/contracts.py',ROOT/'src/bal/features/contract_features.py']
    if args.normalization=='string_aware':
        if not args.scanner:raise ValueError('Explicit scanner required')
        spec=importlib.util.spec_from_file_location('frozen_solidity_scanner',args.scanner);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
        normalizer=mod.corrected_normalised_text;scanner_errors=(mod.SolidityScanError,);code.append(args.scanner.resolve())
    statuses={}
    for name,pin in PINS.items():
        repo=ROOT/'data/raw'/name;head=git(repo,'rev-parse','HEAD');clean=git(repo,'status','--porcelain')==''
        if head!=pin or not clean:raise ValueError(f'Unpinned or dirty upstream {name}')
        statuses[name]={'commit':head,'clean':clean}
    meta_path=args.candidate_audit/'candidate_source_metadata.csv';meta=pd.read_csv(meta_path,keep_default_na=False)
    duplicates=meta.contract_id.str.lower().duplicated(keep=False)|meta.file_hash.duplicated(keep=False)
    test_paths=set(meta.loc[(meta.source_id!='smartbugs_curated')&(meta.reconciliation=='matched')&~duplicates,'path'])
    assert len(test_paths)==1998
    lab=pd.read_csv(args.private_labels);labelkey={(r.path,r['class']):r.label_status for _,r in lab.iterrows()}
    historical=load_all();historical_paths=set(historical.path);full=load_all(max_unlabelled_per_project=None)
    assert len(historical)==7080 and len(full)==21950
    records=[]
    def add(dataset,path,local,project,scope,labels):
        b=local.read_bytes();text=b.decode('utf-8',errors='replace');error=''
        try:nt=normalizer(text)
        except scanner_errors as e:nt=None;error=str(e)
        ident=local.stem.lower();address=ident if re.fullmatch(r'0x[0-9a-f]{40}',ident) else ''
        records.append({'node_id':len(records),'scope':scope,'dataset':dataset,'path':path,'file_sha256':sha(b),
          'normalized_sha256':sha(nt.encode()) if nt is not None else '', 'project_id':project,'address_key':address,'identifier_key':ident,
          'historical_train':path in historical_paths if scope=='upstream' else False,'candidate_test':path in test_paths if scope=='external' else False,
          'normalization_status':'scan_error' if error else 'ok','scan_error':error,'source_bytes':len(b),'_normal':nt,'_label':labels})
    for source,folder in SOURCES.items():
        for p in sorted((ROOT/'data/raw/salzano/contracts'/folder).glob('*.sol')):
            path=p.relative_to(ROOT/'data/raw/salzano').as_posix()
            add(source,path,p,'','external',{c:labelkey[path,c] for c in ['reentrancy','unchecked']})
    for _,r in full.iterrows():add(r.dataset,r.path,ROOT/r.path,r.group,'upstream',{c:int(r[c]) for c in ['reentrancy','unchecked']})
    assert len(records)==24131 and sum(r['candidate_test'] for r in records)==1998
    snapshot=args.out/'executed_source';snapshot.mkdir();sources={}
    for p in code:
        rel=p.resolve().relative_to(ROOT);target=snapshot/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);sources[str(rel)]=sha(p.read_bytes())
    csvout(args.out/'label_input_hashes.csv',[{'path':str(p),'sha256':sha(p.read_bytes())} for p in [ROOT/'data/raw/salzano/csvs/sample_of_interest.csv',*label_files()]])
    config={'schema':'full_dependency_graph_config_v1','started_utc':started,'repo_head':git(ROOT,'rev-parse','HEAD'),'normalization':args.normalization,
      'source_hashes':sources,'upstream_pins':statuses,'thresholds':THRESHOLDS,'candidate_metadata_sha256':sha(meta_path.read_bytes()),'private_labels_sha256':sha(args.private_labels.read_bytes()),
      'candidate_rule':'fixed diagnostic1998; not final eligibility','population':'full uncapped21950 upstream plus2181 external; restrict AFTER graph',
      'base_edges':'upstream projects, within-external lowercase identifiers, identical raw bytes, lexical Jaccard',
      'address_expanded_edges':'base plus equal20byte address basenames across sources; chain unknown, conservative dependency proxy',
      'scan_error_policy':'keep nodes/project/address/raw-hash edges; omit lexical edges; quarantine scan-error training nodes; independence remains unresolved',
      'shingles':'normalized token5gram sets; BLAKE2b128; exhaustive sparse intersections; no LSH','no_model_scoring':True,
      'environment':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__}}
    dump(args.out/'config_before_graph.json',config);config_hash=sha((args.out/'config_before_graph.json').read_bytes())
    public=[k for k in records[0] if not k.startswith('_')];csvout(args.out/'nodes.csv',[{k:r[k] for k in public} for r in records],public)
    run_graph(args,records,config_hash,started,start)

def run_graph(args,records,config_hash,started,start):
    vocab={};indices=[];indptr=[0]
    for r in records:
        text=r['_normal'];tok=text.split() if text is not None else []
        sh=set() if text is None else {hashlib.blake2b(' '.join(tok[j:j+5]).encode(),digest_size=16).digest() for j in range(max(1,len(tok)-4))}
        for s in sh:
            if s not in vocab:vocab[s]=len(vocab)
            indices.append(vocab[s])
        indptr.append(len(indices))
    n=len(records);X=csr_matrix((np.ones(len(indices),np.int32),indices,indptr),shape=(n,len(vocab)));sizes=np.diff(X.indptr)
    graphs={(policy,t):UF(n) for policy in ['base','address_expanded'] for t in THRESHOLDS};edges=[]
    def link(i,j,kind,address_only=False,jaccard=''):
        edges.append({'left':i,'right':j,'edge_type':kind,'jaccard':jaccard,'address_expanded_only':address_only})
        for (policy,t),u in graphs.items():
            if (not address_only or policy=='address_expanded') and (jaccard=='' or jaccard>=t):u.join(i,j)
    for field,kind,scope in [('project_id','upstream_project','upstream'),('identifier_key','candidate_identifier','external'),('file_sha256','identical_raw_source',None),('address_key','syntactic_address',None)]:
        buckets=collections.defaultdict(list)
        for r in records:
            if (scope is None or r['scope']==scope) and r[field]:buckets[r[field]].append(r['node_id'])
        for ids in buckets.values():
            for j in ids[1:]:link(ids[0],j,kind,kind=='syntactic_address')
    for a0 in range(0,n,100):
        z=(X[a0:a0+100]@X.T).tocoo();ii=z.row+a0;jj=z.col;sim=z.data/(sizes[ii]+sizes[jj]-z.data)
        keep=(ii<jj)&(sim>=min(THRESHOLDS))
        for i,j,s in zip(ii[keep],jj[keep],sim[keep]):link(int(i),int(j),'normalized_shingle',jaccard=float(s))
        if a0%5000==0:print(f'{args.normalization}: {min(n,a0+100)}/{n}',flush=True)
    csvout(args.out/'edges.csv',edges)
    memberships=[]
    for r in records:
        row={'node_id':r['node_id'],'scope':r['scope'],'dataset':r['dataset'],'path':r['path']}
        for (policy,t),u in graphs.items():row[f'{policy}_{int(t*100):03d}']=u.find(r['node_id'])
        memberships.append(row)
    csvout(args.out/'memberships.csv',memberships)
    test_ids={r['node_id'] for r in records if r['candidate_test']};historical_ids={r['node_id'] for r in records if r['historical_train']}
    counts=[];external_counts=[];invariants=[]
    for (policy,t),u in graphs.items():
        test_components={u.find(i) for i in test_ids};historical_components={u.find(i) for i in historical_ids}
        excluded={i for i in historical_ids if u.find(i) in test_components};scan_errors={i for i in historical_ids if records[i]['normalization_status']!='ok'}
        usable=historical_ids-excluded-scan_errors
        assert not {u.find(i) for i in usable}&test_components
        assert usable|excluded|scan_errors==historical_ids
        name=f'{policy}_{int(t*100):03d}'
        manifest=[{'node_id':i,'dataset':records[i]['dataset'],'path':records[i]['path'],'component':u.find(i),
          'connected_to_candidate':i in excluded,'scan_error':i in scan_errors,'usable_training':i in usable,
          'reason':'candidate_connected_component' if i in excluded else ('normalization_scan_error' if i in scan_errors else 'retained_provisional')}
          for i in sorted(historical_ids)]
        csvout(args.out/f'training_exclusion_{name}.csv',manifest)
        for dataset in ['all','dappscan','solidifi','smartbugs']:
            ids={i for i in historical_ids if dataset=='all' or records[i]['dataset']==dataset};after=ids&usable
            for cls in ['reentrancy','unchecked']:
                before_positive=sum(records[i]['_label'][cls] for i in ids);after_positive=sum(records[i]['_label'][cls] for i in after)
                counts.append({'normalization':args.normalization,'grouping':policy,'threshold':t,'dataset':dataset,'class':cls,
                  'before_files':len(ids),'after_files':len(after),'connected_excluded_files':len(ids&excluded),'scan_error_files':len(ids&scan_errors),
                  'before_proxy_positive_files':before_positive,'after_proxy_positive_files':after_positive,'after_proxy_zero_files':len(after)-after_positive,
                  'retained_components':len({u.find(i) for i in after}),'positive_retained_components':len({u.find(i) for i in after if records[i]['_label'][cls]}),
                  'two_class_proxy_training_feasible':0<after_positive<len(after)})
        linked={i for i in test_ids if u.find(i) in historical_components}
        for cls in ['reentrancy','unchecked']:
            positive={i for i in test_ids if records[i]['_label'][cls]=='source_reported_positive_pending_adjudication'}
            external_counts.append({'normalization':args.normalization,'grouping':policy,'threshold':t,'class':cls,'test_files':len(test_ids),
              'test_proxy_components':len(test_components),'source_positive_files':len(positive),'positive_proxy_components':len({u.find(i) for i in positive}),
              'test_files_connected_to_historical_training':len(linked),'positive_test_files_connected':len(positive&linked),
              'test_scan_error_files':sum(records[i]['normalization_status']!='ok' for i in test_ids)})
        invariants.append({'graph':name,'intersection_of_retained_train_and_candidate_components':0,'historical_train_partition_count':len(historical_ids)})
    csvout(args.out/'training_feasibility.csv',counts);csvout(args.out/'candidate_component_counts.csv',external_counts)
    for policy in ['base','address_expanded']:
        exclusions=[]
        for t in THRESHOLDS:
            u=graphs[policy,t];tc={u.find(i) for i in test_ids};exclusions.append({i for i in historical_ids if u.find(i) in tc})
        assert exclusions[2]<=exclusions[1]<=exclusions[0]
    for e in edges:
        for (policy,t),u in graphs.items():
            if (not e['address_expanded_only'] or policy=='address_expanded') and (e['jaccard']=='' or e['jaccard']>=t):assert u.find(e['left'])==u.find(e['right'])
    assert sha((args.out/'config_before_graph.json').read_bytes())==config_hash
    dump(args.out/'summary.json',{'schema':'full_dependency_graph_result_v1','started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),
      'config_sha256':config_hash,'normalization':args.normalization,'nodes':n,'candidate_test_files':len(test_ids),'historical_train_files':len(historical_ids),
      'edge_type_counts':dict(collections.Counter(e['edge_type'] for e in edges)),'normalization_scan_errors':sum(r['normalization_status']!='ok' for r in records),
      'invariants':invariants,'threshold_exclusion_monotonicity':'pass','all_recorded_edges_connected':'pass',
      'runtime_seconds':time.monotonic()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
      'status':'diagnostic_full_graph_and_training_exclusions_not_external_eligibility_freeze','no_model_scoring':True})
    print(pd.DataFrame(counts).query('grouping=="address_expanded" and threshold==0.8').to_string(index=False),flush=True)

if __name__=='__main__':main()
