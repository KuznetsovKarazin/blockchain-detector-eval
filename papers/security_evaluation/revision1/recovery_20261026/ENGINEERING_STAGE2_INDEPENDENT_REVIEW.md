# Independent review: external-B orchestration, failure analysis and compiler readiness

Status: scope, performance-v2, exact AP bounds, compiler-runner and orchestration reviews complete. Date: 2026-10-26. This file is separate from the completed stage-1 review and does not amend its frozen receipts. The original four stage-2 suites contain 65 independent tests, all passing; each component has its own source-frozen receipt. A later loader amendment adds four new tests and repeats the 17 orchestration guards, preserving the original receipt.

## Compiler-only readiness before the overall protocol freeze

The current `PROTOCOL_B.md` (SHA-256 `d54c70f59abf63ac3580408fd352b3ff3f77fb006f8a857539f64ed0669ca3ca`) requires the method configuration and analysis code to be sealed before the first human judgment or external model score. Its release sequence gates human review, fitting, and scoring. The compiler section separately requires a finite compiler inventory and binary checksums before execution. It does not explicitly forbid a compiler-only engineering check before the overall freeze.

A separately frozen, annotation-file-blind compiler-readiness stage is therefore compatible with the current draft **without opening the human-review or model/Slither score gates**. This interpretation is limited to the following controlled scope:

- The same 691 training and 1,998 external source identities, pinned bytes, fixed candidate-version order, at-most-five attempts, 180-second per-attempt timeout, and no outside-pragma fallback apply. Missing-plan cases remain present with explicit unavailable status.
- Before execution, save the runner/configuration hashes, verified executable identities, source and import-policy manifest, output definitions, and run identity. The existing global protocol and historical receipts remain unchanged. A new engineering receipt records what was actually attempted.
- Only compiler invocations are permitted. Do not load annotation keys, human review forms, training proxy labels, models, learned feature states, or Slither detectors. Source text can itself reveal contextual hints, so “annotation-file-blind” does not imply perfect semantic blinding.
- Compile outcomes must not change cohort membership, graph thresholds, the annotation sample, feature/model choices, or the fixed compiler policy. Any later policy change needs an explicit dated amendment that records which outcomes were already observed. A new run must not silently replace failed results.
- Freeze import resolution before outcomes: exact declared project/root namespaces and pinned local dependencies; no cross-project basename/suffix rescue, network retrieval, source rewriting, or path/symlink escape outside permitted input trees. Record the bytes of dependencies actually supplied to the compiler.
- State whether the request tests parsing/type checking, AST generation, bytecode generation, or another output. These can fail differently. Compiler success alone does not establish Slither compatibility, vulnerability detection, a successful full pipeline, or ground-truth correctness.
- Preserve raw diagnostics and source excerpts privately. Publish only owned code, aggregate/status metadata, timing, input references and hashes unless redistribution rights are separately resolved.

The parent task currently authorizes code, plan and synthetic verification, not actual corpus compilation by this reviewer. This review has executed no compiler, Slither, model, or real human-reference analysis.

## Gate defect found in the legacy validator

The historical `validate_gate.py` uses empty dictionaries as defaults for missing prerequisite and hash maps. A synthetic protocol containing only the frozen-status string and two identical fictional reviewer names returned **no blockers** even with both top-level execution permissions explicitly false. Its direct Python API also accepted an unknown phase. The real saved protocol remains a draft with many explicit blockers, so this diagnostic does not mean any actual score was authorized or executed.

Reproduction uses only an in-memory fictional document:

```python
payload = {
    'status': 'frozen_before_human_judgments_and_scores',
    'probability_audit': {
        'reviewer_1_name': 'Fictional A',
        'reviewer_2_name': 'Fictional A',
    },
    'model_fitting_allowed': False,
    'external_scoring_allowed': False,
}
# Legacy blockers(payload, protocol_dir, 'score') == []
# Legacy blockers(payload, protocol_dir, 'not-a-real-phase') == []
```

The inspected legacy validator SHA-256 is `ceb8730ce451950f2981548d5e87db8d14608258ab9f73fe80f7076476594a9b`. The issue was immediately sent to the parent and orchestration owner. The new gate must require the expected schema and all named prerequisites, bind required artifacts and their hashes, reject unknown phases and missing/contradictory permissions, normalize and distinguish reviewer identities, and validate sealed review evidence rather than trusting flags alone. The legacy frozen file should remain preserved.

## Completed performance-v2 review

The independently owned [test suite](test_engineering_stage2_performance.py) passed **20 tests** against performance-v2 SHA-256 `71837b15960b1b9b26434957437934cda04c4092a288ca661e1a4eb31ef48b69`. The [sealed result](engineering_independent_stage2_performance_20261026_v1/result.json), pre-test plan and exact source/configuration snapshots record unchanged hashes throughout execution. All data are fictional.

The census oracle has three known positive files. Method A recovers two at a three-file requested budget, including an unavailable positive in the denominator, for recall 2/3. Method B recovers one for recall 1/3. Their exact paired recall difference is 1/3. The four-file common-success domain has a different denominator and yields the separately calculated AP values 1 and 1/2. Full-frame AP remains unavailable when a method has no complete ranking.

