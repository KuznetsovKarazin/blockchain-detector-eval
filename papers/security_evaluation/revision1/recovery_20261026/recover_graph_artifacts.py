#!/usr/bin/env python3
"""Recompute missing graph artifacts locally; restore only two-hash exact matches.

This wrapper reuses byte-verified frozen scientific functions. It does not fit
models, regenerate labels, change a graph definition, upload, or rewrite an
existing frozen artifact. Fresh run records are separate from original records.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
import scipy

ROOT=Path(__file__).resolve().parents[4]
GM=ROOT/'papers/security_evaluation/revision1/graph_mechanism'
sys.path.insert(0,str(GM))
import run_mechanism as m

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def blob(p):
    b=Path(p).read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def check_map(mapping):
    rows=[]
    for path,expected in mapping.items():
        p=Path(path);p=p if p.is_absolute() else ROOT/p
        assert p.is_file(),str(p)
        actual=digest(p);assert actual==expected,(str(p),expected,actual)
        rows.append({'path':str(p.relative_to(ROOT)),'sha256':actual,'match':True})
    return rows

def graph(out):
    frozen=json.loads((GM/'run_20261025_v1/config_before_compute.json').read_text())
    assert m.THRESHOLDS==frozen['thresholds'] and m.SEEDS==frozen['seeds'] and m.POLICIES==frozen['policies']
    checks=check_map(frozen['source_sha256'])+check_map(frozen['input_sha256'])
    preflight(out,'graph',checks,['main frozen config: thresholds/seeds unchanged','recompute all four complete-cohort membership tables and .80 contractions, plus five population rankings; do not rerun 45 sampled-cohort label aggregates'])
    base=ROOT/'papers/security_evaluation/dependency_audit'
    nodes=pd.read_csv(base/'legacy_recovered_20261025/nodes.csv',keep_default_na=False).set_index('node_id',drop=False)
    dapp=nodes.index[nodes.dataset.eq('dappscan')].to_numpy();assert len(dapp)==21457
    cohorts={'historical_7080':nodes.index[nodes.historical_train].to_numpy(),'full_dappscan_21457':dapp,
             'full_upstream_21950':nodes.index[nodes.scope.eq('upstream')].to_numpy(),'full_combined_24131':nodes.index.to_numpy()}
    ranks=[]
    for seed in m.SEEDS:
        ranked=sorted(dapp,key=lambda i:hashlib.sha256(f'revision1|{seed}|{nodes.at[i,"path"]}'.encode()).digest())
        ranks.extend(dict(seed=seed,rank=k+1,node_id=int(i)) for k,i in enumerate(ranked))
    m.saveframe(out/'population_ranks.csv.gz',pd.DataFrame(ranks));graphs=0
    for normal in ['legacy','string_aware']:
        edge=pd.read_csv(base/f'{normal}_recovered_20261025/edges.csv');edge=edge[edge.edge_type.eq('normalized_shingle')].copy()
        for cohort,selected in cohorts.items():
            chosen=np.zeros(len(nodes),dtype=bool);chosen[selected]=True
            sub=edge[chosen[edge.left.to_numpy()]&chosen[edge.right.to_numpy()]]
            prov,raw=m.structural_edges(nodes,selected);members=pd.DataFrame({'node_id':selected})
            for threshold in m.THRESHOLDS:
                le=sub[sub.jaccard.ge(threshold)];lex=(le.left.to_numpy(),le.right.to_numpy())
                for policy in m.POLICIES:
                    pairs=[prov] if policy=='project_only' else ([raw,lex] if policy=='clone_only' else [prov,raw,lex])
                    left=np.concatenate([p[0] for p in pairs]);right=np.concatenate([p[1] for p in pairs])
                    cp=m.partition(len(nodes),selected,left,right);graphs+=1
                    members[f'{policy}_{round(threshold*100):03d}']=cp[selected]
                if threshold==.8 and cohort!='full_combined_24131':
                    adj,weights,vertices,vm,links=m.contract_projects(nodes,selected,sub,threshold)
                    m.saveframe(out/f'contracted_edges_{normal}_{cohort}_080.csv.gz',pd.DataFrame([{**r,'left_project':vertices[u],'right_project':vertices[v]} for (u,v),r in links.items()]))
            m.saveframe(out/f'memberships_{normal}_{cohort}.csv.gz',members)
    return GM/'run_20261025_v1',{'recomputed_complete_cohort_partitions':graphs,'population_rank_rows':len(ranks)}

def identity(out):
    frozen=json.loads((GM/'identity_controls_20261025_v1/config_before_compute.json').read_text())
    checks=check_map({str(GM/name):h for name,h in frozen['source_sha256'].items()})+check_map(frozen['input_sha256'])
    preflight(out,'identity',checks,['run unchanged identity_controls.py in fresh child directory; compare every stable output'])
    subprocess.run([sys.executable,str(GM/'identity_controls.py'),'--out',str(out/'recomputed')],cwd=ROOT,check=True)
    return GM/'identity_controls_20261025_v1',{'recomputed_directory':'recomputed'}

def description(out):
    frozen=json.loads((GM/'description_20261025_v1/config_before_describe.json').read_text())
    checks=check_map(frozen['input_sha256'])+check_map({str(GM/'describe_mechanism.py'):frozen['script_sha256'],str(ROOT/'papers/security_evaluation/normalization_audit/solidity_scanner.py'):frozen['scanner_sha256']})
    preflight(out,'description',checks,['run unchanged describe_mechanism.py against original immutable tables; all 24131 raw-source hashes checked by original implementation'])
    subprocess.run([sys.executable,str(GM/'describe_mechanism.py'),'--run',str(GM/'run_20261025_v1'),'--out',str(out/'recomputed')],cwd=ROOT,check=True)
    return GM/'description_20261025_v1',{'recomputed_directory':'recomputed','all_source_hashes_verified_by_original_code':True}

def preflight(out,stage,checks,scope):
    code=[Path(__file__),GM/'run_mechanism.py']
    if stage=='identity':code.append(GM/'identity_controls.py')
    if stage=='description':code.extend([GM/'describe_mechanism.py',ROOT/'papers/security_evaluation/normalization_audit/solidity_scanner.py'])
    m.dump(out/'recovery_config_before_compute.json',{'schema':'graph_artifact_recovery_v1','created_utc':datetime.now(timezone.utc).isoformat(),
      'stage':stage,'scope':scope,'source_hashes':{str(p.relative_to(ROOT)):digest(p) for p in code},'checked_inputs':checks,
      'environment':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__},
      'restoration_policy':'only a previously missing path listed in publication_omissions.json, matching old SHA256 and Git blob SHA1; never overwrite an existing file',
      'no_model_scoring':True,'no_network_or_upload':True})
    for p in code:
        target=out/'executed_source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['graph','identity','description'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--restore-exact-missing',action='store_true');a=p.parse_args()
    out=a.out.resolve();assert out.is_relative_to(ROOT/'data/derived'),str(out);out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    old,detail={'graph':graph,'identity':identity,'description':description}[a.stage](out)
    new=out/'recomputed' if 'recomputed_directory' in detail else out
    summary=json.loads((old/'summary.json').read_text());omissions=json.loads((ROOT/'papers/security_evaluation/revision1/publication_omissions.json').read_text())
    omitted={x['path']:x['git_blob_sha'] for x in omissions['omitted']};rows=[]
    for name,expected in summary['output_sha256'].items():
        candidate=new/name
        if not candidate.exists():continue
        target=old/name;rel=str(target.relative_to(ROOT));actual=digest(candidate)
        row={'original_path':rel,'recomputed_path':str(candidate.relative_to(ROOT)),'expected_sha256':expected,'actual_sha256':actual,
             'sha256_match':actual==expected,'expected_git_blob_sha':omitted.get(rel),'actual_git_blob_sha':blob(candidate),'original_path_existed_before_restore':target.exists(),'restored':False}
        if rel in omitted:
            row['git_blob_sha_match']=row['actual_git_blob_sha']==omitted[rel]
            if a.restore_exact_missing and row['sha256_match'] and row['git_blob_sha_match']:
                if target.exists():assert digest(target)==expected and blob(target)==omitted[rel]
                else:
                    # Exclusive creation makes overwriting another agent's result impossible.
                    with target.open('xb') as f:f.write(candidate.read_bytes())
                    row['restored']=True
        elif target.exists() and name not in ['config_before_compute.json','config_before_describe.json']:
            row['existing_frozen_file_match']=digest(target)==actual
        rows.append(row)
    receipt={'schema':'graph_artifact_recovery_result_v1','stage':a.stage,'status':'complete','created_utc':datetime.now(timezone.utc).isoformat(),
      'runtime_seconds':time.monotonic()-start,'details':detail,'fresh_run_config_sha256':digest(out/'recovery_config_before_compute.json'),
      'comparisons':rows,'restored_files':sum(x['restored'] for x in rows),'no_model_scoring':True,'no_upload':True,
      'provenance':'new local recomputation; byte identity only where both original recorded hashes match; original timings/configurations remain immutable'}
    m.dump(out/'recovery_result.json',receipt)
    print(json.dumps({'stage':a.stage,'restored':receipt['restored_files'],'compared':len(rows),'exact_sha256_matches':sum(x['sha256_match'] for x in rows),'receipt':str(out/'recovery_result.json')}),flush=True)
if __name__=='__main__':main()
