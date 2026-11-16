# TV — Temporal validity of learned detectors (protocol, fixed before the runs)

Written 2026-10-30, before any TV script was run. Changes after the first run
are listed at the end of this file with their date and reason.

The study asks which part of a detector survives the move to a later period:
the **ranking** (AP, within-day rank), the **threshold** chosen for an alarm
budget, or the **label-free monitor** that should notice a failure. It reuses
the T (Elliptic, Elliptic++) and K4 (Ethereum DeFi) data and adds the
experiments below. Runs T1–T5 and `k4_20261024_204829` are the baselines.

## Hypotheses and decision rules

| ID | Hypothesis | Decision rule |
|---|---|---|
| HV1 | Causal wallet features (computed only from transactions up to the row's step) do at least as well as the 55 Elliptic++ lifetime features under the temporal address-disjoint protocol, and the random-split score drops when only causal features are used. | Supported if, under P3, mean LightGBM AP(causal) ≥ AP(lifetime) − 0.02 AND under P1 AP(causal) < AP(lifetime) − 0.02. Reported for RF as well. |
| HV2 | The order of model families is stable over training cut-offs, while absolute AP varies strongly. | Supported if the tree ensembles rank first at every cut-off with a non-degenerate test set (Kendall τ between cut-off rankings ≥ 0.6) and the AP of the best model varies by more than a factor 1.5 across cut-offs. |
| HV3 | A threshold fixed on the previous period exceeds its alarm budget; a per-day top-k rule keeps the budget by construction and keeps at least half of the fixed threshold's recall. | First part: achieved/planned alarms > 2 at both budgets for at least half of the models. Second part: recall(top-k) ≥ 0.5 × recall(fixed). |
| HV4 | Input-drift monitors fire on every period or on none; an output monitor (estimated positive share) misreads a detector failure as "fewer attacks". | Input monitor uninformative if Spearman ρ(monitor, AP) is below 0.3 in absolute value. Output-monitor misreading: at least one period where AP falls by half or more while the estimated share falls too. |
| HV5 | On K4, models rely more on attacker set-up features than on manipulation features. | Supported if removing set-up features (nonce, gas_used, to_created_today, n_contracts) lowers LightGBM test AP more than removing mechanism features (has_flash, n_flash, flash_to_pool, max_price_move, net_price_move, n_pools). |

## Experiments

* **X1 (tv1_wallet_causal.py).** For every address and step, causal features
  from the transactions of that address up to and including the step:
  counts sent / received (cumulative and at the step), number of active steps,
  steps since first appearance, and min / mean / max over its past sent and
  received transactions of the Elliptic++ transaction columns `total_BTC`,
  `fees`, `size`, `num_input_addresses`, `num_output_addresses`,
  `in_BTC_total`, `out_BTC_total`, `in_txs_degree`, `out_txs_degree`.
  Protocols P1, P1b, P2, P3 as in T5 (same row sets, same seeds, RF and
  LightGBM, 3 seeds), plus P5: temporal rows whose test part is the rows at
  steps >= 35 of addresses with no row at steps <= 34 (added before the first
  run, 2026-10-30). Feature sets: lifetime (55), lifetime without time
  features (P4 set), causal, causal + lifetime. **A1** is this feature-set
  grid. Labels: the Elliptic++ wallet class (lifetime). A causal label
  (illicit if any transaction of the address up to the step is labelled
  illicit) is computed and its agreement with the wallet class is reported;
  it is used as a sensitivity row, not the headline.
* **X2 (tv2_rolling.py).** Rolling origin. Elliptic: train on steps ≤ c,
  validate on c+1..c+4, test on c+5..c+9, for c ∈ {20, 25, 30, 35, 40}
  (c = 40 has test 45–49). K4: train ≤ year Y−1 end, validate on year Y,
  test on year Y+1, for Y ∈ {2023, 2024} (test 2024, 2025–2026), plus the
  original split. Models as in T1 / K4 (LightGBM, RF, logistic regression,
  MLP; KAN in the K4 rows only as in K4). **A2**: training window = all past
  vs the last 10 steps (Elliptic) / last 2 years (K4).
* **X3 (tv3_quiet_days.py).** Ethereum days without a DeFiHackLabs mainnet
  incident within ±3 days: 8 in 2024, 8 in 2025 and 6 in 2026 (up to the
  last complete month), drawn uniformly with seed 20261030. Same extraction
  as K4 (flash stratum complete, background sample of 3,000 with weights; no
  attack or protocol stratum). Thresholds from the K4 validation year are
  applied to these days; the achieved alarms per day are the deployment-like
  false-alarm estimate.
* **X4.** Threshold strategies on the X2 / X3 scores: fixed (validation),
  rolling quantile over the previous 7 days / 3 steps, top-k per day / step.
  Budgets 1 and 10 per day (K4); 1 % and 5 % of the step's transactions
  (Elliptic).
* **X5 (t3 extension).** Optuna, 40 TPE trials each for GraphSAGE and GAT,
  objective validation AP, as in T3.
* **X6.** Monitors per test step / day: PSI median over features, domain
  classifier AUC (train vs period), EM-estimated positive share, mean score.
  Correlated with the true AP per period.
* **A3.** K4 feature-group ablation for HV5, temporal split, 5 seeds.

## Reporting

AP (sklearn, non-interpolated) next to the base rate; 5 seeds for learned
models (3 for X1 as in T5); 90 % bootstrap intervals over days / steps with
the seed mean recomputed in each resample; achieved alarms per day next to
every budget; no hypothesis tests on the 13 K4 test attacks. Every run writes
a manifest. Elliptic labels are not committed.

## Changes after the first run

* 2026-10-30, X1: post-hoc feature set `causal_no_degree` (the causal set
  without `in_txs_degree` / `out_txs_degree`) on P2, P3 and P5. Reason: a
  transaction's out-degree is known only once its outputs are spent, so the
  causal set could carry information from the end of the step. Reported as a
  sensitivity row, not a hypothesis test.
* 2026-10-31, X4 on K4: the per-day top-k rule counted a background row of
  weight w as w alarms as soon as its rank fell inside k, so top-k overshot
  its own budget (up to 15 alarms/day at k = 1). The row that crosses the
  budget is now counted in part (`topk_alarms` returns the share of the row's
  weight inside k; attacks have weight 1). The K4 runs were repeated
  (`tv4_20261031_005129`, `tv4_20261031_014421`); ranking, fixed thresholds,
  monitors and A3 are unchanged, and the first runs were removed.
* 2026-10-31, X4 on K4: the rolling-quantile rule over the previous 7 days
  was not run. K4 test days are incident days spread over the year plus 22
  quiet days, so there are no 7 consecutive previous days to take a quantile
  from. The threshold fixed on the quiet validation days (`fixed_quiet`)
  is reported as a second fixed rule instead.
* 2026-10-31, HV4: "the estimated share falls too" is read as: the EM
  estimate at the step is lower than at the previous test step (test steps
  of different cut-offs do not overlap). The steps where the estimate is
  below half the true share are listed as well.
* 2026-10-31, X5: one Optuna study runs longer than the 2-hour job limit;
  the study is stored in sqlite and continued with `--run`. The TPE sampler
  is re-seeded on each continuation.

## Round 2 (fixed 2026-11-03, before any of its runs)

Added after an external review of the first draft. Each item names what it
lets the paper claim; numbers of round 1 are not changed by it.

* **X1c — lifetime vs prefix of the same aggregates (HV6).** The 60 causal
  aggregates are recomputed over the whole history of the address
  (`causal_full`: every cumulative column takes the value of the address's
  last step, `steps_since_first` becomes the address's span, the per-step
  counts `n_*_t` stay as they are). Point of evaluation of `causal`: the end
  of step t, all transactions of steps <= t. Same protocols, models and seeds
  as X1. Decomposition under P2, P3, P5 (LightGBM, wallet label):
  future effect = AP(causal) - AP(causal_full); representation effect =
  AP(causal_full) - AP(lifetime). **HV6:** under P3 the future effect is
  >= 0.05 AP and under P1 AP(causal_full) >= AP(causal) - 0.01 (the future
  helps on a random split and hurts on a temporal one). Reported whether it
  holds or not.
* **X6b — label-shift estimate, population and assumption.** (a) The EM
  estimate is computed on all transactions of the step as well as on the
  labelled ones; the labelled-only value is the one comparable to the true
  share. (b) Positive control: for cut-offs 25 and 30 (no regime change in
  the test steps), the labelled test transactions of each step are
  resampled to an illicit share of 1, 2, 5, 10 and 20 % (p(x|y) unchanged);
  EM "works" if its median absolute error is <= 0.25 times the target share.
  (c) Assumption check: a classifier (LightGBM, 5-fold, features only)
  separates illicit transactions of steps 35-42 from those of steps 43-49;
  controls: licit 35-42 vs 43-49, and illicit 35-38 vs 39-42. p(x|y) is
  called shifted if the illicit AUC is >= 0.15 above the illicit control.
  The PSI result is narrowed to: PSI detects the change of inputs but does
  not order the steps by AP.
* **A3b — preparation vs execution, and a frozen detector.** K4 t2025,
  LightGBM and RF, 5 seeds. Groups: preparation = nonce, to_created_today;
  execution = gas_used, n_contracts; mechanism unchanged. Retrained without
  each group (as A3). Frozen-model check: the full model of each seed scores
  the test attacks with nonce and to_created_today replaced by the values of
  a random background row of the same day (20 draws); reported as the median
  within-day rank of the attacks and top-k recall at 1 and 10 per day.
  Descriptive; it changes a feature vector, not an attack, and is reported as
  such ("evasion" stays a hypothesis).
* **X4b — sampling uncertainty of alarm counts.** K4 alarms per day are split
  by stratum (flash, protocol, background; flash and protocol are complete,
  background is a uniform sample of 3,000 per day with weight = day count /
  3,000). 90 % intervals: 2,000 bootstrap resamples of the background rows
  within each day, in the validation year (threshold re-fitted) and in the
  test year together; the seed is fixed. The paper reports alarms per day
  with these intervals and says "alarms on days without a known incident"
  instead of false alarms.
* **X7 — fully processed days (pilot).** One quiet 2025 day is processed in
  full (all transactions with receipts and logs) and the alarm count of the
  fixed thresholds is compared with the sample estimate and its X4b
  interval. Only if the pilot fits the machine (15 GB, 2-hour jobs): 2-3
  windows of 7 consecutive days, on which a sequential budget rule (threshold
  from the previous days' scores only, updated each hour) is compared with
  per-day top-k. Both are detection after execution, not prevention.

### Changes in round 2

* 2026-11-03, X4b: a pilot run showed that at 1 alarm/day no sampled
  background row of 2025-26 lies above the fixed thresholds; all alarms come
  from the complete flash stratum. A bootstrap over the sampled rows cannot
  bound background transactions the sample never drew, so a Clopper-Pearson
  90 % interval of the share of background transactions above the threshold
  (times the background transactions per day) is reported next to it.
* 2026-11-04, X7: the pilot (2025-02-01, run `results/kan/tv10_20261104_031501`)
  extracted and scored all 1.11 M successful transactions in about 4 minutes
  on the job machine. Its flash-stratum alarms equal the sample's exactly;
  1-46 further alarms per threshold come from background transactions that
  the 3,000-row sample did not contain (sample estimate 0 in every cell,
  within the Clopper-Pearson bound). Because full days are cheap, X7 is
  extended before any further run: (i) all 22 quiet days are processed in
  full, and the quiet-day alarms per day of the fixed thresholds (seed 0,
  logistic regression, RF, LightGBM; budgets 1 and 10; thresholds fitted as
  in tv4 on the sampled validation year) are counted exactly on the 14 test
  days of t2025; as a sensitivity, the fixed_quiet threshold is also refitted
  on the 8 fully processed quiet days of 2024. (ii) Two windows of 7
  consecutive days without a DeFiHackLabs mainnet incident within +-3 days,
  one in 2025 and one in 2026 (first such window after a seeded uniform
  start date, seed 20261104), are processed in full; on them a sequential
  rule (threshold = score quantile that would have given b alarms per day
  over the previous 24 hours of scored transactions, updated every 300
  blocks, about one hour) is compared with the fixed thresholds and the
  retrospective per-day top-k. Reported: alarms per day and their spread
  over days. All of this is detection after execution.