A two-stratum example with inclusion probabilities 2/4 and 2/8 produces the correct common-domain HT numerator 2 and denominator 6, hence recall 1/3 rather than the unweighted 1/2. For identical methods, marginal AP and recall replicate values vary while every paired difference is exactly zero, verifying covariance preservation. The original strata, sampled rows, and sampling fractions remain present for domain estimation.

Other checks cover successful zero scores, unfilled review budgets, unknown references inside and outside the common domain, empty and nonempty-but-unsampled common domains, every explicit missing/failed file, invalid status/score combinations, mismatched paired-comparison tags, and an undefined ratio replicate that must not be deleted. Queue construction receives no human-reference argument. Conservative suppression of yield when any reference in its target domain is unknown is acceptable; the separately reported workload bounds remain available.

No numerical defect was found in these tested primitives. This is not a finite-sample coverage certificate. Ratio/AP bias, rare positives, undefined denominators, conditional common-success targets, and omitted training/reference-error uncertainty remain explicit limitations. The separate synthetic coverage study evaluates interval behavior; it is not replaced by these unit tests.

## Substantive AP uncertainty finding and exact completion bounds

The independently designed synthetic coverage study found severe undercoverage of the nominal 95% percentile interval. This review separately verified its first counterexample without importing either the study driver or the estimator implementation. There are 20 files, a simple random sample of 4, and one positive in the highest-scoring tied group of 5. Population AP is 1/5. Conditional on sampling the positive, the probability of sampling no other member of its tie group is `C(15,3)/C(19,3) = 455/969`. On that event every bootstrap AP is 1, producing the incorrect interval [1,1]. Independent enumeration of all 64 ordered bootstrap draws for each of four possible sampled tie-group sizes confirms that exactly 514/969 issued intervals cover the population AP: about 53.04%, not 95%.

The [analytic verifier](verify_rare_positive_ap_counterexample.py) and [receipt](rare_positive_ap_counterexample_verification.json) preserve this result. It is a counterexample to calibration, not an estimate of coverage on the actual external population. The new `INFERENCE_GATE_20261026.json` correctly leaves confirmatory AP uncertainty unvalidated. The v1/v2 percentile calculations may remain exploratory computational summaries; a correct HT variance formula does not establish nonlinear interval coverage.

The proposed exact alternative also required a correction before acceptance: assigning a fixed number of unknown positives to the earliest scores does **not** always maximize grouped-threshold AP when ties exist. For scores [2,2,1,1,1], partial labels [?,0,1,1,?], and one unknown positive, the early assignment gives 17/30, while the late assignment gives 3/5. The implementation therefore uses dynamic programming rather than that invalid exchange rule.

The reviewed recurrence is exact. For score group g, let `a_g` be known positives, `u_g` unknown labels, `A_g` cumulative known positives, `N_g` cumulative files, and t cumulative unknown positives. Choosing z unknown positives in the current group contributes `(a_g+z)*(A_g+t)/N_g` to the AP numerator. Future contributions depend on earlier choices only through t, making it a sufficient Bellman state. Taking minima/maxima over feasible z, then dividing each terminal state by its positive total and optimizing across terminals, gives sharp bounds. Scaling by `lcm(N_g)` keeps every transition an integer; final Fraction endpoints and cross-product comparisons avoid floating-point optimization error. A possible all-negative completion remains separately undefined.

The amended API SHA-256 `71147a09cec0f755a735224f127ef379d7b4e78c17094d3ee48c3635df54ef2c` passed **six independent tests**, including all completions for 96 fixed-seed toy cases, extrema for every positive total, endpoint witnesses, both tie counterexamples, undefined states, witness-free operation, large integer ordering, and rejection of a Fraction conversion that would otherwise collapse distinct scores into a tie. The [sealed AP-bounds receipt](engineering_independent_stage2_ap_bounds_20261026_v1/result.json) includes exact source copies. These are logical bounds conditional on fixed known reference labels and a complete score queue, not sampling confidence intervals or validation of expert correctness. They do not automatically open the overall execution gate.

## Orchestration findings and corrections

Early implementation inspection identified several integration gaps and communicated them immediately to the owner: score-status vocabularies differed from performance-v2; only learned-method jobs were enumerated while Slither receipt scope was unstated; artifact counts alone could admit duplicate dependencies; and supplied source-copy hashes did not yet prove that live validator code and its transitive scanner/feature/catalog dependencies matched those bindings. The owner added an explicit status mapping retaining original reasons, 24 learned-job plus two static-comparator slots, artifact/package uniqueness and the exact compiler-plan union, live-validator identities, and transitive code bindings. Sample-key counts and the prohibition on noncensus singleton strata now apply during source preflight. Production counts cannot be replaced with a smaller synthetic profile.

The generic orchestration setup also reads source-label metadata and the coordinator sample key. It is a read-only coordinator check, **not** the annotation-file-blind path for compiler-only readiness. The compiler runner must use a separate metadata-only identity and toolchain check.

