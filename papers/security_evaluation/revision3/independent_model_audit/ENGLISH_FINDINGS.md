# Independently verified R5 results and captions

## Audit scope

The independent implementation recomputed all 10,224 AP values and 30,672 review-budget results from 852 saved prediction vectors, containing 4,607,616 scores across 12 evaluation frames. It did not import the producer's metric functions or retrain models. All 223,944 numeric cells compared with the producer agree within the declared tolerances. The largest per-fit AP discrepancy is 5.55e-17; per-fit expected review findings, attainable tie minima/maxima, and ECDF counts agree exactly. The 355 retained warnings all concern LightGBM feature names; no fit records a convergence warning. This validates saved-score calculations and aggregation, rather than independently validating model training or the proxy labels.

## Primary fixed test: 5,408 files, 83 proxy positives

Each B composition and C contains 708 training files and 24 positives. The table averages tree metrics over five seeds within each composition before constructing the 50-composition distribution. These percentiles describe the observed training-composition distribution; they are not p-values.

| Model | B mean AP | C mean AP | B compositions below / equal / above C | C ECDF midrank |
|---|---:|---:|---:|---:|
| Raw-token LR | 0.014278 | 0.012256 | 8 / 0 / 42 | 16% |
| Normalized-token LR | 0.027472 | 0.022531 | 5 / 0 / 45 | 10% |
| Pattern RF | 0.057351 | 0.041768 | 0 / 0 / 50 | 0% |
| Pattern LightGBM | 0.049931 | 0.040843 | 7 / 0 / 43 | 14% |

The exact expected AP of a uniform random distinct-score ordering is 0.016835982943502, compared with prevalence 0.015347633136095. Both raw-token LR mean APs are below this random-ranking expectation. This statement concerns the means; some individual B compositions exceed it. All other models' B and C mean APs exceed the reference.

The strongest composition separation occurs for RF, whose C seed mean lies below all 50 B composition means. Its seed-matched C percentiles range from 0% to 2%. LightGBM is more sensitive to algorithmic seed: seed-matched C percentiles span 2% to 34%, compared with 14% after averaging seeds. On the earlier 1,082-file precursor test, raw LR has 28 positive and 22 negative B-minus-C AP differences and C lies at the 44th percentile. Results vary substantially across the ten overlapping 1,062-file slices: C AP percentiles span 2–82% for raw LR, 0–92% for normalized LR, 0–86% for RF, and 0–66% for LightGBM. These slices characterize sensitivity within this component; they do not replicate independent families.

## All model and review-budget combinations

Expected findings average uniformly across a score tie at the budget boundary. Random review has expected findings bK/N. Table entries below average tree seeds first and then the 50 B compositions; C uses its fixed membership and the same seed set.

| Model | Review files | Random | B | C | B minus C |
|---|---:|---:|---:|---:|---:|
| Raw-token LR | 270 | 4.144 | 4.060 | 4.000 | 0.060 |
| Raw-token LR | 540 | 8.288 | 7.260 | 4.000 | 3.260 |
| Raw-token LR | 1,081 | 16.591 | 13.200 | 9.000 | 4.200 |
| Normalized-token LR | 270 | 4.144 | 8.320 | 10.000 | -1.680 |
| Normalized-token LR | 540 | 8.288 | 16.900 | 15.000 | 1.900 |
| Normalized-token LR | 1,081 | 16.591 | 30.940 | 25.000 | 5.940 |
| Pattern RF | 270 | 4.144 | 16.101 | 10.450 | 5.651 |
| Pattern RF | 540 | 8.288 | 29.782 | 20.333 | 9.449 |
| Pattern RF | 1,081 | 16.591 | 53.914 | 42.450 | 11.463 |
| Pattern LightGBM | 270 | 4.144 | 13.302 | 9.200 | 4.102 |
| Pattern LightGBM | 540 | 8.288 | 25.152 | 15.200 | 9.952 |
| Pattern LightGBM | 1,081 | 16.591 | 45.420 | 35.200 | 10.220 |

