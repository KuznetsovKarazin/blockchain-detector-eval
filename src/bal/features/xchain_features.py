"""
Causal, chain-agnostic features for bridge outflow events.

Every feature of event t uses only events with index < t (strictly earlier in
the processing order). Nothing is fitted on the test period. Features are
defined without bridge-specific constants so that a detector trained on one
bridge can be applied to another (transfer experiment, HB.3).

Destination-chain view (D):  what a monitor of Ethereum alone can see.
Cross-chain view (X):        D + whether the outflow has a source-chain request.
"""

from __future__ import annotations

from collections import defaultdict, deque

import numpy as np
import pandas as pd

D_FEATURES = [
    "log_value",            # log1p(USD value)
    "value_vs_token_med",   # log value minus running median log value of the token
    "token_novel",          # token never seen before
    "token_share",          # share of past events in this token
    "benef_novel",          # beneficiary never seen before
    "benef_log_count",      # log1p(past events to this beneficiary)
    "log_n_1h",             # log1p(events in the previous hour)
    "log_usd_1h",           # log1p(USD released in the previous hour)
    "n_1h_rel",             # log ratio of previous-hour count to trailing 7-day hourly mean
    "usd_1h_rel",           # same for USD
    "log_gap",              # log1p(seconds since previous event)
    "repeat_1h",            # log1p(events in previous hour with same token AND same value)
    "hour_sin", "hour_cos",
]
X_FEATURES = D_FEATURES + ["unmatched", "log_latency"]

# Feature flagged as specific to replay-style attacks; reported in an ablation.
REPLAY_SPECIFIC = ["repeat_1h"]


def build_features(ev: pd.DataFrame) -> pd.DataFrame:
    ev = ev.sort_values("ts", kind="mergesort").reset_index(drop=True)
    n = len(ev)
    out = {k: np.zeros(n) for k in X_FEATURES}

    tok_count = defaultdict(int)
    tok_vals: dict[str, list] = defaultdict(list)     # running log-values per token
    ben_count = defaultdict(int)
    win = deque()          # (ts, usd, token, value_rounded)
    win7 = deque()         # (ts) last 7 days
    prev_ts = None
    total = 0

    ts = ev["ts"].to_numpy()
    usd = ev["value_usd"].to_numpy()
    tok = ev["token"].to_numpy()
    ben = ev["beneficiary"].to_numpy()
    lat = ev["latency_s"].to_numpy()
    mat = ev["matched"].to_numpy()

    usd_7d = deque()
    for i in range(n):
        t = ts[i]
        while win and win[0][0] < t - 3600:
            win.popleft()
        while win7 and win7[0] < t - 7 * 86400:
            win7.popleft()
        while usd_7d and usd_7d[0][0] < t - 7 * 86400:
            usd_7d.popleft()

        lv = np.log1p(usd[i])
        out["log_value"][i] = lv
        vals = tok_vals[tok[i]]
        out["value_vs_token_med"][i] = lv - (np.median(vals[-500:]) if vals else lv)
        out["token_novel"][i] = float(tok_count[tok[i]] == 0)
        out["token_share"][i] = tok_count[tok[i]] / total if total else 0.0
        out["benef_novel"][i] = float(ben_count[ben[i]] == 0)
        out["benef_log_count"][i] = np.log1p(ben_count[ben[i]])

        n1h = len(win)
        u1h = sum(w[1] for w in win)
        out["log_n_1h"][i] = np.log1p(n1h)
        out["log_usd_1h"][i] = np.log1p(u1h)
        span_h = max(1.0, min(7 * 24.0, (t - ts[0]) / 3600.0))
        mean_n = len(win7) / span_h
        mean_u = sum(x[1] for x in usd_7d) / span_h
        out["n_1h_rel"][i] = np.log((n1h + 1) / (mean_n + 1))
        out["usd_1h_rel"][i] = np.log((u1h + 1) / (mean_u + 1))
        out["log_gap"][i] = np.log1p(t - prev_ts) if prev_ts is not None else np.log1p(86400)
        vr = round(usd[i], 2)
        out["repeat_1h"][i] = np.log1p(sum(1 for w in win if w[2] == tok[i] and w[3] == vr))
        hour = (t % 86400) / 3600.0
        out["hour_sin"][i] = np.sin(2 * np.pi * hour / 24)
        out["hour_cos"][i] = np.cos(2 * np.pi * hour / 24)
        out["unmatched"][i] = float(not mat[i])
        out["log_latency"][i] = np.log1p(max(lat[i], 0)) if np.isfinite(lat[i]) else 0.0

        # update state AFTER computing features
        tok_count[tok[i]] += 1
        vals.append(lv)
        ben_count[ben[i]] += 1
        win.append((t, usd[i], tok[i], vr))
        win7.append(t)
        usd_7d.append((t, usd[i]))
        prev_ts = t
        total += 1

    F = pd.DataFrame(out)
    F.insert(0, "ts", ts)
    F.insert(1, "label", ev["label"].to_numpy())
    F.insert(2, "value_usd", usd)
    F.insert(3, "tx_hash", ev["tx_hash"].to_numpy())
    if "value_usd_ref" in ev:
        F.insert(4, "value_usd_ref", ev["value_usd_ref"].to_numpy())
    return F
