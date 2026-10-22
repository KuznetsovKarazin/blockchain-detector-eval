"""
Cross-chain bridge event streams.

Source: XChainWatcher (Augusto et al., arXiv:2410.02029), MIT licence,
https://github.com/AndreAugusto11/XChainWatcher, commit 4cc1ff1. Data cover
the Ronin bridge (Ethereum <-> Ronin, 2022-01-01 .. 2022-03-29) and the Nomad
bridge (Ethereum <-> Moonbeam, 2022-01-11 .. 2022-08-01).

What one row is
---------------
One *Ethereum-side release* of tokens by the bridge (an outflow). Both hacks
drained funds through such releases:

* Ronin, 2022-03-23: two releases authorised with compromised validator keys
  (173,600 ETH and 25.5M USDC, about $565M at the prices in the data).
* Nomad, 2022-08-01: 382 release EVENTS (in 167 `process` transactions; one
  transaction can release several tokens) without a matching deposit after a
  faulty Merkle-root initialisation (about $160M).

Two sources are combined:

* `datalog/<bridge>/results/CCTX_Withdrawal.csv` / `analysis/.../cctxs_withdrawals.csv`:
  releases MATCHED by the Datalog rules to a withdrawal request on the sidechain.
* `datalog/<bridge>/results/SC_WithdrawalsWithoutMatch.csv`: releases on
  Ethereum WITHOUT a matching request. All 2 Ronin and all 382 Nomad attack
  transactions are in this set, but so are 2,638 Ronin and 5 Nomad releases
  that are not attacks (requests outside the extracted window or not decoded).

Label = 1 iff the release is listed in `analysis/<bridge>/data/attacks.csv`.

USD columns
-----------
* `value_usd`      what a monitor can know at release time; used by features and
                   rules. Default `usd_mode="asof"`: for EVERY release (matched or
                   not) amount / 10^decimals times the close price of the last
                   daily candle that closed at or before the release
                   (bal.data.prices); `price_time_s` is that close time, so
                   availability can be checked row by row. Tokens without a
                   price series get 0 and `usd_unknown` = 1. The valuation does
                   not depend on whether a release was matched.
* `value_usd_ref`  reference value for loss accounting only: attack releases use
                   the value in attacks.csv, other releases equal `value_usd`.
* `value_usd_dataset`  the XChainWatcher value of matched releases (close of the
                   candle labelled with the request date, which closes after the
                   release for most rows); kept only for the ablation.

Ablations: `usd_mode="matched_dataset"` (dataset values for matched releases,
past-only estimate from them for unmatched ones: the previous version) and
`usd_mode="legacy"` (the first version: attack values from attacks.csv and a
+-3-day window that looks into the future), see docs/FINDINGS_BRIDGES.md.

Ordering: the data have timestamps (1 s) but no block number or log index;
events are ordered by (ts, tx_hash, withdrawal_id). Events sharing a timestamp
are treated as one block when losses are counted (bal.eval.alarm).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from bal.data.prices import price_asof

BRIDGES = {
    "ronin": {"dir": "ronin-bridge", "attack_day": "2022-03-23"},
    "nomad": {"dir": "nomad-bridge", "attack_day": "2022-08-01"},
}

DEFAULT_ROOT = Path("data/raw/XChainWatcher/cross-chain-rules-validator")


@dataclass
class BridgeStream:
    name: str
    events: pd.DataFrame
    attack_day: pd.Timestamp


def causal_usd(ev: pd.DataFrame, window_s: int = 3 * 86400, k_fallback: int = 20) -> tuple[np.ndarray, np.ndarray]:
    """Past-only USD estimate for unmatched events (usd_mode="matched_dataset").

    Uses only matched events that come EARLIER in the order, so the value of
    event i does not change when later events are appended (prefix invariance).
    Returns (value_usd, usd_unknown).
    """
    from collections import defaultdict, deque
    hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=5000))   # (ts, unit)
    val = np.zeros(len(ev))
    unknown = np.zeros(len(ev), dtype=np.int8)
    for i, (t, tok, amt, m, v) in enumerate(zip(ev.ts.to_numpy(), ev.token.to_numpy(), ev.amount.to_numpy(),
                                                ev.matched.to_numpy(), ev.value_usd_dataset.to_numpy())):
        if m:
            val[i] = v if np.isfinite(v) else 0.0
            if amt > 0 and np.isfinite(v) and v > 0:
                hist[tok].append((t, v / amt))
            continue
        h = hist.get(tok)
        if not h:
            unknown[i] = 1
            continue
        units = [u for ts_, u in h if ts_ >= t - window_s]
        if not units:
            units = [u for _, u in list(h)[-k_fallback:]]
        val[i] = float(np.median(units)) * amt
    return val, unknown


def _estimate_usd(unm: pd.DataFrame, matched: pd.DataFrame, window_s: int = 3 * 86400) -> np.ndarray:
    """Legacy estimator (+-3 days, may look ahead); kept only for the ablation."""
    m = matched[(matched.amount > 0) & (matched.value_usd > 0)].copy()
    m["unit"] = m.value_usd / m.amount
    out = np.full(len(unm), np.nan)
    by_tok = {t: g.sort_values("ts") for t, g in m.groupby("token")}
    for i, (t, ts, amt) in enumerate(zip(unm.token, unm.ts, unm.amount)):
        g = by_tok.get(t)
        if g is None:
            continue
        sel = g[(g.ts >= ts - window_s) & (g.ts <= ts + window_s)]
        if len(sel) == 0:
            sel = g.iloc[(g.ts - ts).abs().argsort()[:20]]
        out[i] = float(np.median(sel.unit)) * amt
    return out


def load_bridge(name: str, root: str | Path = DEFAULT_ROOT, usd_mode: str = "asof",
                price_root: str | Path | None = None) -> BridgeStream:
    cfg = BRIDGES[name]
    root = Path(root)
    an = root / "analysis" / cfg["dir"] / "data"
    dl = root / "datalog" / cfg["dir"] / "results"

    w = pd.read_csv(an / "cctxs_withdrawals.csv")
    matched = pd.DataFrame({
        "tx_hash": w.dst_tx_hash.str.lower(),
        "ts": w.dst_timestamp.astype(np.int64),
        "token": w.dst_token.str.lower(),
        "beneficiary": w.beneficiary.str.lower(),
        "withdrawal_id": w.withdrawal_id.astype(str),
        "amount": w.amount.astype(float),
        "value_usd": w.value_usd.astype(float),
        "matched": True,
        "latency_s": (w.dst_timestamp - w.orig_timestamp).astype(float),
    })

    u = pd.read_csv(dl / "SC_WithdrawalsWithoutMatch.csv", sep="\t", header=None,
                    names=["chain", "ts", "tx_hash", "withdrawal_id", "token", "beneficiary", "amount"])
    unm = pd.DataFrame({
        "tx_hash": u.tx_hash.str.lower(),
        "ts": u.ts.astype(np.int64),
        "token": u.token.str.lower(),
        "beneficiary": u.beneficiary.str.lower(),
        "withdrawal_id": u.withdrawal_id.astype(str),
        "amount": u.amount.astype(float),
        "matched": False,
        "latency_s": np.nan,
    })
    atk = pd.read_csv(an / "attacks.csv")
    atk_usd = dict(zip(atk.dst_transaction_hash.str.lower() + "|" + atk.beneficiary.str.lower(),
                       atk.value_usd.astype(float)))
    key = unm.tx_hash + "|" + unm.beneficiary
    attack_hashes = set(atk.dst_transaction_hash.str.lower())
    if usd_mode == "legacy":
        unm["value_usd"] = key.map(atk_usd)
        est = _estimate_usd(unm, matched)
        unm["value_usd"] = unm["value_usd"].fillna(pd.Series(est, index=unm.index))
    else:
        unm["value_usd"] = np.nan

    ev = pd.concat([matched, unm], ignore_index=True)
    ev = ev.sort_values(["ts", "tx_hash", "withdrawal_id"], kind="mergesort").reset_index(drop=True)
    ev["label"] = ev.tx_hash.isin(attack_hashes).astype(int)
    ev["event_id"] = ev.tx_hash + "|" + ev.withdrawal_id + "|" + ev.beneficiary
    if usd_mode == "legacy":
        ev["value_usd"] = ev["value_usd"].fillna(0.0).clip(lower=0)
        ev["usd_unknown"] = 0
        ev["value_usd_ref"] = ev["value_usd"]
    elif usd_mode in ("asof", "matched_dataset"):
        ev["value_usd_dataset"] = ev["value_usd"]
        if usd_mode == "asof":
            pr = Path(price_root) if price_root is not None else root.parent / "token-price-data"
            price, ptime, dec = price_asof(name, ev.token.to_numpy(), ev.ts.to_numpy(), pr)
            unk = ~np.isfinite(price)
            v = np.where(unk, 0.0, ev.amount.to_numpy() / 10.0 ** dec * np.nan_to_num(price))
            ev["price_time_s"] = ptime
            unk = unk.astype(np.int8)
        else:
            v, unk = causal_usd(ev)
        ev["value_usd"] = np.clip(v, 0, None)
        ev["usd_unknown"] = unk
        ref = (ev.tx_hash + "|" + ev.beneficiary).map(atk_usd)
        ev["value_usd_ref"] = np.where(ev.label == 1, ref.fillna(ev.value_usd), ev.value_usd)
    else:
        raise ValueError(usd_mode)
    ev["time"] = pd.to_datetime(ev.ts, unit="s")
    return BridgeStream(name=name, events=ev, attack_day=pd.Timestamp(cfg["attack_day"]))


def summary(stream: BridgeStream) -> dict:
    e = stream.events
    return {
        "bridge": stream.name,
        "n_events": int(len(e)),
        "n_attack": int(e.label.sum()),
        "n_attack_tx": int(e.loc[e.label == 1, "tx_hash"].nunique()),
        "attack_usd_ref": float(e.loc[e.label == 1, "value_usd_ref"].sum()),
        "attack_usd_observable": float(e.loc[e.label == 1, "value_usd"].sum()),
        "n_usd_unknown": int(e.usd_unknown.sum()),
        "normal_usd": float(e.loc[e.label == 0, "value_usd"].sum()),
        "n_unmatched_non_attack": int(((~e.matched) & (e.label == 0)).sum()),
        "start": str(e.time.min()),
        "end": str(e.time.max()),
        "n_tokens": int(e.token.nunique()),
        "n_beneficiaries": int(e.beneficiary.nunique()),
    }
