# Conditional historical-pilot training variation

This completed post-pilot diagnostic uses the exact original T: 1,082 files, 21 proxy positives, one historical joint component. It measures variation from training-subset selection on this fixed dependent test, not uncertainty for new projects or families. The external and expanded-graph comparative gates remain unchanged and blocked.

Run fingerprint: `d0b63a12a2ca839743e682b71a33ac138dd6a4d5feee7072c1f203d937652204`.

All 360 logical evaluations completed (282 physical fits; 0 failures; 0 physical fits with convergence warnings). Physical-fit preprocessing/fit/prediction total: 20.75 minutes. Cumulative process peak RSS: 447.98 MiB.

The main panel fixes estimator seed zero and uses 20 paired training draws per regime/method, each with 1,179 files and 31 proxy positives. The joint pool has only one unique training membership; all its main-panel repeats reuse the same fit. All four raw-LR draw-zero score vectors exactly reproduce the original pilot.

## Main-panel AP distributions

Quantiles and ranges below describe the 20 training draws. They are not confidence intervals.

| Method | Regime | Unique training sets | Mean AP | SD | 2.5% quantile | Median | 97.5% quantile | Min–max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Raw TF-IDF LR | Unrestricted | 20 | 0.096463 | 0.060360 | 0.025853 | 0.077251 | 0.222976 | 0.025599–0.259966 |
| Raw TF-IDF LR | Project | 20 | 0.042048 | 0.010123 | 0.025828 | 0.044010 | 0.057031 | 0.024298–0.060754 |
| Raw TF-IDF LR | Clone | 20 | 0.060328 | 0.034318 | 0.022923 | 0.048680 | 0.129306 | 0.020360–0.137118 |
| Raw TF-IDF LR | Joint | 1 | 0.038475 | 0.000000 | 0.038475 | 0.038475 | 0.038475 | 0.038475–0.038475 |
| Normalized TF-IDF LR | Unrestricted | 20 | 0.122939 | 0.050853 | 0.055385 | 0.109456 | 0.208327 | 0.052353–0.209153 |
| Normalized TF-IDF LR | Project | 20 | 0.074029 | 0.012490 | 0.052401 | 0.073005 | 0.097555 | 0.047811–0.099277 |
| Normalized TF-IDF LR | Clone | 20 | 0.103196 | 0.044072 | 0.052713 | 0.096870 | 0.201257 | 0.048672–0.229322 |
| Normalized TF-IDF LR | Joint | 1 | 0.054608 | 0.000000 | 0.054608 | 0.054608 | 0.054608 | 0.054608–0.054608 |
| Pattern RF500 | Unrestricted | 20 | 0.204087 | 0.066005 | 0.101899 | 0.196428 | 0.334575 | 0.083271–0.334766 |
| Pattern RF500 | Project | 20 | 0.087582 | 0.011820 | 0.066889 | 0.088051 | 0.107096 | 0.061080–0.109912 |
| Pattern RF500 | Clone | 20 | 0.178678 | 0.062387 | 0.076066 | 0.186344 | 0.292076 | 0.073079–0.307713 |
| Pattern RF500 | Joint | 1 | 0.073009 | 0.000000 | 0.073009 | 0.073009 | 0.073009 | 0.073009–0.073009 |
| Pattern LightGBM400 | Unrestricted | 20 | 0.139946 | 0.048349 | 0.061585 | 0.147710 | 0.239134 | 0.052556–0.240021 |
| Pattern LightGBM400 | Project | 20 | 0.067985 | 0.010636 | 0.056781 | 0.067625 | 0.090298 | 0.056675–0.102927 |
| Pattern LightGBM400 | Clone | 20 | 0.130541 | 0.052594 | 0.053576 | 0.123170 | 0.209474 | 0.050161–0.222605 |
| Pattern LightGBM400 | Joint | 1 | 0.061576 | 0.000000 | 0.061576 | 0.061576 | 0.061576 | 0.061576–0.061576 |

## Paired AP differences relative to joint

Each difference uses the same draw index, fixed estimator seed and fixed T. The positive fraction is a descriptive count over draws, not a p-value.

| Method | Contrast | Mean difference | 2.5% quantile | Median | 97.5% quantile | Positive draws |
|---|---|---:|---:|---:|---:|---:|
| Raw TF-IDF LR | Unrestricted − joint | 0.057989 | -0.012622 | 0.038776 | 0.184501 | 16/20 |
| Raw TF-IDF LR | Project − joint | 0.003573 | -0.012647 | 0.005536 | 0.018556 | 12/20 |
| Raw TF-IDF LR | Clone − joint | 0.021854 | -0.015552 | 0.010205 | 0.090831 | 12/20 |
| Normalized TF-IDF LR | Unrestricted − joint | 0.068331 | 0.000777 | 0.054848 | 0.153719 | 19/20 |
| Normalized TF-IDF LR | Project − joint | 0.019421 | -0.002207 | 0.018397 | 0.042947 | 19/20 |
| Normalized TF-IDF LR | Clone − joint | 0.048588 | -0.001895 | 0.042262 | 0.146649 | 19/20 |
| Pattern RF500 | Unrestricted − joint | 0.131078 | 0.028889 | 0.123418 | 0.261565 | 20/20 |
| Pattern RF500 | Project − joint | 0.014573 | -0.006120 | 0.015042 | 0.034087 | 19/20 |
| Pattern RF500 | Clone − joint | 0.105669 | 0.003057 | 0.113335 | 0.219067 | 20/20 |
| Pattern LightGBM400 | Unrestricted − joint | 0.078370 | 0.000009 | 0.086134 | 0.177559 | 19/20 |
| Pattern LightGBM400 | Project − joint | 0.006409 | -0.004795 | 0.006049 | 0.028722 | 13/20 |
| Pattern LightGBM400 | Clone − joint | 0.068965 | -0.008000 | 0.061594 | 0.147899 | 18/20 |

## Estimator-seed panel on the fixed joint pool

This panel changes only the tree estimator seed (0–19); training membership is identical. It is separate from training-selection variation.

| Method | Mean AP | SD | Minimum | Maximum |
|---|---:|---:|---:|---:|
| Pattern LightGBM400 | 0.073541 | 0.018984 | 0.053175 | 0.113831 |
| Pattern RF500 | 0.079056 | 0.003595 | 0.073009 | 0.087179 |

## Uniform random-ranking reference

The exact expected AP is **0.025363028221**, compared with proxy prevalence **0.019408502773**. For the frozen 10,000 random rankings, mean AP is 0.025483, median 0.022507, and descriptive 2.5%/97.5% quantiles 0.015621/0.060593. These are a stipulated strict random-ordering reference, not an inferential permutation test or a fitted method. No p-values are computed.

Workload budgets are exactly 54, 108 and 216 reviews. Full per-draw workload, coverage, boundary-tie expectations/ranges and all six paired regime differences are in `summary/`. The original frozen reference helper was validated for these budgets; its generic floating-point budget calculation can underflow at unrelated fractions such as 0.29×100. That edge case does not affect this run and is handled in a separately versioned generic utility without changing the executed source.

`run_20261025_v1` is a preserved unused preflight, never scored. The executed experiment is `run_20261025_v2`. Proxy-label agreement, conditional historical dependence and the previously exposed test remain limitations; none of these results certifies expanded-graph independence or external detection quality.
