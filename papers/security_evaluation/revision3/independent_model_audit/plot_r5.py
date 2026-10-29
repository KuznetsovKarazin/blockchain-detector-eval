"""Publication figures from independently verified R5 metrics only."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator,PercentFormatter
HERE=Path(__file__).resolve().parent;OUT=HERE/'run_20261029_v1'
NAMES={'raw_tfidf_lr':'Raw-token logistic regression','normalized_tfidf_lr':'Normalized-token logistic regression','pattern_rf':'Pattern random forest','pattern_lightgbm':'Pattern LightGBM'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(fig,path):
 for ext in ('png','pdf','svg'):fig.savefig(path.with_suffix('.'+ext),dpi=240)
 plt.close(fig)
def main():
 # Producer comparison must pass before any model-result figure is exported.
 check=json.loads((OUT/'PRODUCER_COMPARISON.json').read_text());assert check['status']=='passed'
 paths=[OUT/n for n in ['composition_seed_means.csv','composition_ECDF.csv','dose_composition_seed_means.csv','random_ranking_references.csv','all_model_review_budgets.csv']]
 comp,ecdf,dose,random,review=[pd.read_csv(p) for p in paths]
 primary=comp[comp.frame.eq('giant_primary')];rank=ecdf[ecdf.frame.eq('giant_primary')&ecdf.metric.eq('ap')];d=dose[dose.frame.eq('giant_primary')];rnd=random[random.frame.eq('giant_primary')].iloc[0]
 folder=OUT/'figures';folder.mkdir(exist_ok=False)
 plt.rcParams.update({'font.size':10,'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,'axes.titlesize':11,'axes.labelsize':10,'svg.fonttype':'none','pdf.fonttype':42})
 fig,axs=plt.subplots(2,2,figsize=(8.6,6.4),sharey=True)
 for ax,(method,label) in zip(axs.flat,NAMES.items()):
  q=primary[primary.method.eq(method)];x=np.sort(q.ap.to_numpy());assert len(x)==50;c=float(q.C_ap.iloc[0]);r=rank[rank.method.eq(method)].iloc[0];limit=max(x[-1],c,float(rnd.random_distinct_ranking_expected_AP))*1.10
  ax.step(np.r_[0,x,limit],np.r_[0,np.arange(1,51)/50,1],where='post',color='#286C8E',linewidth=1.8,label='B: 50 training compositions')
  ax.axvline(c,color='#B45B2E',linewidth=1.8,label='C: fixed training pool')
  ax.axvline(rnd.random_distinct_ranking_expected_AP,color='#777777',linewidth=1.1,linestyle=':',label='Expected random-ranking AP')
  ax.plot(c,r.C_ECDF_midrank,'o',color='#B45B2E',markersize=4)
  ax.text(.98,.05,f'C AP = {c:.4f}\nECDF midrank = {r.C_ECDF_midrank:.0%}',transform=ax.transAxes,ha='right',va='bottom',fontsize=9,bbox={'facecolor':'white','alpha':.85,'edgecolor':'none'})
  ax.set_title(label);ax.set_xlim(0,limit);ax.set_ylim(0,1.02);ax.set_xlabel('Average precision');ax.yaxis.set_major_formatter(PercentFormatter(1));ax.xaxis.set_major_locator(MaxNLocator(4));ax.grid(alpha=.18);ax.set_axisbelow(True)
 for ax in axs[:,0]:ax.set_ylabel('Empirical cumulative fraction')
 handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.5,.055),ncol=2,frameon=False,fontsize=9)
 fig.text(.5,.012,'Fixed 5,408-file proxy-labelled test. Tree metrics average five seeds within each composition. No IID inference.',ha='center',fontsize=8)
 fig.subplots_adjust(left=.10,right=.98,bottom=.21,top=.95,hspace=.38,wspace=.23);save(fig,folder/'fig_R5_composition_ecdf')
 fig,axs=plt.subplots(2,2,figsize=(8.6,6.4))
 for ax,(method,label) in zip(axs.flat,NAMES.items()):
  q=d[d.method.eq(method)];p=q.pivot(index='nominal_linked_retention_percent',columns='composition',values='ap').sort_index();assert p.shape==(5,5);x=q.groupby('nominal_linked_retention_percent').realized_linked_retention.first().loc[p.index].to_numpy()*100
  for column in p:ax.plot(x,p[column],color='#7EABB9',alpha=.65,linewidth=.8)
  ax.fill_between(x,p.min(axis=1),p.max(axis=1),color='#286C8E',alpha=.12,label='Range across five compositions')
  ax.plot(x,p.mean(axis=1),'o-',color='#286C8E',linewidth=1.8,markersize=4,label='Mean across five compositions')
  ax.axhline(float(p.iloc[0,0]),color='#B45B2E',linestyle='--',linewidth=1.1,label='C: zero linked-file retention')
  ax.axhline(rnd.random_distinct_ranking_expected_AP,color='#777777',linestyle=':',linewidth=1.0,label='Expected random-ranking AP')
  ax.set_title(label);ax.set_xlabel('Linked-pool files retained (%)');ax.set_ylabel('Average precision');ax.set_xlim(-2,102);ax.set_xticks([0,25,50,75,100]);ax.yaxis.set_major_locator(MaxNLocator(4));ax.grid(alpha=.18);ax.set_axisbelow(True)
 handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.5,.055),ncol=2,frameon=False,fontsize=8.5)
 fig.text(.5,.012,'Training stays 708 files / 24 positives. 100% retains all 471 linked files (66.53% of training); zero dose reuses C.',ha='center',fontsize=8)
 fig.subplots_adjust(left=.10,right=.98,bottom=.22,top=.95,hspace=.38,wspace=.27);save(fig,folder/'fig_R5_linked_retention_ap')
 # All twelve method/budget combinations are retained, not selected by their direction.
 fig,axs=plt.subplots(3,4,figsize=(12.5,8.2))
 for column,(method,label) in enumerate(NAMES.items()):
  q=d[d.method.eq(method)]
  for row,percent in enumerate((5,10,20)):
   ax=axs[row,column];metric=f'yield_{percent}';p=q.pivot(index='nominal_linked_retention_percent',columns='composition',values=metric).sort_index();x=q.groupby('nominal_linked_retention_percent').realized_linked_retention.first().loc[p.index].to_numpy()*100
   for c in p:ax.plot(x,p[c],color='#7EABB9',alpha=.55,linewidth=.7)
   ax.fill_between(x,p.min(axis=1),p.max(axis=1),color='#286C8E',alpha=.12);ax.plot(x,p.mean(axis=1),'o-',color='#286C8E',linewidth=1.4,markersize=3)
   ax.axhline(float(rnd[f'random_expected_yield_{percent}']),color='#777777',linestyle=':',linewidth=1.0);ax.axhline(float(p.iloc[0,0]),color='#B45B2E',linestyle='--',linewidth=1)
   if row==0:ax.set_title(label.replace('logistic regression','LR'),fontsize=10)
   if column==0:ax.set_ylabel(f'{percent}% review ({int(rnd[f"budget_{percent}"])} files)\nExpected positive findings')
   if row==2:ax.set_xlabel('Linked-pool files retained (%)')
   ax.set_xlim(-2,102);ax.set_xticks([0,50,100]);ax.yaxis.set_major_locator(MaxNLocator(4));ax.grid(alpha=.18);ax.set_axisbelow(True)
 fig.text(.5,.025,'Blue: five-composition mean and range (tree seeds averaged first). Orange dashed: reused C zero dose. Grey dotted: random review.',ha='center',fontsize=9)
 fig.subplots_adjust(left=.08,right=.99,bottom=.10,top=.95,hspace=.33,wspace=.28);save(fig,folder/'fig_R5_linked_retention_all_review_budgets')
 receipt={'status':'generated_pending_visual_QA','source_sha256':sha(Path(__file__)),'producer_comparison_sha256':sha(OUT/'PRODUCER_COMPARISON.json'),'input_sha256':{p.name:sha(p) for p in paths},'output_sha256':{p.name:sha(p) for p in folder.iterdir()}}
 (folder/'FIGURE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print('Three independent-metric figure sets generated')
if __name__=='__main__':main()
