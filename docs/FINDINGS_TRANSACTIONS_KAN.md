# T / K — Elliptic under a strict temporal protocol

Runs: `results/transactions/t1_20261022_v2` (78 fits: LightGBM, RF, MLP, KAN × 3 feature sets × 5 seeds;
logistic regression × 3 feature sets × 1 seed; GCN, GraphSAGE, GAT × 1 feature set × 5 seeds;
GAT re-run after the softmax fix, other parts copied from
`t1_20261021_full`), `results/transactions/t2_20261022_113332` (label-shift
correction and shift diagnostics),
`results/transactions/t3_*` (Optuna, 40 trials per model family),
`results/transactions/t4_20261022_014938` (label-free monitors),
`results/kan/k1_{robust,quantile}_20261022_142521` (KAN analysis, 3 seeds, current LUT code).

Train steps 1–30, validation 31–34, test 35–49 (pre 35–42, post 43–49).
Illicit share: 11.0 % train, 17.0 % validation, 9.2 % pre, 2.5 % post.

## 1. Model families (T1, default configurations, mean of 5 seeds)

Feature set per model chosen by validation AUPRC (`headline_by_validation.csv`).

| Model | Features (by validation) | Test F1 | Test AUPRC | Pre F1 | Post F1 | Test F1 of the test-best set |
|---|---|---|---|---|---|---|
| LightGBM | AF+NB | **0.807** | **0.801** | 0.903 | 0.026 | same |
| Random forest | AF+NB | 0.798 | 0.792 | 0.898 | 0.027 | same |
| GraphSAGE | AF + graph | 0.581 | 0.569 | 0.666 | 0.022 | same |
| MLP | AF+NB | 0.517 | 0.530 | 0.624 | 0.045 | 0.557 (LF) |
| GAT (fixed softmax) | AF + graph | 0.500 | 0.501 | 0.568 | 0.018 | same |
| KAN | AF | 0.488 | 0.474 | 0.585 | 0.061 | same |
| GCN | AF + graph | 0.459 | 0.425 | 0.520 | 0.015 | same |
| Logistic regression | AF+NB | 0.370 | 0.308 | 0.501 | 0.063 | 0.416 (LF) |

* **HT.1 supported.** Tree ensembles beat every GNN by > 0.2 F1 (Maganti 2026
  reports the same ordering: RF 0.821, GraphSAGE 0.688, GAT 0.610, GCN 0.503).
  The GAT fix raised GAT from 0.463 to 0.500 and did not change the order.
* **HT.2 supported.** Mean/max neighbour aggregates add +0.017 F1 to RF and
  +0.009 to LightGBM; message passing never catches up with them.
* GNNs were not tuned; their numbers are a default-configuration result, not
  a ceiling. Early stopping differs by family (PROTOCOLS.md).

## 2. Tuning (T3, same 40-trial TPE budget per family, objective = validation AUPRC)

| Model | Default test F1 (AF) | Tuned test F1 | Tuned test AUPRC | Chosen input normalisation |
|---|---|---|---|---|
| LightGBM | 0.807 | 0.801 | 0.795 | — |
| Random forest | 0.798 | 0.794 | 0.792 | — |
| MLP | 0.542 | **0.681** | 0.765 | quantile |
| KAN | 0.488 | **0.655** | 0.764 | quantile |

* **HT.4 supported.** The "default" column is the AF-only T1 run, so that it
  has the same feature set as the tuned models (the validation-selected T1
  headline for the MLP is AF+NB, F1 0.517, a gain of about 0.164 to the tuned
  0.681). Tuning does nothing for trees and lifts the neural
  models by 0.14–0.17 F1 on AF, but the gap to the trees remains (≈ 0.12–0.15 F1).
* **HT.5 supported on validation.** Rank-based (quantile) normalisation was
  selected in 33/40 MLP and 35/40 KAN trials; the best robust-scaled trial
  reached validation AUPRC 0.935 (MLP) and 0.858 (KAN) against 0.977 / 0.968
  with quantile inputs: the KAN gains more (+0.11 vs +0.04).
