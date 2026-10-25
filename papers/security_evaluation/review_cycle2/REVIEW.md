# Independent automated review of the recovered second cycle

Reviewed 25 October 2026 against the recovered source checkpoint whose published commit is `1a8f4011d374e228f940be85e25386f17778ce25`, and the separately named fresh rerun artifacts. This is an independent AI code/data review, **not human vulnerability adjudication**. No source labels were reassigned, no external models were scored, and no full audit was rerun by this reviewer.

## Material scientific blocker

The two outside-giant development designs pass their declared count screens only under the historical capped 7,080-node graph. Their historical joint-disjoint training sets are overwhelmingly connected to the same tests under the fresh 24,131-node graph. An independent path join of exported memberships against `dependency_audit/string_aware_recovered_20261025/memberships.csv` gives:

| Selected test | Historical matched training files | Connected to its test under expanded full graph, threshold 0.8 | Selected training files still disjoint |
| --- | ---: | ---: | ---: |
| `outside_p90_seed2` | 5,422 | 5,409 | 13 |
| `outside_p90_seed4` | 5,418 | 5,408 | 10 |

These counts are identical for both primary classes and all five sampling seeds. At threshold 0.7 the connected counts are 5,411 and 5,409; at 0.9 they are 5,113 and 5,112. This check concerns the exported matched cells, not a newly sampled maximum eligible pool. Here “expanded full graph” means the full uncapped source population with the base edge policy; equal-address edges add no component changes in the audit.

The subsequently completed full sensitivity audit confirms that the *entire eligible joint pools* at threshold 0.8 also contain only 13 and 10 files: respectively 0/1 and 1/0 reentrancy/unchecked proxy positives. Every one of the 95 candidates fails the joint count/dispersion screens in all twelve graph variants (1,140 rows). This review checked the three declared output hashes, unique design count, zero passing rows, and the two primary-threshold eligible-pool counts in `design_feasibility/expanded_sensitivity_recovered_20261025_v1/`. The separate `CAMPAIGN_GATE.json` records comparative training as blocked while preserving the earlier bundles unchanged.

**Recommendation:** do not describe or execute these bundles as independent-family comparisons. Retain their frozen memberships as a diagnostic of how graph coverage changes feasibility. A historical-graph-only sensitivity is technically possible but cannot repair the scientific claim. Any new full-graph experiment needs newly defined and frozen eligible pools, not relabelling the old cells as disjoint.

The tests also share 961 of their 1,062 files: 90.49% of each test, with Jaccard overlap 0.8263113. They are not independent replications. Selection among the 95 candidates uses proxy class counts after the pilot; deterministic label-blind candidate construction does not make the subsequent selection label blind. The exported decisions correctly disclose this distinction.

## Independent checks completed

1. Verified all declared normalization result hashes and all seven feasibility-audit input/output hashes. Recounted 24,131 normalization rows, 92 changed streams, zero scanner errors, 95 candidate designs, and exactly the two reported passing designs.
2. Independently recomputed 100 evenly spaced edges from each sorted fresh lexical edge list using source-derived **token-tuple sets**, without hashed shingles or sparse matrix products. All 200 sampled Jaccard values matched within `1.12e-16` and met the recorded minimum threshold 0.7. This is an edge sample, not an independent proof of exhaustive edge-generation recall.
3. Checked every raw-hash and normalized-hash equivalence group in each fresh graph: all members lie in the same base component at thresholds 0.7, 0.8 and 0.9. The legacy graph records 133,888 lexical edges at the minimum threshold; the corrected graph records 133,874.
4. Inspected the separate SciPy verifier reports: all twelve reconstructed component partitions pass. The verifier independently reconstructs connectivity from the recorded edge lists; it does not independently regenerate every lexical edge. Its provenance checks align all 7,080 historical paths, dataset names and project IDs.
5. Independently compared the recovered campaign integration predictions with the published original joint-regime pilot: all 1,082 scores are exactly equal after round-trip CSV parsing, and only one attempt directory exists after resume.
6. Inspected scanner error handling, full-population graph construction, threshold monotonicity, candidate restrictions, source gates, matched class counts, train-only preprocessing, frozen configuration/resume checks, deterministic-fit reuse, and explicit failure handling. No material implementation defect was found in the inspected paths. This is a bounded review, not a guarantee of absence of defects.

## Execution-gate follow-up

After the expanded-graph finding, the campaign runner gained a hash-frozen execution assessment and an automatic selected-bundle gate check. The final reviewed runner SHA-256 is `337bab5afd4d9e3956a7d68639d172341338f9f106b6556866b9cb7d00880d59`. Its 22 focused tests pass. In addition, this reviewer independently exercised **14 guard cases with zero fits**: the exact published pilot exception passes; changed test memberships, vulnerability class, model, sampling seed or model settings are rejected; a blocked comparative assessment, wrong bundle hash and changed evidence hash are rejected; an old run without an execution assessment is rejected before `validate_run` or source loading. The latter check replaced `validate_run` with an immediate assertion failure, which was never reached. The four additional checks confirm that both actual selected bundles automatically produce failed assessments, an asserted approval cannot override their computed negative gate, and a legacy configuration is blocked by the newly available bundle gate before input loading.

The exception is limited to reproducing the published raw-TF-IDF/LR, reentrancy, seed-0 pilot memberships and binds the original prediction hash. It cannot authorize the newly selected outside-giant tests. A missing assessment defaults to blocked comparative execution. The comparative positive branch requires and parses a hash-bound computed graph gate, checks that overlap and screen-failure flags are false, and verifies its recorded input/output hashes. The runner does not regenerate graph topology during this check; a future positive gate must therefore come from an actual full-membership graph assessment. The present expanded audit is negative, and no positive comparative assessment has been supplied.

## Interpretation and provenance requirements

The full external diagnostic retains 691 of 6,587 historical DAppSCAN training files at threshold 0.8, with 23 reentrancy and 18 unchecked proxy positives. These are training-feasibility counts, not a powered design. SolidiFI injected labels and DAppSCAN no-published-finding labels must remain separate annotation regimes in claims and tables.

The corrected scanner changes comment recognition, including both markers inside strings and a legacy block-comment prepass starting inside actual line comments. It does not repair all tokenization, preserve semantic equivalence, or validate compilation. The old feature implementation remains frozen for historical comparability. The narrow sensitivity finds no training-retention changes; it does not establish that lexical components capture real project families.

Source snapshots, hash checks and distinct recovered-run directories adequately distinguish new executions from earlier lost artifacts. Original-run durations should remain identified as earlier observations; current execution durations and reproduction commands should link to fresh artifacts. The local source checkpoint `5270cfe...` recorded by early fresh jobs and published `1a8f401...` have the same tree, so their different commit IDs do not indicate changed executed source.

The external eligibility gate must remain closed while annotation disputes, family provenance and independent expert adjudication remain unresolved. Human label-review completion remains zero. A completed automated review or an unchanged lexical sensitivity is not a substitute for those decisions.
