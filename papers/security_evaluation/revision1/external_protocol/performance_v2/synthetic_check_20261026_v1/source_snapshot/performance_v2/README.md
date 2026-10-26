# Paired fixed-frame performance engineering, version 2

This is a **synthetic-only engineering implementation**, not an external study,
protocol freeze, scoring authorization, coverage guarantee or sample-size verdict.
The prospective `../PROTOCOL_B.md` and its gates are unchanged. No real scores,
coordinator keys, human judgments or model/source files are read by the synthetic
runner. Version 1 and its completed source snapshots remain unchanged.

## Inputs and independently testable API

`evaluate_methods(frame, sample, allocation, first, second, adjudication, scores,
target_class, *, methods, expected_files=1998, expected_sample_cases=180,
classes=("reentrancy", "unchecked"), review_fractions=(.05,.1,.2),
replicates=2000, seed=20261026, alpha=.05)` accepts only in-memory DataFrames.

- The full frame contains one `path,class` row for every file by class: by
  default 3,996 cases from 1,998 files. Frame/sample strata remain
  `source_id,class,label_status`. The sample includes **all** 180 selected cases,
  their `case_id,N_h,n_h,inclusion_probability,design_weight`; no replacements.
- Initial/adjudicated forms use the unchanged `review_estimators.py` schema and
  validator: both distinct named reviewers must cover every case; provenance and
  initial judgments must remain present. This validates recorded provenance,
  not human identity, independence or correctness.
- Scores contain `method,path,class,status,score`, for **one class** and every
  declared method × every frame file, including failures. `ok` requires a finite
  score; failure requires a missing (`NaN`/`None`) score. Zero is a valid score.
  Missing rows, unexpected methods/classes/statuses, duplicates and a finite
  failure score are rejected. Accepted failure reasons are `compile_error`,
  `tool_error`, `timeout`, `missing_dependency`, `unsupported_pragma`,
  `missing_score`, `preprocessing_error`, `unavailable_binary`, `model_error`.
  Prospective execution adapters must explicitly map their statuses to this
  inventory before freeze; this list is not evidence of execution coverage.
- Original stratum population/sample counts and weights are validated against
  the full frame. Noncensus n=1 is rejected; census strata remain fixed.

`plan_score_domains` accepts frame and scores only. It constructs every domain,
queue and tie probability **before** review validation or joining outcomes.
`recall_interval`, `yield_interval` and `paired_difference` are standalone
numerical entry points. The latter requires matching tags for the actual shared
replicate-matrix/case-ID hash, target path-set hash, metric and planned budget.

## Two declared populations and queue policies

**Full-frame pipeline:** planned budget is `floor(f*N_full)`, using exact decimal
fraction arithmetic: for N=1,998, 99/199/399 reviews. Rank successful files only;
failed files receive no artificial score and no automated review. Fill at most
the number of successful files; report both filled and unused slots. Failure
triage, manual fallback and extra compilation attempts are outside this policy
and would need a separate prospective budget. A full-population ranking AP is
suppressed if any file lacks a score. Pipeline yield/recall remain defined under
this explicit operational policy; **all full-frame reference positives,
including failed-score positives, enter the recall denominator**.

**Common success:** D is the intersection of `status == ok` across **all declared
methods**, using statuses only. The population and budget become N_D and
`floor(f*N_D)`. Each method ranks that same domain. This estimates conditional
performance on D; it cannot be extrapolated to failures or the full frame. The
method inventory changes D and must be fixed prospectively. Empty or unsampled
domains yield undefined AP/recall, not zeros. Coverage reports include exact
status counts and successful/failed file counts separately for each class/method.

Compare methods only **within** the same target and planned budget. In the full
pipeline, differences may reflect different filled workloads and failure
coverage as well as ranking. Comparing full-frame and common-domain estimates
is not a controlled method comparison. Cross-class, cross-seed and simultaneous
multi-method inference are not implemented here.

For each queue q_i is 1 above cutoff, 0 below and the remaining slots divided by
the boundary tie size at cutoff. Targets average over uniform boundary-tie
ordering. The inference below excludes realized tie-order randomness. Queue
construction always uses the full relevant population, never the human sample.

## Estimands, estimators and common resampling

For fixed reference outcomes Y_i, domain indicator d_i, and queue probabilities
0 ≤ q_i ≤ d_i, define population recovered yield T_q = sum(q_i Y_i), positive
total T_d = sum(d_i Y_i), and recall R = T_q/T_d if T_d>0. Survey estimates are

`T_q_hat = sum_sample(w_i*q_i*Y_i)` and
`R_hat = sum_sample(w_i*q_i*Y_i) / sum_sample(w_i*d_i*Y_i)`.

