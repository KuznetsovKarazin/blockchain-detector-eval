"""
K4 (step 1)  Extract the incident days from the AWS Ethereum dataset.

For every incident day (README date of the incident; the day before or after
is read when an attack transaction is not found there) this script reads
`transactions`, `logs` and `token_transfers` with column projection and keeps

* every transaction of the day in one of four disjoint strata, in this order:
    attack       a linked attack transaction of a selected incident
    flash        any other transaction with a flash loan (Aave v1/v2/v3,
                 Balancer / ERC-3156, Morpho, Uniswap V3 `Flash`, dYdX
                 withdraw + deposit, Uniswap V2 flash swap: the pair pays out
                 before it is paid)
    protocol     a transaction that emits a log from a contract the attack
                 transaction of that day touched (common tokens and flash
                 providers excluded); at most --protocol-cap, sampled
    background   a uniform sample of --background other successful txs
  with the population size of each stratum, so that sampled strata can be
  re-weighted to alarms per day;
* all logs and token transfers of the kept transactions;
* the contracts created that day with the position of their creating
  transaction (`creations.parquet`), so that "called contract created
  earlier" can be decided per transaction;
* the day's pool state events (V2 `Sync`, V3 `Swap`) and the token pair of
  each V2 pool, so that pre-transaction prices are known (state before the
  transaction = last event of an earlier transaction of the same day);
* the WETH price in USD from the USDC/WETH V2 pool.

Transactions of any other DeFiHackLabs exploit are dropped, so they are
neither positives nor negatives. Output: data/derived/k4/<date>/*.parquet
(git-ignored, rebuilt from public data).

Usage
-----
    python scripts/k4_extract_days.py --workers 3
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import fsspec
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bal.data import defi as D   # noqa: E402

OUT = Path("data/derived/k4")
TX_COLS = ["hash", "from_address", "to_address", "nonce", "value", "receipt_gas_used",
           "receipt_status", "gas_price", "block_number", "transaction_index", "receipt_contract_address"]
LOG_COLS = ["address", "topics", "data", "transaction_hash", "log_index", "block_number", "transaction_index"]
TT_COLS = ["token_address", "from_address", "to_address", "value", "transaction_hash", "log_index", "block_number"]


def _read(table, date, cols):
    fs = fsspec.filesystem("https")
    parts = []
    for url in D.aws_files(table, date):
        for attempt in range(4):
            try:
                with fs.open(url, block_size=32 * 2**20) as f:
                    parts.append(pq.read_table(f, columns=cols))
                break
            except Exception:                      # network hiccup: retry with backoff
                if attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))
    return pa.concat_tables(parts)


def _creations(tx: pd.DataFrame) -> pd.DataFrame:
    """Contracts created that day with the position of the creating transaction."""
    c = tx[tx.receipt_contract_address.fillna("").str.len() > 0]      # "" for non-creating txs
    return pd.DataFrame({"address": c.receipt_contract_address.str.lower().to_numpy(),
                         "block_number": c.block_number.to_numpy(),
                         "transaction_index": c.transaction_index.to_numpy()})


def update_day(date, exclude):
    """Add creations.parquet and the count of excluded exploit txs to an older extract."""
    out = OUT / date
    info = json.loads((out / "done.json").read_text())
    if (out / "creations.parquet").exists() and "n_excluded_other_exploits" in info:
        return info
    tx = _read("transactions", date, ["hash", "block_number", "transaction_index",
                                      "receipt_contract_address"]).to_pandas().drop_duplicates("hash")
    _creations(tx).to_parquet(out / "creations.parquet", index=False)
    info["n_excluded_other_exploits"] = len(set(tx.hash) & exclude)
    (out / "done.json").write_text(json.dumps(info, indent=1))
    return info


def extract_day(date, attack_txs, exclude, providers, args):
    out = OUT / date
    if (out / "done.json").exists():
        return json.loads((out / "done.json").read_text())
    t0 = time.time()
    tx = _read("transactions", date, TX_COLS).to_pandas()
    tx = tx.drop_duplicates("hash")
    lg_t = _read("logs", date, LOG_COLS)
    # first topic, null for anonymous events without topics
    first = pc.list_slice(lg_t["topics"], 0, 1)
    idx = pc.list_parent_indices(first).to_numpy()
    t0v = np.full(len(lg_t), None, dtype=object)
    t0v[idx] = pc.list_flatten(first).to_numpy(zero_copy_only=False)
    topic0 = pa.array(t0v, type=pa.string())
    lg_t = lg_t.append_column("topic0", topic0)
    tt = _read("token_transfers", date, TT_COLS).to_pandas()
    for c in ("token_address", "from_address", "to_address"):
        tt[c] = "0x" + tt[c].str[-40:].str.lower()

    # small frame of the events needed for strata and state
    keep = pc.is_in(lg_t["topic0"], value_set=pa.array(sorted(D.KEEP_TOPICS)))
    ev = lg_t.filter(keep).to_pandas()
    ev["address"] = ev.address.str.lower()

    found = set(tx.hash) & set(attack_txs)
    v2 = set(ev[ev.topic0 == D.T_SYNC].address)
    flash = D.flash_hashes(ev, tt, v2)          # same rule as the feature has_flash
    ok = set(tx[tx.receipt_status == 1].hash)

    # contracts touched by the attack txs (protocol stratum)
    att_logs = lg_t.filter(pc.is_in(lg_t["transaction_hash"], value_set=pa.array(sorted(found), type=pa.string())))
    touched = {a.lower() for a in att_logs["address"].to_pylist()} - D.COMMON - providers
    rng = np.random.default_rng(int(date.replace("-", "")))
    strata = {}
    for h in found:
        strata[h] = "attack"
    for h in sorted(flash - found - exclude):
        strata[h] = "flash"
    prot_pop = []
    if touched:
        m = pc.is_in(pc.utf8_lower(lg_t["address"]), value_set=pa.array(sorted(touched), type=pa.string()))
        prot_pop = sorted(set(lg_t.filter(m)["transaction_hash"].to_pylist()) - set(strata) - exclude)
    prot = prot_pop if len(prot_pop) <= args.protocol_cap else list(rng.choice(prot_pop, args.protocol_cap, replace=False))
    for h in prot:
        strata[h] = "protocol"
    bg_pop = sorted(ok - set(strata) - set(prot_pop) - exclude)
    bg = list(rng.choice(bg_pop, min(args.background, len(bg_pop)), replace=False))
    for h in bg:
        strata[h] = "background"
    pop = {"attack": len(found), "flash": len(flash - found - exclude), "protocol": len(prot_pop),
           "background": len(bg_pop)}
    kept = {k: sum(v == k for v in strata.values()) for k in pop}

    out.mkdir(parents=True, exist_ok=True)
    sel = tx[tx.hash.isin(strata)].copy()
    sel["stratum"] = sel.hash.map(strata)
    sel["weight"] = sel.stratum.map(lambda s: pop[s] / max(1, kept[s]))
    sel.to_parquet(out / "txs.parquet", index=False)
    _creations(tx).to_parquet(out / "creations.parquet", index=False)
    sl = lg_t.filter(pc.is_in(lg_t["transaction_hash"], value_set=pa.array(sorted(strata), type=pa.string()))).to_pandas()
    sl["address"] = sl.address.str.lower()
    sl["topics"] = sl.topics.map(list)
    sl.to_parquet(out / "logs.parquet", index=False)
    tt[tt.transaction_hash.isin(strata)].to_parquet(out / "transfers.parquet", index=False)
    st = ev[ev.topic0.isin(D.STATE_TOPICS)][["address", "topic0", "data", "transaction_hash", "block_number",
                                            "transaction_index", "log_index"]]
    st.to_parquet(out / "state.parquet", index=False)
    pt = pd.concat([tt[tt.from_address.isin(v2)][["from_address", "token_address"]].set_axis(["pair", "token"], axis=1),
                    tt[tt.to_address.isin(v2)][["to_address", "token_address"]].set_axis(["pair", "token"], axis=1)])
    pt = pt.drop_duplicates().groupby("pair").token.agg(lambda s: sorted(set(s)))
    pt = pt[pt.map(len) == 2]
    pd.DataFrame({"pair": pt.index, "token0": pt.map(lambda x: x[0]).values,
                  "token1": pt.map(lambda x: x[1]).values}).to_parquet(out / "pairs.parquet", index=False)
    info = {"date": date, "n_tx": int(len(tx)), "n_success": int(len(ok)), "population": pop, "kept": kept,
            "attack_found": sorted(found), "attack_missing": sorted(set(attack_txs) - found),
            "n_excluded_other_exploits": len(set(tx.hash) & exclude),
            "seconds": round(time.time() - t0, 1)}
    (out / "done.json").write_text(json.dumps(info, indent=1))
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/raw/DeFiHackLabs")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--background", type=int, default=3000)
    ap.add_argument("--protocol-cap", type=int, default=5000)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--update", action="store_true",
                    help="only add creations.parquet / exclusion counts to existing day extracts")
    a = ap.parse_args()
    incs = D.load_incidents(a.root)
    all_mainnet = D.load_incidents(a.root, price_only=False)
    exclude_all = {t for i in all_mainnet for t in i.txs}
    providers = {D.DYDX_SOLO, "0xba12222222228d8ba445958a75a0704d566bf2c8",        # Balancer vault
                 "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9",                          # Aave v2 pool
                 "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2",                          # Aave v3 pool
                 "0x398ec7346dcd622edc5ae82352f02be94c62d119",                          # Aave v1 pool
                 "0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb",                          # Morpho Blue
                 "0x60744434d6339a6b27d73d9eda62b6f66a0a04fa"}                          # Maker DssFlash
    days = {}
    for i in incs:
        days.setdefault(i.date, set()).update(i.txs)
    if a.only:
        days = {d: v for d, v in days.items() if d in a.only}
    print(len(incs), "incidents on", len(days), "days")
    if a.update:
        dates = sorted(p.parent.name for p in OUT.glob("*/done.json"))
        txs_of = {}
        for i in incs:
            for dd in (-1, 0, 1):
                txs_of.setdefault(str((pd.Timestamp(i.date) + pd.Timedelta(days=dd)).date()), set()).update(i.txs)
        with ProcessPoolExecutor(a.workers) as ex:
            for d, j in [(d, ex.submit(update_day, d, exclude_all - txs_of.get(d, set()))) for d in dates]:
                print(d, "excluded:", j.result()["n_excluded_other_exploits"], flush=True)
        return
    jobs = []
    with ProcessPoolExecutor(a.workers) as ex:
        for d, txs in sorted(days.items()):
            jobs.append((d, ex.submit(extract_day, d, txs, exclude_all - txs, providers, a)))
        infos = []
        for d, j in jobs:
            info = j.result()
            infos.append(info)
            print(d, info["population"], "missing:", len(info["attack_missing"]), info["seconds"], "s", flush=True)
    # attack txs not found on the README day: try the neighbouring days once
    retry = {}
    for info in infos:
        for h in info["attack_missing"]:
            for dd in (-1, 1):
                nd = str((pd.Timestamp(info["date"]) + pd.Timedelta(days=dd)).date())
                retry.setdefault(nd, set()).add(h)
    retry = {d: v for d, v in retry.items() if not (OUT / d / "done.json").exists()}
    if retry:
        print("neighbour days:", sorted(retry))
        with ProcessPoolExecutor(a.workers) as ex:
            for d, j in [(d, ex.submit(extract_day, d, txs, exclude_all - txs, providers, a))
                         for d, txs in sorted(retry.items())]:
                info = j.result()
                print(d, info["population"], "found:", len(info["attack_found"]), flush=True)


if __name__ == "__main__":
    main()
