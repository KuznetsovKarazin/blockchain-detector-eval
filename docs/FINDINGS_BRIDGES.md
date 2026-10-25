# B — Bridge attacks without attack labels

Current runs (after the audit fixes of 2026-10-22, see [archive/AUDIT_RESPONSE.md](archive/AUDIT_RESPONSE.md)):
`results/bridges/b1_20261022_163601` (7 detectors × 3 views × 5 seeds for
stochastic detectors, rules, transfer) and `results/bridges/b2_20261022_164508`
(per-feature tail scores, rule ∨ detector hybrids). Superseded runs:
`b1_20261022_093114` / `b2_20261022_094142` (dataset prices for
matched releases, see "Price source" below) and the first runs
`b1_20261021_161056` / `b2_20261021_162632`.

What changed against the first runs: thresholds now meet the nominal budget
on the calibration set without splitting ties, the achieved rate is reported,
every release is valued with a price that was available at its time, and
losses are split into value released before the alarm event, through its
block and after a response delay.

## Price source

Every release, matched or not, is valued as amount × the close price of the
last daily candle that closed at or before the release (raw XChainWatcher
candles, `bal.data.prices`). The candles close at 16:00 UTC; the time stamps
in the source files are rounded and are snapped to that grid, with a residual
check. Each run asserts that the close time of the price used is not later
than the release (0 violations on both bridges) and that raw → features is
prefix-invariant (maximum difference 0.0). The second check alone would not
catch a future price stored inside a row; the first one does.

The previous run used the dataset's own USD value for matched releases. That
value is the close of the candle labelled with the request date, which closes
after the release for 15,429 of the 17,340 matched Ronin WETH releases
(median 27 h later), and choosing the valuation by `matched` let the
destination view depend indirectly on the cross-chain match.

Effect of the change (`b1_20261022_093114` → `b1_20261022_163601`):
every rule result, the recall, the first-alarm time and the value released
before and through the alarm for ECOD, ECOD with ties broken by the sum and
Isolation Forest in the headline table are unchanged; the 173,600 ETH release
is still ranked 77th by ECOD and ties with 13 (D) / 62 (X) calibration events
under ECOD-max. False-alarm rates move by up to 0.3 per day for these
detectors. The autoencoders change most (ROC-AUC up to ±0.13 under
transfer; recall at 0.1 % by up to 0.1), so their rows are the least stable
part of the study.

## Data

| Bridge | Test window | Attack events (transactions) | Attack USD (reference) | Unmatched non-attack releases | Calibration events (resolution) |
|---|---|---|---|---|---|
| Ronin | from 2022-03-16 | 2 (2) | 565.4 M | 2,638 | 3,929 (0.025 %) |
| Nomad | from 2022-07-25 | 382 (167) | 159.6 M | 5 | 421 (0.24 %) |

The raw → features pipeline is prefix-invariant on both bridges (maximum
difference 0.0 between features computed on a prefix alone and inside the
full stream). Nomad's calibration set cannot verify a 0.1 % budget: its
smallest non-zero rate is 0.24 %, so at that budget every detector alarms only
on scores above the calibration maximum.

## Nominal 0.1 % budget, in-domain (mean over seeds)

"Before alarm" is the attack value released before the alarm event; "through
block" adds the alarm event and all attack releases with the same timestamp.
Both are already executed transfers.

| Bridge | View | Detector | ROC-AUC | Achieved cal. rate | Attack recall | Before alarm | Through alarm block | False alarms / day |
|---|---|---|---|---|---|---|---|---|
| Ronin | D | ECOD | 0.988 | 0.076 % | 0.50 | 95.5 % | 100 % | 0.29 |
| Ronin | D | ECOD-max | 0.998 | 0 % | 0.00 | 100 % | 100 % | 0.00 |
| Ronin | D | ECOD-max, ties broken by sum | 0.998 | 0.076 % | 0.50 | 95.5 % | 100 % | 0.15 |
| Ronin | D | Isolation Forest | 0.910 | 0.076 % | 0.00 | 100 % | 100 % | 0.04 |
| Ronin | X | Isolation Forest | 0.985 | 0.076 % | 0.50 | 95.5 % | 100 % | 0.04 |
| Ronin | rule | R2 larger than any training release | — | — | 0.50 | 0 % | 95.5 % | 0.00 |
| Ronin | rule | R3 unmatched ∧ > training p99 | — | — | 1.00 | 0 % | 95.5 % | 0.00 |
| Ronin | rule | R1 unmatched | — | — | 1.00 | 0 % | 95.5 % | 26.0 |
| Nomad | D | ECOD | 0.999 | 0 % | 0.997 | 1.4 % | 5.8 % | 3.5 |
| Nomad | D | Isolation Forest | 0.999 | 0 % | 0.98 | 1.4 % | 5.8 % | 1.7 |
| Nomad | X | ECOD | 1.000 | 0 % | 1.00 | 0 % | 5.8 % | 3.5 |
| Nomad | rule | R1 unmatched | — | — | 1.00 | 0 % | 5.8 % | 0.00 |
| Nomad | rule | R3 | — | — | 0.11 | 0 % | 5.8 % | 0.00 |

