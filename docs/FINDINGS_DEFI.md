# K4 — Flash-loan price-manipulation exploits on Ethereum

Run: `results/kan/k4_20261023_200340` (5 seeds for MLP, KAN, RF and
LightGBM; one fit for logistic regression and the rule; leave-protocol-out
with 3 seeds). Protocol: `docs/PROTOCOLS.md` (K4) and the docstring of
`scripts/k4_defi_kan.py`; data construction: `docs/DATA.md` (K4).

## Data

* 40 DeFiHackLabs proof-of-concept entries (38 protocols; Circle and UwULend
  have two each) from 2021-10-27 to 2026-07-01, selected by the README
  heading (price / oracle manipulation), a mainnet fork and a flash loan in
  the PoC. All 40 linked attack transactions were found in the AWS data, on
  the README day or the day next to it (49 days read).
* 337,864 kept transactions in four strata: 40 attacks, 106,369 other
  flash-loan transactions of those days (all of them, the hard negatives),
  84,455 transactions touching the attacked contracts (sampled, at most 5,000
  per day) and 147,000 background transactions (3,000 per day). Weighted to
  the population, the days hold about 1.0–1.3 million transactions each.
* Temporal split by incident date: 18 positives on 24 days (train, ≤ 2023),
  9 on 12 days (validation, 2024), 13 on 13 days (test, 2025–2026).
* Features: 14 causal transaction features (flash loan count and size
  relative to the pool, Uniswap V2/V3 price move inside the transaction,
  pools, contracts, logs, tokens, WETH/stablecoin profit, gas used, sender
  nonce, ETH value, target created the same day).

## 1. Temporal split (test 2025–2026, 13 attacks)

Mean of 5 seeds; the interval is a 90 % bootstrap over test days of the
seed-averaged score. Rank = position of the attack among the weighted
transactions of its day (1 = top).

| Model | Test AP | 90 % CI | Recall @ 1/day | Recall @ 10/day | Median day rank |
|---|---|---|---|---|---|
| **LightGBM** | **0.228** | [0.116, 0.439] | **0.49** | 0.63 | 5.2 |
| Random forest | 0.181 | [0.079, 0.347] | 0.43 | **0.77** | **2.9** |
| MLP (75 hidden, matched) | 0.108 | [0.033, 0.274] | 0.28 | 0.49 | 92.6 |
| KAN [14, 8, 1], grid 5 | 0.098 | [0.029, 0.289] | 0.20 | 0.54 | 30.8 |
| Logistic regression | 0.082 | [0.034, 0.180] | 0.46 | **0.77** | 5.0 |
| Rule (flash loan × price move) | 0.002 | [0.001, 0.005] | 0.00 | 0.00 | 295 |

Population-weighted AP is within 0.002 of the kept-sample AP for every model.
ROC-AUC is 0.95–1.00 for all learned models; at a base rate of about one
attack per million transactions it says little.

* **Budgets do not transfer in time.** Thresholds were set on 2024 so that
  validation alarms per day met the budget (achieved 0.92–1.0 at 1/day). On
  the test days the same thresholds give 2.3 (RF), 4.2 (MLP), 4.5 (logistic
  regression), 9.2 (KAN) and 9.9 (LightGBM) alarms per day at the 1/day
  budget, and 50–114 at the 10/day budget. The recall above is bought with
  2–10× the planned alarm load.
* **Per-incident ranks** (median over seeds, LightGBM / KAN): six of the 13
  test attacks are at rank 1–2 for LightGBM (GradientMakerPool, ResupplyFi,
  Curve LlamaLend, edel-xstock, PresaleV5, StakeOnMe). Scorch (494 / 5,524), DRLVaultV3
  (165 / 1,707) and ThetanutsVaultShareRounding (4,947 / 2,250) are missed by
  all models; the last is a rounding bug that the README heading filter took
  in through the word "price".
