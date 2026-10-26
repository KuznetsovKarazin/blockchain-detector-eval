"""Prepare an unscored external protocol and a probability-based human packet.

Raw contracts, annotations and sampling keys stay in ignored data/derived/.
No model is imported or fitted and all human judgment cells remain blank.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'src'))
from bal.data.contracts import load_all,label_files
SEED=2026102501
CLASSES=('reentrancy','unchecked')
POS='source_reported_positive_pending_adjudication'
N_SAMPLE=180
STRATA=['source_id','class','label_status']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def utc():return datetime.now(timezone.utc).isoformat()
def csvout(p,rows,fields):
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def allocate(frame,n=N_SAMPLE):
    """Fixed oversampling of source positives; proportional residual allocation.

    Integer Hamilton remainders are resolved by lexicographic stratum key.
    Allocation uses source status counts only, never human or model outcomes.
    """
    tab=frame.groupby(STRATA,sort=True).size().rename('N_h').reset_index()
    tab['n_h']=[min(int(r.N_h),20 if r.label_status==POS else 5) for r in tab.itertuples()]
    if n<int(tab.n_h.sum()) or n>int(tab.N_h.sum()):raise ValueError('Requested n incompatible with fixed stratum minima/population')
    remaining=n-int(tab.n_h.sum());capacity=tab.N_h-tab.n_h
    if remaining:
        shares=remaining*capacity/capacity.sum();extra=np.floor(shares).astype(int)
        tab.n_h+=extra;left=remaining-int(extra.sum())
        ordering=sorted(range(len(tab)),key=lambda i:(-(shares.iloc[i]-extra.iloc[i]),tuple(tab.loc[i,STRATA])))
        for i in ordering[:left]:tab.loc[i,'n_h']+=1
    assert int(tab.n_h.sum())==n and (tab.n_h>=1).all() and (tab.n_h<=tab.N_h).all()
    tab['inclusion_probability']=tab.n_h/tab.N_h
    tab['design_weight']=tab.N_h/tab.n_h
    return tab

def sample_cases(frame,allocation,seed=SEED):
    rng=np.random.default_rng(seed);pieces=[]
    for row in allocation.itertuples(index=False):
        group=frame[(frame.source_id==row.source_id)&(frame['class']==row[1])&(frame.label_status==row.label_status)].sort_values('path')
        take=rng.choice(len(group),size=row.n_h,replace=False)
        part=group.iloc[np.sort(take)].copy()
        part['N_h']=row.N_h;part['n_h']=row.n_h;part['inclusion_probability']=row.inclusion_probability;part['design_weight']=row.design_weight
        pieces.append(part)
    sample=pd.concat(pieces,ignore_index=True)
    sample=sample.iloc[rng.permutation(len(sample))].reset_index(drop=True)
    sample['case_id']=[f'P{i:03d}' for i in range(1,len(sample)+1)]
    assert not sample[['path','class']].duplicated().any()
    return sample

def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--private',type=Path,required=True)
    a=ap.parse_args();os.chdir(ROOT)
    if a.out.exists() or a.private.exists():raise FileExistsError('Fresh public/private directories required')
    if not a.private.resolve().is_relative_to((ROOT/'data/derived').resolve()):raise ValueError('Private keys must stay under ignored data/derived')
    a.out.mkdir(parents=True);a.private.mkdir(parents=True)
    source_audit=ROOT/'papers/security_evaluation/external_audit/source_audit_full_20261025'
    graph=ROOT/'papers/security_evaluation/dependency_audit/string_aware_recovered_20261025'
    private_labels=ROOT/'data/derived/security_external_recovered_20261025/provisional_label_manifest.csv'
    cfg={'schema':'external_probability_review_plan_v1','created_utc':utc(),'status':'prepared_before_human_judgments_and_external_scores',
      'sampling_frame':'fixed1998provisionalfiles by2primaryclasses=3996cases;17unresolvedidentities excluded',
      'sample_size':N_SAMPLE,'strata':STRATA,'randomization':'independent simple random sampling without replacement within strata; numpy default_rng then random case order',
      'seed':SEED,'allocation':'min(N_h,20)source-positive or min(N_h,5)other; remaining slots proportional residual capacity; Hamilton rounding; lexicographic ties',
      'selection_uses_source_annotations':True,'selection_uses_human_judgments':False,'selection_uses_model_scores':False,
      'two_reviewers':'both independently assess every probability case; names pending, no scores/source-label key supplied',
      'additional_identity_cases':'17quarantinedsourceissues census, separate frame and purpose, not added to corpus-error denominator',
      'existing_purposive_106_packet':'preserved unchanged; not pooled with probabilitysample',
      'external_scoring_allowed':False,'human_judgments_generated':0}
    dump(a.out/'sampling_plan_before_selection.json',cfg)
    meta=pd.read_csv(source_audit/'candidate_source_metadata.csv',keep_default_na=False)
    duplicated=meta.contract_id.str.lower().duplicated(keep=False)|meta.file_hash.duplicated(keep=False)
    cohort=meta[(meta.source_id!='smartbugs_curated')&(meta.reconciliation=='matched')&~duplicated].copy()
    assert len(cohort)==1998 and cohort.path.is_unique
    labels=pd.read_csv(private_labels,keep_default_na=False)
    frame=labels.merge(cohort[['path','source_id']],on='path',validate='many_to_one')
    assert len(frame)==3996 and set(frame['class'])==set(CLASSES) and frame.binary_target.eq('').all()
    assert not frame.label_status.str.startswith('unknown_unresolved').any()
    allocation=allocate(frame);sample=sample_cases(frame,allocation)
    allocation.to_csv(a.out/'stratum_allocation.csv',index=False)
    sample[['case_id','path','source_id','class','label_status','label_source','N_h','n_h','inclusion_probability','design_weight']].to_csv(a.private/'coordinator_sampling_key.csv',index=False)
    # Full sources are private and renamed; original source/status labels are withheld.
    sources=a.private/'blinded_sources';sources.mkdir()
    rows=[]
    for r in sample.itertuples():
        path=ROOT/'data/raw/salzano'/r.path;destination=sources/(r.case_id+'.sol');shutil.copy2(path,destination)
        rows.append({'case_id':r.case_id,'class':getattr(r,'_1',None)})
    # Avoid tuple column-renaming ambiguity for the reserved name class.
    blank=[{'case_id':r['case_id'],'class':r['class'],'code_ref':'blinded_sources/'+r['case_id']+'.sol',
      'reviewer_id':'','reviewed_utc':'','judgment_positive_negative_unknown':'','affected_lines':'','compiler_assumptions':'',
      'exploit_preconditions':'','reason':'','uncertainty_or_missing_context':'','time_minutes':'','source_label_reveal_detected':''} for _,r in sample.iterrows()]
    fields=list(blank[0])
    for reviewer in [1,2]:
        csvout(a.out/f'reviewer_{reviewer}_blank.csv',blank,fields)
        shutil.copy2(a.out/f'reviewer_{reviewer}_blank.csv',a.private/f'reviewer_{reviewer}_working.csv')
    final=[{'case_id':r['case_id'],'class':r['class'],'reviewer_1_judgment':'','reviewer_2_judgment':'',
            'adjudicated_judgment':'','adjudicator_id':'','adjudication_reason':'','adjudicated_utc':''} for _,r in sample.iterrows()]
    csvout(a.out/'adjudication_blank.csv',final,list(final[0]))
    issues=pd.read_csv(source_audit/'reconciliation_issues.csv',keep_default_na=False);assert len(issues)==17
    issuekey=issues.copy();issuekey.insert(0,'identity_case_id',[f'Q{i:02d}' for i in range(1,18)])
    issuekey.to_csv(a.private/'quarantined_identity_key.csv',index=False)
    identity=[{'identity_case_id':x,'reviewer_id':'','identity_resolution':'','evidence_reference':'',
               'proposed_correction':'','reason':'','reviewed_utc':'','cohort_reentry_allowed':'no'} for x in issuekey.identity_case_id]
    for reviewer in [1,2]:csvout(a.out/f'identity_reviewer_{reviewer}_blank.csv',identity,list(identity[0]))
    # Inspect raw source and graph hashes, then export metadata-only test/train manifests.
    nodes=pd.read_csv(graph/'nodes.csv',keep_default_na=False);membership=pd.read_csv(graph/'memberships.csv')
    nodegraph=nodes.merge(membership[['node_id','address_expanded_080']],on='node_id',validate='one_to_one')
    ext=nodegraph[(nodegraph.scope=='external')&nodegraph.candidate_test.astype(str).str.lower().eq('true')]
    assert len(ext)==1998 and set(ext.path)==set(cohort.path)
    assert set(ext.file_sha256)==set(cohort.file_hash)
    test_manifest=cohort[['source_id','source_commit','path','file_hash','compiler_range','reconciliation']].merge(ext[['path','node_id','address_expanded_080']],on='path',validate='one_to_one')
    test_manifest.to_csv(a.out/'external_cohort_manifest.csv',index=False)
    exclusion=pd.read_csv(graph/'training_exclusion_address_expanded_080.csv')
    train=exclusion[(exclusion.dataset=='dappscan')&exclusion.usable_training].copy();assert len(train)==691
    all_data=load_all();all_data['file_id']=range(len(all_data))
    train=train.merge(all_data[['file_id','path','reentrancy','unchecked']],on='path',validate='one_to_one')
    assert int(train.reentrancy.sum())==23 and int(train.unchecked.sum())==18
    assert not set(train.component)&set(ext.address_expanded_080)
    train['file_sha256']=[sha(ROOT/p) for p in train.path]
    train[['file_id','node_id','dataset','path','component','file_sha256','reason']].to_csv(a.out/'training_manifest.csv',index=False)
    exclusion[exclusion.dataset=='dappscan'].to_csv(a.out/'training_exclusion_manifest.csv',index=False)
    # Training proxies and all source annotation contents remain private.
    train[['file_id','path','reentrancy','unchecked']].to_csv(a.private/'training_proxy_key.csv',index=False)
    provenance={'annotation_lineage':'sourceCSV -> source-key reconciliation -> fixed provisionalcohort -> class-status adapter -> sampledcase; deterministic provenance is not correctness validation',
      'source_annotation_values_human_validated':False,'human_judgments_completed':0,'case_unit':'file by vulnerabilityclass',
      'probability_cases':len(sample),'unique_sampled_files':int(sample.path.nunique()),'strata':len(allocation),
      'identities_quarantined':17,'separate_identity_cases':17,'two_initial_reviews_per_case':True,
      'training_files':691,'training_proxy_positive_counts':{'reentrancy':23,'unchecked':18},
      'training_external_graph_component_intersection':0,
      'source_test_files':1998,'source_test_cases':3996,
      'data_commits':{x:git(ROOT/'data/raw'/x,'rev-parse','HEAD') for x in ['salzano','DAppSCAN','smartbugs-curated','SolidiFI-benchmark']},
      'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [source_audit/'candidate_source_metadata.csv',source_audit/'reconciliation_issues.csv',private_labels,graph/'nodes.csv',graph/'memberships.csv',graph/'training_exclusion_address_expanded_080.csv']},
      'source_code_sha256':sha(Path(__file__)),'private_sampling_key_sha256':sha(a.private/'coordinator_sampling_key.csv'),
      'private_data_root':str(a.private),'private_rows_and_source_not_for_redistribution':True,
      'reviewer_names':{'reviewer_1':None,'reviewer_2':None,'adjudicator':None},
      'external_scoring_allowed':False,'model_fits_executed':0}
    dump(a.out/'packet_manifest.json',provenance)
    shutil.copy2(Path(__file__),a.out/'executed_build_packet.py')
    dump(a.out/'public_file_hashes.json',{p.name:sha(p) for p in sorted(a.out.iterdir()) if p.is_file()})
    print(json.dumps({k:provenance[k] for k in ['probability_cases','unique_sampled_files','strata','identities_quarantined','training_files','training_proxy_positive_counts','external_scoring_allowed']}))
    print(allocation.to_string(index=False))


if __name__=='__main__':main()
