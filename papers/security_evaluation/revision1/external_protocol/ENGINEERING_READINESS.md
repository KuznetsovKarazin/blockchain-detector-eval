# B engineering readiness, 25 October 2026

This records completed preparation only. Human judgments and external scores both remain zero. The original probability packet is unchanged. The protocol is still a draft, with its execution gate closed.

## Executable assessment of future human review

`review_estimators.py` consumes the frozen coordinator key/allocation, both sealed initial review forms and a separate adjudication form. It rejects incomplete selections, blank or invalid judgments, non-distinct reviewer IDs, missing reviewer/adjudication provenance, incorrect inclusion probabilities, incorrect weights, changed classes and adjudication rows that fail to preserve the original judgments. Recording names and timestamps is not proof that a real specialist performed a review; that remains a human process requirement.

For each complete source-status/class domain, the estimator reports the Horvitz–Thompson total divided by the known domain population size. With no unresolved reference outcomes this also equals the calibrated Hájek mean, because the stratified fixed sample weights sum exactly to that known size. Its variance includes the finite-population correction and is verified against exhaustive enumeration of small randomized sampling designs. A raw sample proportion is deliberately not substituted when inclusion probabilities differ.

The interval implementation inverts exact hypergeometric tails in each stratum and combines count bounds conservatively with Bonferroni coverage. It is boundary-valid when no sampled errors are observed; a zero estimated variance does not imply certainty. Census strata have zero sampling variance. A non-census stratum with one sampled case is rejected because its variance is not estimable by the implemented formula (the actual packet has no such stratum). Unweighted Wilson intervals are not used for this unequal-probability stratified design.

Unknown human reference outcomes stay in the selected sample. The tool reports estimated confirmed-outcome and unresolved-inclusive bounds, with a sampling confidence envelope around them, and suppresses the single point error rate. It neither assumes missing-at-random review outcomes nor drops nonresponse. Missing/blank forms are a pending collection error, not automatically an unknown judgment. Exact interval coverage is for the stated fixed finite-population outcome/domain; it does not claim simultaneous coverage across every differently defined output, truth infallibility, or generalization to new project families.

Initial reviewer agreement has separate raw and inverse-inclusion-weighted 3×3 tables, marginals, category agreement and optional nominal Cohen kappa. Kappa is undefined when expected agreement is one; no kappa confidence interval or correctness claim is inferred. Human source-error estimation is implemented; model ranking and workload uncertainty is a distinct remaining implementation.

## Read-only source and compiler preparation

`validate_external_inputs.py` checks the frozen packet hashes, four upstream commit pins and clean trees, every source byte hash, source decoding, corrected comment scanning, lexical token availability, and the 691-train / 1,998-test component exclusion. It never opens proxy label keys, human judgments or model scores, fits a vocabulary, trains a model, compiles Solidity, or executes Slither. Future vectorizer/scaler fitting remains restricted to the 691 training files.

The saved receipt `input_readiness_20261025_v1/summary.json` confirms lexical inputs for all 2,689 files. This is not model coverage or successful static analysis.

| Cohort | Lexical inputs ready | Compatible compiler plan only | Other plan statuses |
|---|---:|---:|---|
| External | 1,998 | 1,968 | 23 missing pragma; 4 unsupported constraint; 3 outside finite catalog |
| Training | 691 | 682 | 9 missing pragma |

`compiler_policy.py` uses the historical finite release catalog, whose last patches are 0.4.26 / 0.5.17 / 0.6.12 / 0.7.6 / 0.8.26. These are historical catalog bounds, not a claim about the latest available compiler. The corrected scanner ignores comments and string literals, intersects all active pragma constraints, and selects the newest allowed patch per minor, in descending minor order, with at most five attempts. Unsupported syntax and empty compatibility fail closed. There is no outside-pragma fallback.

The actual inventory found no Slither package in this environment and no required compiler binaries at the explicitly recorded historical installation paths. A different unrecorded installation is not inferred to be absent everywhere, nor accepted without a verified checksum. No executable coverage number exists. Source snapshots and input/output hashes accompany the read-only run.

## Remaining prerequisites

Before a prospective protocol freeze: implement and regression-test the final training/transform adapters (including corrected 43-pattern preprocessing); implement and test survey-weighted model AP/workload uncertainty; provision and hash the selected Slither/solc executables and permitted dependencies; obtain semantic sign-off on class/detector mapping; name the two independent specialists and obtain their review-protocol sign-off. Compiler planning tests and source-readiness checks are complete; those broader prerequisites are not.

After that freeze, obtain and seal both independent initial assessments, complete documented adjudication with unresolved outcomes retained, and revalidate unchanged source/configuration hashes. Only then may the closed score gate be reconsidered. The 17 unresolved identity issues remain quarantined and separate from the probability estimator. Any release of third-party raw sources or row annotations also requires a resolved rights basis; none is inferred here.

The complete 28-test engineering suite passed in 4.33 seconds. Tests include exhaustive hypergeometric coverage enumeration, exact stratified sampling variance, unequal-inclusion weighting, unknown/nonresponse handling, provenance preservation, compiler constraints and immutable packet/readiness receipts. Synthetic judgments exist only in in-memory unit tests; no actual review form was filled.

Run the engineering regression tests with:

```bash
.venv/bin/python -m pytest -q papers/security_evaluation/revision1/external_protocol
```

Run `review_estimators.py --help` for the future analysis interface. Passing the present blank forms correctly refuses analysis and does not manufacture estimates. Existing readiness outputs are immutable; reproductions require a new output directory.
