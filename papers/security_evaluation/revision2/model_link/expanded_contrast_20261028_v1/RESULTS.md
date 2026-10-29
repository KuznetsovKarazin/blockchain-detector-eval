# Matched B/C graph-exclusion comparison

The separately frozen post-review experiment completed **72 physical fits and 120 logical evaluations**, with zero failed fits and zero convergence warnings. All thirty LightGBM fits retained the same feature-name warning; it is not suppressed or described as absent. The total recorded execution elapsed time was 412.518 seconds on this machine. No external file was scored and no human label was generated.

## Design

The test is the unchanged historical 1,082-file set with 21 reentrancy proxy positives. Exhaustive construction on the historical reference population (B) leaves a joint-disjoint candidate training pool of 1,179 DAppSCAN files with 31 positives. Expanding graph construction to the uncapped reference population (C), under the same pairwise relation, leaves 708 files with 24 positives. The 471 newly excluded B-pool files include seven positives.

Each comparison trains on exactly 708 files with 24 positives. Five deterministic, class-stratified path-hash draws select B-pool training subsets. C uses its complete pool for each draw index. Raw and normalized LR use seed zero. RF and LightGBM cross the five training draws with five paired estimator seeds, 0–4. All model settings and the model-fitting function are unchanged from the historical experiment. C requires two LR fits and ten tree fits; their outputs are reused across draw indices with exact configuration and prediction-hash verification. This yields 60 physical B fits and 12 C fits, represented by 120 logical comparison entries.

The design was frozen before its first model fit. It is a review-triggered conditional experiment on a previously observed test, not an untouched confirmation set. Matching training count and positive count isolates their arithmetic influence, while the resulting training composition remains a consequence of the exclusion policy. The result does not identify information flow through individual edges, semantic vulnerability equivalence or generalization to independent projects.

## Conditional AP

| Method | Mean B AP | Mean C AP | Mean B−C | Paired difference minimum | Paired difference maximum | Positive paired differences |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Raw-token LR | 0.034481 | 0.028383 | 0.006098 | −0.005448 | 0.018700 | 3/5 |
| Normalized-token LR | 0.049071 | 0.035399 | 0.013672 | 0.000584 | 0.029484 | 5/5 |
| Pattern RF | 0.078779 | 0.052509 | 0.026270 | −0.003022 | 0.055742 | 24/25 |
| Pattern LightGBM | 0.076546 | 0.044357 | 0.032189 | −0.001814 | 0.093872 | 24/25 |

The means average the prespecified training-draw/estimator-seed grid. C means use one LR fit or five tree fits, reused across draws. The difference ranges are observed extrema, not confidence intervals; the positive fractions are descriptive counts of dependent comparisons, not hypothesis tests. After averaging tree seeds within each training draw, the B−C AP difference is positive in all five draws for both tree models.

Thus graph-population expansion changes both training eligibility and conditional model scores in this design: the stricter C policy gives lower mean AP for all four methods at matched training counts and class counts. Raw-LR differences change sign across training draws, and the positive results for other methods remain conditional on this test and protocol.

## Review yield need not follow AP

| Method | B findings at 54 reviews | C findings at 54 | B findings at 216 | C findings at 216 |
| --- | ---: | ---: | ---: | ---: |
| Raw-token LR | 2.0000 | 2.0000 | 4.8000 | 4.0000 |
| Normalized-token LR | 2.8000 | 4.0000 | 7.6000 | 5.0000 |
| Pattern RF | 4.5467 | 1.8000 | 13.0480 | 11.8000 |
| Pattern LightGBM | 3.8000 | 2.0000 | 11.4000 | 8.8000 |

Boundary ties use expected findings under uniform ordering within the tied block. A strict random ranking has expected yield 1.0481 at 54 and 4.1922 at 216 reviews. These references are not significance thresholds. In particular, normalized LR has higher mean B AP but lower mean B yield at 54 reviews; the policy comparison should not be summarized as uniformly better ranking at every budget.

## Verification and provenance

`FREEZE_BEFORE_FITTING.json` binds the complete plan, source code, inputs, memberships, labels and runtime record; its SHA-256 is `16c21941565a6a508feedd1e06453adee45be46543faf7469b954bde38db3565`. All 2,256 used source files were verified against the historical source inventory, and all 948 pinned annotation files were checked. Runtime package versions match the earlier experiment. The downloaded LightGBM 4.6.0 wheel is separately hashed; identity with the unavailable historical wheel is not claimed.

Each logical attempt has a start record, result status, predictions, resource or reuse record, metrics and artifact hashes. Fitted model binaries are deliberately not saved, as declared before execution. `COMPLETE.json` has SHA-256 `a3da644827a6494e50c5a70d4e13608bf1bf40eeaff4b7c73887d9e9f76a42e5`.

A separate manual equal-score-group implementation recomputed all 120 AP and 360 review-budget values; maximum absolute discrepancy from the execution metrics was 1.78×10⁻¹⁵. A second agent independently replayed selection and checked 480 artifact hashes and 480 metrics using exact rational arithmetic. Its records are `../../reproducibility/EXPANDED_CONTRAST_DESIGN_AUDIT.json`, `../../reproducibility/EXPANDED_CONTRAST_POSTRUN_AUDIT.json` and `../../reproducibility/EXPANDED_CONTRAST_RUNTIME_AUDIT.json`. These are computational audits, not human vulnerability adjudication.

Reproduction commands from the repository root (use a new directory):

```sh
python papers/security_evaluation/revision2/model_link/expanded_contrast.py prepare --out NEW_RUN_DIRECTORY
python papers/security_evaluation/revision2/model_link/expanded_contrast.py run --out NEW_RUN_DIRECTORY
python papers/security_evaluation/revision2/model_link/verify_expanded_contrast.py --run NEW_RUN_DIRECTORY
```

The pinned DAppSCAN source/annotation checkout and dependencies must first be present. The old failed outside-giant campaign gate remains unchanged; this new experiment uses the original inside-giant test and does not authorize the old campaign. All work remains private pending the author's review.