* Validation AUPRC (0.95–0.99) is far above test AUPRC (0.76–0.80) for all
  models: steps 31–34 are easier than the test period, so tuning on them cannot
  anticipate the shift.

## 3. The post-shutdown collapse is not explained by prior shift (T2) — HT.3 rejected

RF AF+NB, F1 by test period, validation threshold kept fixed:

| Correction | Pre | Post | Whole test |
|---|---|---|---|
| none | 0.898 | 0.027 | 0.798 |
| EM prior | 0.896 | 0.000 | 0.814 |
| BBSE prior | 0.897 | 0.009 | 0.814 |
| oracle prior (true per-step share) | 0.899 | 0.014 | 0.815 |

The oracle row alone proves little: with a fixed F1 threshold, prior
correction can lower F1 even under exact label shift
(`tests/test_eval.py::test_prior_correction_with_fixed_threshold_can_fail_under_exact_label_shift`).
The evidence is in the per-step diagnostics (`shift_diagnostics_by_step.csv`,
RF and LightGBM AF+NB, labels used only to describe the shift):

| Steps | Illicit KS vs validation | Licit KS vs validation | ROC-AUC | F1 at the step's own best threshold |
|---|---|---|---|---|
| 35–42 (pre) | 0.20–0.53 | 0.06–0.34 | 0.91–1.00 | 0.78–0.98 |
| 43–45, 47 (post) | **0.94–1.00** | 0.09–0.33 | **0.65–0.78** | **0.03–0.14** |
| 48–49 (post) | 0.98–0.99 | 0.17–0.26 | 0.78–0.90 | 0.42–0.47 |

Step 46 has 2 illicit transactions and is left out. After the shutdown the
score distribution of illicit transactions moves almost completely (KS close
to 1) while that of licit ones does not move more than before, the ranking
degrades (ROC-AUC, which does not depend on prevalence), and no threshold —
hence no prior correction — recovers F1. Under pure label shift P(score | y)
would be unchanged. The data are therefore inconsistent with pure label
shift; they do not identify which mechanism replaced it.

## 4. Label-free monitors would not have raised the right alarm (T4)

| Step | True illicit share | RF AUPRC | EM prior estimate | median PSI |
|---|---|---|---|---|
| 42 | 0.111 | 0.890 | 0.090 | 0.047 |
| 43 | 0.018 | 0.034 | 0.000 | 0.086 |
| 48 | 0.076 | 0.254 | 0.000 | 0.061 |
| 49 | 0.118 | 0.226 | 0.000 | 0.042 |

* The output monitor (EM prior) tracks model quality (Spearman 0.84 with
  per-step AUPRC) but reads as "illicit activity has stopped": in steps 48–49
  the true share is back at 8–12 % while the estimate stays at 0.
* Input monitors are uninformative on Elliptic: a classifier separates every
  single test step from the training steps with ROC-AUC ≈ 1.0 (pre and post
  alike), and the median PSI of post steps (0.04–0.09) is within the pre range
  (0.04–0.12).
* Practical rule: a collapse of the estimated illicit share to
  zero must trigger label acquisition (an audit sample), not be read as good news.

## 5. KAN-specific results (K1)

Runs `results/kan/k1_quantile_20261022_142521` and
`results/kan/k1_robust_20261022_142521`, re-run on the current LUT code
(float32 interpolation); every accuracy number is identical to the first
runs of 2026-10-21 and LUT logit errors differ by < 1e-5.

Matched parameter count (MLP with one hidden layer of the same size), mean of
3 seeds. Both models get the same fitted transform (robust z-score, or
quantile → normal and ×5/3), clipped to ±5; the KAN then receives that input
×0.6, so its spline grid on [−3, 3] covers the clipped range. The MLP receives
the clipped input unscaled. This rescaling is part of the KAN's definition:

