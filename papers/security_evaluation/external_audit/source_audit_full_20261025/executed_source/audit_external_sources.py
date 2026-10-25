#!/usr/bin/env python3
"""Audit source identities and overlap; never train a model or compute scores.

Redistributable outputs contain our metadata/aggregate findings only. Upstream
annotations and reviewer keys stay in the required gitignored private directory.
The token normalization is pinned to the historical code for comparability; it
is a lexical screen, not a semantic equivalence or project-independence proof.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
import math
import platform
import re
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from bal.data.contracts import load_all
from bal.features.contract_features import normalised_text, strip_comments

COMMIT = 'da079440bf2cf4fd803c864ef29aeea8a3da50c3'
SOURCES = {'smartbugs_results': 'sb_results_contracts', 'smartbugs_curated': 'smartbugs_curated',
           'zeus_safe': 'zeus_safe_contracts', 'zeus_vulnerable': 'zeus_vulnerable_contracts'}
CLASSES = {'reentrancy': 'reentrancy', 'unchecked': 'unchecked_low_calls'}

def sha(b): return hashlib.sha256(b).hexdigest()
def git(repo, *args): return subprocess.check_output(['git', '-C', str(repo), *args]).decode().strip()
def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None: fields = list(rows[0]) if rows else []
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
def json_default(x):
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.floating):return float(x)
    raise TypeError(type(x).__name__)
def write_json(path, x): path.write_text(json.dumps(x, indent=2, ensure_ascii=False,default=json_default)+'\n')

def parse_tag(tag):
    text=tag.strip().rstrip(';').strip()
    if text=='no': return [], []
    entries=[]; errors=[]
    for part in text.split(';'):
        if not part.strip(): continue
        m=re.fullmatch(r'\s*(\d+)\s*:\s*([a-z_]+)\s*', part)
        if m: entries.append((int(m[1]), m[2]))
        else: errors.append(part)
    return entries, errors

class Union:
    def __init__(self,n): self.p=list(range(n))
    def find(self,a):
        while self.p[a]!=a: self.p[a]=self.p[self.p[a]]; a=self.p[a]
        return a
    def join(self,a,b):
        a,b=self.find(a),self.find(b)
        if a!=b:self.p[max(a,b)]=min(a,b)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--candidate',type=Path,default=Path('data/raw/salzano'))
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--private-out',type=Path,required=True)
    ap.add_argument('--review-seed',type=int,default=20261025)
    ap.add_argument('--full-upstream',action='store_true',help='Uncap DAppSCAN; screen all original source files')
    args=ap.parse_args(); start=time.monotonic(); started=datetime.now(timezone.utc).isoformat()
    args.out.mkdir(parents=True,exist_ok=False); args.private_out.mkdir(parents=True,exist_ok=False)
    if git(args.candidate,'rev-parse','HEAD')!=COMMIT: raise ValueError('Candidate commit differs')
    if git(ROOT,'check-ignore',str(args.private_out))!=str(args.private_out): raise ValueError('Private output must be gitignored')
    upstream=args.candidate/'csvs/sample_of_interest.csv'
    rows=list(csv.DictReader(upstream.open()))
    bykey=collections.defaultdict(list)
    for ri,r in enumerate(rows,2): bykey[(r['label'],r['contract'].lower())].append((ri,r))
    external=[]; labels=[]; private_details=[]; problems=[]
    for source,dirname in SOURCES.items():
        for p in sorted((args.candidate/'contracts'/dirname).glob('*.sol')):
            b=p.read_bytes(); text=b.decode('utf-8',errors='replace'); nt=normalised_text(text)
            key=(source,p.stem.lower()); rr=bykey.get(key,[])
            variants={r['tag'].strip() for _,r in rr}; duplicate_conflict=len(variants)>1
            entries=[]; errors=[]
            for _,r in rr:
                ent,err=parse_tag(r['tag']); entries+=ent; errors+=err
            out_of_bounds=sorted({line for line,_ in entries if not 1<=line<=len(text.splitlines())})
            status='matched'
            if not rr: status='missing_annotation_row'
            elif errors: status='unparsed_tag'
            elif duplicate_conflict: status='conflicting_duplicate_key'
            elif out_of_bounds: status='annotation_line_out_of_bounds'
            if status!='matched':problems.append({'source_id':source,'contract_id':p.stem,'reason':status,'manifest_rows':len(rr),'out_of_bounds_count':len(out_of_bounds)})
            pragmas=re.findall(r'pragma\s+solidity\s+([^;]+);',strip_comments(text))
            spdx=sorted(set(re.findall(r'SPDX-License-Identifier:\s*([^\r\n*]+)',text)))
            path=p.relative_to(args.candidate).as_posix()
            ext={'source_id':source,'source_commit':COMMIT,'path':path,'contract_id':p.stem,
                 'file_hash':sha(b),'normalized_hash':sha(nt.encode()),'bytes':len(b),'lines':len(text.splitlines()),
                 'contract_address':p.stem.lower() if re.fullmatch(r'0x[0-9a-fA-F]{40}',p.stem) else '',
                 'address_shape':'valid_20_byte' if re.fullmatch(r'0x[0-9a-fA-F]{40}',p.stem) else 'unvalidated_identifier',
                 'compiler_range':' | '.join(pragmas),'library_origin':'not_established',
                 'project_id':'unknown','base_contract_id':p.stem.lower(),'spdx_observed':' | '.join(spdx),
                 'manifest_row_count':len(rr),'reconciliation':status,
                 'prior_curated_exposure':source=='smartbugs_curated'}
            external.append(ext)
            private_details.append({'path':path,'manifest_rows':[ri for ri,_ in rr], 'upstream_tags':[r['tag'] for _,r in rr],
                                    'out_of_bounds_lines':out_of_bounds})
            lab={}
            for cls,raw in CLASSES.items():
                if status!='matched':ls='unknown_unresolved_source_identity_or_annotation'
                elif any(c==raw for _,c in entries):ls='source_reported_positive_pending_adjudication'
                elif not entries:ls='source_reported_no_finding_pending_adjudication'
                else:ls='source_class_not_listed_pending_adjudication'
                lab[cls]=ls
                labels.append({'path':path,'class':cls,'label_status':ls,'label_source':'csvs/sample_of_interest.csv',
                               'binary_target':'','inclusion_reason':'not_frozen_pending_overlap_and_label_review'})
            ext['_text']=nt; ext['_labels']=lab
    train=load_all(max_unlabelled_per_project=None) if args.full_upstream else load_all()
    train_records=[]
    for _,r in train.iterrows():
        p=Path(r['path']);b=p.read_bytes();nt=normalised_text(r['source'])
        train_records.append({'dataset':r['dataset'],'path':r['path'],'project_id':r['group'],
                              'file_hash':sha(b),'normalized_hash':sha(nt.encode()),'_text':nt,
                              'identifier':p.stem.lower()})
    records=external+train_records; n_ext=len(external); n=len(records)
    # 128-bit digests keep the sparse vocabulary compact. A digest collision is
    # cryptographically negligible; token normalization itself is intentionally lossy.
    vocab={}; indptr=[0];indices=[]
    for r in records:
        tok=r['_text'].split(); shingles={hashlib.blake2b(' '.join(tok[j:j+5]).encode(),digest_size=16).digest()
                    for j in range(max(1,len(tok)-4))}
        for s in shingles:
            if s not in vocab:vocab[s]=len(vocab)
            indices.append(vocab[s])
        indptr.append(len(indices))
    X=csr_matrix((np.ones(len(indices),dtype=np.int32),np.array(indices),np.array(indptr)),shape=(n,len(vocab)))
    sizes=np.diff(X.indptr); cross=[]; within=[]; thresholds=[.7,.8,.9]
    union={t:Union(n) for t in thresholds}
    # Include transitive links through historical projects; they are dependency
    # proxies, not verified project assignments for the candidate.
    groups=collections.defaultdict(list)
    for i,r in enumerate(train_records,n_ext):groups[r['project_id']].append(i)
    for ids in groups.values():
        for j in ids[1:]:
            for u in union.values():u.join(ids[0],j)
    idgroups=collections.defaultdict(list)
    for i,r in enumerate(external):idgroups[r['contract_id'].lower()].append(i)
    for ids in idgroups.values():
        for j in ids[1:]:
            for u in union.values():u.join(ids[0],j)
    # Exhaustive all-pairs screening over the full external + historical sample.
    # No stochastic LSH retrieval stage; each retained edge has exact Jaccard.
    edge_counts=collections.Counter()
    for a in range(0,n,100):
        prod=(X[a:a+100]@X.T).tocoo()
        aa=prod.row+a;bb=prod.col; jac=prod.data/(sizes[aa]+sizes[bb]-prod.data)
        keep=(aa<bb)&(jac>=.7)
        for i,j,z in zip(aa[keep],bb[keep],jac[keep]):
            i,j=int(i),int(j);z=float(z)
            for t in thresholds:
                if z>=t:union[t].join(i,j);edge_counts[str(t)]+=1
            if i<n_ext:
                item={'external_path':records[i]['path'],'other_path':records[j]['path'],
                      'other_dataset':records[j].get('dataset',records[j].get('source_id')),
                      'jaccard':z,'exact_bytes':records[i]['file_hash']==records[j]['file_hash'],
                      'normalized_equal':records[i]['normalized_hash']==records[j]['normalized_hash']}
                (within if j<n_ext else cross).append(item)
        print(f'screened {min(a+100,n)}/{n}',flush=True) if a%1000==0 else None
    # Hash/address matches are independent audit channels, including short or
    # empty token streams. They are never inferred from lexical similarity.
    hashmaps={k:collections.defaultdict(list) for k in ['file_hash','normalized_hash','identifier']}
    for r in train_records:
        for k in hashmaps:hashmaps[k][r[k]].append(r)
    direct_counts={}; matched_paths={}
    for kind in hashmaps:
        pairs=[]
        for r in external:
            key=r['contract_id'].lower() if kind=='identifier' else r[kind]
            for tr in hashmaps[kind].get(key,[]):pairs.append({'external_path':r['path'],'training_path':tr['path'],'training_dataset':tr['dataset']})
        write_csv(args.out/f'{kind}_matches.csv',pairs,['external_path','training_path','training_dataset'])
        direct_counts[kind]={'pairs':len(pairs),'external_files':len({x['external_path'] for x in pairs})}
        matched_paths[kind]={x['external_path'] for x in pairs}
    overlaps=collections.defaultdict(set)
    for x in cross:
        for t in thresholds:
            if x['jaccard']>=t:overlaps[t].add(x['external_path'])
    for i,r in enumerate(external):
        r['proxy_dependency_component_080']=f"dep_{union[.8].find(i):05d}"
        r['direct_historical_jaccard_ge_080']=r['path'] in overlaps[.8]
        r['exact_historical_match']=r['path'] in matched_paths['file_hash']
        r['normalized_historical_match']=r['path'] in matched_paths['normalized_hash']
        r['identifier_historical_match']=r['path'] in matched_paths['identifier']
    fields=[k for k in external[0] if not k.startswith('_')]
    write_csv(args.out/'candidate_source_metadata.csv',[{k:r[k] for k in fields} for r in external],fields)
    write_csv(args.out/'reconciliation_issues.csv',problems,['source_id','contract_id','reason','manifest_rows','out_of_bounds_count'])
    write_csv(args.out/'near_overlap_edges.csv',cross,['external_path','other_path','other_dataset','jaccard','exact_bytes','normalized_equal'])
    write_csv(args.out/'within_candidate_edges.csv',within,['external_path','other_path','other_dataset','jaccard','exact_bytes','normalized_equal'])
    write_csv(args.private_out/'provisional_label_manifest.csv',labels)
    write_json(args.private_out/'source_annotation_reconciliation.json',private_details)
    # Purposeful diagnostic audit: sample whole proxy components, then up to 6
    # file-class cases per component. No population estimator is claimed.
    # Family goal is bounded at 25; actual case count follows source availability.
    candidates=collections.defaultdict(list)
    for r in external:
        if r['prior_curated_exposure']:continue
        for cls in CLASSES:
            candidates[r['proxy_dependency_component_080']].append((r,cls))
    rng=np.random.default_rng(args.review_seed)
    families=list(candidates);rng.shuffle(families)
    # Deterministic priority to annotation problems, then family size. This is
    # explicitly purposive; randomization only resolves equal priorities.
    families.sort(key=lambda f:(not any(r['reconciliation']!='matched' for r,c in candidates[f]),-len(candidates[f])))
    selected=families[:25];review=[];key=[]
    for fam in selected:
        cases=candidates[fam].copy();rng.shuffle(cases)
        cases.sort(key=lambda q:(q[0]['reconciliation']=='matched',q[0]['_labels'][q[1]]!='source_reported_positive_pending_adjudication'))
        for r,cls in cases[:6]:
            cid=f"review_{len(review)+1:03d}"
            review.append({'case_id':cid,'source_commit':COMMIT,'source_path':r['path'],'file_hash':r['file_hash'],
                'class_to_assess':cls,'source_url':f'https://github.com/fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts/blob/{COMMIT}/{r["path"]}',
                'reviewer_id':'','judgment_positive_negative_unknown':'','affected_lines':'','compiler_assumptions':'','evidence_and_reason':'','reviewed_utc':''})
            key.append({'case_id':cid,'family':fam,'source_label_status':r['_labels'][cls],'issue':r['reconciliation']})
    write_csv(args.private_out/'blind_review_cases.csv',review)
    write_csv(args.private_out/'blind_review_key_private.csv',key)
    disputes=[x['case_id'] for x in key if x['issue']!='matched']
    ordinary=[x['case_id'] for x in key if x['issue']=='matched']
    n_second=math.ceil(.25*len(ordinary));rng.shuffle(ordinary)
    second=[{'case_id':cid,'assignment_reason':'all_source_reconciliation_disputes','conditional_inclusion_probability':1.0} for cid in disputes]
    second += [{'case_id':cid,'assignment_reason':'random_quarter_of_other_sampled_cases','conditional_inclusion_probability':n_second/len(ordinary)} for cid in ordinary[:n_second]]
    write_csv(args.private_out/'second_reviewer_assignment.csv',second)
    summary={'schema':'p1_external_source_audit_v1','started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
       'repository_head':git(ROOT,'rev-parse','HEAD'),'script_sha256':sha(Path(__file__).read_bytes()),
       'imported_source_sha256':{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in [ROOT/'src/bal/data/contracts.py', ROOT/'src/bal/features/contract_features.py']},
       'input_commits':{p:git(ROOT/'data/raw'/p,'rev-parse','HEAD') for p in ['DAppSCAN','smartbugs-curated','SolidiFI-benchmark']},
       'upstream_scope':'full_uncapped_original_sources' if args.full_upstream else 'historical_capped_sample',
       'candidate_commit':COMMIT,'compact_manifest_sha256':sha(upstream.read_bytes()),
       'source_counts':dict(collections.Counter(r['source_id'] for r in external)),
       'manifest_rows':len(rows),'manifest_unique_keys':len(bykey),'source_files':n_ext,
       'reconciliation_status_counts':dict(collections.Counter(r['reconciliation'] for r in external)),
       'provisional_label_status_counts':{c:dict(collections.Counter(r['_labels'][c] for r in external)) for c in CLASSES},
       'historical_sample_counts':dict(train.dataset.value_counts()),'direct_overlap':direct_counts,
       'jaccard_thresholds':thresholds,'direct_historical_overlap_files':{str(t):len(overlaps[t]) for t in thresholds},
       'all_population_edge_counts':dict(edge_counts),
       'candidate_proxy_components':{str(t):len({union[t].find(i) for i in range(n_ext)}) for t in thresholds},
       'candidate_proxy_component_sizes_080':dict(collections.Counter(r['proxy_dependency_component_080'] for r in external)),
       'spdx_files':sum(bool(r['spdx_observed']) for r in external),'valid_20byte_identifier_files':sum(r['address_shape']=='valid_20_byte' for r in external),
       'review_packet':{'selection':'purposive_diagnostic_no_population_inference','seed':args.review_seed,'proxy_families':len(selected),'file_class_cases':len(review),
                        'source_files':len({r['source_path'] for r in review}),'second_reviewer_cases':len(second),'human_reviews_completed':0,'private_directory':str(args.private_out)},
       'limitations':['Candidate project and library provenance unestablished.','Normalized tokens are lossy lexical representation, not semantic equivalence.',
         'Near edges exact within normalized hashed shingle representation; source-level family independence is not established.',
         'Upstream scope is explicit; uncapped scope may include files never used in historical model fitting.',
         'Source labels remain provisional; no final eligible independent test is frozen.','No models trained and no scores computed.'],
       'runtime_seconds':time.monotonic()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
       'environment':{'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,'pandas':pd.__version__}}
    write_json(args.out/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ['source_files','reconciliation_status_counts','direct_overlap','direct_historical_overlap_files','review_packet','runtime_seconds','max_rss_kib']},indent=2,default=json_default))
if __name__=='__main__':main()
