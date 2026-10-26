"""Validate fixed B input bytes/pins and lexical/compile-plan readiness only.

No training labels, human judgments, vocabulary fitting or model scores are read.
Lexical readiness is not analysis success, compiler coverage or model coverage.
"""
import argparse,hashlib,importlib.metadata,json,os,shutil,subprocess,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(Path(__file__).resolve().parent));import compiler_policy as cp
sys.path.insert(0,str(ROOT/'src'));from bal.features.contract_features import TOKEN_RE
sys.path.insert(0,str(ROOT/'papers/security_evaluation/normalization_audit'))
from solidity_scanner import scan_comments,corrected_normalised_text,SolidityScanError
PINS={'DAppSCAN':'66a56619c44770e05c2db600fa6468115ff0dcd5','salzano':'da079440bf2cf4fd803c864ef29aeea8a3da50c3','smartbugs-curated':'230e649123477eff332742a59a1c7cc6dc286cab','SolidiFI-benchmark':'4b0573e1b3f7031396de6f48f7f3e7380222ad3a'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(p,*a):return subprocess.check_output(['git','-C',str(p),*a],text=True).strip()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--packet',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();os.chdir(ROOT)
    if a.out.exists():raise FileExistsError(a.out)
    a.out.mkdir(parents=True)
    receipt=json.loads((a.packet/'public_file_hashes.json').read_text())
    for name,want in receipt.items():assert sha(a.packet/name)==want,name
    pins={}
    for name,pin in PINS.items():
        p=ROOT/'data/raw'/name;head=git(p,'rev-parse','HEAD');clean=not git(p,'status','--porcelain')
        if head!=pin or not clean:raise ValueError('Changed upstream '+name)
        pins[name]={'commit':head,'clean':clean}
    train=pd.read_csv(a.packet/'training_manifest.csv');test=pd.read_csv(a.packet/'external_cohort_manifest.csv')
    assert len(train)==691 and len(test)==1998 and not set(train.component)&set(test.address_expanded_080)
    rows=[];plans=[]
    for cohort,frame in [('train',train),('external',test)]:
        for r in frame.itertuples():
            p=ROOT/r.path if cohort=='train' else ROOT/'data/raw/salzano'/r.path
            want=r.file_sha256 if cohort=='train' else r.file_hash
            if sha(p)!=want:raise ValueError('Changed source '+str(p))
            b=p.read_bytes();status='lexical_ready';error='';raw_n=norm_n=None
            try:
                source=b.decode('utf-8');raw_n=len(TOKEN_RE.findall(scan_comments(source).text));norm_n=len(corrected_normalised_text(source).split())
                if raw_n==0 or norm_n==0:status='empty_token_stream'
                plan=cp.strict_compile_plan(source)
            except UnicodeDecodeError as e:status='decode_error';error=str(e);plan={'status':'decode_error','candidates':[]}
            except SolidityScanError as e:status='scanner_error';error=str(e);plan={'status':'scanner_error','candidates':[]}
            rows.append({'cohort':cohort,'path':r.path,'source_sha256':want,'source_bytes':len(b),'lexical_readiness':status,'raw_token_count':raw_n,'normalized_token_count':norm_n,'error':error})
            plans.append({'cohort':cohort,'path':r.path,'status':plan['status'],'candidate_versions':'|'.join(plan['candidates']),'outside_pragma':False,'executed':False})
    pd.DataFrame(rows).to_csv(a.out/'input_readiness.csv',index=False);pd.DataFrame(plans).to_csv(a.out/'compiler_plans.csv',index=False)
    candidates=sorted(set(v for p in plans for v in p['candidate_versions'].split('|') if v))
    binaries=[]
    for v in candidates:
        p=Path.home()/'.solc-bin'/('solc-'+v)
        binaries.append({'version':v,'expected_local_path':str(p),'installed_file_present':p.is_file(),'sha256':sha(p) if p.is_file() else None})
    try:slither=importlib.metadata.version('slither-analyzer')
    except importlib.metadata.PackageNotFoundError:slither=None
    source_paths=[Path(__file__),Path(cp.__file__),ROOT/'scripts/c3_slither_baseline.py',ROOT/'papers/security_evaluation/normalization_audit/solidity_scanner.py',ROOT/'src/bal/features/contract_features.py']
    snap=a.out/'source_snapshot';snap.mkdir()
    for p in source_paths:shutil.copy2(p,snap/p.name)
    summary={'schema':'external_B_input_readiness_v1','source_files':len(rows),'upstream_pins':pins,
      'counts':pd.DataFrame(rows).groupby(['cohort','lexical_readiness']).size().rename('n').reset_index().to_dict('records'),
      'compiler_plan_counts':pd.DataFrame(plans).groupby(['cohort','status']).size().rename('n').reset_index().to_dict('records'),
      'catalog_last_patch':cp.legacy.LAST_PATCH,'catalog_origin':'historical pinned scripts/c3_slither_baseline.py; not a claim of newest releases',
      'slither_installed_version':slither,'required_slither_version':'0.11.6','compiler_binary_inventory':binaries,
      'readiness_scope':'source decoding/scanner and deterministic compiler planning only; not compile/tool/model coverage',
      'training_labels_read':False,'human_judgments_read':False,'model_scores_read':False,'models_fitted':0,'vocabularies_fitted':0,'compiler_or_slither_executed':False,
      'feature_transform_fit_policy':'future fit vectorizer/scaler on training691 only, then transform external1998 without fit',
      'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in source_paths},
      'input_manifest_sha256':{n:sha(a.packet/n) for n in ['training_manifest.csv','external_cohort_manifest.csv']},
      'output_sha256':{n:sha(a.out/n) for n in ['input_readiness.csv','compiler_plans.csv']}}
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ['source_files','counts','compiler_plan_counts','slither_installed_version','models_fitted','vocabularies_fitted']}))
if __name__=='__main__':main()
