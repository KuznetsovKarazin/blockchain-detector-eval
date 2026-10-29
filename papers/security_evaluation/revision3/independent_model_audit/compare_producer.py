"""Compare independently reconstructed scores/aggregates with producer outputs."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
OUT=HERE/'run_20261029_v1';RUN=ROOT/'papers/security_evaluation/revision3/model_link/run_20261029_v1';PROD=RUN/'analysis'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return pd.read_csv(p,float_precision='round_trip')
def metric_name(name):return name.replace('yield_','findings_')
def main():
 final=json.loads((RUN/'ANALYSIS_COMPLETE.json').read_text());ind=json.loads((OUT/'NUMERIC_RECOMPUTATION_COMPLETE.json').read_text());checks=[];compared=0
 for name,h in final['outputs'].items():assert sha(PROD/name)==h,name
 for name,h in ind['output_sha256'].items():assert sha(OUT/name)==h,name
 def compare(label,a,b,keys,mapping,tolerance=1e-12):
  nonlocal compared
  assert not a.duplicated(keys).any() and not b.duplicated(keys).any(),label
  aa=a.set_index(keys).sort_index();bb=b.set_index(keys).sort_index();assert aa.index.equals(bb.index),(label,'keys')
  maxima={}
  for ac,bc in mapping.items():
   x=aa[ac].to_numpy(dtype=float);y=bb[bc].to_numpy(dtype=float);assert np.array_equal(np.isnan(x),np.isnan(y)),(label,ac,'nan')
   err=np.abs(x-y);maximum=float(np.nanmax(err)) if len(err) and not np.isnan(err).all() else 0.;maxima[ac]=maximum
   assert maximum<=tolerance,(label,ac,maximum,tolerance)
   compared+=len(x)
  checks.append({'table':label,'rows':len(a),'max_absolute_differences':maxima,'tolerance':tolerance})
 a=read(OUT/'independent_metrics.csv.gz');b=read(PROD/'per_fit_frame_metrics.csv.gz');mapping={'n':'n_test','k':'n_positive','ap':'ap'}
 for p in (5,10,20):mapping.update({f'budget_{p}':f'budget_{p}',f'yield_{p}':f'findings_{p}',f'yield_min_{p}':f'findings_min_{p}',f'yield_max_{p}':f'findings_max_{p}'})
 compare('per_fit_frame_metrics',a,b,['job_id','frame'],mapping)
 wide=read(OUT/'composition_seed_means.csv');rows=[]
 for r in wide.to_dict('records'):
  for metric in ['ap','yield_5','yield_10','yield_20']:
   rows.append({'frame':r['frame'],'method':r['method'],'draw':r['draw'],'metric':metric_name(metric),'B_seed_mean':r[metric],'C_seed_mean':r['C_'+metric],'B_minus_C':r['delta_B_minus_C_'+metric],'n_seeds':r['seed_count'],'linked_training_files':r['linked_files_in_B_draw'],'linked_training_positive':r['linked_positive_in_B_draw']})
 compare('composition_seed_means',pd.DataFrame(rows),read(PROD/'composition_seed_means.csv'),['frame','method','draw','metric'],{k:k for k in ['B_seed_mean','C_seed_mean','B_minus_C','n_seeds','linked_training_files','linked_training_positive']})
 a=read(OUT/'composition_ECDF.csv');a['metric']=a.metric.map(metric_name)
 for k in ['strict','weak','midrank']:a['pct_'+k]=100*a['C_ECDF_'+k]
 compare('composition_ecdf',a,read(PROD/'composition_ecdf_summary.csv'),['frame','method','metric'],{'B_mean':'B_mean','C_seed_mean':'C_mean','B_below_C':'B_below_C','B_equal_C':'B_equal_C','pct_strict':'C_strict_percentile','pct_weak':'C_weak_percentile','pct_midrank':'C_midrank_percentile'})
 a=read(OUT/'seed_matched_ECDF.csv');a['metric']=a.metric.map(metric_name)
 for k in ['strict','weak','midrank']:a['pct_'+k]=100*a['C_ECDF_'+k]
 compare('seed_matched_ecdf',a,read(PROD/'seed_matched_ecdf.csv'),['frame','method','seed','metric'],{'C_value':'C_value','B_below_C':'B_below_C','B_equal_C':'B_equal_C','pct_strict':'C_strict_percentile','pct_weak':'C_weak_percentile','pct_midrank':'C_midrank_percentile'})
 a=read(OUT/'dose_summaries.csv');a['metric']=a.metric.map(metric_name);a=a.rename(columns={'nominal_linked_retention_percent':'dose_nominal_percent'})
 compare('dose_composition_summary',a,read(PROD/'dose_composition_summary.csv'),['frame','method','metric','dose_nominal_percent'],{'mean':'mean','min':'min','max':'max','unique_memberships':'unique_compositions'})
 a=read(OUT/'dose_composition_seed_means.csv');a=a.rename(columns={'source_membership':'membership'}).drop_duplicates(['frame','method','membership'])
 compare('dose_seed_averaged_compositions',a,read(PROD/'dose_seed_averaged_compositions.csv'),['frame','method','membership'],{k:metric_name(k) for k in ['ap','yield_5','yield_10','yield_20']})
 a=read(OUT/'random_ranking_references.csv');b=read(PROD/'frame_random_references.csv');mapping={'n':'n_test','k':'n_positive','prevalence':'prevalence','random_distinct_ranking_expected_AP':'random_strict_expected_ap'}
 for p in (5,10,20):mapping.update({f'budget_{p}':f'budget_{p}',f'random_expected_yield_{p}':f'random_expected_findings_{p}'})
 compare('random_ranking_references',a,b,['frame'],mapping)
 a=read(OUT/'secondary_linked_count_correlations.csv');a['linked_variable']=a.predictor.map({'linked_files':'linked_training_files','linked_positive':'linked_training_positive'})
 compare('linked_count_AP_correlations',a,read(PROD/'linked_count_AP_correlations.csv'),['frame','method','linked_variable'],{'pearson_descriptive':'pearson','spearman_descriptive':'spearman'},tolerance=1e-11)
 result={'status':'passed','numeric_cells_compared':compared,'comparison_tables':checks,'producer_analysis_complete_sha256':sha(RUN/'ANALYSIS_COMPLETE.json'),'independent_recomputation_complete_sha256':sha(OUT/'NUMERIC_RECOMPUTATION_COMPLETE.json'),'comparison_source_sha256':sha(Path(__file__)),'scope':'Independent metrics from852savedvectors plusallprespecifiedaggregate comparisons; no model rerun and noIIDinference'}
 (OUT/'PRODUCER_COMPARISON.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':'passed','numeric_cells_compared':compared,'tables':len(checks),'max_abs_difference':max(max(x['max_absolute_differences'].values()) for x in checks)}))
if __name__=='__main__':main()
