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
  LightGBM, 3 seeds). Feature sets: lifetime (55), lifetime without time
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

(none yet)