| Config (params) | Robust inputs: KAN / MLP test F1 | Quantile inputs: KAN / MLP test F1 | Quantile: KAN / MLP test AUPRC |
|---|---|---|---|
| width 4, grid 3 (5.3 k) | 0.477 / 0.529 | 0.627 / 0.639 | 0.774 / 0.781 |
| width 8, grid 5 (13.3 k) | 0.474 / 0.542 | **0.694** / 0.632 | 0.768 / 0.779 |
| width 8, grid 8 (17.3 k) | 0.467 / 0.578 | 0.651 / 0.625 | 0.780 / 0.783 |
| width 16, grid 5 (26.6 k) | 0.527 / 0.567 | 0.612 / 0.629 | 0.777 / 0.783 |
| RF reference | 0.777 | 0.777 | 0.791 |

* **HK.1 supported.** With robust scaling the KAN loses to the matched MLP in
  all four sizes. With quantile inputs the 3-seed means are close, but 3
  seeds cannot establish either a tie or a difference; see §5a.
  Neither reaches the RF in F1, although quantile inputs bring the neural
  AUPRC (0.77–0.78) within 0.01–0.02 of the RF.
* **HK.2 rejected.** The spline-range relevance of the first KAN layer agrees
  only weakly with the same model's permutation importance (Spearman 0.33
  robust, 0.39 quantile; top-10 overlap 6/10). It is not a faithful
  explanation on its own.
* **HK.3 rejected.** The share of inputs outside the training range (clipped
  before the splines) is 0.9 % in training and 1.5 % in both pre and post
  periods; it does not rise after the shutdown and does not explain per-step
  F1 (robust inputs, |Spearman| ≤ 0.21 for every model). Consistent with §3: the new illicit behaviour lies
  inside the training range.
* **HK.4 partly supported.** The pre-set target (≥ 99.9 % decision
  agreement at 8 points per interval) is met with quantile inputs (99.985 %)
  but not with robust inputs (99.88 %; met from 16 points on). Agreement here
  is over all labelled nodes, in K2 over test nodes; 99.96–99.99 % at 16–32 points. The timings
  stored in `lut.csv` were taken on a loaded 4-core VM and are not used;
  §6 has the idle-machine measurement.

## 5a. KAN vs matched MLP: pre-declared 10-seed analysis (K3)

`results/kan/k3_20261022_163604`. KAN 165→8→1 (grid 5, 13,280 parameters)
against the MLP 165→80→1 (13,361), quantile inputs, AF features, 10 paired
seeds. This is a pre-declared follow-up analysis, not a confirmatory
preregistration: margin and decision rule were written in the script header
before the run, but after the first look at the same test period, and seeds
0–2 repeat T1. Decision rule: "better" if both 90 % intervals of the difference lie above 0,
"equivalent" if both lie inside ±0.02 AUPRC / ±0.03 F1.

| Metric | KAN | MLP | KAN − MLP | KAN wins | 90 % CI, seeds | 90 % CI, cluster bootstrap over test steps | Decision |
|---|---|---|---|---|---|---|---|
| test AUPRC (primary) | 0.767 | 0.780 | −0.013 | 3 / 10 | [−0.024, −0.002] | [−0.037, +0.002] | inconclusive |
| test F1 (secondary) | 0.638 | 0.605 | +0.034 | 6 / 10 | [−0.010, +0.077] | [+0.016, +0.049] | inconclusive |

The two metrics point in opposite directions: the MLP ranks slightly better
(AUPRC), while the KAN's validation threshold transfers slightly better (F1).
Neither difference passes the pre-declared rule, and neither is small enough
to call the models equivalent. Supported statement: **no stable advantage of
the KAN over a same-size MLP was found on Elliptic.** The first-pass
3-seed F1 difference (+0.06) did not hold up with 10 seeds.

## What these runs do NOT show

* GNNs were trained with one fixed configuration (2 layers, 64 hidden);
  GraphSAGE/GAT were not Optuna-tuned. Published tuned inductive GNNs stay
  below RF too (Maganti 2026, arXiv:2604.19514: RF F1 0.821 vs GraphSAGE
  0.689 ± 0.017), but our GNN numbers are a lower bound.
* The bootstrap resamples the observed test steps as clusters; it does not
  model dependence between neighbouring steps or new histories, so it says
  nothing about variability over future periods. A rolling-origin design or
  an independent source would be needed for that.
