"""
Token prices with a known availability time, for the bridge streams.

Source: the raw daily candles shipped with XChainWatcher
(`token-price-data/<bridge>/bitget/*.csv`, columns timeOpen ... priceClose).
The millisecond timestamps in these files are stored in rounded scientific
notation (5-6 significant digits, error <= 5e6 ms). Every open and close time
lies within 4.8e6 ms of 16:00 UTC (00:00 UTC+8), so the exact times are
recovered by snapping to that daily grid; the loader checks the residual.

Availability rule: a release at time t is valued with the close price of the
LAST candle whose close time is <= t (the previous completed day). XChainWatcher
values a transfer with the close of the candle labelled with the transfer's
date, which closes up to ~40 h after the transfer.

Token address -> price series and decimals follow the maps in the
XChainWatcher analysis notebooks (MAP_SRC_DST_TOKENS, MAP_TOKEN_TO_ID,
MAP_TOKEN_TO_DECIMALS), written here for the Ethereum-side addresses of the
released tokens. Tokens without a series (MYT and five tokens with no entry)
get no price.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DAY_MS = 86_400_000
GRID_MS = 16 * 3_600_000          # candles open at 16:00 UTC
MAX_RESIDUAL_MS = 5_000_000       # half of the rounding step of the files

# Ethereum token address -> (price series id, decimals)
TOKENS = {
    "ronin": {
        "0xbb0e17ef65f82ab018d8edd776e8dd940327b28b": ("axie-infinity", 18),
        "0xcc8fa225d80b9c7d42f96e9570156c65d6caaa25": ("smooth-love-potion", 0),
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("usdc", 6),
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": ("weth", 18),
    },
    "nomad": {
        "0xba8d75baccc4d5c4bd814fde69267213052ea663": ("moonbeam", 18),
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("usdc", 6),
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": ("weth", 18),
        "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": ("wrapped-bitcoin", 8),
        "0x6b175474e89094c44da98b954eedeac495271d0f": ("dai", 18),
        "0xdac17f958d2ee523a2206206994597c13d831ec7": ("tether-usdt", 6),
        "0xd417144312dbf50465b1c641d016962017ef6240": ("covalent", 18),
        "0x853d955acef822db058eb8505911ed77f175b99e": ("frax", 18),
        "0x3432b6a60d23ca0dfca7761b7ab56459d9c964d0": ("frax-share", 18),
    },
}

BRIDGE_DIRS = {"ronin": "ronin-bridge", "nomad": "nomad-bridge"}
DEFAULT_PRICE_ROOT = Path("data/raw/XChainWatcher/token-price-data")


def _snap(ms: pd.Series, what: str, path: Path) -> np.ndarray:
    v = ms.str.replace(",", ".").astype(float).to_numpy()
    k = np.round((v - GRID_MS) / DAY_MS)
    exact = k * DAY_MS + GRID_MS
    res = np.abs(v - exact).max()
    if res > MAX_RESIDUAL_MS:
        raise ValueError(f"{path.name}: {what} off the 16:00 UTC grid by {res:.0f} ms")
    return (exact // 1000).astype(np.int64)


def price_files(bridge: str, root: str | Path = DEFAULT_PRICE_ROOT) -> dict[str, Path]:
    d = Path(root) / BRIDGE_DIRS[bridge] / "bitget"
    out = {}
    for f in sorted(d.glob("*.csv")):
        out["-".join(f.stem.split("-")[:-1])] = f
    return out


def load_series(path: Path) -> pd.DataFrame:
    """Candles of one token: open_s, close_s (UTC seconds), close price; sorted by close."""
    raw = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig")
    df = pd.DataFrame({
        "open_s": _snap(raw.timeOpen, "timeOpen", path),
        "close_s": _snap(raw.timeClose, "timeClose", path),
        "price": raw.priceClose.str.replace(",", ".").astype(float),
    }).sort_values("close_s").reset_index(drop=True)
    if not ((df.close_s - df.open_s) == 86_400).all():
        raise ValueError(f"{path.name}: not daily candles")
    if df.close_s.duplicated().any():
        raise ValueError(f"{path.name}: duplicate candles")
    return df


def price_asof(bridge: str, token: np.ndarray, ts: np.ndarray, root: str | Path = DEFAULT_PRICE_ROOT):
    """Unit price available at each ts, with the close time of the candle used.

    Returns (price, price_time_s, decimals); price is NaN when the token has no
    series or no candle has closed yet.
    """
    files = price_files(bridge, root)
    token = np.asarray(token)
    ts = np.asarray(ts, dtype=np.int64)
    price = np.full(len(ts), np.nan)
    ptime = np.full(len(ts), -1, dtype=np.int64)
    dec = np.zeros(len(ts), dtype=np.int64)
    for addr, (sid, d) in TOKENS[bridge].items():
        sel = np.flatnonzero(token == addr)
        if len(sel) == 0:
            continue
        s = load_series(files[sid])
        j = np.searchsorted(s.close_s.to_numpy(), ts[sel], side="right") - 1
        ok = j >= 0
        price[sel[ok]] = s.price.to_numpy()[j[ok]]
        ptime[sel[ok]] = s.close_s.to_numpy()[j[ok]]
        dec[sel] = d
    return price, ptime, dec


def used_files(bridge: str, root: str | Path = DEFAULT_PRICE_ROOT) -> list[Path]:
    files = price_files(bridge, root)
    return [files[sid] for sid, _ in TOKENS[bridge].values()]
