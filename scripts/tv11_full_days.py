"""
TV round 2 / X7  Fully processed Ethereum days (docs/PROTOCOLS_TV.md, "Round 2",
change of 2026-11-04).

(i)  All 22 quiet days are extracted in full and scored by the seed-0 models of
     the t2025 split (logistic regression, RF, LightGBM). Alarms per day of the
     fixed thresholds (fitted on the sampled validation year as in tv4/tv9) are
     counted exactly on the 14 test days, next to the sample estimate of the
     same day; as a sensitivity, fixed_quiet is refitted on the 8 full quiet
     days of 2024 (fixed_quiet_full).
(ii) Two windows of 7 consecutive days without a DeFiHackLabs mainnet incident
     within +-3 days (2025 and 2026; first window after a seeded uniform start)
     are processed in full. Days 2-7 of each window compare the fixed
     thresholds with a sequential rule (threshold = the score of the b-th
     highest transaction per 24 hours over the previous 7,200 blocks, updated
     every 300 blocks) and the retrospective per-day top-k (b by construction).

    python scripts/tv11_full_days.py [--run results/kan/tv11_<stamp>]

Days go to data/derived/k4_full/<date>/ (git-ignored); the per-day scores are
kept in data/derived/k4_full/scores/ (seed-0 t2025 models), so finished days
are skipped on a re-run. Results: results/kan/tv11_<stamp>/.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bal.data import defi as D                                    # noqa: E402
from bal.features.defi_features import day_features               # noqa: E402
from bal.models.kan import kan_param_count                        # noqa: E402
from bal.utils.repro import atomic_to_csv, dump_json, set_seed, write_manifest   # noqa: E402


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TV4 = _load("tv4", "tv4_k4_temporal.py")
TV3 = _load("tv3", "tv3_quiet_days.py")
K4 = TV4.K4
FULL = Path("data/derived/k4_full")
BUDGETS = (1, 10)
MODELS = ("logreg", "rf", "lgbm")
WINDOW_SEED = 20261104
WINDOW_RANGES = {"2025": ("2025-01-01", "2025-12-31"), "2026": ("2026-01-01", "2026-09-30")}
CHUNK, HISTORY = 300, 7200


def blocked_days(incs):
    out = set()
    for i in incs:
        for dd in range(-3, 4):
            out.add(str((pd.Timestamp(i.date) + pd.Timedelta(days=dd)).date()))
    return out


def windows(blocked):
    rng = np.random.default_rng(WINDOW_SEED)
    out = {}
    for y, (lo, hi) in WINDOW_RANGES.items():
        days = [str(d.date()) for d in pd.date_range(lo, hi)]
        start = int(rng.integers(0, len(days) - 7))
        for i in range(start, len(days) - 6):
            if not any(d in blocked for d in days[i:i + 7]):
                out[y] = days[i:i + 7]
                break
    return out


def full_day(date, exclude):
    feats = FULL / date / "features.parquet"
    if not feats.exists():
        TV3.OUT = FULL
        t0 = time.time()
        TV3.run(date, exclude, 10 ** 9)
        f = day_features(FULL / date)
        f.to_parquet(feats, index=False)
        # the raw day is large; keep the features and the extraction record only
        for p in ("txs", "logs", "transfers", "state", "creations", "pairs", "pair_tokens"):
            (FULL / date / f"{p}.parquet").unlink(missing_ok=True)
        print("full day", date, len(f), round(time.time() - t0), "s", flush=True)
    f = pd.read_parquet(feats)
    return f[f.receipt_status == 1].reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="existing run folder: finished days are skipped")
    ap.add_argument("--out", default="results/kan")
    a = ap.parse_args()
    run = Path(a.run) if a.run else Path(a.out) / time.strftime("tv11_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    (FULL / "scores").mkdir(parents=True, exist_ok=True)
    incs = D.load_incidents("data/raw/DeFiHackLabs", price_only=False)
    exclude = {t for i in incs for t in i.txs}
    quiet = json.loads((TV4.QUIET / "dates.json").read_text())["dates"]
    win = windows(blocked_days(incs))
    dump_json({"quiet_days": quiet, "windows": win}, run / "dates.json")
    print("windows", win, flush=True)

    df = TV4.load(Path(TV4.K4_RUN), Path(TV4.QUIET))
    X = K4.transform(df)
    y, q = df.y.to_numpy(), df.quiet.to_numpy()
    w, st, day = df.weight.to_numpy(), df.stratum.to_numpy(), df.day.to_numpy()
    year = df.day.str[:4].to_numpy()
    tr_end, va_year, te_years = TV4.SPLITS["t2025"]
    tr = (year <= tr_end) & ~q
    va_i, va_q = (year == va_year) & ~q, (year == va_year) & q
    h = max(1, round((kan_param_count([X.shape[1], 8, 1], 5) - 1) / (X.shape[1] + 2)))
    models, s_samp = {}, {}
    for name in MODELS:
        set_seed(0)
        models[name] = K4.make(name, 0, h).fit(X[tr], y[tr])
        s_samp[name] = np.asarray(models[name].predict_score(X), float)

    # scores of every full day (cached per day as npz: block_number, flash flag, scores)
    def scores(date):
        p = FULL / "scores" / f"{date}.npz"
        if p.exists():
            z = np.load(p)
            return {k: z[k] for k in z.files}
        f = full_day(date, exclude)
        Xf = K4.transform(f)
        z = {"block": f.block_number.to_numpy(), "flash": (f.stratum.to_numpy() == "flash")}
        for name in MODELS:
            z[name] = np.asarray(models[name].predict_score(Xf), float)
        np.savez_compressed(p, **z)
        (FULL / date / "features.parquet").unlink(missing_ok=True)   # disk: the scores are kept
        return z

    q24 = [d for d in quiet if d[:4] == va_year]
    q_test = [d for d in quiet if d[:4] in te_years]
    win_days = sorted({d for ds in win.values() for d in ds})
    S = {d: scores(d) for d in q24 + q_test + win_days}

    thr = {}
    for name in MODELS:
        s = s_samp[name]
        full24 = np.concatenate([S[d][name] for d in q24])
        for b in BUDGETS:
            for sname, mask in (("fixed_incident", va_i), ("fixed_quiet", va_q)):
                neg = mask & (y == 0)
                thr[name, b, sname] = K4.budget_threshold(s[neg], w[neg], df.day[mask].nunique(), b)[0]
            thr[name, b, "fixed_quiet_full"] = K4.budget_threshold(full24, np.ones(len(full24)), len(q24), b)[0]

    rows = []
    for d in q_test:
        samp = (day == d) & q
        for name in MODELS:
            sf = S[d][name]
            for (nm, b, sname), t in thr.items():
                if nm != name:
                    continue
                al = sf >= t
                als = samp & (s_samp[name] >= t)
                rows.append({"part": "quiet_test", "date": d, "model": name, "budget": b, "strategy": sname,
                             "threshold": t, "full_alarms": int(al.sum()),
                             "full_flash": int((al & S[d]["flash"]).sum()),
                             "sample_estimate": float(w[als].sum()) if sname != "fixed_quiet_full" else np.nan,
                             "n_tx": int(len(sf))})

    for y_, ds in win.items():
        blocks = np.concatenate([S[d]["block"] for d in ds])
        order = np.argsort(blocks, kind="stable")
        blocks = blocks[order]
        day_of = np.concatenate([np.full(len(S[d]["block"]), i) for i, d in enumerate(ds)])[order]
        for name in MODELS:
            s = np.concatenate([S[d][name] for d in ds])[order]
            for b in BUDGETS:
                seq = np.zeros(len(s), bool)
                first = blocks[day_of == 1].min()
                for c0 in range(int(first), int(blocks.max()) + 1, CHUNK):
                    hist = s[(blocks >= c0 - HISTORY) & (blocks < c0)]
                    t = np.sort(hist)[-b] if len(hist) >= b else -np.inf
                    m = (blocks >= c0) & (blocks < c0 + CHUNK)
                    seq[m] = s[m] >= t
                for i, d in enumerate(ds[1:], start=1):
                    m = day_of == i
                    r = {"part": f"window_{y_}", "date": d, "model": name, "budget": b, "n_tx": int(m.sum())}
                    rows.append({**r, "strategy": "sequential_24h", "full_alarms": int(seq[m].sum())})
                    for sname in ("fixed_incident", "fixed_quiet", "fixed_quiet_full"):
                        rows.append({**r, "strategy": sname, "threshold": thr[name, b, sname],
                                     "full_alarms": int((s[m] >= thr[name, b, sname]).sum())})
    res = pd.DataFrame(rows)
    atomic_to_csv(res, run / "full_days.csv", index=False)
    summ = (res.groupby(["part", "model", "budget", "strategy"])
            .agg(days=("date", "nunique"), mean=("full_alarms", "mean"), median=("full_alarms", "median"),
                 min=("full_alarms", "min"), max=("full_alarms", "max"),
                 sample_mean=("sample_estimate", "mean")).reset_index())
    atomic_to_csv(summ, run / "summary.csv", index=False)
    dump_json({"windows": win, "summary": summ.round(3).to_dict("records")}, run / "summary.json")
    pd.set_option("display.width", 220)
    print(summ.round(2).to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(TV4.K4_RUN) / "features.parquet"], extra={"split": "t2025"})
    print("wrote", run)


if __name__ == "__main__":
    main()
