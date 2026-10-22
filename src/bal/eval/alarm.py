"""
Alarm-budget thresholds and loss accounting for event streams.

Threshold policy
----------------
`threshold_at_budget(s_cal, fpr)` returns a conservative threshold t, taken from
the observed calibration scores, whose ACHIEVED calibration alarm rate mean(s_cal >= t) does not exceed the budget. Ties are
never split: if the top tied block alone exceeds the budget, the threshold is
placed just above the calibration maximum (the detector then alarms only on
scores never seen in calibration). The achieved rate and the resolution 1/n of
the calibration set are always reported, because a budget below 1/n cannot be
verified on that calibration set. t is not necessarily the lowest admissible
value: for scores [10, 9, 0] and budget 1/3 it returns 10, although any t just
above 9 would also meet the budget.

Loss accounting
---------------
The data contain released (already executed) outflows. For the first alarm
raised at or after the first attack event, `alarm_accounting` reports:

* usd_before_alarm          attack value of events strictly before the alarm event
* usd_through_alarm_event   ... plus the alarm event itself (it has already executed)
* usd_through_alarm_block   ... plus every attack event with the same timestamp
                            (no block numbers in the data; one timestamp ~ one block)
* usd_after_delay_<d>       attack value released AFTER alarm time + d seconds: an
                            upper bound on what an immediate pause with response
                            delay d could still protect (no pause is simulated)
"""

from __future__ import annotations

import numpy as np

RESPONSE_DELAYS_S = (0, 60, 600, 3600)


def threshold_at_budget(s_cal, fpr: float) -> tuple[float, float]:
    """(threshold, achieved calibration rate) with achieved rate <= fpr, ties kept whole."""
    s = np.sort(np.asarray(s_cal, dtype=float))[::-1]
    n = len(s)
    k = int(np.floor(fpr * n + 1e-12))         # max number of calibration alarms
    if k == 0:
        return float(np.nextafter(s[0], np.inf)), 0.0
    t = s[k - 1]
    if k < n and s[k] == t:                   # the tie at position k would exceed the budget
        higher = s[s > t]
        if len(higher) == 0:
            return float(np.nextafter(s[0], np.inf)), 0.0
        t = higher.min()
    return float(t), float((s >= t).mean())


def alarm_accounting(ts, label, usd_ref, alarm) -> dict:
    """Loss accounting around the first alarm at/after the first attack event."""
    ts, label, usd, alarm = map(np.asarray, (ts, label, usd_ref, alarm))
    atk = np.where(label == 1)[0]
    if len(atk) == 0:
        return {}
    total = max(float(usd[atk].sum()), 1e-9)
    out = {"attack_recall": float(alarm[atk].mean()),
           "usd_recall": float(usd[atk][alarm[atk]].sum() / total)}
    later = np.where(alarm[atk[0]:])[0]
    if len(later) == 0:
        out.update(detected=False, seconds_to_alarm=np.nan, attack_events_before_alarm=int(len(atk)),
                   usd_share_before_alarm=1.0, usd_share_through_alarm_event=1.0,
                   usd_share_through_alarm_block=1.0,
                   **{f"usd_share_after_delay_{d}s": 0.0 for d in RESPONSE_DELAYS_S})
        return out
    a = atk[0] + later[0]
    before = atk[atk < a]
    through = atk[atk <= a]
    block = atk[(atk <= a) | (ts[atk] == ts[a])]
    out.update(detected=True, seconds_to_alarm=int(ts[a] - ts[atk[0]]),
               attack_events_before_alarm=int(len(before)),
               usd_share_before_alarm=float(usd[before].sum() / total),
               usd_share_through_alarm_event=float(usd[through].sum() / total),
               usd_share_through_alarm_block=float(usd[block].sum() / total),
               **{f"usd_share_after_delay_{d}s": float(usd[atk[ts[atk] > ts[a] + d]].sum() / total)
                  for d in RESPONSE_DELAYS_S})
    return out
