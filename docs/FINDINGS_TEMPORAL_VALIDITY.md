# TV — What survives the next period: ranking, threshold, monitor

Protocol: `docs/PROTOCOLS_TV.md` (hypotheses HV1–HV5 and decision rules,
committed in f862189 before the first run; the changes made after it are
listed at its end). Decision rules are evaluated by
`scripts/tv6_analysis.py`, output `results/tv_analysis_20261031/`.

| Experiment | Run |
|---|---|
| X1 / A1 causal wallet features (Elliptic++) | `results/transactions/tv1_20261030_x1` |
| X2 / X4 / X6 / A2 rolling origin (Elliptic) | `results/transactions/tv2_20261030_x2` |
| X2 / X3 / X4 / X6 / A3 K4 temporal splits, quiet days (rule, logreg, RF, LightGBM) | `results/kan/tv4_20261031_005129` |
| same, MLP and KAN | `results/kan/tv4_20261031_014421` |
| X5 Optuna GraphSAGE / GAT | `results/transactions/tv5_sage_20261030`, `tv5_gat_20261031` |

## Verdicts

| ID | Verdict by the pre-registered rule | In one line |
|---|---|---|
| HV1 | **Not supported** (part 1 holds by a wide margin, part 2 fails) | Causal features beat lifetime features under the temporal split by 0.28–0.31 AP and do *not* lose anything under the random split. |
| HV2 | Elliptic **not supported** (τ = 0.47); K4 **supported** (τ = 0.82, best AP varies 2.0×) | Trees rank first at every cut-off on both data sets, but on Elliptic the order below them moves and collapses at c = 40. |
| HV3 | Elliptic part 1 **not supported**, part 2 supported; K4 part 1 **supported**, part 2 **not supported** (logistic regression) | On Elliptic the fixed threshold mostly *under*-alarms; on K4 it over-alarms 5–8× on quiet days. Top-k keeps the budget by construction. |
| HV4 | **Supported** (both parts) | PSI and the domain classifier do not track AP; the EM estimate of the illicit share goes to 0 from step 43 while the true share is 0.3–11.8 %. |
| HV5 | **Supported** | Without set-up features LightGBM test AP falls from 0.21 to 0.03; without mechanism features it rises to 0.28. |

## HV1 / X1 — causal wallet features

Elliptic++ wallet rows: 367,472 labelled rows of 265,354 addresses. The
wallet class equals "the address ever touched an illicit transaction": at
each address's last row the causal label (illicit transaction so far)
agrees with the class for every address; at the first row only 153 illicit
wallets have no illicit transaction yet (`audit.json`).

Mean AP over 3 seeds (wallet label; std ≤ 0.026):

| Protocol | LGBM causal | LGBM lifetime | LGBM lifetime, no time | LGBM causal + lifetime | RF causal | RF lifetime |
|---|---|---|---|---|---|---|
| P1 random rows | 0.989 | 0.987 | 0.968 | 0.994 | 0.989 | 0.985 |
| P1b random addresses | 0.967 | 0.957 | 0.916 | 0.978 | 0.967 | 0.941 |
| P2 temporal rows | 0.716 | 0.426 | 0.381 | 0.767 | 0.628 | 0.311 |
| P3 temporal, first row per address | 0.555 | 0.277 | 0.271 | 0.609 | 0.532 | 0.218 |
| P5 temporal, new addresses only | 0.716 | 0.413 | 0.370 | 0.765 | 0.631 | 0.289 |

* Under P3 causal − lifetime = +0.277 (LightGBM) and +0.314 (RF): part 1
  holds. Under P1 the difference is +0.002 / +0.004, not < −0.02: part 2
  fails, so HV1 as written is not supported. The prediction that
  lifetime features owe their random-split score to information from the
  future is wrong in direction: they are worse features, and the random
  split hides how much worse.
* Post-hoc check (`causal_no_degree`, without transaction in/out degree,
  which is complete only once the outputs are spent): LightGBM AP 0.689
  (P2), 0.536 (P3), 0.690 (P5). The gain does not rest on the degrees.
* The causal label (sensitivity row) gives the same picture: P3 LightGBM
  0.575 causal vs 0.289 lifetime; P5 0.707 vs 0.398.

## HV2 / X2 — rolling origin

Elliptic, window = all past steps, test AP over the five test steps
(LightGBM/RF/MLP mean of 5 seeds, logistic regression 1 seed):

| Cut-off (test steps) | LightGBM | RF | MLP | Logistic |
|---|---|---|---|---|
| c20 (25–29) | 0.788 | 0.759 | 0.736 | 0.652 |
| c25 (30–34) | 0.980 | 0.989 | 0.839 | 0.689 |
| c30 (35–39) | 0.960 | 0.954 | 0.632 | 0.497 |
| c35 (40–44) | 0.819 | 0.808 | 0.763 | 0.485 |
| c40 (45–49) | 0.192 | 0.079 | 0.101 | 0.188 |

LightGBM per-step mean AP with 90 % bootstrap interval over steps: c30 0.960
[0.941, 0.977], c35 0.558 [0.232, 0.883], c40 0.328 [0.193, 0.443]. A tree
ensemble is first at every cut-off, mean Kendall τ between cut-off rankings
is 0.47 (min −0.33, c40 against the others: RF falls to last), best AP varies
5.2×. A2 (last 10 steps only) changes AP by at most 0.11 and does not
rescue c40 (LightGBM 0.132).

K4 test AP (incident days; 5 seeds; window = all):

| Split (test year, attacks) | LightGBM | RF | MLP | KAN | Logistic | Rule |
|---|---|---|---|---|---|---|
| t2024 (2024, 9) | 0.197 | 0.072 | 0.036 | 0.018 | 0.002 | 0.009 |
| t2025 (2025–26, 13) | 0.212 | 0.209 | 0.094 | 0.140 | 0.026 | 0.002 |
| t2026 (2026, 5) | 0.400 | 0.274 | 0.114 | 0.097 | 0.018 | 0.000 |

