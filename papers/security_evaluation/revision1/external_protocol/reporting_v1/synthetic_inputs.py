"""Fictional file/class records only; no actual dataset or label reads."""
from pathlib import Path
import numpy as np
import pandas as pd
import reporting as r

def fixture(N=8,n_per_class=4,target_class='reentrancy',census=False,broad=False):
    old=r._load('_reporting_fictional_generator',Path(__file__).parents[1]/'performance_v1/synthetic_inputs.py')
    frame,sample,allocation,first,second,adjudication,base=old.fixture(N,n_per_class,classes=r.CLASSES,census=census)
    parts=[]
    for index,identity in enumerate(r.primary_inventory(target_class)):
        rows=base.copy();rows['class']=target_class
        for k,v in identity.items():rows[k]=v
        rows['execution_status']='ok'
        rows['score']=np.roll(np.linspace(1,0,N),index)
        if identity['method']=='slither':rows['score']=(np.arange(N)%3==0).astype(float)
        parts.append(rows)
    if broad:
        rows=parts[-1].copy();rows['job_id']=f'slither_broad:{target_class}:0';rows['variant']='broad_secondary'
        if target_class=='reentrancy':rows.loc[np.arange(N)%5==0,'score']=1.
        parts.append(rows)
    scores=pd.concat(parts,ignore_index=True)
    return [frame,sample,allocation,first,second,adjudication,scores],sample.copy(deep=True)

def evaluate(data,case_manifest,**kwargs):
    return r.report_class(*data,'reentrancy',case_manifest=case_manifest,expected_files=data[0].path.nunique(),
      expected_sample_cases=len(data[1]),synthetic_fixture=True,review_fractions=(.25,.5,1.),**kwargs)
