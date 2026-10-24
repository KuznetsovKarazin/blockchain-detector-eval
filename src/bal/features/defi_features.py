"""
Transaction features for flash-loan price-manipulation detection (K4).

Every feature uses only the transaction itself (its logs and token transfers)
and the pool state before it: the last V2 `Sync` / V3 `Swap` of an earlier
transaction on the same day (earlier transactions of the same block count as
earlier). Nothing is taken from later transactions, labels or incident text.

Features
--------
has_flash            any flash loan (explicit event or V2 flash swap)
n_flash              number of flash-loan events (+ V2 flash swaps)
flash_to_pool        max over flash-borrowed tokens of amount / largest
                     pre-transaction reserve of that token in a V2 pool the
                     transaction touches (0 if no such pool)
max_price_move       max over touched pools of |log(price inside the tx /
                     price before the tx)|, V2 reserves ratio and V3 sqrtP²;
                     a V2 pool without an earlier event that day gets its
                     state before the tx from its first Swap in the tx
net_price_move       same, for the last price of the tx in each pool (max)
n_pools              V2 + V3 pools with a state event in the tx
n_contracts          distinct log-emitting contracts
n_logs, n_tokens     logs, distinct transferred tokens
profit_usd           net inflow of WETH, USDC, USDT, DAI to the sender and the
                     called contract, in USD (WETH priced by the USDC/WETH V2
                     pool before the tx); native ETH is not visible without
                     traces and is not counted
gas_used, nonce, value_eth
to_created_today     the called contract was created earlier the same day
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bal.data import defi as D

FEATURES = ["has_flash", "n_flash", "flash_to_pool", "max_price_move", "net_price_move", "n_pools",
            "n_contracts", "n_logs", "n_tokens", "profit_usd", "gas_used", "nonce", "value_eth",
            "to_created_today"]


def _pos(block, txi):
    return block.astype(np.int64) * 100_000 + txi.astype(np.int64)


def _price_rows(ev: pd.DataFrame) -> pd.DataFrame:
    """address, pos, log_index, price (token1 per token0, raw units), r0, r1 for Sync / V3 Swap."""
    out = []
    for r in ev.itertuples(index=False):
        w = D.words(r.data)
        if r.topic0 == D.T_SYNC and len(w) >= 2:
            p = w[1] / w[0] if w[0] else np.nan
            out.append((r.address, r.pos, r.log_index, p, float(w[0]), float(w[1])))
        elif r.topic0 == D.T_SWAP_V3 and len(w) >= 3:
            out.append((r.address, r.pos, r.log_index, (w[2] / 2**96) ** 2, np.nan, np.nan))
    return pd.DataFrame(out, columns=["address", "pos", "log_index", "price", "r0", "r1"])


def _flash_loans(lg: pd.DataFrame, tt: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    """transaction_hash, token, amount of every flash loan visible in the logs."""
    rows = []
    for r in lg[lg.topic0.isin(D.FLASH_TOPICS)].itertuples(index=False):
        kind, tp, w = D.FLASH_TOPICS[r.topic0], list(r.topics), D.words(r.data)
        try:
            if kind == "aave_v2":
                rows.append((r.transaction_hash, D.addr(tp[3]), w[0]))
            elif kind == "aave_v3":
                rows.append((r.transaction_hash, D.addr(tp[2]), w[1]))
            elif kind in ("aave_v1", "morpho"):
                rows.append((r.transaction_hash, D.addr(tp[2]), w[0]))
            elif kind == "balancer_or_erc3156":
                rows.append((r.transaction_hash, D.addr(tp[2]), w[0]) if len(tp) >= 3
                            else (r.transaction_hash, "0x" + format(w[0], "040x")[-40:], w[1]))
            elif kind == "uniswap_v3_flash":
                rows.append((r.transaction_hash, r.address + ":0", w[0]))
                rows.append((r.transaction_hash, r.address + ":1", w[1]))
        except IndexError:
            continue
    return pd.DataFrame(rows, columns=["transaction_hash", "token", "amount"])


def day_features(day_dir: str | Path) -> pd.DataFrame:
    d = Path(day_dir)
    tx = pd.read_parquet(d / "txs.parquet")
    lg = pd.read_parquet(d / "logs.parquet")
    tt = pd.read_parquet(d / "transfers.parquet")
    st = pd.read_parquet(d / "state.parquet")
    pairs = pd.read_parquet(d / "pairs.parquet").set_index("pair")
    # pairs whose transfers in the day file include their own LP token: take the
    # two other tokens from the kept transactions' transfers
    v2 = set(pd.read_parquet(d / "state.parquet", columns=["address", "topic0"]).query(
        "topic0 == @D.T_SYNC").address)
    pt = pd.concat([tt[tt.from_address.isin(v2)][["from_address", "token_address"]].set_axis(["pair", "token"], axis=1),
                    tt[tt.to_address.isin(v2)][["to_address", "token_address"]].set_axis(["pair", "token"], axis=1)])
    pt = pt[pt.pair != pt.token].drop_duplicates().groupby("pair").token.agg(lambda s: sorted(set(s)))
    pt = pt[pt.map(len) == 2]
    extra = pd.DataFrame({"token0": pt.map(lambda x: x[0]), "token1": pt.map(lambda x: x[1])})
    pairs = pd.concat([pairs, extra[~extra.index.isin(pairs.index)]])
    tx["pos"] = _pos(tx.block_number, tx.transaction_index)
    pos = tx.set_index("hash").pos
    lg["pos"] = lg.transaction_hash.map(pos)

    # pool prices inside each kept tx, and the last price before it
    own = _price_rows(lg[lg.topic0.isin(D.STATE_TOPICS)])
    pools = set(own.address) | {D.USDC_WETH_V2}
    st = st[st.address.isin(pools)].copy()
    st["pos"] = _pos(st.block_number, st.transaction_index)
    allp = _price_rows(st).sort_values(["pos", "log_index"])
    last = allp.groupby(["address", "pos"]).tail(1)           # state after each tx
    own = own.sort_values(["address", "pos", "log_index"])
    pre = pd.merge_asof(own[["address", "pos"]].drop_duplicates().sort_values("pos"),
                        last[["address", "pos", "price", "r0", "r1"]].rename(columns={"pos": "pre_pos"}).sort_values("pre_pos"),
                        left_on="pos", right_on="pre_pos", by="address", allow_exact_matches=False)
    pre = pre.rename(columns={"price": "pre_price", "r0": "pre_r0", "r1": "pre_r1"})
    own = own.merge(pre[["address", "pos", "pre_price", "pre_r0", "pre_r1"]], on=["address", "pos"], how="left")
    # V2 pool not seen earlier that day: the state before the tx follows from its
    # first Sync if that Sync belongs to a Swap (Sync is logged just before Swap):
    # reserves before = reserves after - amounts in + amounts out
    sw = lg[lg.topic0 == D.T_SWAP_V2][["address", "pos", "log_index", "data"]]
    first = own.dropna(subset=["r0"]).groupby(["address", "pos"]).head(1)
    first = first.merge(sw.assign(log_index=sw.log_index - 1), on=["address", "pos", "log_index"], how="inner")
    if len(first):
        w = np.array([D.words(x)[:4] for x in first.data], dtype=float)
        first = first.assign(d_r0=first.r0 - w[:, 0] + w[:, 2], d_r1=first.r1 - w[:, 1] + w[:, 3])
        first = first[(first.d_r0 > 0) & (first.d_r1 > 0)]
        derived = first.set_index(["address", "pos"])[["d_r0", "d_r1"]]
        own = own.join(derived, on=["address", "pos"])
        miss = own.pre_price.isna() & own.d_r0.notna()
        own.loc[miss, "pre_r0"], own.loc[miss, "pre_r1"] = own.d_r0[miss], own.d_r1[miss]
        own.loc[miss, "pre_price"] = own.d_r1[miss] / own.d_r0[miss]
        own = own.drop(columns=["d_r0", "d_r1"])
    own["move"] = np.abs(np.log(own.price / own.pre_price))
    hash_of = lg.drop_duplicates("pos").set_index("pos").transaction_hash
    own["tx"] = own.pos.map(hash_of)
    mv = own.groupby("tx").move.max()
    net = own.groupby(["tx", "address"]).tail(1).groupby("tx").move.max()

    # flash loans and their size relative to the touched V2 pools before the tx
    fl = _flash_loans(lg, tt, pairs)
    v2 = own.dropna(subset=["pre_r0"]).drop_duplicates(["tx", "address"])
    v2 = v2.join(pairs, on="address", how="inner")
    res = pd.concat([v2[["tx", "token0", "pre_r0"]].set_axis(["tx", "token", "reserve"], axis=1),
                     v2[["tx", "token1", "pre_r1"]].set_axis(["tx", "token", "reserve"], axis=1)])
    res = res.groupby(["tx", "token"]).reserve.max()
    flash_tx = set(tx[tx.stratum.isin(["flash", "attack"])].hash)
    # V2 flash swaps: first out-transfer of the pair before any in-transfer
    t_in = tt[tt.to_address.isin(pairs.index)].groupby(["transaction_hash", "to_address"]).log_index.min()
    t_out = tt[tt.from_address.isin(pairs.index)].sort_values("log_index").groupby(
        ["transaction_hash", "from_address"]).agg(first=("log_index", "min"), token=("token_address", "first"),
                                                  amount=("value", "first"))
    t_in.index.names = t_out.index.names = ["tx", "pair"]
    fs = t_out.join(t_in.rename("first_in"), how="inner")
    fs = fs[fs["first"] < fs.first_in].reset_index()
    fl = pd.concat([fl, fs[["tx", "token", "amount"]].rename(columns={"tx": "transaction_hash"})])
    fl["reserve"] = [res.get((h, t), np.nan) for h, t in zip(fl.transaction_hash, fl.token)]
    fl["ratio"] = fl.amount.astype(float) / fl.reserve
    n_flash = fl.groupby("transaction_hash").size()
    ratio = fl.groupby("transaction_hash").ratio.max()

    # net profit of sender + called contract in WETH and stablecoins
    wp = last[last.address == D.USDC_WETH_V2][["pos", "r0", "r1"]].sort_values("pos")
    wp["usd_per_weth"] = (wp.r0 / 1e6) / (wp.r1 / 1e18)
    tpos = tx[["hash", "pos"]].sort_values("pos")
    tpos = pd.merge_asof(tpos, wp[["pos", "usd_per_weth"]].rename(columns={"pos": "wpos"}),
                         left_on="pos", right_on="wpos", allow_exact_matches=False).set_index("hash")
    who = tx.set_index("hash")[["from_address", "to_address"]].rename(columns={"from_address": "sender",
                                                                               "to_address": "called"})
    t = tt[tt.token_address.isin(set(D.STABLES) | {D.WETH})].join(who, on="transaction_hash")
    dec = t.token_address.map(lambda a: D.STABLES.get(a, 18))
    usd = np.where(t.token_address.isin(D.STABLES), 1.0, t.transaction_hash.map(tpos.usd_per_weth))
    amt = t.value / 10.0 ** dec * usd
    to_me = (t.to_address == t.sender) | (t.to_address == t.called)
    from_me = (t.from_address == t.sender) | (t.from_address == t.called)
    profit = (amt.where(to_me, 0) - amt.where(from_me, 0)).groupby(t.transaction_hash).sum()

    g = lg.groupby("transaction_hash")
    pool_n = own.groupby("tx").address.nunique()
    f = pd.DataFrame(index=tx.hash)
    f["n_flash"] = n_flash.reindex(f.index).fillna(0)
    f["has_flash"] = ((f.n_flash > 0) | f.index.isin(flash_tx)).astype(float)
    f["flash_to_pool"] = ratio.reindex(f.index).fillna(0).clip(0, 1e6)
    f["max_price_move"] = mv.reindex(f.index).fillna(0).clip(0, 50)
    f["net_price_move"] = net.reindex(f.index).fillna(0).clip(0, 50)
    f["n_pools"] = pool_n.reindex(f.index).fillna(0)
    f["n_contracts"] = g.address.nunique().reindex(f.index).fillna(0)
    f["n_logs"] = g.size().reindex(f.index).fillna(0)
    f["n_tokens"] = tt.groupby("transaction_hash").token_address.nunique().reindex(f.index).fillna(0)
    f["profit_usd"] = profit.reindex(f.index).fillna(0)
    tx = tx.set_index("hash")
    f["gas_used"] = tx.receipt_gas_used.astype(float)
    f["nonce"] = tx.nonce.astype(float)
    f["value_eth"] = tx.value.astype(float) / 1e18
    f["to_created_today"] = tx.created_today.astype(float)
    meta = tx[["stratum", "weight", "block_number", "transaction_index", "from_address", "to_address",
               "receipt_status"]]
    return f[FEATURES].join(meta).reset_index().rename(columns={"index": "hash"})
