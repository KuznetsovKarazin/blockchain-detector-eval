# K4 — Keyword-selected flash-loan price-manipulation exploits on Ethereum

Run: `results/kan/k4_20261024_204829`, from a clean tree. MLP, KAN, RF and
LightGBM were fitted with 5 seeds, logistic regression and the rule once;
leave-days-out uses 3 seeds. Protocol: `docs/PROTOCOLS.md` (K4) and the
docstring of `scripts/k4_defi_kan.py`. Data construction: `docs/DATA.md`
(K4).

The run was interrupted by restarts of the machine and continued twice with
`--resume` (104 fits reused). It started at commit 44a3f76 and its manifest
records the commit of the last segment, de55dc4; the commits in between
change only the resume cache and the implementation of the bootstrap (same
values up to 1e-16, `tests/test_k4_bootstrap.py`).

This run supersedes `k4_20261024_080035` (release 0.5.1). There, a Uniswap
V2 pool's token pair was taken from the transfers of the whole day, the
MLP / KAN input transform for the held-out-day evaluation was chosen outside
its folds, and the run was made from a modified working tree. The feature
changes are measured in `results/kan/k4_feature_diff_v0.6.0` (CHANGELOG
0.6.0). The earlier `k4_20261023_200340` (release 0.5.0) set `has_flash`
from the stratum and let `to_created_today` see later creations.

## Data

* **Incidents.** 40 DeFiHackLabs proof-of-concept entries (38 protocols;
  Circle and UwULend have two each), dated 2021-10-27 to 2026-07-01. An entry
  is kept when its README heading names a price or oracle manipulation and
  its PoC forks mainnet and uses a flash loan. The selection is by keywords,
  so the cohort does not share one verified mechanism: one test entry is a
  rounding bug whose heading contains "price" (section 1). All 40 linked
  attack transactions were found in the AWS data, on the README day or the
  day next to it. 49 days were read: 38 days with an attack and 11 adjacent
  days read while locating the transactions. 36 of the 40 attack
  transactions carry a flash-loan event or V2 flash swap that the feature
  rule recognises; the other four borrow through routes it does not see.
* **Transactions.** 337,871 kept transactions in four strata:
  * 40 attacks;
  * 106,376 other flash-loan transactions of those days, all of them (the
    hard negatives);
  * 84,455 transactions touching the attacked contracts, sampled at most
    5,000 per day;
  * 147,000 background transactions, 3,000 per day.

  Weighted to the population, each day holds 0.90–2.26 million
  transactions (1.02–2.26 million on the test days). Background was sampled from successful transactions only
  (1,493,192 of 61,580,886 transactions on these days failed). Six
  transactions of other DeFiHackLabs exploits were removed.
* **Temporal split** by incident date:

  | Part | Period | Positives | Days |
  |---|---|---|---|
  | train | ≤ 2023 | 18 | 24 |
  | validation | 2024 | 9 | 12 |
  | test | 2025–2026 | 13 | 13 |

  Base rate on the test days: 9.2 × 10⁻⁵ on the kept rows and
  6.0 × 10⁻⁷ population-weighted.
* **Features.** 14 causal transaction features:
  * flash loans: whether there is one, how many, and their size relative to
    the pool;
  * Uniswap V2/V3 price move inside the transaction, and the pools touched;
  * contracts, logs and tokens;
  * WETH/stablecoin profit;
  * gas used, sender nonce, ETH value;
  * whether the target was created by an earlier transaction that day.

## 1. Temporal split (test 2025–2026, 13 attacks)

AP is the mean over seeds of the per-seed AP. The 90 % interval is a
bootstrap over test days that recomputes the same seed mean in every
resample. Rank is the position of the attack among the weighted transactions
of its day (1 = top). Recall is given with the achieved alarms per test day
in brackets (mean over seeds).

