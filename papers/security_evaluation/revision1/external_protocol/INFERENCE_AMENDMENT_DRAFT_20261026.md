# Proposed inference amendment for external protocol B

**DRAFT — 26 October 2026. Not approved, activated or a prospective study freeze.**
This document makes a proposed scientific choice reviewable. It does not edit
`PROTOCOL_B.md`, `protocol_B_draft.json`, their manifests or execution gates.
`human_semantic_signoff=false`; no expert response or external model result is
created by this amendment. Adoption requires the conditions below and a new,
explicitly dated protocol version before the first human case judgment or
external model fit/score.

## Proposed decision and reason

Use **coverage and fixed-budget recovery of expert-reference positives** as the
primary operational performance outcomes. For AP, report **sharp finite-population
completion bounds**, conditional on known reference labels and a complete score
queue. Retain survey-weighted sample AP and its percentile bootstrap output only
as exploratory diagnostics. Do not describe those percentiles as validated
primary 95% uncertainty, or use them to declare a winning detector.

This change follows the independently verified, prespecified synthetic diagnostic
in [performance_validation_v1](performance_validation_v1/REPORT.md): nominal 95%
AP percentile intervals had conditional coverage of 53.04% and 22.22% in two
specified examples. The diagnostic does not estimate the actual external
design's coverage. The replacement [completion-bound algorithm](ap_bounds_v1/README.md)
answers a different, logical question; it is not a recalibrated confidence
interval or a substitute for reviewing labels.

## Population, methods and queues retained in the proposal

- Keep the existing 1,998-file external population, two classes and 3,996
  file–class frame; the selected 180 probability cases from 170 files in 17
  strata; and the 691-file training population. Do not replace the sample or
  change the dependency rule because a metric or bound is inconvenient.
- Retain raw and normalized TF-IDF LR, each fitted once; RF and LightGBM seeds
  0–4; and Slither. This gives **13 primary score vectors per class**. Every
  declared vector is reported, including errors; tree seeds are not independent
  external populations. Report their values individually and any seed summary
  descriptively, without choosing a favorable seed.
  Each seed-specific vector must have a unique immutable `job_id`; a method name
  shared across seeds is not a unique performance-engine identifier.
- Preserve the draft Slither primary and broad-secondary mappings pending
  semantic agreement. The broad sensitivity is derived from the same complete
  scan output, not selected using performance. Its exact semantics and failure
  adapter must be resolved before freeze; this proposal does not silently change
  the union or remove the informational detector.
- The primary target is the **full-frame pipeline**. Planned review budgets are
  `floor(f*1998)=99,199,399` for `f=0.05,0.10,0.20`. Rank successful files only,
  fill up to the available successful count, and report unfilled slots. Failed
  files get no artificial score or automated review. Manual failure triage is
  outside these budgets unless separately specified prospectively.
- Build score domains and queues from identifiers, scores and statuses before
  joining expert outcomes. At a boundary tie, use the label-independent expected
  inclusion fraction `q_i`; the outcome is expected yield over uniform tie
  ordering, not uncertainty from a realized random ordering.

For a secondary conditional analysis, define one common-success set per class:
the intersection of successful files across all 13 primary score vectors. Keep
that set unchanged across comparisons and use `floor(f*N_common)` budgets.
Do not recalculate survey strata or weights inside this domain. This secondary
target excludes failures and is not an estimate of full-frame performance.
An empty common domain is explicitly undefined for ranking analysis.
The broad Slither sensitivity stays outside this 13-vector domain definition.

## Exact intended primary outputs

| Output | Population and reported quantity | Uncertainty or identification statement |
|---|---|---|
| Coverage and execution | Full frame, each class/vector: exact success count, every failure status, planned/filled/unfilled queue slots | Descriptive finite-frame counts; no sampling interval needed |
| Reference composition and annotation audit | Expert-reference findings and unknowns by the existing source/class/status domains; initial 3×3 reviewer agreement and adjudication retained | Existing design-weighted estimates and exact hypergeometric/unknown envelopes only for supported whole-stratum binary domains; agreement is not correctness |
| Reference-positive total and review yield | Full-frame positive total and expected positives recovered in each declared queue | HT point estimates and their stratified without-replacement design variance/SE, under the stated conditions below; no default primary 95% Wald or bootstrap claim |
| AP identification | For each vector with finite scores for all 1,998 files, AP over every label completion consistent with assessed cases | Exact rational lower/upper endpoints, attaining completions, unknown count, and all-negative/undefined possibility; no confidence level |

For a fixed full-frame queue, let `Y_i` be the adjudicated binary reference
outcome and `q_i` its queue inclusion fraction, with `q_i=0` for failed files.
For stratum `h`, `w_i=N_h/n_h`. Report

`T_hat = sum_sample(w_i*Y_i)` and `yield_hat = sum_sample(w_i*q_i*Y_i)`.

For either total, with `z_i=Y_i` or `q_i*Y_i`, the existing design-variance
estimate is

`V_hat = sum_h N_h²*(1−n_h/N_h)*s_h²(z)/n_h`.

This is appropriate design uncertainty for a fixed finite population, fixed
queue and fully observed binary responses in the sampled target domain.
Unbiasedness of the HT total and its variance estimator does not make a normal
interval exact. A zero sample variance can occur despite unsampled positives;
it must not be labelled certainty. Census strata have no sampling variance,
but reference and execution errors remain possible. Noncensus strata require
the existing `n_h≥2` check. HT totals remain unclipped even when sampling
variation places an estimate outside the physical queue limits.

