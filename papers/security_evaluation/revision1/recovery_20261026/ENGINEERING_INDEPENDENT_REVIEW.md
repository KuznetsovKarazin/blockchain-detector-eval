# Independent review of prospective external-B engineering

Date: 2026-10-26. Scope: source-code/design review and fictional, in-memory tests. This review does not authorize a protocol freeze, human annotation, compilation of project contracts, model fitting on project data, or external scoring.

The implemented preprocessing and complete-score performance primitives pass the independent checks described below. Two training-cohort/provenance hazards found during review were corrected before this conclusion. The tested primitives are useful engineering progress; a complete external comparison remains prospective.

## Fixed design and review boundary

The protocol's finite frame contains 1,998 external files and 3,996 file-by-class cases. Its 180 selected cases cover 170 files in 17 strata defined jointly by source, class, and source-label status. These are probability-sampled cases; the separate identity census and earlier purposive packet cannot be pooled into its estimators. The retained training cohort is 691 files, with source-reported findings rather than independently established negative labels.

The performance API verifies a complete file-by-class frame, allocation counts, selected-case identities, stratum weights, both initial reviewers, and preserved initial judgments in the adjudication form. Each class is analyzed with its own strata and full file queue. Requiring both classes' complete review forms before an evaluation prevents silent deletion of selected cases. The pure DataFrame interface cannot authenticate that a caller supplied the frozen packet or an authorized, previously sealed score file; a future integration layer must enforce those provenance and execution gates.

This is design-based sampling of a fixed population. Dependence among contracts does not turn its sampling intervals into evidence about new projects or families. Conditioning on the supplied expert reference also does not establish perfect ground-truth accuracy. No human judgments or actual external scores were produced or examined in this review.

## Findings corrected before review completion

1. **Pattern training could silently change its cohort.** The initial stateless `Pattern43.transform` returned coverage failures plus a shortened matrix for invalid training sources. This is useful for external coverage, but unsafe as the sole training entry point. The owner added `Pattern43.fit_transform_training`, which requires an all-training batch and rejects any failed member before a future classifier can fit it. The independent test supplies one valid source and one undecodable source and requires failure.
2. **A fitted training identity could be rebound to different bytes.** The initial TF-IDF transform accepted a training-role ID with changed source contents. The owner now requires every training-role transform to match the fitted ID and source hash; unknown training IDs also fail. The independent regression test exercises the changed-byte case.

These changes concern API guards. The owner's `adapters_v1/api_amendment_after_coverage.json` preserves the original coverage plan and source snapshot, records the amended implementation, and compares the AST hashes of the pure representation functions. Therefore the completed all-source preprocessing evidence was not retroactively relabeled as execution of the amended API.

## Independent numerical and adversarial checks

`test_engineering_independent.py` contains 21 passing tests, including six parameterized adversarial-input cases. All sources, reviewer identities, judgments, and scores used in these tests are fictional and remain in test code or memory.

The identified run is [engineering_independent_20261026_v1/result.json](engineering_independent_20261026_v1/result.json), with the [pre-test plan](engineering_independent_20261026_v1/plan_before_tests.json), exact source copies, and captured pytest output alongside it. All source hashes stayed unchanged during execution. The reviewed adapter SHA-256 is `b1a7db8049516790efa12c8f012c2b0a2137adfedc41d2efdb373d4f74d3400e`; the tested performance module is `b5bdd17f6e90b0456b03ca64a5d528e53927437a9d72cfef0d9d962316e46d9b`. The runner independently confirmed equality of the original/amended pure representation-function ASTs before testing.