* The post-shutdown analysis is one event in one dataset.
* LUT timings (K2) compare the NumPy LUT with a NumPy B-spline KAN and a NumPy
  MLP; a compiled or hardware benchmark has not been run.

## 6. Clean inference-cost measurement (K2, idle machine, 1 thread)

`results/kan/k2_20261022_144836` (re-measured on the current float32 LUT
code; supersedes `k2_20261022_021810`): KAN 165→8→1, grid 5, quantile
inputs (13,280 parameters) against the parameter-matched MLP 165→80→1
(13,361). Median µs per transaction, 300 repetitions, one thread, no other
job running. The trained models and threshold are in `models.pkl`, so the
measurement can be repeated without training
(`--models results/kan/k2_20261022_144836/models.pkl`).

| Path | batch 1 | batch 32 | batch 1024 |
|---|---|---|---|
| KAN float, PyTorch | 353.5 | 38.5 | 30.4 |
| KAN float, NumPy (matched baseline) | 113.2 | 26.0 | 37.2 |
| **KAN LUT, NumPy, 8 points/interval** | **78.3** | 17.0 | 13.1 |
| MLP, PyTorch | **17.9** | **0.91** | **0.34** |

LUT decision agreement with the float KAN on 16,670 test transactions:
99.93 % (4 points/interval, 12 decisions differ), 99.988 % (8, 16 and 32
points, 2 differ), the same as before the float32 change; memory 0.24–1.9 MB
against 53 KB for the float weights. Single timings vary by about ±20 %
between runs (old run: 70.7 µs for the LUT at batch 1).

* LUT vs matched float B-spline (both NumPy): 1.4× faster at batch 1,
  2.8× at batch 1024. The LUT advantage is real but modest in interpreted code.
* The matched MLP is 4.4× faster than the LUT-KAN at batch 1 and 38× faster at
  batch 1024 on this CPU. A deployment argument for KAN on Elliptic-scale
  inputs therefore needs compiled LUT kernels (the lut-kan toolchain) or MCU
  targets, not Python; this is the planned next step.

## 7. T5 — Elliptic++ wallets: sensitivity to the split protocol

Runs: `results/transactions/t5_20261022_022444` (P1–P4) and `results/transactions/t5_20261022_023415` (P1b).
Labelled wallet data: 367,472 (address, step) rows, 265,354 addresses, 55 features.

**Observation.** All 55 wallet features are constant across the rows of an
address (share = 1.00) and several are explicit lifetime quantities
(`last_block_appeared_in`, `lifetime_in_blocks`, `num_timesteps_appeared_in`).
Constancy alone does not prove that every column uses future data. Under a
random row split, 34.8 % of test rows belong to an address that also has a
training row with the same features and label.

| Protocol | RF F1 | LightGBM F1 | LightGBM AUPRC | Test base rate |
|---|---|---|---|---|
| P1 random rows | 0.951 | 0.944 | 0.987 | 7.9 % |
| P1b random addresses (one row per address) | 0.875 | 0.889 | 0.957 | 5.2 % |
| P2 temporal rows (train ≤ 30, test ≥ 35) | 0.336 | 0.432 | 0.426 | 7.1 % |
| P3 temporal + address-disjoint | 0.273 | 0.346 | 0.277 | 5.3 % |
| P4 = P3 without block/lifetime features | **0.387** | 0.348 | 0.271 | 5.3 % |

Mean of 3 seeds; std ≤ 0.017 F1 everywhere.

**Findings**

1. Wallet-level F1 ≈ 0.95 is a property of the random row split. Each step
   towards a deployment-like split lowers it; the largest drop comes with the
   temporal split (0.88 → 0.27–0.35). Each transition also changes address
   weighting, training size, prevalence and period, so the drops measure
   protocol sensitivity, not an amount of leakage.
2. Removing the block and lifetime features does not lower the score
   (HT.6, second part, rejected): RF gains +0.11 F1. These features act as
   period identifiers that overfit the training period.
3. Under P3/P4 wallet-level F1 is 0.35–0.39, against 0.80 at transaction level
   (T1). The remaining features are still lifetime aggregates, so P4 is not
   a deployment estimate either; a causal wallet feature set has to be rebuilt
   from transactions.