The count is an HT estimate for the fixed queue under the sampling design. It is
reported **unclipped**, even if sampling variability takes it outside [0,k].
The ratio is generally biased in finite samples. It is a ratio of HT totals,
not an expectation of per-case ratios or an unbiased recall estimator.
Weighted AP is the unchanged sklearn nonlinear weighted empirical plug-in from
v1, restricted to the declared domain; it is not exactly unbiased either.
Census inputs reduce to exact ordinary AP and exact population yield/recall.

ONE Rao–Wu finite-population-corrected replicate matrix is drawn from the
original class sample, retaining every original stratum and every sampled case.
For stratum h with n_h<N_h, m_h=n_h−1 and f_h=n_h/N_h:

`M_h ~ Multinomial(n_h−1, (1/n_h,...,1/n_h))`

`w_hi* = w_hi * [1−sqrt(1−f_h) + sqrt(1−f_h)*n_h/(n_h−1)*M_hi]`.

Census weights stay fixed at 1. The implementation is reused byte-for-byte from
v1; its references and exact linear variance enumeration remain the basis for
the resampling formula. The ECB/HFCN 2023 methodological report, §7.2 pp52–53,
gives this single-stage stratified SRSWOR specialization. It does **not** establish
AP/ratio percentile interval coverage. See `REFERENCES.json` and v1 references.

For common-domain totals and ratios, sampled cases outside D remain in the
replicate matrix with **zero domain contribution**. They are not deleted,
relabelled negative, used to alter n_h/N_h or independently resampled inside D.
Domain AP uses original sampled domain weights and the corresponding columns
of this same matrix; weights are not recalibrated to a new domain sample design.

All method/domain metrics use the same replicate indices. A paired interval is
the percentile interval of `metric_A* − metric_B*`, not a subtraction of
marginal interval endpoints and not independent resampling. For paired yield,
the standard SRSWOR design variance of `q_A*Y − q_B*Y` is additionally reported.
There is no multiplicity adjustment and no automatically generated significance,
superiority, ranking-winner or inferential p-value conclusion.

## Unknowns, undefined ratios and uncertainty limits

An unknown sampled reference **in the target domain** suppresses AP, recall,
yield and paired point/percentile summaries for that domain. Workload's existing
v1 HT lower/upper endpoint estimates, their design variances and hard logical
finite-population bounds remain separately available. Endpoint estimates are
not hard population bounds. Unknowns outside D do not affect conditional-domain
metrics; their counts are still disclosed. No unknown is called a known negative.

Zero estimated positive denominator gives undefined recall, including k=0 with
no positives; k=0 recall is 0 only when a positive denominator exists. Every
zero-denominator or otherwise invalid replicate is retained as an explicit
`null`. **Any invalid replicate blocks the whole corresponding interval**;
none is silently discarded. Undefined components suppress paired contrasts.
Recall's [0,1] safe support applies conditional on at least one domain positive.

Intervals are **design-approximate, conditional on the fixed finite population,
fixed scores, selected methods and recorded reference process**. They are not
new-project/family confidence intervals. FPC rescaling retains an observed
positive even when its multinomial multiplicity is zero. Therefore no invalid
replicates, zero replicate spread, many bootstrap repetitions, or exact linear
variance identity establishes rare-positive AP/recall coverage. Census removes
sampling error, not reference errors or model-training variation. Formal
synthetic AP-coverage diagnostics live in the separately owned
`performance_validation_v1`; they do not authorize real external execution.

## Reproducibility and tests

From the repository root:

```
.venv/bin/python -m pytest papers/security_evaluation/revision1/external_protocol/performance_v2/test_performance.py -q
.venv/bin/python papers/security_evaluation/revision1/external_protocol/performance_v2/run_synthetic.py --out papers/security_evaluation/revision1/external_protocol/performance_v2/synthetic_check_20261026_v1
```

The runner has **no real-input arguments**. It refuses an existing output path,
saves a dated configuration and dependency-preserving source snapshots before
creating fictional data or estimating metrics, and records package/source/output
hashes in a receipt. Its artificial 1,998-file, 3,996-case, 180-selected-case data
use `synthetic://` identities and explicitly fictional reviewer provenance.
Scenarios cover complete scores, mixed failures, and unknown references inside
and outside common success. Protected v1/protocol hashes are checked afterward.
This is an engineering freeze of a synthetic check, not the prospective study
freeze required before authentic reviews and external scoring.

Production tests cover census truth; failed-positive denominator; shared
replicate cancellation and paired contrasts; retained outside-domain cases;
full-queue unsampled leaders; explicit invalid denominators; tied queues against
exhaustive subset enumeration; unknown suppression/bounds; permutation
invariance; empty domains and k=0; and adversarial score/design/reviewer inputs.
