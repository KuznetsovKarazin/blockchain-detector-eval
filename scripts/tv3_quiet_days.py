"""
TV / X3  Extract Ethereum days without a DeFiHackLabs mainnet incident, so
that K4 thresholds can be checked against a deployment-like false-alarm load.

Dates: uniform draws (seed 20261030) from 2024, 2025 and 2026-01-01..2026-09-30
(8 / 8 / 6 days), excluding every day within +-3 days of any mainnet incident
of DeFiHackLabs @23c7bd8 (all 146, not only the 40 of the K4 cohort).
Extraction: `k4_extract_days.extract_day` with no attack transactions, so a
day keeps its complete flash-loan stratum and a weighted uniform background
sample of 3,000 successful transactions (no attack or protocol stratum).
Output: data/derived/k4_quiet/<date>/ (git-ignored, rebuilt from public data).

Usage
-----
    python scripts/tv3_quiet_days.py --workers 3
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bal.data import defi as D   # noqa: E402

_spec = importlib.util.spec_from_file_location("k4x", ROOT / "scripts" / "k4_extract_days.py")
K4X = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(K4X)

OUT = Path("data/derived/k4_quiet")
SEED = 20261030
PLAN = {"2024": ("2024-01-01", "2024-12-31", 8),
        "2025": ("2025-01-01", "2025-12-31", 8),
        "2026": ("2026-01-01", "2026-09-30", 6)}
PROVIDERS = {D.DYDX_SOLO, "0xba12222222228d8ba445958a75a0704d566bf2c8", "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9",
             "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2", "0x398ec7346dcd622edc5ae82352f02be94c62d119",
             "0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb", "0x60744434d6339a6b27d73d9eda62b6f66a0a04fa"}


def quiet_dates(incidents) -> list[str]:
    blocked = set()
    for i in incidents:
        for dd in range(-3, 4):
            blocked.add(str((pd.Timestamp(i.date) + pd.Timedelta(days=dd)).date()))
    rng = np.random.default_rng(SEED)
    out = []
    for _, (lo, hi, n) in PLAN.items():
        pool = [str(d.date()) for d in pd.date_range(lo, hi) if str(d.date()) not in blocked]
        out += sorted(rng.choice(pool, n, replace=False).tolist())
    return out


def run(date, exclude, background):
    K4X.OUT = OUT
    args = argparse.Namespace(background=background, protocol_cap=0)
    return K4X.extract_day(date, set(), exclude, PROVIDERS, args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/raw/DeFiHackLabs")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--background", type=int, default=3000)
    ap.add_argument("--dates-only", action="store_true")
    a = ap.parse_args()
    incs = D.load_incidents(a.root, price_only=False)
    exclude = {t for i in incs for t in i.txs}
    dates = quiet_dates(incs)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dates.json").write_text(json.dumps({"seed": SEED, "plan": PLAN, "dates": dates}, indent=1))
    print(dates, flush=True)
    if a.dates_only:
        return
    with ProcessPoolExecutor(a.workers) as ex:
        for d, j in [(d, ex.submit(run, d, exclude, a.background)) for d in dates]:
            info = j.result()
            print(d, info["population"], info["kept"], info["seconds"], "s", flush=True)


if __name__ == "__main__":
    main()