The review-budget results qualify the AP result. Normalized LR has higher mean AP under B but fewer expected findings at the 5% budget. Raw LR changes little at 5%, and both its B and C mean yields remain below random review at all three budgets. Both tree models have higher mean yields under B at every budget; these are composition means, not uniformly positive differences for every draw.

## Linked-pool retention

The nominal retention levels 0%, 25%, 50%, 75%, and 100% retain 0, 118, 236, 353, and 471 files from the B-minus-C pool. The 100% endpoint therefore contains linked files in 471/708 = 66.53% of training; it is not a 100%-linked training set. Training size and positive count remain fixed at 708 and 24. Each nonzero level has five compositions, with five seeds per tree composition. Zero dose reuses one C membership and its existing fits.

| Nominal linked-pool retention | Raw LR AP | Normalized LR AP | Pattern RF AP | Pattern LightGBM AP |
|---|---:|---:|---:|---:|
| 0% (reused C) | 0.012256 | 0.022531 | 0.041768 | 0.040843 |
| 25% | 0.012753 | 0.025075 | 0.046604 | 0.038195 |
| 50% | 0.016599 | 0.027405 | 0.055039 | 0.045370 |
| 75% | 0.015170 | 0.031184 | 0.058934 | 0.052820 |
| 100% | 0.016113 | 0.032228 | 0.070310 | 0.062354 |

Mean AP increases across all successive levels for normalized LR and RF. LightGBM decreases at 25% before increasing at subsequent levels; all five 25% compositions are below C. Raw LR is nonmonotonic. The mean AP of all five raw-LR retention levels remains below the random-ranking reference, although individual compositions can exceed it. Review findings also depend on model and budget; in particular normalized LR's 5% mean yield is below C at every nonzero dose, while its 20% mean yield increases across levels. Ranges show the five observed compositions and are not confidence intervals.

## Figure captions

**Main composition ECDF (`fig_R5_composition_ecdf`).** AP distributions on the fixed 5,408-file, 83-positive proxy-labelled test. The blue curve is the empirical distribution of 50 matched B training compositions, each containing 708 files and 24 positives. Tree AP is averaged over five seeds within each composition; LR uses the single frozen seed. The orange line is the corresponding C AP, with its ECDF midrank, and the grey dotted line is the exact expected AP of uniform random ranking with distinct scores. ECDF percentiles are descriptive, not significance probabilities or independent-family estimates.

**Supplementary AP retention (`fig_R5_linked_retention_ap`).** AP as linked training files from the 471-file B-minus-C pool are retained at five levels, with training size and positive count fixed at 708 and 24. Thin blue lines show the five compositions, the bold line their mean, and shading their observed range after averaging tree seeds within each composition. The horizontal orange line marks the reused C zero-dose fit, which is one training membership, not five replications. Grey dots mark expected random-ranking AP. The 100% endpoint retains all 471 linked files, or 66.53% of training. Curves are descriptive; shading is not a confidence interval.

**Supplementary review retention (`fig_R5_linked_retention_all_review_budgets`).** Expected positive findings at budgets of 270, 540, and 1,081 reviews for all four models on the same fixed test. Boundary ties receive their uniform-order expectation. Thin blue lines, bold blue means, and blue ranges summarize the five retention compositions after tree-seed averaging; orange dashes mark reused C and grey dots mark random review, bK/N. Training remains 708 files with 24 positives. Zero dose has one unique membership; the 100% endpoint retains all 471 linked-pool files. Ranges are descriptive rather than confidence intervals.

## Reproducibility records

`run_20261029_v1/NUMERIC_RECOMPUTATION_COMPLETE.json` seals the independent score reconstruction. `PRODUCER_COMPARISON.json` records all comparison discrepancies. `figures/VISUAL_QA.json` records inspection of all three complete PNGs. `AUDIT_COMPLETE.json` combines the final receipts. Original predictions and the frozen experiment remain unchanged.
