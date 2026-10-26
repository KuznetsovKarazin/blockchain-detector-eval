"""Show the complete main noncensus factorial, without selecting successful cases."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
source=HERE/'run_20261026_v1/summary.csv'
frame=pd.read_csv(source)
frame=frame[(frame.method=='exact_support')&(frame.N==20)&(frame.K>0)]
patterns=['one_top','one_middle','one_bottom','one_oversampled','two_spread','half_alternating']
labels=['1 positive at rank 1','1 positive at rank 10','1 positive at rank 20',
        '1 positive at rank 17','2 positives at ranks 2,19','10 alternating positives']
scores=['unique','blocks5','all_tied']
designs=['srs4','unequal2x2']
metrics=['unconditional_issued_and_covering_probability','coverage_conditional_on_issued']
fig,axes=plt.subplots(2,2,figsize=(10.8,8.8),sharex=True,sharey=True)
fig.subplots_adjust(left=.25,right=.87,top=.86,bottom=.15,wspace=.18,hspace=.38)
for row,design in enumerate(designs):
    part=frame[frame.design==design].set_index(['pattern','score_type'])
    for col,metric in enumerate(metrics):
        values=np.asarray([[100*part.loc[(p,s),metric] for s in scores] for p in patterns])
        ax=axes[row,col]
        plotted=ax.imshow(values,vmin=0,vmax=100,cmap='viridis',aspect='auto')
        for i in range(6):
            for j in range(3):
                ax.text(j,i,f'{values[i,j]:.1f}',ha='center',va='center',fontsize=10,
                        color='black' if values[i,j]>52 else 'white')
        ax.set_xticks(range(3),['Unique','Blocks of 5','All tied'])
        ax.set_yticks(range(6),labels)
        ax.tick_params(axis='both',length=0,labelsize=9)
        for spine in ax.spines.values():spine.set_visible(False)
        title=('SRS, n=4' if design=='srs4' else 'Unequal strata: N=16/4, n=2/2')
        ax.set_title(title,fontsize=10,pad=11)
        ax.set_xticks(np.arange(-.5,3),minor=True);ax.set_yticks(np.arange(-.5,6),minor=True)
        ax.grid(which='minor',color='white',linewidth=1.5);ax.tick_params(which='minor',bottom=False,left=False)
fig.text(.395,.92,'Interval issued and covers (%)',ha='center',fontsize=11,weight='bold')
fig.text(.735,.92,'Coverage among issued (%)',ha='center',fontsize=11,weight='bold')
fig.suptitle('Synthetic N=20 populations: percentile AP coverage diagnostic',fontsize=14,y=.98)
color_axis=fig.add_axes([.90,.20,.025,.63]);fig.colorbar(plotted,cax=color_axis,label='Probability (%)')
fig.text(.25,.075,'Exact enumeration of every sample. Nominal interval level: 95%.\n'
    'Undefined samples count as noncoverage only in the left column.\n'
    'This small-population diagnostic does not estimate coverage of the proposed external study.',fontsize=9,va='top')
fig.savefig(HERE/'coverage_diagnostic.png',dpi=160)
fig.savefig(HERE/'coverage_diagnostic.svg')
plt.close(fig)
(HERE/'figure_provenance.json').write_text(json.dumps({'source_summary_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'all_main_non_census_positive_scenarios':36,
    'selection_rule':'complete N20 noncensus factorial; census/no-positive/N50 controls retained in full report'},indent=2)+'\n')
