# R5 model linkage: full giant, composition ECDFs and linked-retention dose

The frozen R5 experiment completed **852 physical fits**, with no failed fits and no convergence warnings. All 355 LightGBM feature-name warnings are retained. It produced 4,607,616 predictions on the full historical giant and evaluated twelve predefined nested frames. All planned model, seed, composition, dose and review-budget outcomes are retained, including reversals and weak baseline results. No public repository update, external-cohort score or human annotation was created.

## Design and scope

The primary evaluation frame contains all **5,408 files in the historical joint giant**, with **83 reentrancy proxy positives**. This is larger historical coverage, not a new external population. The original 1,082-file test with 21 positives is a precursor/compatibility slice. Ten previously defined label-blind inside-giant tests each contain 1,062 files and 13–21 positives; they are overlapping nested sensitivity slices, not independent families or independent replications.

The B-eligible pool contains 1,179 files with 31 positives. The C-eligible pool contains 708 files with 24 positives. Their difference is 471 C-linked files, including seven positives. All training sets have exactly **708 files and 24 positives**, and none intersects the full historical giant.

The main experiment draws fifty class-stratified B training compositions using a frozen path-hash ranking. The first five are exactly the R4 compositions. C uses its complete 708-file pool. Raw and normalized LR use seed zero; RF and LightGBM use five paired seeds, 0–4. This requires 600 B fits and twelve C fits. C outputs are reused in comparisons, never counted as fifty new independent fits.

For trees, the primary composition distribution consists of **fifty averages over five estimator seeds**, compared with the C average over the same five seeds. Seed-matched ECDFs are reported separately. The 250 B tree cells are not treated as 250 independent composition draws. ECDF strict and weak counts have a two-percentage-point grid; tied midranks are also retained. Percentiles are descriptive positions in this conditional reference distribution, not p-values.

The dose experiment retains 0, 118, 236, 353 or 471 of the linked files, with respectively 0, 2, 4, 5 or 7 linked positives. Complementary C-safe rows keep total training size and positive count fixed. Five independently salted compositions use nested ranks within linked/safe and positive/no-finding strata. The zero-dose set is always the same complete C pool, so it has one unique composition. The four positive doses add 240 fits.

**100% retention means all 471 linked candidates, which are 66.53% of a 708-file training set.** It does not mean 100% linked training. Every positive dose connects every giant test file under C; dose varies the amount and composition of linked training support, not the fraction of connected test files. All 71 distinct training memberships remain B-disjoint.

## Full-giant AP and composition percentiles

| Method | Mean B AP | Mean C AP | Mean B−C | Positive B−C compositions | C composition percentile |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw-token LR | 0.014278 | 0.012256 | 0.002022 | 42/50 | 16th |
| Normalized-token LR | 0.027472 | 0.022531 | 0.004941 | 45/50 | 10th |
| Pattern RF | 0.057351 | 0.041768 | 0.015583 | 50/50 | 0th |
| Pattern LightGBM | 0.049931 | 0.040843 | 0.009087 | 43/50 | 14th |

The exact expected AP for a uniform strict random ranking of this frame is **0.016835983**; prevalence is **0.015347633**. Raw LR's mean AP is below this descriptive random-ranking reference under both policies. Its positive mean B−C difference therefore does not establish useful detector performance. RF gives the strongest separation of the observed composition distributions: every B seed-averaged AP exceeds the C seed-averaged AP. Its zero empirical C percentile is not a significance statement or a bound on a population probability.

Separating estimator seeds matters. RF's seed-matched C percentiles range from 0th to 2nd, while LightGBM's range from 2nd to 34th. Their seed-averaged primary percentiles are 0th and 14th, respectively. All seed-specific results are retained in `analysis/seed_matched_ecdf.csv`.

## All model-specific review budgets

Floor budgets are 270, 540 and 1,081 reviews. The random strict-ranking expected yields are **4.143861, 8.287722 and 16.590791** recorded findings, respectively.

| Method | Reviews | Mean B findings | Mean C findings | B−C |
| --- | ---: | ---: | ---: | ---: |
| Raw-token LR | 270 | 4.060000 | 4.000000 | 0.060000 |
| Raw-token LR | 540 | 7.260000 | 4.000000 | 3.260000 |
| Raw-token LR | 1,081 | 13.200000 | 9.000000 | 4.200000 |
| Normalized-token LR | 270 | 8.320000 | 10.000000 | −1.680000 |
| Normalized-token LR | 540 | 16.900000 | 15.000000 | 1.900000 |
| Normalized-token LR | 1,081 | 30.940000 | 25.000000 | 5.940000 |
| Pattern RF | 270 | 16.100565 | 10.450000 | 5.650565 |
| Pattern RF | 540 | 29.782305 | 20.333333 | 9.448971 |
| Pattern RF | 1,081 | 53.913720 | 42.450475 | 11.463246 |
| Pattern LightGBM | 270 | 13.302000 | 9.200000 | 4.102000 |
| Pattern LightGBM | 540 | 25.152000 | 15.200000 | 9.952000 |
| Pattern LightGBM | 1,081 | 45.420000 | 35.200000 | 10.220000 |

Findings use expected positive counts under uniform ordering within a boundary score tie. Per-fit attainable minima/maxima, precision, recall, boundary tie sizes and slots are also preserved. Raw LR is below the random expected yield at all three budgets under both policies. Normalized LR reverses the AP comparison at the smallest budget: C retrieves more findings despite lower mean AP. The policy effect is therefore model- and budget-dependent.

