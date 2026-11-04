"""
TV round 2 / X7 pilot  One quiet 2025 day processed in full (docs/PROTOCOLS_TV.md,
"Round 2"): every successful transaction of the day is extracted and scored, and
the alarms of the fixed thresholds (t2025 split, seed 0, budgets 1 and 10 per
day, thresholds fitted as in tv4/tv9) are counted exactly and compared with the
estimate from the same day's 3,000-row background sample and its 90 %
Clopper-Pearson interval.

    python scripts/tv10_full_day.py --date 2025-02-01

The extracted day goes to data/derived/k4_full/<date>/ (git-ignored, rebuilt
from public data); features are cached there. Results: results/kan/tv10_<stamp>/.
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
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bal.features.defi_features import FEATURES, day_features     # noqa: E402
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


def extract(date):
    from bal.data import defi as D
    incs = D.load_incidents("data/raw/DeFiHackLabs", price_only=False)
    exclude = {t for i in incs for t in i.txs}
    TV3.OUT = FULL
    t0 = time.time()
    info = TV3.run(date, exclude, 10 ** 9)          # background = every successful transaction
    print("extracted", date, info["population"], round(time.time() - t0), "s", flush=True)
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2025-02-01")
    ap.add_argument("--models", default="logreg,rf,lgbm")
    ap.add_argument("--out", default="results/kan")
    a = ap.parse_args()
    run = Path(a.out) / time.strftime("tv10_%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    info = extract(a.date)
    cache = FULL / a.date / "features.parquet"
    if cache.exists():
        full = pd.read_parquet(cache)
    else:
        t0 = time.time()
        full = day_features(FULL / a.date)
        full.to_parquet(cache, index=False)
        print("features", full.shape, round(time.time() - t0), "s", flush=True)
    full = full[full.receipt_status == 1].reset_index(drop=True)
    full["day"], full["y"], full["quiet"] = a.date, 0, True

    df = TV4.load(Path(TV4.K4_RUN), Path(TV4.QUIET))
    X = K4.transform(df)
    Xf = K4.transform(full)
    y, q = df.y.to_numpy(), df.quiet.to_numpy()
    year = df.day.str[:4].to_numpy()
    tr_end, va_year, te_years = TV4.SPLITS["t2025"]
    assert a.date[:4] in te_years
    tr = (year <= tr_end) & ~q
    va = year == va_year
    va_i, va_q = va & ~q, va & q
    samp = (df.day.to_numpy() == a.date) & q
    assert samp.any(), "the date must be one of the sampled quiet days"
    h = max(1, round((kan_param_count([X.shape[1], 8, 1], 5) - 1) / (X.shape[1] + 2)))
    st_s, w_s = df.stratum.to_numpy(), df.weight.to_numpy()
    fl_f = full.stratum.to_numpy() == "flash"
    rows = []
    for name in a.models.split(","):
        t0 = time.time()
        set_seed(0)
        mdl = K4.make(name, 0, h).fit(X[tr], y[tr])
        s = np.asarray(mdl.predict_score(X), float)
        sf = np.asarray(mdl.predict_score(Xf), float)
        for b in BUDGETS:
            for sname, mask in (("fixed_incident", va_i), ("fixed_quiet", va_q)):
                neg = mask & (y == 0)
                t, _ = K4.budget_threshold(s[neg], w_s[neg], df.day[mask].nunique(), b)
                al_f = sf >= t
                al_s = (s >= t) & samp
                bg_s = samp & (st_s == "background")
                k, n = int((al_s & bg_s).sum()), int(bg_s.sum())
                per_day = float(w_s[bg_s].sum())
                lo = beta.ppf(0.05, k, n - k + 1) if k > 0 else 0.0
                hi = beta.ppf(0.95, k + 1, n - k)
                rows.append({"model": name, "budget": b, "strategy": sname, "threshold": float(t),
                             "full_flash": int((al_f & fl_f).sum()), "full_other": int((al_f & ~fl_f).sum()),
                             "full_total": int(al_f.sum()),
                             "sample_flash": float(w_s[al_s & (st_s == "flash")].sum()),
                             "sample_background": float(w_s[al_s & bg_s].sum()),
                             "sample_background_rows_over": k, "sample_background_rows": n,
                             "sample_background_cp_lo": float(lo * per_day),
                             "sample_background_cp_hi": float(hi * per_day)})
        print(name, round(time.time() - t0), "s", flush=True)
    res = pd.DataFrame(rows)
    res["sample_total"] = res.sample_flash + res.sample_background
    atomic_to_csv(res, run / "full_day_alarms.csv", index=False)
    dump_json({"date": a.date, "extraction": info, "n_scored": int(len(full)),
               "n_flash": int(fl_f.sum()), "rows": res.round(3).to_dict("records")}, run / "summary.json")
    print(res.round(2).to_string())
    write_manifest(run, script=Path(__file__).name, config=vars(a),
                   data_files=[Path(TV4.K4_RUN) / "features.parquet"], extra={"split": "t2025"})
    print("wrote", run)


if __name__ == "__main__":
    main()
