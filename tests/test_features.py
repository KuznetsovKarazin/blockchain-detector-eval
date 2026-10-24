import numpy as np
import pandas as pd

from bal.features.contract_features import near_duplicate_groups, normalised_text
from bal.features.xchain_features import X_FEATURES, build_features
from bal.models.anomaly import ECOD


def _events(n=300, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "ts": np.cumsum(rng.integers(1, 600, n)),
        "value_usd": rng.lognormal(6, 2, n),
        "token": rng.choice(["ETH", "USDC", "WBTC"], n),
        "beneficiary": rng.choice([f"0x{i:02x}" for i in range(40)], n),
        "latency_s": rng.exponential(300, n),
        "matched": rng.random(n) > 0.05,
        "label": 0,
        "tx_hash": [f"h{i}" for i in range(n)],
    })


def test_bridge_features_are_causal():
    """Features of the first k events must not change when later events are appended."""
    ev = _events()
    full = build_features(ev)
    part = build_features(ev.iloc[:200])
    assert np.allclose(full[X_FEATURES].iloc[:200].to_numpy(), part[X_FEATURES].to_numpy())


def test_identifier_normalisation_removes_names():
    a = "contract Bank { mapping(address=>uint) balances_re_ent; function withdraw() public {} }"
    b = "contract Vault { mapping(address=>uint) userFunds; function take() public {} }"
    assert normalised_text(a) == normalised_text(b)


def test_near_duplicates_are_grouped_and_deterministic():
    base = " ".join(f"tok{i}" for i in range(200))
    near = base.replace("tok100", "tokX")
    other = " ".join(f"zz{i}" for i in range(200))
    g = near_duplicate_groups([base, near, other])
    assert g[0] == g[1] != g[2]
    assert (near_duplicate_groups([base, near, other]) == g).all()


def test_ecod_max_not_diluted_by_dimension():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2000, 20))
    one_extreme = np.zeros((1, 20))
    one_extreme[0, 0] = 50.0
    many_moderate = np.full((1, 20), 2.0)
    s_sum = ECOD().fit(X).score(np.vstack([one_extreme, many_moderate]))
    s_max = ECOD(agg="max").fit(X).score(np.vstack([one_extreme, many_moderate]))
    assert s_sum[0] < s_sum[1]          # sum-aggregation ranks the single extreme LOWER
    assert s_max[0] > s_max[1]          # max-aggregation ranks it higher


def _partition(comp, order):
    """Partition as a set of frozensets of ORIGINAL indices."""
    groups = {}
    for pos, c in enumerate(comp):
        groups.setdefault(c, set()).add(order[pos])
    return {frozenset(g) for g in groups.values()}


def test_near_duplicate_partition_is_order_invariant():
    import itertools
    import random
    rnd = random.Random(1)
    words = [f"w{i}" for i in range(400)]
    B = " ".join(rnd.choice(words) for _ in range(300))
    A = " ".join(B.split()[:40] + [rnd.choice(words) for _ in range(260)])   # low Jaccard with B
    texts = [A, B, B]
    parts = {frozenset(_partition(near_duplicate_groups([texts[i] for i in o]), o))
             for o in itertools.permutations(range(3))}
    assert len(parts) == 1
    assert frozenset({1, 2}) in next(iter(parts))          # identical texts always merged


def test_near_duplicates_cover_brute_force_pairs():
    import random
    from bal.features.contract_features import exact_pairs_check
    rnd = random.Random(2)
    words = [f"t{i}" for i in range(300)]
    bases = [[rnd.choice(words) for _ in range(200)] for _ in range(15)]
    texts = []
    for bs in bases:
        for _ in range(3):                                 # 3 light edits of each base
            t = list(bs)
            for k in rnd.sample(range(200), 2):
                t[k] = rnd.choice(words)
            texts.append(" ".join(t))
    comp = near_duplicate_groups(texts, threshold=0.8)
    for i, j, _ in exact_pairs_check(texts, 0.8):
        assert comp[i] == comp[j]


def test_pattern_version_ignores_commented_pragma():
    from bal.features.contract_features import pattern_features
    src = "// pragma solidity ^0.4.0;\n/* pragma solidity 0.5.0; */\npragma solidity ^0.8.0;\ncontract A {}"
    f = pattern_features(src)
    assert f["solc_version"] == 0.08 and f["pre_08"] == 0.0