## What changes after fifty compositions and wider test coverage

On the original 1,082-file slice, raw LR has mean B AP 0.032541 and C AP 0.028383, a mean difference of +0.004158. However, C is at the **44th composition percentile**, with 28 positive and 22 negative B−C differences. The earlier five-draw mean is insufficient to characterize a consistently adverse C policy for this model. This observation does not establish equivalence or absence of all effects.

Among the ten nested label-blind slices, mean B−C AP is positive for eight slices with raw LR and nine with each other model. Reversals are retained: RF reverses on seed1302; LightGBM on seed1305; normalized LR on seed1310; raw LR on seed1303 and seed1310. Their overlap and common giant prevent treating these counts as independent-family evidence. Wider test coverage and the chosen evaluation slice materially affect the numerical comparison.

## Dose response is model-specific

The table gives mean AP after averaging tree seeds within each of the five compositions. Zero dose is the single fixed C composition.

| Linked-candidate retention | Linked files / linked positives | Raw LR | Normalized LR | RF | LightGBM |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0% | 0 / 0 | 0.012256 | 0.022531 | 0.041768 | 0.040843 |
| approximately 25% | 118 / 2 | 0.012753 | 0.025075 | 0.046604 | 0.038195 |
| approximately 50% | 236 / 4 | 0.016599 | 0.027405 | 0.055039 | 0.045370 |
| approximately 75% | 353 / 5 | 0.015170 | 0.031184 | 0.058934 | 0.052820 |
| 100% | 471 / 7 | 0.016113 | 0.032228 | 0.070310 | 0.062354 |

The observed dose means increase monotonically for normalized LR and RF. LightGBM decreases at the first positive dose before increasing; raw LR is non-monotone. All five composition outcomes and complete dose-by-budget results are retained, rather than selecting a favorable curve or fitting an outcome-chosen trend.

The fifty B compositions contain 269–299 linked files (mean 282.48) and three to seven linked positives (mean 5.34). The secondary descriptive correlation analysis finds weak Pearson correlations between linked file count and full-giant AP: −0.054 raw LR, −0.070 normalized LR, +0.019 RF and +0.156 LightGBM. Linked-positive count has correlations −0.046, +0.217, +0.540 and +0.424, respectively. These are associations within the prescribed composition distribution, without p-values or a causal interpretation; they cannot separate linked-positive identity, project composition and other source characteristics. The additional correlation analysis was requested while fitting was in progress and is documented separately from the original frozen fit plan.

## Verification and computational provenance

`FREEZE_BEFORE_FITTING.json` SHA-256 is `c63d285e357f2b3e29506d34577e70b3ccb5ff647e4f6936defca1bdf556dd1a`. Independent design checks replayed all membership ranks, verified all 6,587 historical labels against pinned annotations and checked all twelve frame definitions before the first fit.

Only deterministic source preprocessing was memoized. Raw/normalized token strings were recomputed for 6,134 distinct decoded sources; original and cached pattern matrices matched bitwise in float64 and the float32 input representation for all 6,587 files. Vectorizers, scalers and estimators were fitted separately for every physical configuration. The unchanged historical fitting function was used with an explicit cached-preprocessing adapter. No fitted model binary was recovered or retained.

The first 72 physical configurations retrained the R4 models, predicted the full giant and extracted the original 1,082 scores. Maximum score discrepancy was 2.78×10⁻¹⁷, within the frozen 10⁻¹² technical tolerance; bitwise equality of every score is not claimed. All 72 AP values and 216 review-yield values on that precursor slice matched exactly. The remaining 780 fits launched only after this compatibility check passed.

Execution used two workers, at most four threads per tree fit and one per LR fit. Feature-cache construction took 29.898 seconds; fitting and score storage took 1,011.734 seconds. These are observations on this environment, not an algorithmic speed claim. The cache was removed after successful completion.

The producer verified 2,556 artifact hashes, 10,224 AP values and 30,672 budget cells. A second agent independently checked **223,944 numeric cells** across per-fit and aggregate outputs; ECDF counts and yield/minimum/maximum values agreed exactly, with maximum AP discrepancy 5.55×10⁻¹⁷. Computational audits do not constitute human vulnerability adjudication.

Machine-readable entry points are `COMPLETE.json`, `ANALYSIS_COMPLETE.json`, `analysis/primary_AP_table.csv`, `analysis/primary_review_budget_table.csv`, `analysis/composition_ecdf_summary.csv`, `analysis/seed_matched_ecdf.csv`, `analysis/dose_composition_summary.csv` and `analysis/linked_count_AP_correlations.csv`. Independent records and figures reside under `../../independent_model_audit/`; graph design and connectivity checks reside under `../../graph_checks/`.

Reproduction from the repository root requires the pinned DAppSCAN source/annotation checkout and the declared numerical environment:

```sh
python papers/security_evaluation/revision3/model_link/run_r5.py prepare --out NEW_RUN_DIRECTORY
python papers/security_evaluation/revision3/model_link/run_r5.py execute --out NEW_RUN_DIRECTORY --workers 2
python papers/security_evaluation/revision3/model_link/analyze_r5.py --run NEW_RUN_DIRECTORY
```

The historical R4 score artifacts are required for the replay gate. No old file or receipt was modified by this study. The main scientific result is a conditional, model-specific response to an explicitly defined graph-exclusion policy; no independently validated vulnerability detection, semantic clone truth or universal leakage mechanism is established.
