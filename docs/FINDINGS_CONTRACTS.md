# C — What smart-contract vulnerability benchmarks measure

Current runs (after the audit fixes of 2026-10-22, see [AUDIT_RESPONSE.md](AUDIT_RESPONSE.md)):

* `results/contracts/c1_20261022_141306`: corpus audit with the order-invariant
  near-duplicate grouping (replaces the first run of 2026-10-21: DAppSCAN
  4,993 components instead of 5,001, SolidiFI 214 instead of 222);
* `results/contracts/c2_20261024_004314`: ML benchmark, 3 seeds, 5 folds, with
  fixed near-duplicate groups, saved folds and per-file scores. The pattern
  rows were re-fitted after the pragma fix of 2026-10-23 (the compiler-version
  features read commented-out pragmas; 10 of 6,587 DAppSCAN files change, no
  SmartBugs or SolidiFI file). The lex rows do not depend on the patterns and
  are copied from `c2_20261022_092004` and, for `local_random` / `local_safe`
  (groups re-derived inside the local population), `c2_20261022_113242`,
  after a check that groups and fold assignments are identical;
* `results/contracts/c3_20261022_163601`: Slither 0.11.6, compiler chosen inside
  the pragma range, full diagnostic log of every file not analysed (`logs/`);
* `results/contracts/c4_20261024_011448`: Slither and learned models compared
  on equal terms, top-k independent of file order.

The two older C2 runs predate the data digests in manifests; `manifest_data_posthoc.json`
in each run gives corpus digests computed afterwards at the pinned data
commits.

Metric: AUPRC, always next to the base rate (the AUPRC of a random ranking).
Representations: `lex_raw` (TF-IDF of raw tokens), `lex_norm` (identifiers → ID,
numbers → NUM), `pat` (43 hand-written pattern features, see PROTOCOLS). Within-corpus models:
logistic regression on TF-IDF, RF and LightGBM on patterns. Cross-corpus runs
also include MLP and KAN.

## 1. Within SolidiFI every protocol gives AUPRC ≈ 1.0

The best mean AUPRC is 1.000 for every class under every protocol (most other
models are near-perfect too: 0.979–1.0 over all 288 runs): `random`,
`project` (all injections of one base contract together), `safe` (plus
near-duplicate components) and `local_*` (project-local code only). That
includes identifier normalisation, which removes the `re_ent`, `tmstmp`, …
stems found in 100 % of SolidiFI positives (C1). The injected bug
snippets are fixed templates, so the result is consistent with template
recognition; the causal role of the remaining template cues was not isolated
(no held-out-template or buggy/patched control). SolidiFI
was built to test static analysers, and it cannot rank learned detectors.

## 2. DAppSCAN: overlap, library code and training size

Best AUPRC per protocol (mean of 3 seeds; model in brackets). Base rates: arithmetic 2.1 %,
reentrancy 1.7 %, unchecked 1.1 %, timestamp 0.5 % (2.6 / 2.1 / 1.4 / 0.7 % in the local population).

| Class | random | random_matched | project | safe | local_random | local_safe |
|---|---|---|---|---|---|---|
| reentrancy | 0.150 (pat/LGBM) | 0.145 | 0.131 | 0.058 | 0.124 | **0.091** |
| unchecked | 0.145 (pat/RF) | 0.135 | 0.071 | 0.048 | 0.135 | **0.059** |
| arithmetic | 0.119 (pat/RF) | 0.110 | 0.104 | 0.085 | 0.099 | **0.099** |
| timestamp (33–36 positives) | 0.049 | 0.038 | 0.042 | 0.050 | 0.067 | 0.093 |

How to read the protocols:

* `safe` does not isolate leakage on DAppSCAN. Near-duplicate components
  alone have at most 51 files (4,993 components) and projects at most 34
  (608 groups), but their transitive union gives 227 `safe` groups, the
  largest with 5,408 of 6,587 files (82 %). That is a joint grouping
  constraint, not evidence that 82 % of the files are near-duplicates. In the
  `safe` folds one fold therefore has 1,179
  training files and 5,408 test files. The drop from `random` to `safe` mixes
  overlap removal with a much smaller training set for most predictions.
* `random_matched` gives one random fold the same small training set; it
  barely moves AUPRC. It is only a partial control, because in `safe` most
  out-of-fold predictions come from the small-training fold.
* `local_random` vs `local_safe` compares random and project-disjoint folds
  at comparable sample sizes. It uses the same 4,648 files whose
  near-duplicate component stays inside one project, five folds with
  3,718–3,719 training files each, and project-disjoint test folds in
  `local_safe`. Splitting by project lowers AUPRC 1.4× for reentrancy and
  2.3× for unchecked calls, and leaves arithmetic unchanged. This is the
  effect of project-disjoint splitting, not a pure measure of leakage
  through duplicates: in-project near-duplicates, shared project style and
  project-level label density all move together with the split. Timestamp
  has too few positives to conclude anything.
* Declared projects alone (`project`) already remove most of the inflation for
  unchecked calls, but not for reentrancy.

DAppSCAN negatives mean "no published finding of this class", not "verified
safe". Missing labels can move AUPRC up or down, so these numbers are neither
lower nor upper bounds.

