# K4 — Flash-loan price-manipulation exploits on Ethereum

Run: `results/kan/k4_20261024_080035`. MLP, KAN, RF and LightGBM were fitted
with 5 seeds, logistic regression and the rule once; leave-protocol-out uses
3 seeds. Protocol: `docs/PROTOCOLS.md` (K4) and the docstring of
`scripts/k4_defi_kan.py`. Data construction: `docs/DATA.md` (K4).

This run supersedes `k4_20261023_200340`, which had two feature defects
found in review (see `docs/AUDIT_RESPONSE.md`, fifth review). There,
`has_flash` was set from the stratum, so every attack had it by
construction. `to_created_today` also counted contracts created later the
same day. Fixing both changes 22 of 337,864 rows: `has_flash` of 4 attacks
and `to_created_today` of 18 background transactions.

## Data

* **Incidents.** 40 DeFiHackLabs proof-of-concept entries (38 protocols;
  Circle and UwULend have two each), dated 2021-10-27 to 2026-07-01. An entry
  is kept when its README heading names a price or oracle manipulation and
  its PoC forks mainnet and uses a flash loan. All 40 linked attack
  transactions were found in the AWS data, on the README day or the day next
  to it (49 days read). 36 of the 40 attack transactions carry a flash-loan
  event or V2 flash swap that the feature rule recognises; the other four
  borrow through routes it does not see.
* **Transactions.** 337,864 kept transactions in four strata:
  * 40 attacks;
  * 106,369 other flash-loan transactions of those days, all of them (the
    hard negatives);
  * 84,455 transactions touching the attacked contracts, sampled at most
    5,000 per day;
  * 147,000 background transactions, 3,000 per day.

  Weighted to the population, each day holds about 1.0–1.3 million
  transactions. Background was sampled from successful transactions only
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
of its day (1 = top).

| Model | Test AP | 90 % CI | Weighted AP | Recall @ 1/day | Recall @ 10/day | Median day rank |
|---|---|---|---|---|---|---|
| **LightGBM** | **0.230** | [0.106, 0.423] | **0.228** | **0.46** | 0.62 | 6.0 |
| Random forest | 0.189 | [0.081, 0.364] | 0.188 | 0.42 | **0.78** | **3.4** |
| MLP (75 hidden, matched) | 0.101 | [0.027, 0.252] | 0.098 | 0.31 | 0.46 | 61 |
| KAN [14, 8, 1], grid 5 | 0.072 | [0.029, 0.178] | 0.068 | 0.20 | 0.43 | 83 |
| Logistic regression | 0.022 | [0.013, 0.045] | 0.020 | 0.23 | 0.54 | 12 |
| Rule (flash loan × price move) | 0.002 | [0.001, 0.005] | 0.002 | 0.00 | 0.00 | 669 |

The weighted AP has its own interval in `temporal_summary.csv`; it differs
from the sample AP by at most 0.005. The AP of the seed-averaged score is
reported there too (`seed_mean_score_test_ap`; LightGBM 0.228, KAN 0.108).
ROC-AUC is 0.94–0.99 for all learned models. At a base rate below one attack
per million transactions it says little.

* **Budgets do not transfer in time.** Thresholds were set on 2024 so that
  validation alarms per day met the budget (achieved 0.67–1.0 at 1/day). On
  the test days the same thresholds give 2.0 (RF), 5.6 (MLP), 5.9
  (LightGBM), 8.7 (logistic regression) and 18.9 (KAN) alarms per day at the
  1/day budget, and 20–125 at the 10/day budget. The recall above is bought
  with 2–19× the planned alarm load.
* **Per-incident ranks** (median over seeds):
  * LightGBM puts five of the 13 test attacks at rank 1–2: GradientMakerPool,
    ResupplyFi, PresaleV5, Curve LlamaLend and edel-xstock.
  * All models miss three attacks:
    * Scorch: LightGBM 521, KAN 18,708.
    * DRLVaultV3: LightGBM 107, KAN 4,145.
    * ThetanutsVaultShareRounding: a rounding bug that the heading filter let
      in through the word "price".
* **HK4.1, learned models: partly supported.** The tree ensembles put the
  median test attack around rank 3–6 of about a million transactions, but
  the alarm budget is not met (above).