- **HT point and variance:** enumerate every one of the 60 possible stratified samples from two tiny populations. The mean estimated total equals the known population total, and the mean estimated design variance equals the actual variance over the complete sampling distribution. Fractional outcomes exercise tie-averaged yield rather than only binary prevalence.
- **Implemented Rao–Wu weights:** replace random generation with all nine equiprobable ordered bootstrap draws for a three-unit sample. The actual implementation preserves each stratum's population-weight total, and its exact conditional replicate mean and variance match the HT estimate and finite-population variance estimator. Census singleton weights remain fixed; a noncensus singleton is rejected. Seeded weights remain aligned to case IDs after input-row permutation.
- **Weighted AP:** compare against a hand-derived unequal-weight, tied-score example, independent of the implementation's call to scikit-learn. The expected value is `(2/5)*(2/8) + (3/5)*(5/11)`; an unweighted calculation differs.
- **Queue ties:** enumerate every equally likely selection at a boundary tie and compare the resulting inclusion probabilities. A full-API example puts all highest-scoring files outside the annotation sample, detecting the erroneous alternative of ranking only sampled files.
- **Unknown and unsampled labels:** enumerate every completion in a tiny workload example and verify that the reported hard population bounds contain exactly the smallest and largest possible yield. All-unknown references suppress AP and workload point estimates; an observed sample with no positives does not produce a precise AP interval.
- **HT support:** deliberately construct an estimated recovered-positive total above the queue budget. The API preserves and flags the unclipped HT estimate and reports separate logical population bounds. Silently clipping that point would alter the estimator.
- **Input integrity:** reject missing scores, failed scores, a missing selected review, reused reviewer identity, class changes, and stratum changes. Test corrected string/comment recognition and confirm that an external batch of rare terms cannot modify the training vocabulary, IDF, or scaler; all-out-of-vocabulary rows remain explicit coverage failures.

The test result is a scoped check of these primitives, not a proof of every future orchestration path. It does not establish bootstrap coverage for rare positives. The performance module labels weighted AP as a nonlinear plug-in, labels percentile/normal intervals as approximations, and distinguishes a missing positive in the sample from absence of positives in the population. Its positive finite-population bootstrap baseline can retain every observed positive in every replicate; a nonempty replicate set or zero spread must not be advertised as a coverage guarantee.

## Remaining integration requirements

- The current performance interface requires a complete successful score vector. It correctly rejects a failed score instead of replacing it with a safe value. The protocol's failure/common-success analysis and handling of a queue that cannot be fully scored remain unimplemented in this interface.
- The current workload output estimates recovered-positive counts under a uniform boundary-tie policy. Weighted recall ratios, paired method differences using shared sampling replicates, and any treatment of model-training variability need explicit additional integration and tests before those results can be reported. Cross-class paired inference is not supplied.
- Fitted-state hashes and explicit roles prevent ordinary mistakes, but are not an authenticated execution gate. The eventual runner must bind the fixed training/test manifests, adapter and model configurations, fitted-state digest, complete score file, and authorized reference release. It must use the strict training entry points and preserve every external coverage status.
- Named human reviewers, semantic mapping and adjudication decisions, and a prospective protocol freeze remain pending. Synthetic provenance strings used in tests are not evidence that these obligations have been met.

## Compiler inventory cross-check

A separate read-only review of the frozen compiler plans and official release metadata found 2,689 source rows, of which 2,650 have plans: 1,968 external and 682 training. The other 39 rows remain unavailable. The ordered plans contain 3,900 candidate-version slots and exactly 30 distinct versions. Those counts agree with the provisioned toolchain manifest. The planned CSV SHA-256 is `e6db64c3b1061ab86944b412c73743ba897cbbc710b77963398ca746a2fb5e38`.

The independently consulted primary sources were the [official Solidity binary catalog](https://binaries.soliditylang.org/linux-amd64/list.json), [Solidity installation documentation](https://docs.soliditylang.org/en/latest/installing-solidity.html), and [PyPI's Slither 0.11.6 release](https://pypi.org/project/slither-analyzer/0.11.6/). The Slither wheel's published SHA-256 is `01f809198d3f171e2d768569c0054c96af5736614e183c64f42c9b51636c33c1`. Recommended checks included the full compiler build identifier, official artifact hashes, exact ordered plan membership, isolated Python dependencies, and explicit executable paths. Artifact/version verification is not compilation coverage and does not establish compatibility of imported dependencies.

A final source inspection also identified that the verifier originally described itself as read-only while rewriting receipts, and used assertions that optimized Python could disable. These points were sent to its owner for explicit handling; they do not invalidate the already recorded normal-mode inventory run. The final engineering receipt records the reviewed source hashes and test outcome separately from the original scientific artifacts.