## 3. Transfer between labelling regimes

| Train → test | Class | Base rate | Best AUPRC (representation) | Lift |
|---|---|---|---|---|
| SolidiFI → SmartBugs | reentrancy | 0.217 | 0.784 (lex_raw) | 3.6× |
| SolidiFI → SmartBugs | timestamp | 0.035 | 0.586 (lex_norm) | 16.8× |
| SolidiFI → SmartBugs | unchecked | 0.364 | 0.707 (pat/LightGBM) | 1.9× |
| SolidiFI → SmartBugs | arithmetic | 0.105 | 0.542 (pat/KAN) | 5.2× |
| DAppSCAN → SmartBugs | unchecked | 0.364 | 0.733 (pat/RF) | 2.0× |
| DAppSCAN → SmartBugs | reentrancy | 0.217 | 0.617 (lex_raw) | 2.8× |
| SolidiFI → DAppSCAN | all four | 0.04–0.15 | 0.09–0.22 | 1.3–2.4× |
| DAppSCAN → SolidiFI | timestamp | 0.143 | 0.988 (pat/KAN) | 6.9× |

"Best" is chosen on the target itself, so this table is exploratory: it shows
what the representations can reach, not the score of a model frozen on source
validation before the external test.

The DAppSCAN target in cross-corpus runs is its 948 files with any SWC
annotation, a different population from the 6,587 within-corpus files.
Models trained on injected or audited labels rank the small hand-labelled
SmartBugs set well above chance, but real audit labels barely: 1.3–2.4× for
every class.

## 4. Slither on the same files (C3)

The compiler is now chosen inside the full pragma range, newest allowed minor
first (330 files use 0.5.17). Only 4 of 493 files are not analysed, all from
SmartBugs; their logs show three Slither 0.11.6 crashes (two assertions on a
tuple assignment while building SlithIR, `reentrancy_bonus.sol` and
`reentrancy_cross_function.sol`; one `NotConstant` in constant folding) and
one solc 0.4.11 internal error ("Unbalanced stack") on
`parity_wallet_bug_1.sol`, whose pragma admits no release with a static
binary. The three crashes have status `tool_error`, the solc failure
`compile_error`. With `--json -` Slither prints nothing when it crashes, so the
script reruns a failed file once without it to keep the traceback. The first
version lost 46 files, including 42 SolidiFI files compiled with 0.4.26
despite 0.5 syntax.

| Corpus | Class | Precision | Recall | F1 (end-to-end) | Before the fix |
|---|---|---|---|---|---|
| SmartBugs | reentrancy | 0.76 | 0.94 | 0.84 | 0.84 |
| SmartBugs | unchecked call | 0.89 | 0.98 | 0.94 | 0.94 |
| SmartBugs | timestamp | 0.22 | 1.00 | 0.36 | 0.36 |
| SolidiFI | reentrancy | 0.51 | 1.00 | 0.68 | 0.59 |
| SolidiFI | unchecked call | 1.00 | 0.50 | 0.67 | 0.58 |
| SolidiFI | tx.origin | 0.89 | 1.00 | 0.94 | 0.85 |
| both | arithmetic | no detector | — | — | — |

On SmartBugs both reentrancy misses are among the 4 unanalysed files. On the
139 analysed SmartBugs files Slither's recall is 1.00 for reentrancy and for
unchecked calls. SolidiFI "unchecked" mixes two injected bug types, and
Slither finds one of them.

## 5. Static analysis vs learned models, measured the same way (C4)

On SmartBugs, Slither's binary flags and the cross-corpus model scores are
compared on AUPRC and at Slither's own alarm count k (top-k files by model
score). When files tie with the k-th score, the tied files are taken at
random: the table gives the expected precision and recall, and the number of
true positives over all tie orders where it is not fixed.

| Class | k | Slither AUPRC | Slither P / R at k | Best model AUPRC | That model's P / R at k |
|---|---|---|---|---|---|
| reentrancy | 38 | 0.728 | 0.76 / 0.94 | 0.784 (lex_raw, SolidiFI) | 0.70 / 0.85 (26–27 of 31 found) |
| unchecked | 57 | 0.885 | 0.90 / 0.98 | 0.733 (pat/RF, DAppSCAN) | 0.64 / 0.71 |
| timestamp | 23 | 0.217 | 0.22 / 1.00 | 0.586 (lex_norm, SolidiFI) | 0.22 / 1.00 |

For reentrancy the best model ranks better overall (higher AUPRC), yet at
the alarm budget Slither actually uses, Slither is more precise and finds more.
For unchecked calls Slither is better on both. For timestamp both flag every
positive at k = 23 with the same precision. Among the evaluated methods, only the
learned models address integer arithmetic (other static and symbolic
analysers were not compared).

## What these runs do NOT show

* No graph or transformer model was trained. By design, the question is what
  the benchmark measures, not which architecture wins it.
* Slither numbers are file-level (any finding of the mapped detectors), not
  line-level.
* The local population excludes the 29 % of DAppSCAN files that share code
  across projects. That shared code is a real part of audited systems and
  needs its own evaluation (e.g. per library version).