* **HK4.1, learned models: partly supported.** Tree ensembles and logistic
  regression put the median test attack around rank 3–5 of about a million
  transactions, but the alarm budget is not met (above).
* **HK4.1, rule part: rejected.** The two-condition rule is near random. Eight
  of the 40 attacks show no V2/V3 price move at all (the manipulated pool is a
  Curve, Balancer or custom AMM, or the price source is a vault share price),
  and thousands of ordinary arbitrage transactions per day combine a flash
  loan with a large pool move.
* **HK4.2: supported.** The KAN is not better than the matched MLP (AP 0.098 vs
  0.108, overlapping intervals) and clearly below the tree ensembles in median
  rank. Seed spread is large for both neural models (KAN test AP SD 0.088).

## 2. Leave-protocol-out (8 folds grouped by incident day, out-of-fold)

| Model | AP | 90 % CI | Median day rank | Share of attacks at rank ≤ 10 |
|---|---|---|---|---|
| **LightGBM** | **0.350** | [0.248, 0.487] | **2.0** | **0.83** |
| Random forest | 0.193 | [0.122, 0.311] | 2.0 | 0.75 |
| KAN | 0.184 | [0.097, 0.345] | 3.0 | 0.65 |
| MLP | 0.152 | [0.093, 0.282] | 3.5 | 0.65 |
| Logistic regression | 0.043 | [0.025, 0.077] | 4.0 | 0.68 |
| Rule | 0.004 | [0.002, 0.009] | 338 | 0.13 |

Without the time shift, all learned models put most attacks among the top
ten transactions of their day; the ordering of the model families is the same
as in the temporal split.

## 3. What the KAN uses, and whether its edge functions say so (HK4.3)

The three most relevant inputs of the KAN (seed 0) are `nonce` (18.9),
`gas_used` (16.4) and `to_created_today` (13.5); the mechanism features
(`flash_to_pool` 3.6, `max_price_move` 3.4, `net_price_move` 3.8) are the
least relevant. Attack transactions come from fresh senders (median nonce 4
against 771 for other transactions), call a contract deployed the same day
(25 of 40) and use about ten times the gas. The model therefore recognises
**the attacker's set-up, not the price manipulation**; a careful attacker who
pre-deploys and uses an older account removes most of this signal.

| Feature | Relevance | Spearman: signed edge path vs partial dependence | Plain sum of edges vs PD | Permutation AP drop (val) |
|---|---|---|---|---|
| nonce | 18.9 | +1.00 | −1.00 | 0.020 |
| gas_used | 16.4 | +1.00 | −1.00 | 0.017 |
| to_created_today | 13.5 | +1.00 | −1.00 | 0.012 |

* **The shape of an edge function is faithful only with its sign.** Weighting
  each first-layer function by the mean slope of the second-layer function
  that follows it reproduces the model's partial dependence exactly (Spearman
  +1.00). The plain sum of the first-layer functions, which is what a plot of
  layer 0 alone shows, has the opposite direction (−1.00).
* **Relevance is not importance.** Across all 14 features, KAN relevance
  (range of the edge functions) and permutation importance on validation
  agree only weakly (Spearman 0.31); several features with a large function
  range (`has_flash`, `n_tokens`, `value_eth`) have a negative permutation
  drop, i.e. shuffling them slightly helps on 2024.
* HK4.3: **supported for direction, not for ranking.**

## What this does NOT show

* Detection before execution. Every feature is computed from the mined
  transaction and its logs; this is a forensic or post-block alarm.
* Native-ETH profit (no traces), Uniswap V4 accounting, chains other than
  Ethereum, or price moves on Curve, Balancer and custom AMMs.
* A deployment false-alarm rate: the day set is the set of incident days, and
  alarms per day are measured on those days only.
* A detection rate for future attack styles: 13 test attacks give wide
  intervals, and the incident set follows one community repository and a
  keyword filter on its headings.