* **HK4.1, rule part: rejected.** The two-condition rule is near random, for
  three reasons. Eight of the 40 attacks show no V2/V3 price move: the
  manipulated pool is a Curve, Balancer or custom AMM, or the price source
  is a vault share price. Four have no recognised flash loan. And thousands
  of ordinary arbitrage transactions per day combine a flash loan with a
  large pool move.
* **The label leak mattered most for the linear model.** With `has_flash`
  taken from the stratum (superseded run), logistic regression reached test
  AP 0.082; it is 0.022 now. The tree ensembles are unchanged within seed
  noise (LightGBM 0.228 → 0.230).
* **HK4.2: supported.** The KAN is not better than the matched MLP (AP 0.072
  vs 0.101, overlapping intervals) and is clearly below the tree ensembles.
  Seed spread is large for both neural models (KAN test AP SD 0.089). Both
  stop early on an internal 15 % hold-out of the training rows, which
  contains only about three attacks (KAN seed 0: 19 epochs), so they are
  weakly trained by design of the shared protocol.

## 2. Leave-protocol-out (8 folds grouped by incident day, out-of-fold)

AP is the out-of-fold AP of each seed, averaged over seeds, with the same
seed-mean bootstrap over days. The AP of the seed-averaged out-of-fold score
is in `ensemble_ap`. Base rate: 1.2 × 10⁻⁴ on the kept rows and
6.7 × 10⁻⁷ weighted.

| Model | AP | 90 % CI | Weighted AP | Median day rank | Share of attacks at rank ≤ 10 |
|---|---|---|---|---|---|
| **LightGBM** | **0.322** | [0.220, 0.465] | **0.235** | **2.0** | **0.75** |
| Random forest | 0.192 | [0.122, 0.306] | 0.139 | 2.0 | 0.73 |
| KAN | 0.173 | [0.107, 0.289] | 0.114 | 3.0 | 0.63 |
| MLP | 0.146 | [0.083, 0.277] | 0.106 | 4.0 | 0.60 |
| Logistic regression | 0.056 | [0.031, 0.104] | 0.040 | 3.5 | 0.60 |
| Rule | 0.004 | [0.002, 0.008] | 0.003 | 446 | 0.10 |

Without the time shift, most attacks are among the top ten transactions of
their day for every learned model. The ordering of the model families is the
same as in the temporal split. The weighted AP is lower than the sample AP
here because the background negatives weigh several hundred times more than
the hard negatives.

## 3. What the KAN uses, and whether its edge functions say so (HK4.3)

The three most relevant inputs of the KAN (seed 0) are `nonce` (18.9),
`gas_used` (16.4) and `to_created_today` (13.5). The mechanism features are
the least relevant: `flash_to_pool` 3.6, `max_price_move` 3.4,
`net_price_move` 3.8. Attack transactions come from fresh senders (median
nonce 4, against 771 for other transactions). 25 of the 40 call a contract
deployed by an earlier transaction that day, and they use about ten times
the gas. The model therefore recognises **the attacker's set-up, not the
price manipulation**. A careful attacker who pre-deploys and uses an older
account removes most of this signal.

Permutation importance is the AP drop on validation, mean (SD) of 20
permutations:

| Feature | Relevance | Spearman: signed edge path vs partial dependence | Plain sum of edges vs PD | Permutation AP drop |
|---|---|---|---|---|
| nonce | 18.9 | +1.00 | −1.00 | 0.010 (0.032) |
| gas_used | 16.4 | +1.00 | −1.00 | −0.005 (0.034) |
| to_created_today | 13.5 | +1.00 | −1.00 | 0.012 (0.000) |

* **The shape of an edge function is faithful only with its sign.**
  Weighting each first-layer function by the mean slope of the second-layer
  function that follows it reproduces the model's partial dependence
  exactly (Spearman +1.00). The plain sum of the first-layer functions,
  which is what a plot of layer 0 alone shows, has the opposite direction
  (−1.00).
* **Relevance is not importance, and validation permutation cannot rank
  features here.** With 9 validation attacks, the SD of the permutation drop
  over 20 permutations is larger than its mean for most features. Across all
  14 features, KAN relevance and mean permutation drop do not agree (Spearman
  0.02). The superseded run reported 0.31 from a single permutation per
  feature; the two permutation numbers in its summary disagreed for the same
  reason.
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