| Model | Test AP | 90 % CI | Weighted AP | Recall @ 1/day | Recall @ 10/day | Median day rank |
|---|---|---|---|---|---|---|
| **LightGBM** | **0.212** | [0.092, 0.398] | **0.211** | **0.45** (11.2) | 0.62 (135) | 7.4 |
| Random forest | 0.209 | [0.085, 0.418] | 0.209 | 0.42 (1.8) | **0.82** (117) | **5.0** |
| KAN [14, 8, 1], grid 5 | 0.140 | [0.048, 0.303] | 0.136 | 0.20 (2.3) | 0.48 (16) | 11.8 |
| MLP (75 hidden, matched) | 0.094 | [0.028, 0.246] | 0.089 | 0.35 (15.7) | 0.54 (49) | 50.4 |
| Logistic regression | 0.026 | [0.016, 0.056] | 0.019 | 0.38 (8.5) | 0.54 (68) | 8.5 |
| Rule (flash loan × price move) | 0.002 | [0.001, 0.005] | 0.002 | 0.00 (0) | 0.00 (25) | 669 |

The weighted AP has its own interval in `temporal_summary.csv`. The AP of the
seed-averaged score is reported there too (`seed_mean_score_test_ap`):
LightGBM 0.222, random forest 0.219, MLP 0.171, KAN 0.148. ROC-AUC is
0.93–1.00 for all learned models; at a base rate below one attack per
million transactions it says little. Validation chose robust scaling for the
MLP and quantile scaling for the KAN (`summary.json`, `prep`).

* **Budgets do not transfer in time.** Thresholds were set on 2024 so that
  validation alarms per day met the budget (achieved 0.92–1.0 at 1/day for
  the learned models). On the test days the same thresholds give 1.8 (RF),
  2.3 (KAN), 8.5 (logistic regression), 11.2 (LightGBM) and 15.7 (MLP)
  alarms per day at the 1/day budget, and 16–135 at the 10/day budget. The
  seed spread is large (MLP: SD 20 alarms per day over seeds). The recall
  above is bought with up to about 16× the planned alarm load.
* **Per-incident ranks** (median over seeds):
  * LightGBM puts five of the 13 test attacks at rank 1–2: GradientMakerPool,
    Curve LlamaLend, ResupplyFi, edel-xstock and PresaleV5.
  * Three attacks are below rank 40 for every model:
    * DRLVaultV3: random forest 41, LightGBM 179, KAN 2,362.
    * Scorch: LightGBM 568, KAN 634.
    * ThetanutsVaultShareRounding: a rounding bug that the heading filter let
      in through the word "price"; best rank 1,951 (logistic regression).
* **HK4.1, learned models: partly supported.** The tree ensembles put the
  median test attack around rank 5–7 of one to two million transactions,
  but the alarm budget is not met (above).
* **HK4.1, rule part: rejected.** The two-condition rule ranks attacks far
  down (median rank 669) and alarms on none at either budget, for three
  reasons. Eight of the 40 attacks show no V2/V3 price move: the manipulated
  pool is a Curve, Balancer or custom AMM, or the price source is a vault
  share price. Four have no recognised flash loan. And thousands of ordinary
  arbitrage transactions per day combine a flash loan with a large pool
  move.
* **HK4.2: not contradicted.** The KAN has a higher mean AP than the matched
  MLP in both protocols (temporal 0.140 vs 0.094, held-out days 0.131 vs
  0.066), but the intervals overlap, the KAN's seed SD is 0.077, and on
  seed-averaged scores the MLP is ahead on the temporal test (0.171 vs
  0.148). Both are below the tree ensembles. Both neural models stop early
  on an internal 15 % hold-out of the training rows, which contains only
  about three attacks, so they are weakly trained by design of the shared
  protocol.
* **Against the superseded run** `k4_20261024_080035`, the temporal test AP
  moved within its intervals for the tree ensembles and the MLP (LightGBM
  0.230 → 0.212, random forest 0.189 → 0.209, MLP 0.101 → 0.094). The KAN
  rose from 0.072 to 0.140; validation now chose quantile instead of robust
  scaling for it. With held-out days, choosing the transform inside each
  fold lowered the MLP from 0.146 to 0.066.

## 2. Leave-days-out (8 folds grouped by incident day, out-of-fold)

