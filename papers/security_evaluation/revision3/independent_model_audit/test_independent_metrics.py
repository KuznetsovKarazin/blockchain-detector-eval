import itertools
import numpy as np
import pytest
from independent_metrics import grouped_metrics,finite_random_ap,formula_check

def test_finite_ranking_formula_exhaustive():assert formula_check()==55

def test_constant_scores_ap_and_expected_yields():
 y=np.array([1]*7+[0]*13);m=grouped_metrics(y,np.ones(20))
 assert m['ap']==7/20
 for percent in [5,10,20]:
  budget=20*percent//100
  assert m[f'yield_{percent}']==budget*7/20
  assert m[f'yield_min_{percent}']==0
  assert m[f'yield_max_{percent}']==budget
 assert finite_random_ap(20,7)>m['ap']

def test_grouped_ap_known_fraction_and_tie_permutation():
 y=np.array([1,0,1,0,0,1]);s=np.array([3,3,2,2,1,0],float)
 expected=(1/2+2/4+3/6)/3
 assert grouped_metrics(y,s)['ap']==expected
 for order in itertools.permutations(range(6)):
  p=list(order);assert grouped_metrics(y[p],s[p])==grouped_metrics(y,s)

def test_boundary_tie_expectation_against_all_tie_orders():
 y=np.array([1,0,1,0,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0])
 s=np.array([3,3,3,3,3,3,2,1,0,0,0,0,0,0,0,0,0,0,0,0],float)
 m=grouped_metrics(y,s)
 for percent in [5,10,20]:
  b=20*percent//100;values=[sum(y[list(order)][:b]) for order in itertools.permutations(range(6))]
  assert abs(m[f'yield_{percent}']-sum(values)/len(values))<1e-15
  assert m[f'yield_min_{percent}']==min(values)
  assert m[f'yield_max_{percent}']==max(values)

def test_no_positive_undefined_and_nonfinite_rejected():
 assert np.isnan(grouped_metrics([0,0],[2,1])['ap'])
 with pytest.raises(ValueError):grouped_metrics([0,1],[float('nan'),1])
 with pytest.raises(ValueError):grouped_metrics([0,2],[0,1])
