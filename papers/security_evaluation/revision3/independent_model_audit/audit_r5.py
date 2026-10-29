"""Independent R5 score audit and aggregation; no producer metric imports."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,re,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from independent_metrics import grouped_metrics,finite_random_ap,formula_check,PERCENTS
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
RUN=ROOT/'papers/security_evaluation/revision3/model_link/run_20261029_v1'
OUT=HERE/'run_20261029_v1'
METHODS=['raw_tfidf_lr','normalized_tfidf_lr','pattern_rf','pattern_lightgbm']
METRICS=['ap']+[f'yield_{p}' for p in PERCENTS]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def load(p):return json.loads(p.read_text())
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def frozen_inputs():return ['FREEZE_BEFORE_FITTING.json','PLAN_BEFORE_FITTING.json','evaluation_frames.json','labels.json','membership_ids.json','pool_ids.json','frame_counts.csv','SECONDARY_ANALYSIS_AMENDMENT.json']
def prepare():
 OUT.mkdir(exist_ok=False)
 plan={'schema':'independent_R5_score_audit_v1','created_utc':datetime.now(timezone.utc).isoformat(),'producer_run':str(RUN.relative_to(ROOT)),'input_sha256':{p:sha(RUN/p) for p in frozen_inputs()},'source_sha256':{p.name:sha(p) for p in [Path(__file__),HERE/'independent_metrics.py',HERE/'test_independent_metrics.py']},'metric_implementation':'Explicit distinct-score groups: AP=sum(group positives/K * cumulative positives/cumulative population). Boundary review ties use all above + boundary slots * boundary positives / boundary size; exact attainable min/max. No producer metric function imports.','random_AP':'H_N/N + (K-1)/(N-1)*(1-H_N/N), K>0,N>1; derived from ranking indicator first/second moments; exhaustively checked for N1..10 all55N,K pairs.','random_review':'b*K/N; b=floor(N*percent/100)','primary_aggregation':'For trees average 5 seed metrics within each of50Bmembership draws; compare50averages toC5seedmean. LR50draws againstoneC. AlsoretainseedmatchedECDFsseparately.','ECDF':'strict=count(B<C)/50;weak=count(B<=C)/50;midrank=(strict+weak)/2; no pvalues','dose':'5 compositions x5levels x4methods x12frames; zero level referencesC_full and is reused, not anewfit orindependentreplicate; showmean/min/max across5seedaveragedcompositions','secondary_correlation':'Pre-specified supplementary amendment, descriptivePearson andrank-Pearson only over50Bcomposition seedmeans; no IIDinference','dependencies':'12nestedoverlappingframes aredescriptiveconditional sensitivity, not12independentfamilies','refit_models':False,'public_write':False}
 dump(OUT/'PLAN_BEFORE_AUDIT.json',plan)
 print('Independent audit prepared; no R5 metric results inspected')
def assert_inputs():
 plan=load(OUT/'PLAN_BEFORE_AUDIT.json')
 for name,h in plan['input_sha256'].items():assert sha(RUN/name)==h,name
 for name,h in plan['source_sha256'].items():assert sha(HERE/name)==h,name
 return plan

def summarize(df,frames,labels,memberships,pools,plan):
 composition=[];ecdfs=[];seed_ecdfs=[];review=[];dose=[];dose_summary=[];correlations=[]
 for frame,ids in frames.items():
  n=len(ids);k=sum(labels[i]['reentrancy'] for i in ids)
  for method in METHODS:
   q=df[(df.frame==frame)&(df.method==method)];expected=1 if method.endswith('tfidf_lr') else 5
   c=q[q.membership=='C_full'];assert len(c)==expected
   cmeans={v:float(c[v].mean()) for v in METRICS}
   b=q[q.membership.str.startswith('B_draw')];groups=b.groupby('membership');assert len(groups)==50 and groups.size().eq(expected).all()
   means=groups[METRICS].mean().sort_index()
   for name,row in means.iterrows():
    linked=sum(i in pools['linked'] for i in memberships[name]);rec={'frame':frame,'method':method,'membership':name,'draw':int(name[6:]),'seed_count':expected,'linked_files_in_B_draw':linked,'linked_positive_in_B_draw':sum(labels[i]['reentrancy'] for i in memberships[name] if i in pools['linked'])}
    for metric in METRICS:rec[metric]=float(row[metric]);rec['C_'+metric]=cmeans[metric];rec['delta_B_minus_C_'+metric]=float(row[metric])-cmeans[metric]
    composition.append(rec)
   for metric in METRICS:
    values=means[metric].to_numpy();cv=cmeans[metric];below=int((values<cv).sum());equal=int((values==cv).sum())
    ecdfs.append({'frame':frame,'method':method,'metric':metric,'n_compositions':50,'seeds_per_composition':expected,'B_mean':float(values.mean()),'B_min':float(values.min()),'B_median':float(np.median(values)),'B_max':float(values.max()),'B_sd_descriptive':float(values.std(ddof=1)),'C_seed_mean':cv,'B_below_C':below,'B_equal_C':equal,'B_above_C':50-below-equal,'C_ECDF_strict':below/50,'C_ECDF_weak':(below+equal)/50,'C_ECDF_midrank':(below+equal/2)/50})
    for seed in sorted(c.seed):
     sv=b[b.seed==seed].sort_values('membership')[metric].to_numpy();assert len(sv)==50;sc=float(c.loc[c.seed==seed,metric].iloc[0]);lo=int((sv<sc).sum());eq=int((sv==sc).sum())
     seed_ecdfs.append({'frame':frame,'method':method,'seed':int(seed),'metric':metric,'C_value':sc,'B_below_C':lo,'B_equal_C':eq,'C_ECDF_strict':lo/50,'C_ECDF_weak':(lo+eq)/50,'C_ECDF_midrank':(lo+eq/2)/50})
   for percent in PERCENTS:
    metric=f'yield_{percent}';values=means[metric].to_numpy();cv=cmeans[metric];budget=n*percent//100
    review.append({'frame':frame,'method':method,'budget_percent':percent,'budget_files':budget,'n':n,'k':k,'random_expected_yield':budget*k/n,'B_mean_yield':float(values.mean()),'B_min_composition_mean':float(values.min()),'B_max_composition_mean':float(values.max()),'C_mean_yield':cv,'B_minus_C_mean_yield':float(values.mean()-cv),'B_draws_above_C':int((values>cv).sum()),'B_draws_below_C':int((values<cv).sum()),'B_draws_equal_C':int((values==cv).sum())})
   for comp in range(5):
    for ds in plan['dose_schedule']:
     pct=ds['nominal_linked_retention_percent'];name='C_full' if pct==0 else f'dose{pct:03d}_composition{comp}';v=q[q.membership==name];assert len(v)==expected
     r={'frame':frame,'method':method,'composition':comp,'nominal_linked_retention_percent':pct,'linked_files':ds['linked_files'],'realized_linked_retention':ds['realized_linked_retention'],'linked_fraction_of_training':ds['linked_fraction_of_training'],'source_membership':name,'seeds':expected,'zero_dose_reuses_C':pct==0}
     for metric in METRICS:r[metric]=float(v[metric].mean());r['C_'+metric]=cmeans[metric];r['delta_vs_C_'+metric]=float(v[metric].mean())-cmeans[metric]
     dose.append(r)
   subset=[r for r in composition if r['frame']==frame and r['method']==method]
   x=np.array([r['linked_files_in_B_draw'] for r in subset]);xp=np.array([r['linked_positive_in_B_draw'] for r in subset]);a=np.array([r['ap'] for r in subset])
   for name,values in [('linked_files',x),('linked_positive',xp)]:
    pearson=float(np.corrcoef(values,a)[0,1]) if np.ptp(values) and np.ptp(a) else None
    rankx=pd.Series(values).rank(method='average').to_numpy();ranky=pd.Series(a).rank(method='average').to_numpy();spearman=float(np.corrcoef(rankx,ranky)[0,1]) if np.ptp(rankx) and np.ptp(ranky) else None
    correlations.append({'frame':frame,'method':method,'predictor':name,'n_compositions':50,'predictor_min':int(values.min()),'predictor_max':int(values.max()),'pearson_descriptive':pearson,'spearman_descriptive':spearman})
 dose_df=pd.DataFrame(dose)
 for (frame,method,pct),g in dose_df.groupby(['frame','method','nominal_linked_retention_percent']):
  assert len(g)==5
  for metric in METRICS:
   v=g[metric].to_numpy();dose_summary.append({'frame':frame,'method':method,'nominal_linked_retention_percent':int(pct),'metric':metric,'composition_count':5,'unique_memberships':g.source_membership.nunique(),'mean':float(v.mean()),'min':float(v.min()),'max':float(v.max()),'delta_C_mean':float(g['delta_vs_C_'+metric].mean()),'positive_differences':int((g['delta_vs_C_'+metric]>0).sum()),'negative_differences':int((g['delta_vs_C_'+metric]<0).sum()),'zero_dose_reuses_C':bool(pct==0)})
 outputs={'composition_seed_means.csv':pd.DataFrame(composition),'composition_ECDF.csv':pd.DataFrame(ecdfs),'seed_matched_ECDF.csv':pd.DataFrame(seed_ecdfs),'all_model_review_budgets.csv':pd.DataFrame(review),'dose_composition_seed_means.csv':dose_df,'dose_summaries.csv':pd.DataFrame(dose_summary),'secondary_linked_count_correlations.csv':pd.DataFrame(correlations)}
 for name,value in outputs.items():value.to_csv(OUT/name,index=False)

def audit():
 own=assert_inputs();complete=load(RUN/'COMPLETE.json');assert complete['physical_fits_attempted']==852 and complete['failed']==0
 frozen=load(RUN/'FREEZE_BEFORE_FITTING.json');plan=load(RUN/'PLAN_BEFORE_FITTING.json');frames=load(RUN/'evaluation_frames.json');labels={int(k):v for k,v in load(RUN/'labels.json').items()};memberships=load(RUN/'membership_ids.json');p=load(RUN/'pool_ids.json');pools={'B':set(p['B']),'C':set(p['C']),'linked':set(p['C_linked_B_minus_C'])}
 assert sha(RUN/'FREEZE_BEFORE_FITTING.json')==complete['freeze_sha256']
 for name,h in frozen['prepared_files'].items():assert sha(RUN/name)==h,name
 assert len(frames)==12 and len(plan['jobs'])==852 and len(memberships)==71
 assert pools['linked']==pools['B']-pools['C']
 giant=frames['giant_primary'];assert len(giant)==5408 and len(set(giant))==5408 and sum(labels[i]['reentrancy'] for i in giant)==83
 assert all(len(ids)==len(set(ids)) and set(ids)<=set(giant) for ids in frames.values())
 rows=[];artifacts=[];warningfits=[];random=[]
 for frame,ids in frames.items():
  n=len(ids);k=sum(labels[i]['reentrancy'] for i in ids);r={'frame':frame,'n':n,'k':k,'prevalence':k/n,'random_distinct_ranking_expected_AP':finite_random_ap(n,k)}
  for percent in PERCENTS:r[f'budget_{percent}']=n*percent//100;r[f'random_expected_yield_{percent}']=(n*percent//100)*k/n
  random.append(r)
 for index,job in enumerate(plan['jobs']):
  folder=RUN/'fits'/job['job_id'];result=load(folder/'result.json');assert sha(folder/'result.json')==complete['result_hashes'][job['job_id']]
  assert result['status']=='ok' and all(result[f]==job[f] for f in ['job_id','method','seed','membership'])
  assert fingerprint([memberships[job['membership']],job['method'],job['seed']])==job['physical_key']
  for name,h in result['artifact_hashes'].items():assert sha(folder/name)==h,(job['job_id'],name)
  with gzip.open(folder/'predictions.csv.gz','rt',newline='') as f:score_rows=list(csv.DictReader(f))
  ids=[int(r['file_id']) for r in score_rows];assert ids==giant and all(r['status']=='ok' for r in score_rows)
  scores={int(r['file_id']):float(r['score']) for r in score_rows};assert all(math.isfinite(v) for v in scores.values())
  resources=load(folder/'resources.json')
  if resources.get('warnings') or resources.get('convergence_warning'):warningfits.append({'job_id':job['job_id'],'warnings':resources.get('warnings',[]),'convergence_warning':resources.get('convergence_warning')})
  for frame,test in frames.items():
   metric=grouped_metrics([labels[i]['reentrancy'] for i in test],[scores[i] for i in test]);rows.append({'job_id':job['job_id'],'membership':job['membership'],'method':job['method'],'seed':job['seed'],'frame':frame,**metric})
  artifacts.append({'job_id':job['job_id'],'prediction_sha256':sha(folder/'predictions.csv.gz'),'result_sha256':sha(folder/'result.json'),'score_count':len(ids)})
  if (index+1)%100==0:print(f'Independently checked {index+1}/852 score vectors',flush=True)
 df=pd.DataFrame(rows);assert len(df)==10224 and len(artifacts)==852
 df.to_csv(OUT/'independent_metrics.csv.gz',index=False,compression='gzip');pd.DataFrame(artifacts).to_csv(OUT/'verified_prediction_hashes.csv',index=False);pd.DataFrame(random).to_csv(OUT/'random_ranking_references.csv',index=False);dump(OUT/'warning_fits.json',warningfits)
 summarize(df,frames,labels,memberships,pools,plan)
 checks={'status':'numeric_recomputation_complete_awaiting_producer_comparison','finished_utc':datetime.now(timezone.utc).isoformat(),'physical_vectors':852,'score_values':852*5408,'AP_values':len(df),'review_budget_values':len(df)*3,'frames':12,'primary_compositions_per_method':50,'overlapping_secondary_frames_are_independent':False,'finite_random_AP_exact_NK_checks':formula_check(),'warning_fit_count':len(warningfits),'producer_complete_sha256':sha(RUN/'COMPLETE.json'),'own_plan_sha256':sha(OUT/'PLAN_BEFORE_AUDIT.json'),'output_sha256':{p.name:sha(p) for p in OUT.iterdir() if p.is_file()}}
 assert_inputs();dump(OUT/'NUMERIC_RECOMPUTATION_COMPLETE.json',checks);print(json.dumps({k:v for k,v in checks.items() if k!='output_sha256'}))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','audit']);a=ap.parse_args();prepare() if a.action=='prepare' else audit()
