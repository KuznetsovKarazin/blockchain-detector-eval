"""K4 features: label-free flash flag and causal `to_created_today` on a synthetic day."""

import numpy as np
import pandas as pd
import pytest

from bal.data import defi as D
from bal.features.defi_features import FEATURES, day_features

P, A, B = "0x" + "aa" * 20, "0x" + "a1" * 20, "0x" + "b1" * 20      # V2 pair and its tokens
C, E, U = "0x" + "cc" * 20, "0x" + "ee" * 20, "0x" + "dd" * 20      # contract, attacker EOA, user
AAVE_V2 = next(k for k, v in D.FLASH_TOPICS.items() if v == "aave_v2")


def _w(*xs):
    return "0x" + "".join(format(int(x), "064x") for x in xs)


def _t(a):
    return "0x" + "0" * 24 + a[2:]


def _day(tmp_path, strata=("background", "attack", "background", "flash"), creations=None):
    h = [f"0x{i:064x}" for i in range(4)]
    tx = pd.DataFrame({"hash": h, "from_address": [U, E, U, U], "to_address": [P, C, C, U],
                       "nonce": [5, 0, 7, 9], "value": [0.0] * 4, "receipt_gas_used": [1e5, 2e6, 3e5, 2e4],
                       "receipt_status": 1, "block_number": 100, "transaction_index": [0, 5, 7, 9],
                       "stratum": list(strata), "weight": 1.0})
    lg = pd.DataFrame([
        # tx0: ordinary swap leaves reserves 1000 / 1000
        (P, [D.T_SYNC], _w(1000, 1000), h[0], 1, 100, 0),
        # tx1: V2 flash swap (pair pays out before it is paid), reserves move to 500 / 2000
        (P, [D.T_SYNC], _w(500, 2000), h[1], 2, 100, 5),
        (P, [D.T_SWAP_V2, _t(E), _t(E)], _w(0, 1000, 500, 0), h[1], 3, 100, 5),
        # tx2: Aave v2 flash loan event
        (U, [AAVE_V2, _t(C), _t(C), _t(A)], _w(10, 0, 0, 0), h[2], 4, 100, 7),
    ], columns=["address", "topics", "data", "transaction_hash", "log_index", "block_number", "transaction_index"])
    lg["topic0"] = lg.topics.str[0]
    tt = pd.DataFrame([(A, P, E, 500.0, h[1], 1, 100), (B, E, P, 1000.0, h[1], 4, 100)],
                      columns=["token_address", "from_address", "to_address", "value", "transaction_hash",
                               "log_index", "block_number"])
    st = lg[lg.topic0 == D.T_SYNC][["address", "topic0", "data", "transaction_hash", "block_number",
                                    "transaction_index", "log_index"]]
    cr = creations if creations is not None else pd.DataFrame(
        {"address": [C], "block_number": [100], "transaction_index": [6]})
    d = tmp_path / "2025-01-01"
    d.mkdir(exist_ok=True)
    tx.to_parquet(d / "txs.parquet")
    lg.to_parquet(d / "logs.parquet")
    tt.to_parquet(d / "transfers.parquet")
    st.to_parquet(d / "state.parquet")
    pd.DataFrame({"pair": [P], "token0": [A], "token1": [B]}).to_parquet(d / "pairs.parquet")
    cr.to_parquet(d / "creations.parquet")
    return day_features(d).set_index("hash")


def test_flash_flag_does_not_use_the_stratum(tmp_path):
    f = _day(tmp_path)
    assert f.has_flash.tolist() == [0, 1, 1, 0]       # tx3 is in the "flash" stratum but has no flash loan
    g = _day(tmp_path, strata=("flash", "background", "attack", "protocol"))
    pd.testing.assert_frame_equal(f[FEATURES], g[FEATURES])


def test_created_today_only_counts_earlier_creations(tmp_path):
    f = _day(tmp_path)
    assert f.to_created_today.tolist() == [0, 0, 1, 0]    # C is created at index 6: after tx1, before tx2
    later = pd.DataFrame({"address": [C, P, U], "block_number": [100, 150, 160], "transaction_index": [6, 0, 3]})
    g = _day(tmp_path, creations=later)                   # creations in later blocks change nothing
    pd.testing.assert_frame_equal(f[FEATURES], g[FEATURES])


def test_price_move_of_the_flash_swap(tmp_path):
    f = _day(tmp_path)
    assert f.loc[f.index[1], "max_price_move"] == pytest.approx(np.log(4.0))   # 1000/1000 -> 2000/500
