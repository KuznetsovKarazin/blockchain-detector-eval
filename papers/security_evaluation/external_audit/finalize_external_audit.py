#!/usr/bin/env python3
"""Preserve executed code, export unlabelled provenance, and check audit outputs.

Diagnostic cohort filters are not a frozen external test. No models or scores.
"""
import argparse
import json
import shutil
from pathlib import Path
import pandas as pd
import scipy
from audit_external_sources import ROOT, CLASSES, load_all, normalised_text, git, sha, write_csv, write_json

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--audit',type=Path,required=True);ap.add_argument('--private',type=Path,required=True)
    args=ap.parse_args();summary=json.loads((args.audit/'summary.json').read_text())
    script=Path(__file__).with_name('audit_external_sources.py')
    assert sha(script.read_bytes())==summary['script_sha256']
    snapshot=args.audit/'executed_source';snapshot.mkdir(exist_ok=False)
    shutil.copy2(script,snapshot/script.name)
    for name,expected in summary['imported_source_sha256'].items():
        p=ROOT/name;assert sha(p.read_bytes())==expected
        target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    external=pd.read_csv(args.audit/'candidate_source_metadata.csv',keep_default_na=False)
    labels=pd.read_csv(args.private/'provisional_label_manifest.csv',keep_default_na=False)
    df=load_all(max_unlabelled_per_project=None);ref=[]
    for _,r in df.iterrows():
        p=Path(r['path']);b=p.read_bytes();ref.append({'dataset':r['dataset'],'path':r['path'],
          'project_id':r['group'],'file_hash':sha(b),'normalized_hash':sha(normalised_text(r['source']).encode()),'bytes':len(b)})
    write_csv(args.audit/'upstream_source_metadata.csv',ref)
    repeated=external.contract_id.str.lower().duplicated(keep=False)|external.file_hash.duplicated(keep=False)
    stages=[('all_candidate_paths',external),('after_excluding_previously_used_curated_source',external[external.source_id!='smartbugs_curated'])]
    stages.append(('after_quarantining_source_reconciliation_issues',stages[-1][1].query('reconciliation=="matched"')))
    stages.append(('after_quarantining_repeated_identifiers_or_exact_source_identity',stages[-1][1][~repeated.loc[stages[-1][1].index]]))
    flow=[]
    for name,subset in stages:
        lab=labels.merge(subset[['path','proxy_dependency_component_080']],on='path')
        for cls in CLASSES:
            lc=lab[lab['class']==cls];pos=lc[lc.label_status=='source_reported_positive_pending_adjudication']
            flow.append({'diagnostic_stage':name,'class':cls,'files':len(subset),'coverage_of_all_paths':len(subset)/len(external),
              'source_reported_positive_files_pending_review':len(pos),'positive_proxy_components_080':pos.proxy_dependency_component_080.nunique(),
              'all_proxy_components_080':subset.proxy_dependency_component_080.nunique(),'unknown_source_identity_or_location':int(lc.label_status.str.startswith('unknown').sum()),
              'direct_normalized_overlap_with_upstream':int(subset.normalized_historical_match.sum()),
              'direct_jaccard_ge_080_overlap_with_upstream':int(subset.direct_historical_jaccard_ge_080.sum())})
    write_csv(args.audit/'diagnostic_cohort_flow.csv',flow)
    identities=external[repeated][['source_id','path','contract_id','file_hash']].copy()
    identities['reason']='repeated_lowercase_identifier_or_exact_source_hash_pending_source_reconciliation'
    identities.to_csv(args.audit/'identity_reconciliation_candidates.csv',index=False)
    edges=pd.read_csv(args.audit/'near_overlap_edges.csv')
    sample=edges.sample(n=min(100,len(edges)),random_state=20261025)
    def tokset(path):
        t=normalised_text(path.read_text(encoding='utf-8',errors='replace')).split()
        return {tuple(t[i:i+5]) for i in range(max(1,len(t)-4))}
    for _,e in sample.iterrows():
        a=tokset(ROOT/'data/raw/salzano'/e.external_path);b=tokset(ROOT/e.other_path)
        assert abs(len(a&b)/len(a|b)-e.jaccard)<1e-12
    exact=pd.read_csv(args.audit/'file_hash_matches.csv');normal=pd.read_csv(args.audit/'normalized_hash_matches.csv')
    near_pairs=set(zip(edges.external_path,edges.other_path))
    assert set(zip(exact.external_path,exact.training_path))<=near_pairs
    assert set(zip(normal.external_path,normal.training_path))<=near_pairs
    assert len(external)==2181 and len(ref)==21950 and not external.path.duplicated().any()
    assert sum(summary['candidate_proxy_component_sizes_080'].values())==len(external)
    packet=args.audit/'review_packet';packet.mkdir(exist_ok=False)
    for name in ['blind_review_cases.csv','second_reviewer_assignment.csv']:shutil.copy2(args.private/name,packet/name)
    statuses={}
    for name in ['salzano','DAppSCAN','smartbugs-curated','SolidiFI-benchmark']:
        repo=ROOT/'data/raw'/name;status=git(repo,'status','--porcelain')
        statuses[name]={'commit':git(repo,'rev-parse','HEAD'),'porcelain_status':status,'clean':status==''}
    assert all(x['clean'] for x in statuses.values())
    out={'schema':'p1_external_audit_postcheck_v1','audit_summary_sha256':sha((args.audit/'summary.json').read_bytes()),
       'postprocessor_sha256':sha(Path(__file__).read_bytes()),'source_clean_status':statuses,
       'checks':{'literal_tuple_jaccard_edges_checked':len(sample),'exact_pairs_present_in_near_edges':len(exact),
                 'normalized_pairs_present_in_near_edges':len(normal),'unique_source_paths':2181,'all_uncapped_reference_paths':21950},
       'candidate_cohort_status':'diagnostic_not_frozen_not_independence_verified',
       'source_identity_policy':'Conservatively quarantine repeated lowercase identifiers or raw-source hashes; no silent row reassignment or source-priority deduplication.',
       'normalization_limitations':['Identifier/numeric literal collapse is not semantic equivalence.',
         'Legacy regex comment removal may strip // or /* inside Solidity string literals; these lexical groups require sensitivity checks before protocol freeze.',
         'No SPDX identifier observed; absence is not a legal determination, and redistribution remains unresolved.'],
       'reference_metadata_sha256':sha((args.audit/'upstream_source_metadata.csv').read_bytes()),
       'environment':{'scipy':scipy.__version__},'diagnostic_flow':flow}
    write_json(args.audit/'postcheck.json',out)
    print(json.dumps({'checks':out['checks'],'diagnostic_flow':flow},indent=2))
if __name__=='__main__':main()
