"""Complete R5 descriptive metrics and ECDFs; no model fitting or hypothesis tests."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')


def metrics(y,s):
    order=np.argsort(-s,kind='stable');ss=s[order];yy=y[order];n=len(y);k=int(y.sum())
    ends=np.r_[np.flatnonzero(ss[1:]!=ss[:-1]),n-1];tp=np.cumsum(yy)[ends];increments=np.diff(np.r_[0,tp])
    ap=float(np.sum(increments/k*tp/(ends+1)))
    reference=float(average_precision_score(y,s))
    if abs(ap-reference)>1e-14:raise ValueError('Manual group AP disagrees with sklearn')
    result={'ap':ap,'ap_manual_sklearn_difference':abs(ap-reference)}
    for f in [5,10,20]:
        b=n*f//100;cut=ss[b-1];above=ss>cut;tie=ss==cut;a=int(above.sum());t=int(tie.sum());pa=int(yy[above].sum());pt=int(yy[tie].sum());slots=b-a
        expected=pa+pt*slots/t;lo=pa+max(0,slots-(t-pt));hi=pa+min(slots,pt)
        result.update({f'budget_{f}':b,f'findings_{f}':expected,f'findings_min_{f}':lo,f'findings_max_{f}':hi,f'precision_{f}':expected/b,f'recall_{f}':expected/k,f'boundary_tie_files_{f}':t,f'boundary_tie_slots_{f}':slots})
    return result


def ecdf(x,c):
    x=np.asarray(x,dtype=float);lo=int((x<c).sum());eq=int((x==c).sum());hi=lo+eq
    return {'n_B_compositions':len(x),'B_below_C':lo,'B_equal_C':eq,'B_at_or_below_C':hi,'C_strict_percentile':100*lo/len(x),'C_weak_percentile':100*hi/len(x),'C_midrank_percentile':100*(lo+.5*eq)/len(x)}


def summarize_values(x):
    x=np.asarray(x,dtype=float)
    return {'mean':float(x.mean()),'median':float(np.median(x)),'min':float(x.min()),'q05':float(np.quantile(x,.05)),'q25':float(np.quantile(x,.25)),'q75':float(np.quantile(x,.75)),'q95':float(np.quantile(x,.95)),'max':float(x.max()),'sd':float(x.std(ddof=1)) if len(x)>1 else 0.}


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();r=a.run;out=r/'analysis'
    if out.exists():raise ValueError('Analysis directory already exists')
    complete=json.loads((r/'COMPLETE.json').read_text());freeze=json.loads((r/'FREEZE_BEFORE_FITTING.json').read_text());plan=json.loads((r/'PLAN_BEFORE_FITTING.json').read_text())
    if complete['physical_fits_attempted']!=852:raise ValueError('Incomplete attempts')
    if complete['failed']:raise ValueError('Failed fits retained; full-grid summaries require explicit incomplete-data report, not silent deletion')
    if sha(r/'FREEZE_BEFORE_FITTING.json')!=complete['freeze_sha256']:raise ValueError('Freeze changed')
    for path,h in freeze['prepared_files'].items():
        if sha(r/path)!=h:raise ValueError('Frozen file changed')
    for path,h in freeze['source_hashes'].items():
        if sha(r/'code_snapshot'/path)!=h:raise ValueError('Frozen code copy changed')
    prefix=json.loads((r/'R4_PREFIX_COMPATIBILITY.json').read_text())
    if not prefix['all_passed']:raise ValueError('R4 replay compatibility failed')
    frames=json.loads((r/'evaluation_frames.json').read_text());memberships=json.loads((r/'membership_ids.json').read_text());labels={int(k):v for k,v in json.loads((r/'labels.json').read_text()).items()};pools=json.loads((r/'pool_ids.json').read_text());linked=set(pools['C_linked_B_minus_C'])
    primary=frames['giant_primary'];offset={fid:i for i,fid in enumerate(primary)};indices={name:np.array([offset[i] for i in ids]) for name,ids in frames.items()};ys={name:np.array([labels[i]['reentrancy'] for i in ids]) for name,ids in frames.items()}
    out.mkdir();rows=[];resources=[];warnings=Counter();convergence=0;verified_hashes=0
    for j in plan['jobs']:
        folder=r/'fits'/j['job_id'];result=json.loads((folder/'result.json').read_text())
        if sha(folder/'result.json')!=complete['result_hashes'][j['job_id']]:raise ValueError('Result changed')
        for path,h in result['artifact_hashes'].items():
            if sha(folder/path)!=h:raise ValueError('Artifact changed')
            verified_hashes+=1
        pred=pd.read_csv(folder/'predictions.csv.gz',float_precision='round_trip')
        if pred.file_id.tolist()!=primary or not pred.status.eq('ok').all() or not np.isfinite(pred.score).all():raise ValueError('Invalid prediction coverage')
        scores=pred.score.to_numpy();train=memberships[j['membership']];q=sum(i in linked for i in train);qp=sum(i in linked and labels[i]['reentrancy'] for i in train)
        for name,ix in indices.items():
            record={'job_id':j['job_id'],'membership':j['membership'],'method':j['method'],'seed':j['seed'],'frame':name,'n_test':len(ix),'n_positive':int(ys[name].sum()),'linked_training_files':q,'linked_training_positive':qp}
            record.update(metrics(ys[name],scores[ix]));rows.append(record)
        res=json.loads((folder/'resources.json').read_text());warnings.update(res['warnings']);convergence+=bool(res['convergence_warning']);resources.append({'job_id':j['job_id'],**{k:res[k] for k in ['total_seconds','train_preprocessing_seconds','test_preprocessing_seconds','fit_seconds','predict_seconds','n_features','convergence_warning']}})
    d=pd.DataFrame(rows);d.to_csv(out/'per_fit_frame_metrics.csv.gz',index=False,compression={'method':'gzip','mtime':0});pd.DataFrame(resources).to_csv(out/'physical_fit_resources.csv',index=False)
    frame_rows=[]
    for name,y in ys.items():
        n=len(y);k=int(y.sum());h=float(np.sum(1/np.arange(1,n+1)))
        z={'frame':name,'n_test':n,'n_positive':k,'prevalence':k/n,'random_strict_expected_ap':h/n+(k-1)*(n-h)/(n*(n-1))}
        for f in [5,10,20]:z.update({f'budget_{f}':n*f//100,f'random_expected_findings_{f}':(n*f//100)*k/n})
        frame_rows.append(z)
    pd.DataFrame(frame_rows).to_csv(out/'frame_random_references.csv',index=False)
    metricnames=['ap','findings_5','findings_10','findings_20'];compositions=[];ecdfs=[];seed_ecdfs=[];seed_distributions=[];dose_rows=[];correlations=[]
    for (frame,method),g in d.groupby(['frame','method']):
        C=g[g.membership.eq('C_full')].set_index('seed');B=g[g.membership.str.startswith('B_draw')].copy();B['draw']=B.membership.str.removeprefix('B_draw').astype(int)
        ns=1 if method.endswith('tfidf_lr') else 5
        assert len(C)==ns and len(B)==50*ns
        for metric in metricnames:
            c=float(C[metric].mean());bm=B.groupby('draw')[metric].mean();assert len(bm)==50
            for draw,b in bm.items():
                source=B[B.draw.eq(draw)].iloc[0];compositions.append({'frame':frame,'method':method,'metric':metric,'draw':draw,'B_seed_mean':b,'C_seed_mean':c,'B_minus_C':b-c,'n_seeds':ns,'linked_training_files':int(source.linked_training_files),'linked_training_positive':int(source.linked_training_positive)})
            stats=summarize_values(bm.to_numpy()-c)
            row={'frame':frame,'method':method,'metric':metric,'B_mean':float(bm.mean()),'C_mean':c,'n_seeds':ns,**ecdf(bm.to_numpy(),c),**{'difference_'+k:v for k,v in stats.items()},'positive_compositions':int((bm>c).sum()),'negative_compositions':int((bm<c).sum())};ecdfs.append(row)
            for seed,cr in C.iterrows():
                br=B[B.seed.eq(seed)][metric].to_numpy();assert len(br)==50
                seed_ecdfs.append({'frame':frame,'method':method,'metric':metric,'seed':int(seed),'C_value':float(cr[metric]),'B_mean_at_seed':float(br.mean()),**ecdf(br,float(cr[metric]))})
                seed_distributions.append({'frame':frame,'method':method,'metric':metric,'seed':int(seed),'C_value':float(cr[metric]),'B_mean_over_50_compositions':float(br.mean())})
            dose_rows.append({'frame':frame,'method':method,'metric':metric,'dose_nominal_percent':0,'linked_files':0,'linked_retention':0.,'linked_fraction_training':0.,'unique_compositions':1,'n_seeds':ns,**summarize_values([c])})
            for percent,q,qp in [(25,118,2),(50,236,4),(75,353,5),(100,471,7)]:
                sub=g[g.membership.str.startswith(f'dose{percent:03d}_')].copy();sub['composition']=sub.membership.str.rsplit('composition',n=1).str[-1].astype(int);assert len(sub)==5*ns
                means=sub.groupby('composition')[metric].mean();assert len(means)==5
                dose_rows.append({'frame':frame,'method':method,'metric':metric,'dose_nominal_percent':percent,'linked_files':q,'linked_retention':q/471,'linked_fraction_training':q/708,'unique_compositions':5,'n_seeds':ns,**summarize_values(means.to_numpy())})
        bm=B.groupby('draw').agg(ap=('ap','mean'),linked_training_files=('linked_training_files','first'),linked_training_positive=('linked_training_positive','first'))
        for variable in ['linked_training_files','linked_training_positive']:
            x=bm[variable];y=bm.ap
            correlations.append({'frame':frame,'method':method,'n_compositions':50,'n_seeds_averaged':ns,'linked_variable':variable,'pearson':float(x.corr(y)) if x.nunique()>1 else None,'spearman':float(x.rank(method='average').corr(y.rank(method='average'))) if x.nunique()>1 else None,'interpretation':'secondary descriptive association; no p-value or causal claim'})
    pd.DataFrame(compositions).to_csv(out/'composition_seed_means.csv',index=False)
    pd.DataFrame(ecdfs).to_csv(out/'composition_ecdf_summary.csv',index=False)
    pd.DataFrame(seed_ecdfs).to_csv(out/'seed_matched_ecdf.csv',index=False)
    pd.DataFrame(seed_distributions).to_csv(out/'separate_seed_distribution.csv',index=False)
    pd.DataFrame(dose_rows).to_csv(out/'dose_composition_summary.csv',index=False)
    pd.DataFrame(correlations).to_csv(out/'linked_count_AP_correlations.csv',index=False)
    # Preserve individual dose compositions after seed averaging, not just summaries.
    dose=d[d.membership.str.startswith('dose')|d.membership.eq('C_full')]
    dose.groupby(['frame','method','membership'],as_index=False)[metricnames+['linked_training_files','linked_training_positive']].mean().to_csv(out/'dose_seed_averaged_compositions.csv',index=False)
    # The complete four-method by three-budget primary table includes direction reversals.
    main_summary=pd.DataFrame(ecdfs);main_summary[main_summary.frame.eq('giant_primary')&main_summary.metric.ne('ap')].to_csv(out/'primary_review_budget_table.csv',index=False)
    main_summary[main_summary.frame.eq('giant_primary')&main_summary.metric.eq('ap')].to_csv(out/'primary_AP_table.csv',index=False)
    receipt={'schema':'r5_all_planned_descriptive_analysis_complete_v1','analysis_source_sha256':sha(__file__),'complete_sha256':sha(r/'COMPLETE.json'),'physical_prediction_vectors':len(plan['jobs']),'prediction_values':len(plan['jobs'])*5408,'evaluation_frames':len(frames),'AP_checks':len(d),'budget_cells':len(d)*3,'artifact_hashes_verified':verified_hashes,'maximum_manual_sklearn_AP_difference':float(d.ap_manual_sklearn_difference.max()),'convergence_warning_fits':convergence,'warning_counts_physical':dict(warnings),'composition_ECDF_denominator':50,'seed_rows_are_not_independent_compositions':True,'secondary_tests_are_nested_not_independent_families':True,'hypothesis_tests':False,'outputs':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
    dump(r/'ANALYSIS_COMPLETE.json',receipt);print(json.dumps({k:v for k,v in receipt.items() if k!='outputs'},indent=2))


if __name__=='__main__':main()