If a sampled expert outcome is unknown in the target domain, preserve the
existing fail-closed suppression of its primary point/SE summary. Report
unknowns, the implemented lower/upper HT endpoint estimates with their own
design variances, and separately the **hard logical population bounds** from
known labels and all remaining unknowns. Estimated endpoints are not themselves
hard population bounds. Do not drop unknown cases, relabel them negative, or
interpret them as random nonresponse.

The annotation-audit hypergeometric envelopes apply to their declared binary
whole-stratum domains, with the existing simultaneous-stratum allocation of
`alpha=0.05`. They are not transferred to fractional queue weights, AP, recall
ratios or arbitrary common-success subdomains. No new exact workload confidence
interval is asserted by this amendment.

For AP completion bounds, known adjudicated labels constrain their original
files; all unassessed, unresolved and unsampled files remain unknown. If all
feasible positive completions share one AP and an all-negative completion is
impossible, report that identified point as well as the coincident endpoints.
Otherwise give bounds without manufacturing a point estimate. If an all-negative
completion is possible, retain an explicit `undefined_possible` flag alongside
the bounds over positive completions. A complete all-negative reference has
undefined AP, not zero. **Any missing score suppresses full-frame AP bounds**;
do not assign a failure a fictitious rank or quietly reduce the denominator.

## Secondary and exploratory outputs

1. On the common-success domain, report coverage, the same logical AP bounds,
   and HT queue yields/design variances under the original sampling design.
   Cases outside the domain retain zero domain contribution in totals and the
   original replicate matrix; they are not deleted from the sample design.
2. Report survey-weighted assessed-sample AP, recall ratios of HT totals and
   their percentile bootstrap ranges as **exploratory, design-approximate**
   summaries only. Use the existing shared 2,000-replicate matrix, seed
   `20261026`, and `alpha=0.05`; retain every invalid replicate and suppress the
   corresponding range if any is invalid. Preserve unknown and zero-denominator
   guards. No ordinary unweighted bootstrap or recalibration on the common
   subset is introduced. AP/recall coverage is not established by valid weights.
3. Fix paired contrasts against raw-token LR for normalized LR, each RF seed,
   each LightGBM seed and Slither, within the same class/domain/budget. For yield,
   report the difference of HT totals and the design variance of
   `(q_A−q_B)*Y` using the paired observations. Paired AP/recall percentile ranges
   remain exploratory and use shared replicate indices, not independently drawn
   resamples. Repeated LR values do not become extra independent observations.
4. If shown, `[L_A−U_B,U_A−L_B]` from individual AP completion bounds is a
   **conservative, generally nonsharp difference envelope**. Separate endpoints
   may use incompatible label completions. It is not a 95% confidence interval
   and supplies no confidence-based superiority claim. Form it only for the
   same declared domain and completions on which both APs are defined; propagate
   `undefined_possible` rather than silently conditioning it away. If either
   AP has no feasible positive completion, give no numeric contrast. No significance test,
   multiplicity-adjusted ranking or best-method selection is planned.
5. Retain broad Slither mapping sensitivity and source-reported annotation
   agreement as separately labelled secondary analyses. Preserve source absence,
   explicit no-finding and unresolved statuses; source agreement does not become
   expert-verified detection quality. Initial agreement tables and supplementary
   kappa remain descriptive, with undefined kappa retained where appropriate.

Report both the full-frame operational result and conditional common-success
result, even when they differ. Changes in coverage, filled workloads, domain
membership, label completion or training seed must not be presented as isolated
effects of detector accuracy. None of these outputs supports inference to unseen
deployment families or accounts automatically for reviewer mistakes.

## Conditions before adoption and execution

One reporting integration remains necessary: frozen `performance_v2` emits all
unordered method pairs and default percentile/normal fields. A new prospectively
versioned reporting adapter must select the 12 declared raw-LR-reference contrasts,
separate primary point/SE outputs from exploratory ranges, propagate undefined
states, and use unique job IDs for seed-specific vectors. Preserve the complete
engine output as an audit artifact; do not change frozen v2 or select contrasts
after seeing their results. The reporting choice in this document is therefore
concrete but not yet implemented or activated by its existence.

The following are prospective conditions, not assertions of completed sign-off:

1. The author and two named independent specialists agree the class definitions,
   EVM/gas/context assumptions, treatment of event-only or repeated-call effects,
   adequate unchecked-failure handling, imported-code attribution and unknown
   rules. Resolve the [coordinator semantic review](semantic_review_v1/SEMANTIC_REVIEW.md)
   without injecting detector-specific answers into blind review forms.
2. Confirm this precise primary/secondary outcome hierarchy, all 13 vectors,
   contrast list, score conventions, queue policy and common-domain rule. Freeze
   the actual status adapter, source/tool/configuration hashes and AP-bound API
   version. Coverage runs and version probes must retain their true scope.
3. Independently verify the final integration joins each adjudicated case to the
   correct full-frame file/class, carries all unsampled labels as unknown,
   respects shared sampling weights and does not assign scores to failures.
   Synthetic API checks alone do not authenticate reviewers or release authority.
4. Create a new dated protocol/configuration and record this amendment, its
   reason and what had already been inspected. The completed historical pilot
   remains inspected, and the new synthetic diagnostic remains post-pilot work;
   neither is retroactively preregistered. Preserve original protocols and runs.
5. Obtain and seal both initial expert review sets before adjudication and source
   disclosure, following the existing review order; retain unresolved responses
   and separate identity cases. Apply the existing execution/release gates before
   fitting or scoring external models. Preparing this document changes none.

**Status of this document: proposed scientific analysis choice only. Author
approval, human semantic sign-off, full B freeze and external performance are
not claimed.**