τ = 0.82 (min 0.73), best AP varies 2.0×: supported. With 5–13 test attacks
per split these are descriptive numbers, no tests (protocol).

## HV3 / X3 / X4 — thresholds and budgets

K4 t2025, alarms per day on the 14 quiet test days (the deployment-like
false-alarm rate) and recall on the 13 attacks, budget 1 alarm/day:

| Model | fixed on incident days: alarms, recall | fixed on quiet days: alarms, recall | top-k: alarms, recall |
|---|---|---|---|
| LightGBM | 8.3, 0.45 | 30.4, 0.58 | 1.0, 0.31 |
| RF | 7.1, 0.42 | 23.1, 0.57 | 1.0, 0.38 |
| MLP | 5.1, 0.35 | 16.0, 0.45 | 1.0, 0.23 |
| KAN | 2.7, 0.20 | 23.5, 0.51 | 1.0, 0.28 |
| Logistic | 5.1, 0.38 | 5.4, 0.38 | 1.0, 0.08 |

At 10/day the fixed threshold gives 37–68 alarms/day on quiet days. Five of
six models exceed 2× the plan at both budgets (the rule does not at 1/day,
it raises nothing): part 1 supported. Top-k keeps ≥ half the fixed recall for
all learned models except logistic regression at 1/day (0.08 vs 0.38):
part 2 not supported as written. Even the threshold set on the quiet validation days (2024) is exceeded
16–30× on the quiet test days of 2025–26 by the four non-linear models, so
the excess comes from the change between years, not from the difference
between incident and quiet days.

Elliptic (budget as share of all transactions of the step, mean over the 25
test steps): fixed thresholds give 0.4–1.7× the plan; the tree ensembles and
under-alarm at 1 % (achieved/planned 0.59 for LightGBM, 0.44 for RF; below
half the plan in 68 % and 79 % of the steps), logistic regression
over-alarms 1.6× at both budgets and the MLP 1.4× at 1 %. No
model exceeds 2× at both budgets: part 1 not supported. Top-k vs fixed recall:
median ratio 1.05, minimum 0.59: part 2 supported. The rolling quantile over
the previous 3 steps sits between the two.

## HV4 / X6 — label-free monitors

Elliptic, LightGBM seed 0, Spearman ρ with step AP over 25 test steps:
PSI median 0.17, domain-classifier AUC −0.10 (it is 1.000 at every step, so
it carries no information), mean score 0.54, EM-estimated illicit share 0.73.
The EM estimate follows the true share well (ρ = 0.88) until step 42. From
step 43 on it is below half the true share at every step and reads 0.000 at
steps 43 and 45–48 while the true share is 0.3–11.8 % and AP falls to
0.03–0.10 at steps 43–45.
A dashboard would read "fewer illicit transactions" when the detector has
stopped seeing them.

K4, incident test days of t2024–t2026, Spearman ρ with the (negated) median
attack rank: PSI 0.07 in absolute value, mean score 0.37, share above the
1/day threshold 0.33. PSI is 0.32 on quiet days and 0.39 on incident days.

## HV5 / A3 — set-up vs mechanism features (K4 t2025)

| Model | full | without set-up | without mechanism |
|---|---|---|---|
| LightGBM | 0.212 | 0.029 | 0.281 |
| RF | 0.209 | 0.020 | 0.156 |

Set-up = nonce, gas_used, to_created_today, n_contracts; mechanism =
has_flash, n_flash, flash_to_pool, max_price_move, net_price_move, n_pools.
The learned detectors find attackers by how they prepare (fresh contract,
low nonce, high gas), not by the price manipulation itself.

## X5 — tuned graph neural networks

GraphSAGE, Optuna TPE, 40 trials on the validation steps of T1 (run
`results/transactions/tv5_sage_20261030`). Best trial 31: AF features,
hidden 256, 3 layers, dropout 0.45, lr 0.013, validation AP 0.961. Refit on
5 seeds (validation AP 0.955 mean):

| Period | AP mean (std) | F1 mean |
|---|---|---|
| test (35–49) | 0.522 (0.078) | 0.564 |
| before shutdown (35–42) | 0.624 (0.094) | 0.633 |
| after shutdown (43–49) | 0.036 (0.001) | 0.024 |

Tuning raises validation AP but not test AP: the default GraphSAGE gave
0.569 on the same split, LightGBM 0.801. The validation steps sit before the
test period, so a better validation score buys nothing in the next period.
GAT (run `results/transactions/tv5_gat_20261031`, 40 trials with five
resumptions; interrupted trials discarded): best trial 42, AF features,
hidden 32, 2 layers, dropout 0.33, lr 0.028, validation AP 0.918; refit on
5 seeds: validation AP 0.893, test AP 0.545 (std 0.054), AP 0.641 before and
0.054 after the shutdown (default GAT: test AP 0.501).

Tuning moves GraphSAGE by −0.05 and GAT by +0.04 test AP, both within two
seed standard deviations; both stay 0.25–0.30 below LightGBM (0.801), and
every model has F1 ≈ 0.02 after step 43. Tuning does not change the RQ2 order.

## Limits

* K4 has 40 attacks and 5–13 per test split; all K4 numbers are descriptive.
* Elliptic labels cover about 23 % of transactions; budgets are shares of
  all transactions, recall is measured on the labelled ones.
* The causal features use the Elliptic++ transaction table; Elliptic++
  wallet labels are themselves derived from transaction labels (audit
  above), so the wallet task is close to "has this address been in an
  illicit transaction yet".
