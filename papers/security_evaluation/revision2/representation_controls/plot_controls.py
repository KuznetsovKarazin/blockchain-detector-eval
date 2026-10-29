from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
q=pd.read_csv(HERE/'pair_run_20261028_v1/graph_controls.csv').query("policy=='address_expanded'")
plt.rcParams.update({'font.size':10,'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42})
fig,ax=plt.subplots(figsize=(8.3,4.3))
cases=['full_080','full_080_mask_availability_only','masked_080'];labs=['Full lexical graph','Availability-only control','Masked lexical graph']
for j,(flavor,label,color) in enumerate([('normalized','Identifiers/numbers collapsed','#3A6489'),('preserved','Identifiers/numbers preserved','#B66B37')]):
 rows=q.set_index(['flavor','case']).loc[[(flavor,c) for c in cases]];vals=rows.dapp_giant_fraction.to_numpy()*100;y=[i+(-.17 if j==0 else .17) for i in range(3)]
 ax.barh(y,vals,height=.30,color=color,label=label)
 for yy,(_,row) in zip(y,rows.iterrows()):ax.text(row.dapp_giant_fraction*100+.6,yy,f'{row.dapp_giant_files:,} ({row.dapp_giant_fraction:.2%})',va='center',fontsize=9)
ax.set_yticks(range(3),labs);ax.invert_yaxis();ax.set_xlim(0,117);ax.set_xticks([0,20,40,60,80,100]);ax.set_xlabel('DAppSCAN files in largest component (%)');ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
fig.legend(*ax.get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.55,.065),frameon=False,ncol=2,fontsize=9)
fig.text(.12,.025,'All 21,457 nodes remain. Jaccard ≥ 0.8; fixed structural edges; empty lexical streams excluded.',fontsize=8)
fig.subplots_adjust(left=.26,right=.98,top=.97,bottom=.28)
out=HERE/'figures';out.mkdir(exist_ok=True)
for ext in ['png','pdf','svg']:fig.savefig(out/f'fig04_representation_controls.{ext}',dpi=220)
plt.close(fig)
