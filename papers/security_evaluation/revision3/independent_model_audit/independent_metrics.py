"""Independent grouped-score AP and exact boundary-tie review expectations."""
from __future__ import annotations
from fractions import Fraction
import itertools
import math
import numpy as np

PERCENTS=(5,10,20)

def finite_random_ap(n:int,k:int)->float:
    if n<1 or not 0<=k<=n:raise ValueError('Invalid finite population')
    if k==0:return float('nan')
    if n==1:return 1.0
    h=math.fsum(1.0/r for r in range(1,n+1))
    return h/n+(k-1)/(n-1)*(1-h/n)

def grouped_metrics(labels,scores):
    y=np.asarray(labels,dtype=np.int64);s=np.asarray(scores,dtype=np.float64)
    if y.ndim!=1 or s.shape!=y.shape or len(y)==0:raise ValueError('Invalid shapes')
    if not np.isin(y,[0,1]).all() or not np.isfinite(s).all():raise ValueError('Invalid labels/scores')
    order=np.argsort(-s,kind='stable');ys=y[order];ss=s[order]
    ends=np.r_[np.flatnonzero(ss[:-1]!=ss[1:])+1,len(y)]
    starts=np.r_[0,ends[:-1]];count=ends-starts
    positives=np.add.reduceat(ys,starts);cumulative=np.cumsum(positives);k=int(y.sum())
    ap=float(np.sum((positives/k)*(cumulative/ends))) if k else float('nan')
    result={'n':len(y),'k':k,'ap':ap,'score_groups':len(ends)}
    for percent in PERCENTS:
        budget=len(y)*percent//100
        if budget==0:expected=lower=upper=0.0
        else:
            group=int(np.searchsorted(ends,budget,side='left'))
            before=int(cumulative[group-1]) if group else 0
            slots=budget-int(starts[group]);m=int(count[group]);p=int(positives[group])
            expected=before+slots*p/m
            lower=before+max(0,slots-(m-p));upper=before+min(slots,p)
        result[f'budget_{percent}']=budget
        result[f'yield_{percent}']=expected
        result[f'yield_min_{percent}']=lower
        result[f'yield_max_{percent}']=upper
    return result

def formula_check():
    """Enumerate label positions, equivalent to uniform distinct-score rankings."""
    checked=0
    for n in range(1,11):
        harmonic=sum((Fraction(1,r) for r in range(1,n+1)),Fraction())
        for k in range(1,n+1):
            values=[]
            for positions in itertools.combinations(range(n),k):
                count=0;total=Fraction()
                for rank in range(1,n+1):
                    if rank-1 in positions:
                        count+=1;total+=Fraction(count,rank*k)
                values.append(total)
            exact=sum(values,Fraction())/len(values)
            formula=Fraction(1) if n==1 else harmonic/n+Fraction(k-1,n-1)*(1-harmonic/n)
            assert exact==formula
            assert abs(float(exact)-finite_random_ap(n,k))<2e-15
            checked+=1
    return checked
