"""Independent exact-completion oracles; all score/label arrays are fictional."""
from fractions import Fraction
import importlib.util
import itertools
from pathlib import Path
import random
import sys

import pytest

FILE=Path(__file__).parents[1]/'external_protocol/ap_bounds_v1/ap_bounds.py'
spec=importlib.util.spec_from_file_location('independent_ap_bounds',FILE)
b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=b;spec.loader.exec_module(b)


def direct_ap(scores,labels):
    if not sum(labels):return None
    total=Fraction(0);seen=positives=0
    for score in sorted(set(scores),reverse=True):
        ids=[i for i,s in enumerate(scores) if s==score]
        found=sum(labels[i] for i in ids);seen+=len(ids);positives+=found
        total+=Fraction(found*positives,seen)
    return total/sum(labels)


def completions(scores,labels):
    unknown=[i for i,y in enumerate(labels) if y is None]
    out={}
    for assignment in itertools.product((0,1),repeat=len(unknown)):
        y=list(labels)
        for i,value in zip(unknown,assignment):y[i]=value
        value=direct_ap(scores,y)
        if value is not None:out.setdefault(sum(y),[]).append(value)
    return out


def check_case(scores,labels):
    oracle=completions(scores,labels);got=b.sharp_ap_completion_bounds(scores,labels)
    assert got.undefined_possible==(1 not in labels)
    assert got.defined_completions_exist==bool(oracle)
    by_positive={r.total_positives:(r.lower_ap,r.upper_ap) for r in got.by_total_positives}
    assert by_positive=={count:(min(values),max(values)) for count,values in oracle.items()}
    if oracle:
        all_values=list(itertools.chain.from_iterable(oracle.values()))
        assert (got.lower_ap,got.upper_ap)==(min(all_values),max(all_values))
        for witness,value in ((got.lower_completion,got.lower_ap),(got.upper_completion,got.upper_ap)):
            assert all(original is None or witness[i]==original for i,original in enumerate(labels))
            assert direct_ap(scores,witness)==value
    else:assert got.lower_ap is got.upper_ap is got.lower_completion is got.upper_completion is None


def test_tie_exchange_counterexample_is_optimized_not_sorted_away():
    scores=[2,2,1,1,1];labels=[None,0,1,1,None]
    got=b.sharp_ap_completion_bounds(scores,labels)
    fixed=next(row for row in got.by_total_positives if row.total_positives==3)
    assert fixed.lower_ap==Fraction(17,30) and fixed.upper_ap==Fraction(3,5)
    assert direct_ap(scores,[1,0,1,1,0])<direct_ap(scores,[0,0,1,1,1])
    check_case(scores,labels)


def test_two_equal_tie_groups_defeat_the_latest_positive_minimum_rule():
    got=b.sharp_ap_completion_bounds([2]*3+[1]*3,[None]*6)
    fixed=next(row for row in got.by_total_positives if row.total_positives==3)
    assert fixed.lower_ap==Fraction(4,9)<Fraction(1,2)
    check_case([2]*3+[1]*3,[None]*6)


def test_96_prespecified_toy_cases_against_all_binary_completions():
    rng=random.Random(20261026)
    for n in range(1,9):
        for _ in range(12):
            scores=[rng.choice((-2,-1,0,1,2)) for _ in range(n)]
            labels=[rng.choice((0,1,None)) for _ in range(n)]
            check_case(scores,labels)


def test_undefined_all_negative_completion_is_never_hidden_by_identification():
    got=b.sharp_ap_completion_bounds([1],[None])
    assert got.lower_ap==got.upper_ap==1
    assert got.undefined_possible and got.identified_ap is None and got.census_ap is None
    negative=b.sharp_ap_completion_bounds([3,2,1],[0,0,0])
    assert not negative.defined_completions_exist and negative.census_ap is None


def test_precision_loss_cannot_silently_create_a_score_tie():
    with pytest.raises(ValueError):b.sharp_ap_completion_bounds([Fraction(2**54+1,2**54),1],[1,0])
    # Native arbitrarily large integers retain their true order.
    result=b.sharp_ap_completion_bounds([2**200+1,2**200],[1,0])
    assert result.census_ap==1 and result.tie_groups==2


def test_no_witness_mode_keeps_the_same_sharp_endpoints():
    scores=[3,1,1,3,0];labels=[None,1,None,0,None]
    with_witness=b.sharp_ap_completion_bounds(scores,labels)
    without=b.sharp_ap_completion_bounds(scores,labels,include_witnesses=False)
    assert without.by_total_positives==with_witness.by_total_positives
    assert (without.lower_ap,without.upper_ap)==(with_witness.lower_ap,with_witness.upper_ap)
    assert without.lower_completion is without.upper_completion is None