The new early admission path checks the frozen protocol and inference policy before private training/source-label access. It then verifies the human-review release chain before a future worker can read training inputs. These checks validate consistency relative to a separately selected binding digest; they do not authenticate people, certify event times, prove real expertise, or authorize execution. Both the schema guard and full checker retain `execution_authorized=false`.

The [sealed orchestration receipt](engineering_independent_stage2_orchestration_20261026_v1/result.json) records **17 passing independent adversarial tests** against checker SHA-256 `905ff25df2adc2c58b352248b25619db3523cf4fad9a32e0999254fd53995890` and schema gate SHA-256 `bbb595a82ede8681699d7cc2652fbc7236f66df360db6ddec6685b1ac61c7c48`. Tests require every declared prerequisite and transitive code hash, reject legacy/unknown phases, and instrument early reads to detect private access before draft/inference rejection. They also reject fake live-code copies under a production profile, symlink escapes, an omitted static-comparator job, fabricated success from a preprocessing failure, permuted training identities, static analysis before adjudication, and substituted fitted membership despite correctly rebound artifact hashes. Blank human judgments remain invalid even after their event hashes and chain links are repaired. Toy-file construction reuses the owner's fixture; mutation choices and correctness assertions are independently owned and preserved in the snapshot. No remaining blocker was found within this read-only integrity-checking scope.

The later exact-byte loader amendment is independently **pass** in [its separate receipt](engineering_independent_stage2_orchestration_loader_20261026_v1/result.json), against final checker SHA-256 `fb0640a89d4607aae33687202d04b3e4fa86f4ada92d65529bbed3fed912bf05`; the schema-gate hash is unchanged. All 17 prior adversarial tests pass again, along with four focused tests. A fictional dependency is changed without changing its timestamp or byte length, and an ordinary loader demonstrably executes the stale bytecode; the amended loader instead compiles the current bytes and records their digest. Further checks bypass a preloaded module object, restore the previous module-cache entry after a failed load, and verify the actual gate/review-helper compiled-byte digests. Only fixed trusted implementation paths are loaded. This corrects cached-code provenance without changing statistical definitions or claiming to authenticate arbitrary code or people.

## Compiler-only review completed

The final [plan-bound review receipt](compiler_plan_review_20261026_v2.json) is **pass** for plan SHA-256 `7f5da3a7cf0a9fcef75d3b4c1f071552dca7d42dcf8fdb98855a514b90aafa80`, jobs SHA-256 `5f83146346595c6680fef5f9ac45d129983fc51fcf4a942d185be9a0e2ba204c`, and runner SHA-256 `ee80047bf6d2e6f77e47fb35260cd0eaaa5a6703f3e96b92674c9dd129a5aaa4`. It checks the exact 2,689 original identities, order and compiler candidates, all input/source hashes and snapshots, clean raw pins, source-unit identities against the pinned node inventory, and the parent's successful benign smoke fixture across all 30 compiler versions. The latter is not corpus compilation evidence.

There are 2,304 attemptable files: 336 training and 1,968 external. The 346 additional training context failures and 39 originally unplanned files remain represented; none is silently removed. Attemptable closures contain 2,725 source-unit occurrences. This is a pre-execution count, not successful compilation coverage.

Two findings were corrected first. A declared root contract with missing requested output could initially be reported as a successful file with no root contracts; the classifier now requires matching AST/output contract sets. Malformed nested output containers could initially raise an exception and interrupt the run; they now produce a per-file schema failure. Source snapshots/hashes are now captured before closure enumeration and checked again afterward. The initial metadata-only preparation was interrupted before any output, and the final plan has a new v2 identity.

The [independent compiler receipt](engineering_independent_stage2_compiler_20261026_v1/result.json) records **22 passing tests**: import/literal recognition, exact relative namespaces, no basename rescue, external context restrictions, traversal/URL/symlink rejection, cycle termination, changed/ambiguous pins, missing and malformed compiler outputs, interface/abstract semantics, diagnostic sanitization, output limits, closed-pipe timeouts, and refusal before a reviewed permit. Process tests use fictional Python snippets, never Solidity corpus files. This review is not an end-to-end safety guarantee or a kernel-sandbox claim. Any actual corpus compilation belongs to the parent's separate plan-bound authorization and receipt; this reviewer executed none.

After the parent's authorized corpus execution finished, a separate [read-only output review](COMPILER_EXECUTION_INDEPENDENT_REVIEW.md) verified all 2,689 records, 3,514 attempts and all 7,028 private diagnostic hashes without rerunning a compiler. It confirms 330/691 training and 1,807/1,998 external compiler successes, with every failure/unavailable file retained. The original pre-execution review remains unchanged.

## Execution boundaries retained

Common-success results are a conditional estimand and cannot replace full-pipeline results.

The orchestration review tests incomplete/forged schema documents, altered source/configuration hashes, contradictory permissions, incomplete or reused reviewer forms, malformed scores, and mismatched fit/source identities. A successful read-only preflight must still not execute a fit or score.

No real human review, model fit, external scoring or publication was performed by this reviewer. The mathematical and engineering improvements do not create missing human references, resolve semantic mapping sign-off, or constitute an overall prospective protocol freeze.
