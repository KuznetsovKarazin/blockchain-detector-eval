# Independent R5 model-score audit

The audit reads immutable saved predictions. It never imports producer metric functions, retrains models, changes predictions, or changes the frozen experiment. `PLAN_BEFORE_AUDIT.json` fixes the input/source hashes and all comparisons before the audit computes R5 metrics.

## Independent estimands

For each distinct descending score group, AP contributes `(group positives / total positives) × (cumulative positives / cumulative files)`. This is non-interpolated average precision with a threshold at each unique score. A zero-positive frame would retain undefined AP. Scores must be finite and each prespecified file must appear exactly once.

For a review budget crossing a score tie, expected findings equal all positives above the tie plus `(remaining review slots × tie positives / tie size)`. The minimum and maximum possible boundary-tie yields are retained separately. Budgets are exact integer floors of 5%, 10%, and 20% of each frame.

The exact expected AP of a uniform distinct-score random ordering is

`H_N/N + (K-1)/(N-1) × (1 - H_N/N)`, for `N > 1` and `K > 0`.

Derivation: writing `I_r` for the indicator of a positive at rank `r`, AP is `sum_r [I_r × sum_{j<=r} I_j / r] / K`. In a uniform ordering, `E[I_r]=K/N` and `E[I_r I_j]=K(K-1)/(N(N-1))` for distinct positions. Separating the diagonal term gives the displayed expression. It differs from prevalence at finite N. Exact rational enumeration verifies all 55 `(N,K)` combinations with `1 <= K <= N <= 10`. Constant scores instead yield AP equal to prevalence; this differs from the expected AP of a random distinct ordering.

Random review has expected findings `bK/N`. For the 5,408-file, 83-positive primary frame, expected random AP is 0.016835982943502, while prevalence is 0.015347633136095. The budgets 270, 540, and 1,081 have random expected findings 4.143860946746, 8.287721893491, and 16.590791420118.

## Aggregation

The main composition ECDF has 50 B values per method and frame. Tree metrics are averaged across five seeds *within each training membership first*; the C comparator is its five-seed mean. LR uses its single frozen seed. Separate seed-matched ECDFs are retained, without treating the 250 tree fit cells as 250 independent composition draws. Strict ECDF, weak ECDF and midrank are reported to expose exact ties.

All five linked-retention compositions and all four methods are retained at every dose. Zero dose references the same C fits and is explicitly marked as reused; it does not create five independent experiments. At the 100% linked-pool retention endpoint, all 471 linked files are retained, comprising 66.53% of the fixed 708-file training set. Every dose still contains 24 proxy positives. All four methods and all three review budgets are summarized, regardless of direction.

The twelve evaluation frames are nested and overlapping subsets of one historically inspected component. Neither the frames nor their quantiles constitute independent-family replication. All ECDFs, composition ranges and linked-count correlations are descriptive. No significance tests, IID confidence intervals, semantic labels, or causal effect of an individual graph edge are inferred.

## Commands

From the repository root:

```sh
python -m pytest -q papers/security_evaluation/revision3/independent_model_audit/test_independent_metrics.py
python papers/security_evaluation/revision3/independent_model_audit/audit_r5.py prepare
# Only after the producer COMPLETE.json exists and records every planned fit:
python papers/security_evaluation/revision3/independent_model_audit/audit_r5.py audit
python papers/security_evaluation/revision3/independent_model_audit/compare_producer.py
python papers/security_evaluation/revision3/independent_model_audit/plot_r5.py
```

Preparation uses a fresh output directory and refuses to overwrite a prior audit. The audit verifies prediction and per-fit result hashes against producer receipts, reconstructs 10,224 AP values and 30,672 review-budget values, then creates independently derived aggregate CSVs. The separate producer comparison must pass before `plot_r5.py` exports figures. A pending preparation or generated script is not evidence that these checks have completed; consult the final completion records.

## Completed result

The frozen run `run_20261029_v1` passed independent reconstruction and producer comparison: 852 score vectors, 4,607,616 scores, 10,224 AP values, 30,672 review-budget cells, and 223,944 aggregate/per-fit comparison cells. Per-fit AP differs by at most 5.55e-17; all per-fit review yields and ECDF counts agree exactly. The 355 retained LightGBM feature-name warnings include zero convergence warnings. All three scientific figure sets passed visual inspection. See `ENGLISH_FINDINGS.md` for balanced interpretation, all twelve method/budget results, and manuscript-ready captions; see `run_20261029_v1/AUDIT_COMPLETE.json` for the final receipt.