At the nominal 1 % budget (achieved 0.9–1.0 %), ECOD-max on Ronin D alarms on
the first attack release at 3.3 false alarms per day.

## Claims supported by these runs

1. **High ROC-AUC does not imply an early alarm.** On Ronin, ECOD ranks the two
   attack releases 4th and 77th of 3,368 test events (ROC-AUC 0.988), yet at a
   0.1 % budget it alarms only on the second one (25.5 M USDC), 115 s after the
   173,600 ETH (≈ 515–540 M USD) release.
2. **Mechanism: tail-score saturation.** Each per-feature tail score is capped
   at log(n + 1) = 9.8. The ETH release reaches the cap on two value features
   only; summed over 14 features it ranks 77th. Taking the maximum removes this
   dilution, but then the release ties at the cap with 13 calibration events
   (62 in the X view), so a budget that is actually met (≤ 0.1 %) cannot
   separate it. The first version reported recall 1.0 for ECOD-max because its
   quantile threshold let the whole tied block alarm (achieved 0.33 % in D,
   1.6 % in X): **that result was a threshold artefact and is withdrawn.**
3. **Simple rules give the earliest alarm on these two incidents.** R2 and R3
   flag the Ronin ETH release itself with zero false alarms over the test
   window; on Nomad R1 flags the first attack event with zero false alarms.
   OR-combining R3 with any detector keeps that first alarm.
4. **An alarm on the first release is not a prevented loss.** The release that
   raises the alarm has already executed. On Ronin it carries 95.5 % of the
   stolen value; only the USDC release 115 s later (4.5 %) could have been
   stopped, and only by a pause faster than 115 s. On Nomad the attack spans
   hours: 5.8 % is released within the first attack timestamp, while 94.2 %,
   89.9 % and 82.7 % is released more than 0 s, 10 min and 1 h after the first
   alarm. Nomad is the case where alarm latency matters.
5. **Transfer is asymmetric and retrospective.** ECOD and Isolation Forest
   trained on Ronin detect Nomad with ≤ 4.0 false alarms per day; Nomad → Ronin
   ECOD (D) reaches recall 1.0 at 6.0 false alarms per day against 0.29
   in-domain. The Nomad training period lies after the Ronin attack.
   Autoencoders transferred in either direction raise 59–201 false alarms per day.

## What these runs do NOT show

* Two incidents are case studies, not detection rates for future attacks.
  Ronin has two attack releases. The split is historical and the rules were
  written after the data had been seen; no false alarm in the chosen window
  does not mean none in operation.
* No pause, finality, ingestion delay or analyst triage is simulated; the
  delay columns are upper bounds on what a pause could protect.
* The data have timestamps but no block numbers or log indexes; same-timestamp
  events are treated as one block.
* R1/R3 need the source-chain match computed by XChainWatcher; the comparison
  with D-view detectors therefore includes the value of source-chain access.
  The X view is the fair comparison.
* The `ecod*` detectors are a frozen, train-only, smoothed two-tail ECDF
  variant in the spirit of ECOD (Li et al. 2023), not the PyOD algorithm.
* Prices are daily closes, and a candle is assumed usable once it has closed;
  the provider's real publication time was not measured. The sensitivity to
  intraday price data was not evaluated. Six Nomad releases have no price
  (five tokens without a series, one before the first closed candle); two
  attack rows have zero reference USD already in the source.
