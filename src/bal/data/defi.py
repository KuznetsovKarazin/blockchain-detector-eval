"""
DeFi exploits on Ethereum (K4): incidents from DeFiHackLabs, transactions from
the AWS public blockchain dataset.

Incidents
---------
DeFiHackLabs (SunWeb3Sec/DeFiHackLabs @23c7bd8, Apache-2.0) keeps one Foundry
proof of concept per exploit (`src/test/<yyyy-mm>/<name>.sol`) and one README
entry per exploit (`### <yyyymmdd> <name> - <type or summary>`). An incident is
kept as a positive when

* the PoC forks Ethereum mainnet (`createSelectFork("mainnet", ...)`),
* the PoC uses a flash loan (the word "flash" appears in its code),
* the README entry names a price or oracle manipulation (keywords below), and
* the PoC or its README entry links at least one Ethereum attack transaction
  (etherscan, Phalcon / BlockSec explorer, or an "Attack Tx" line).

The README heading, not the code, decides the type, so the selection does not
look at the transactions it will later score. Every linked transaction is a
candidate positive; `attack_rows` keeps those that are found on the incident
day (or the day before / after) and succeeded.

Transactions
------------
`s3://aws-public-blockchain/v1.0/eth/{transactions,logs,token_transfers}/
date=YYYY-MM-DD/` (public, read over HTTPS with column projection). Traces
are not used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DEFAULT_ROOT = Path("data/raw/DeFiHackLabs")
AWS = "https://aws-public-blockchain.s3.us-east-2.amazonaws.com"

PRICE_WORDS = r"price|oracle|manipul|spot|reserve|twap|exchange rate|getreserves|\bsync\b|\bskim\b"


@dataclass(frozen=True)
class Incident:
    date: str            # yyyy-mm-dd from the README heading
    name: str
    heading: str
    sol: str
    fork_block: int | None
    txs: tuple[str, ...]


TX_PATTERNS = (r"etherscan\.io/tx/(0x[0-9a-fA-F]{64})", r"tx/eth(?:ereum)?/(0x[0-9a-fA-F]{64})",
               r"[Aa]ttack\s*[Tt]x[^\n]{0,40}?(0x[0-9a-fA-F]{64})")


def _txs(text: str) -> set[str]:
    return {t.lower() for p in TX_PATTERNS for t in re.findall(p, text)}


def _headings(root: Path) -> dict[str, tuple[str, set[str]]]:
    """PoC path -> (README heading, attack transactions linked in that README entry)."""
    out = {}
    for f in sorted((root / "past").glob("*/README.md")) + [root / "README.md"]:
        text = f.read_text(errors="replace").replace("\r", "")
        for block in re.split(r"\n(?=### \d{8})", text):
            head = block.split("\n", 1)[0]
            if not re.match(r"### \d{8}", head):
                continue
            for sol in set(re.findall(r"(src/test/[^)\s]+?\.sol)", block)):
                out[sol] = (head[4:].strip(), _txs(block))
    return out


def load_incidents(root: str | Path = DEFAULT_ROOT, price_only: bool = True) -> list[Incident]:
    """Ethereum flash-loan incidents (price / oracle manipulation if `price_only`)."""
    root = Path(root)
    heads = _headings(root)
    out = []
    for sol in sorted(root.glob("src/test/*/*.sol")):
        rel = str(sol.relative_to(root))
        src = sol.read_text(errors="replace")
        m = re.search(r'createSelectFork\(\s*"([^"]+)"\s*(?:,\s*([0-9_]+))?', src)
        if not m or m.group(1) != "mainnet" or not re.search("flash", src, re.I):
            continue
        head, readme_txs = heads.get(rel, ("", set()))
        hm = re.match(r"(\d{4})(\d{2})(\d{2})\s*-?\s*(.+)", head)
        if not hm:
            continue
        if price_only and not re.search(PRICE_WORDS, head.lower()):
            continue
        txs = tuple(sorted(_txs(src) | readme_txs))
        if not txs:
            continue
        name = re.split(r"\s+-\s+", hm.group(4), maxsplit=1)[0].strip()
        out.append(Incident(f"{hm.group(1)}-{hm.group(2)}-{hm.group(3)}", name, head, rel,
                            int(m.group(2).replace("_", "")) if m.group(2) else None, txs))
    return out


def incidents_frame(incs: list[Incident]) -> pd.DataFrame:
    return pd.DataFrame([{"date": i.date, "name": i.name, "heading": i.heading, "sol": i.sol,
                          "fork_block": i.fork_block, "n_txs": len(i.txs), "txs": ";".join(i.txs)}
                         for i in incs])


def aws_files(table: str, date: str) -> list[str]:
    """HTTPS URLs of the parquet parts of one table and day."""
    import urllib.request
    q = f"{AWS}/?list-type=2&prefix=v1.0/eth/{table}/date={date}/"
    xml = urllib.request.urlopen(q, timeout=60).read().decode()
    return [f"{AWS}/{k}" for k in re.findall(r"<Key>([^<]+\.parquet)</Key>", xml)]


# ---------------------------------------------------------------------------
# event topics (keccak-256 of the event signature)
T_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
T_SYNC = "0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1"        # Uniswap V2 pair
T_SWAP_V2 = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
T_SWAP_V3 = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
FLASH_TOPICS = {
    "0xbdbdb71d7860376ba52b25a5028beea23581364a40522f6bcfb86bb1f2dca633": "uniswap_v3_flash",
    "0x631042c832b07452973831137f2d73e395028b44b250dedc5abb0ee766e168ac": "aave_v2",
    "0xefefaba5e921573100900a3ad9cf29f222d995fb3b6045797eaea7521bd8d6f0": "aave_v3",
    "0x5b8f46461c1dd69fb968f1a003acee221ea3e19540e350233b612ddb43433b55": "aave_v1",
    "0x0d7d75e01ab95780d3cd1c8ec0dd6c2ce19e3a20427eec8bf53283b6fb8e95f0": "balancer_or_erc3156",
    "0xc76f1b4fe4396ac07a9fa55a415d4ca430e72651d37d3401f3bed7cb13fc4f12": "morpho",
}
T_DYDX_WITHDRAW = "0xbc83c08f0b269b1726990c8348ffdf1ae1696244a14868d766e542a2f18cd7d4"
T_DYDX_DEPOSIT = "0x2bad8bc95088af2c247b30fa2b2e6a0886f88625e0945cd3051008e0e270198f"
DYDX_SOLO = "0x1e0447b19bb6ecfdae1e4ae1694b0c3659614e4e"
STATE_TOPICS = {T_SYNC, T_SWAP_V3}
KEEP_TOPICS = {T_SYNC, T_SWAP_V2, T_SWAP_V3, T_DYDX_WITHDRAW, T_DYDX_DEPOSIT, *FLASH_TOPICS}

WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
STABLES = {"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": 6,     # USDC
           "0xdac17f958d2ee523a2206206994597c13d831ec7": 6,     # USDT
           "0x6b175474e89094c44da98b954eedeac495271d0f": 18}    # DAI
USDC_WETH_V2 = "0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc"     # token0 USDC, token1 WETH
COMMON = {WETH, *STABLES, "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"}   # + WBTC


def addr(word: str) -> str:
    """32-byte topic / padded address -> 0x + 40 hex."""
    return "0x" + word[-40:].lower()


def words(data: str) -> list[int]:
    h = data[2:] if data.startswith("0x") else data
    return [int(h[i:i + 64], 16) for i in range(0, len(h) - 63, 64)]


def flash_hashes(logs: pd.DataFrame, transfers: pd.DataFrame, v2_pairs: set[str]) -> set[str]:
    """Transactions with a flash loan, by one rule for every transaction.

    * a flash-loan event (`FLASH_TOPICS`);
    * dYdX SoloMargin `Withdraw` and `Deposit` in the same transaction;
    * a Uniswap V2 flash swap: in a transaction with a V2 `Swap`, a V2 pair
      (`v2_pairs`, the emitters of `Sync` that day, or an emitter of a V2
      `Swap` in `logs`) transfers a token out before any transfer into it.

    `logs` needs transaction_hash, address, topic0; `transfers` needs
    transaction_hash, from_address, to_address, log_index.
    """
    out = set(logs.loc[logs.topic0.isin(FLASH_TOPICS), "transaction_hash"])
    dy = logs[logs.address == DYDX_SOLO]
    out |= set(dy.loc[dy.topic0 == T_DYDX_WITHDRAW, "transaction_hash"]) & \
        set(dy.loc[dy.topic0 == T_DYDX_DEPOSIT, "transaction_hash"])
    swaps = logs[logs.topic0 == T_SWAP_V2]
    swap_tx = set(swaps.transaction_hash)
    v2_pairs = set(v2_pairs) | set(swaps.address)       # V2-style pools without a Sync count too
    t = transfers[transfers.transaction_hash.isin(swap_tx)]
    first_out = t[t.from_address.isin(v2_pairs)].groupby(["transaction_hash", "from_address"]).log_index.min()
    first_in = t[t.to_address.isin(v2_pairs)].groupby(["transaction_hash", "to_address"]).log_index.min()
    first_out.index.names = first_in.index.names = ["tx", "pair"]
    j = pd.concat([first_out.rename("o"), first_in.rename("i")], axis=1).dropna()
    out |= set(j[j.o < j.i].index.get_level_values("tx"))
    return out
