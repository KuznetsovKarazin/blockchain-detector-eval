"""X1: a wallet's causal features at step t must not change when later transactions are removed."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tv1", ROOT / "scripts" / "tv1_wallet_causal.py")
tv1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tv1)


def _write(d: Path, n_tx=60, seed=0, max_step=None):
    rng = np.random.default_rng(seed)
    tx = pd.DataFrame({"txId": np.arange(n_tx), "Time step": rng.integers(1, 8, n_tx)})
    for c in tv1.TX_COLS:
        tx[c] = rng.random(n_tx)
    tx["class"] = rng.integers(1, 4, n_tx)
    if max_step is not None:
        tx = tx[tx["Time step"] <= max_step]
    tx[["txId", "class"]].to_csv(d / "txs_classes.csv", index=False)
    tx.drop(columns="class").to_csv(d / "txs_features.csv", index=False)
    addrs = [f"a{i}" for i in range(6)]
    r2 = np.random.default_rng(seed + 1)
    pd.DataFrame({"input_address": r2.choice(addrs, 90), "txId": r2.integers(0, n_tx, 90)}).to_csv(
        d / "AddrTx_edgelist.csv", index=False)
    pd.DataFrame({"txId": r2.integers(0, n_tx, 90), "output_address": r2.choice(addrs, 90)}).to_csv(
        d / "TxAddr_edgelist.csv", index=False)


def test_prefix_invariance(tmp_path):
    full, cut = tmp_path / "full", tmp_path / "cut"
    full.mkdir(), cut.mkdir()
    _write(full)
    _write(cut, max_step=4)
    a = tv1.causal_features(full)
    b = tv1.causal_features(cut)
    a = a[a.step <= 4].set_index(["address", "step"]).sort_index()
    b = b.set_index(["address", "step"]).sort_index()
    assert a.index.equals(b.index)
    pd.testing.assert_frame_equal(a, b[a.columns], check_dtype=False)


def test_counts_are_cumulative(tmp_path):
    _write(tmp_path)
    f = tv1.causal_features(tmp_path)
    for _, g in f.groupby("address"):
        assert (np.diff(g.n_sent_cum.to_numpy()) >= 0).all()
        assert (np.diff(g.active_steps.to_numpy()) == 1).all()
