"""Compact landscape supplement; unchanged independently verified score data."""
from pathlib import Path
import hashlib,json,datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

HERE=Path(__file__).resolve().parent
OUT=HERE/'run_20261029_v1'
NAMES={'raw_tfidf_lr':'Raw-token LR','normalized_tfidf_lr':'Normalized-token LR','pattern_rf':'Pattern random forest','pattern_lightgbm':'Pattern LightGBM'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert json.loads((OUT/'PRODUCER_COMPARISON.json').read_text())['status']=='passed'
    inputs=[OUT/'dose_composition_seed_means.csv',OUT/'random_ranking_references.csv']
    dose,random=[pd.read_csv(p) for p in inputs]
    dose=dose[dose.frame.eq('giant_primary')]
    rnd=random[random.frame.eq('giant_primary')].iloc[0]
    dest=OUT/'figures'/'fig_R5_linked_retention_all_review_budgets_landscape'
    assert not dest.with_suffix('.pdf').exists(),'Refuse to overwrite original or prior output'
    plt.rcParams.update({'font.size':11,'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,'axes.titlesize':11.5,'axes.labelsize':11,'svg.fonttype':'none','pdf.fonttype':42})
    fig,axs=plt.subplots(3,4,figsize=(11.5,6.3))
    for column,(method,label) in enumerate(NAMES.items()):
        q=dose[dose.method.eq(method)]
        for row,percent in enumerate((5,10,20)):
            ax=axs[row,column]
            p=q.pivot(index='nominal_linked_retention_percent',columns='composition',values=f'yield_{percent}').sort_index()
            assert p.shape==(5,5)
            x=q.groupby('nominal_linked_retention_percent').realized_linked_retention.first().loc[p.index].to_numpy()*100
            for c in p:ax.plot(x,p[c],color='#7EABB9',alpha=.65,linewidth=.8)
            ax.fill_between(x,p.min(axis=1),p.max(axis=1),color='#286C8E',alpha=.12)
            ax.plot(x,p.mean(axis=1),'o-',color='#286C8E',linewidth=1.5,markersize=3)
            ax.axhline(float(rnd[f'random_expected_yield_{percent}']),color='#777777',linestyle=':',linewidth=1.2)
            ax.axhline(float(p.iloc[0,0]),color='#B45B2E',linestyle='--',linewidth=1.1)
            if row==0:ax.set_title(label)
            if column==0:ax.set_ylabel(f'{percent}% review ({int(rnd[f"budget_{percent}"])} files)\nExpected findings')
            if row==2:ax.set_xlabel('Linked-pool retention (%)')
            ax.set_xlim(-2,102);ax.set_xticks([0,50,100]);ax.yaxis.set_major_locator(MaxNLocator(3));ax.grid(alpha=.18);ax.set_axisbelow(True)
    fig.text(.5,.018,'Blue: composition mean and range; thin lines: five compositions. Orange: reused C. Grey: random review.',ha='center',fontsize=10.5)
    fig.subplots_adjust(left=.085,right=.99,bottom=.13,top=.94,hspace=.34,wspace=.34)
    for ext in ('png','pdf','svg'):fig.savefig(dest.with_suffix('.'+ext),dpi=240)
    plt.close(fig)
    receipt={'status':'generated_pending_visual_QA','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':sha(Path(__file__)),'input_sha256':{p.name:sha(p) for p in inputs},'producer_comparison_sha256':sha(OUT/'PRODUCER_COMPARISON.json'),'output_sha256':{dest.with_suffix('.'+ext).name:sha(dest.with_suffix('.'+ext)) for ext in ('png','pdf','svg')},'geometry_inches':[11.5,6.3],'plot_text_pt':11,'footer_text_pt':10.5,'unchanged_data':True,'scope':'All four models by all three budgets; all five dose levels; zero reuses C; observed ranges, not confidence intervals.'}
    (OUT/'figures'/'LANDSCAPE_FIGURE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(dest)
if __name__=='__main__':main()