AP is the out-of-fold AP of each seed, averaged over seeds, with the same
seed-mean bootstrap over days. The MLP / KAN input transform is chosen again
inside every fold on its training days (`prep_choice_by_fold.csv`; the
choice differs between folds). The AP of the seed-averaged out-of-fold score
is in `ensemble_ap`. Base rate: 1.2 × 10⁻⁴ on the kept rows and
6.7 × 10⁻⁷ weighted.

| Model | AP | 90 % CI | Weighted AP | Median day rank | Share of attacks at rank ≤ 10 |
|---|---|---|---|---|---|
| **LightGBM** | **0.294** | [0.197, 0.437] | **0.219** | **2.5** | **0.75** |
| Random forest | 0.189 | [0.122, 0.304] | 0.141 | 2.5 | 0.75 |
| KAN | 0.131 | [0.080, 0.250] | 0.096 | 3.0 | 0.68 |
| Logistic regression | 0.067 | [0.038, 0.126] | 0.013 | 3.75 | 0.55 |
| MLP | 0.066 | [0.038, 0.212] | 0.032 | 3.0 | 0.63 |
| Rule | 0.004 | [0.002, 0.008] | 0.003 | 446 | 0.10 |

Without the time shift, most attacks are among the top ten transactions of
their day for every learned model. The tree ensembles again lead. The
weighted AP is lower than the sample AP here because the background
negatives weigh several hundred times more than the hard negatives.

## 3. What the KAN uses, and whether its edge functions say so (HK4.3)

The three most relevant inputs of the KAN (seed 0) are `nonce` (12.7),
`to_created_today` (11.1) and `gas_used` (9.8). The flash-loan count and
size follow (`n_flash` 8.6, `flash_to_pool` 6.7); the price moves are 10th
and 12th of 14 (`max_price_move` 4.6, `net_price_move` 3.7) and `has_flash`
is last (2.4). Attack transactions come from fresh senders (median nonce
4.5, against 772 for the other kept transactions). 25 of the 40 call a
contract deployed by an earlier transaction that day, and they use about ten
times the gas. The model therefore leans on **the attacker's set-up more
than on the price manipulation**. An attacker who pre-deploys and uses an
older account may weaken this signal; the effect was not measured.

Permutation importance is the AP drop on validation, mean (SD) of 20
permutations:

| Feature | Relevance | Spearman: signed edge path vs partial dependence | Plain sum of edges vs PD | Permutation AP drop |
|---|---|---|---|---|
| nonce | 12.7 | +1.00 | −1.00 | 0.018 (0.026) |
| to_created_today | 11.1 | +1.00 | −1.00 | 0.125 (0.006) |
| gas_used | 9.8 | +1.00 | −1.00 | 0.075 (0.038) |

* **The shape of an edge function is faithful only with its sign.**
  Weighting each first-layer function by the mean slope of the second-layer
  function that follows it reproduces the model's partial dependence
  (Spearman +1.00). The plain sum of the first-layer functions, which is
  what a plot of layer 0 alone shows, has the opposite direction (−1.00).
* **Relevance and permutation importance agree only in part.** Both put
  `to_created_today` and `gas_used` among their top three; the largest and
  stable permutation drop is that of `to_created_today`. With 9 validation
  attacks, the SD of the permutation drop over 20 permutations is larger than
  its mean for 10 of the 14 features, including `nonce`, the most relevant
  input. Across all 14 features the rank correlation of relevance and mean
  permutation drop is 0.19.
* HK4.3: **supported for direction, not for ranking.**

## What this does NOT show

* Detection before execution. Every feature is computed from the mined
  transaction and its logs, so this is a forensic or post-block alarm.
* Things the features do not see: native-ETH profit (no traces), Uniswap V4
  accounting, chains other than Ethereum, price moves on Curve, Balancer and
  custom AMMs, and flash loans without a recognised event (4 of 40 attacks).
* A deployment false-alarm rate: the day set is the set of incident days, and
  alarms per day are measured on those days only.
* A detection rate for future attack styles. 13 test attacks give wide
  intervals, and the incident set follows one community repository and a
  keyword filter on its headings.
