# Article 1 status on 25 October 2026

Working title: **Project Dependence and Label Provenance in Smart Contract Vulnerability Evaluation**.

The first development cycle and the second-cycle normalization/dependency/design audits are complete. The package contains a matched fixed-test pilot, exhaustive source and dependency audits, a blank specialist review packet, metric and campaign code, and a working manuscript. It does not contain confirmed independent external performance or a submission-ready article. Recovery and new-run provenance are explicit in `RECOVERY_2026-10-25.md`.

## Current task state

| Task | State | Evidence and remaining condition |
| --- | --- | --- |
| P1.01 protocol | v0.3 draft, main freeze pending | `protocol.json`, `DECISIONS.md`; external eligibility and main test design unresolved |
| P1.02 external data | Source and exhaustive lexical audit completed | `external_audit/SOURCE_AUDIT_2026-10-25.md`; family provenance, source disputes and annotation semantics still require review |
| P1.03 controlled comparison | Four-regime development pilot completed | `runs/dev_fixed_t_20261025_v1/`; one test component and only three unchecked proxy positives prevent a broad main-study conclusion |
| P1.04 external confirmation | Not run | `external.scoring_allowed=false`; models must not be selected using external results |
| P1.05 workload and labels | Metric implementation tested; review packet prepared | 106 file-class cases from 25 proxy components, 51 initial second-reader cases, zero completed human reviews |
| P1.06 article and final analysis | Development manuscript drafted; not ready for submission | `manuscript/DRAFT.md`; needs eligible cohort, expert decisions, frozen main design and appropriate independent units |

## Controlled pilot

One fixed test contains 1,082 DAppSCAN files and 21 reentrancy proxy positives. Every training regime has 1,179 files and 31 proxy positives. The model is the fixed historical raw TF-IDF/LR configuration with one paired sampling seed. No test file enters any training set. Joint-disjointness preserves the full transitive historical project-union-clone graph before any cohort restriction.

| Training regime | AP against proxy labels |
| --- | ---: |
| Other files unrestricted | 0.076554 |
| Project disjoint | 0.028044 |
| Clone disjoint | 0.027697 |
| Joint project and clone disjoint | 0.038475 |

Test prevalence is 0.019409. These are descriptive results on one observed dependency component, not a causal leakage estimate or inference over new projects. Joint AP exceeds project and clone AP here, so monotonic worsening is not established. The same test contains only three unchecked proxy positives. A metadata-only two-class analysis and separately identified post-hoc floor-workload calculation are preserved. The original pilot's ceiling-budget settings and outputs remain unchanged.

All four models converged. Input validation and the four fits/scorings took 19.95 seconds, with cumulative peak RSS 394.42 MiB. Full source snapshots, configuration, inputs, memberships and predictions without copied third-party labels are saved. An additional automated implementation review recomputed AP/workload and checked regime exclusions; it is not a substitute for human vulnerability assessment.

## External candidate

The audit compared 2,181 candidate paths with 21,950 reference paths, including all 21,457 upstream DAppSCAN files. The 2,182 compact-manifest rows correspond to 2,180 source/identifier keys. Seventeen candidate paths need reconciliation: fourteen out-of-range source-location records, two differing repeated-key annotations, and one missing manifest row. A likely ZEUS identifier transcription mismatch is quarantined, not silently repaired.

There are 142 exact-byte overlaps, all curated; 148 normalized overlaps; and 208 direct lexical overlaps at Jaccard 0.8. These are different tests of dependency. The diagnostic flow excluding prior-curated sources, unresolved records and repeated identities leaves 1,998 files, with 46 source-reported reentrancy positives and 200 unchecked positives. These counts are provisional, not an approved final test. The residual still contains 65 directly and 186 transitively linked files in 11 proxy components; see the source audit for details. The preferred response is to restrict training where feasible, not to remove inconvenient test cases.

The exhaustive screen took 88.54 seconds and approximately 614 MiB peak RSS. It removes LSH candidate omission for the chosen lexical representation. String-unaware legacy comment removal, lossy normalization, missing real-world project provenance and incomplete source rights remain explicit limits. Proxy component counts do not establish independent families.

## Resource feasibility

`runs/resource_profile_20261025_v1/` profiles the four declared ML methods on the fixed joint pool without reading test annotations or computing performance metrics. Raw LR, normalized LR, RF and LightGBM took 5.10, 2.74, 5.65 and 5.30 seconds respectively including preprocessing and prediction; cumulative peak RSS was 322.16 MiB. A linear projection for 4 regimes × 2 classes × 5 paired sampling seeds × 4 methods is about 12.5 minutes for one test and one size point. This is a projection from one pool, not a full-campaign measurement. It excludes Slither, source audit, expert assessment, bootstrap, additional test populations and learning curves. GPU and paid model APIs are not required for these baselines.

The executable pilot, audit and resource-profile reproduction commands are in the paper README and individual run READMEs. Do not mistake the 160-fit projection for completion of the main grid: the main test needs revision before that grid is scientifically useful.

## Second-cycle sensitivity and feasibility

The string-aware scanner changes 92 of 24,131 normalized streams, with zero scanner errors. Fifty changes involve comment markers in literals and 42 expose block-comment removal beginning inside a real line comment. Historical token normalization is otherwise retained. The regenerated full normalization CSV and the 42-case diagnostic CSV match their previously recorded hashes. Historical model features remain unchanged.

Full dependency graphs include all 24,131 paths before training restrictions. Two normalizers, two grouping policies and three thresholds give 12 partitions. An independent SciPy implementation reproduces every partition and training aggregate. The following counts retain historical DAppSCAN training files after excluding all components connected to the provisional 1,998-file candidate cohort:

| Jaccard threshold | Retained DAppSCAN files / 6,587 | Reentrancy proxy positives | Unchecked proxy positives |
| --- | ---: | ---: | ---: |
| 0.7 | 418 | 17 | 15 |
| 0.8 | 691 | 23 | 18 |
| 0.9 | 1,085 | 29 | 22 |

At 0.8, the historical SolidiFI and SmartBugs contributions retain 350 and 134 files respectively. These annotation regimes must not be pooled to disguise the small remaining DAppSCAN sample. String-aware normalization removes 14 lexical edges at 0.7 and none at 0.8 or 0.9; training-retention decisions are unchanged at all three thresholds. The 80 syntactic address links cause no additional partition changes. Unknown networks and family provenance remain unresolved.

Of 95 deterministic development test designs, two pass the recorded historical count/dispersion screens. Both contain 1,062 test files and omit the giant component, covering only 16.12% of the original DAppSCAN population. They share 961 files (90.49% of each test), so are not independent replications. Historical joint restriction removes only 103/107 additional training files. Passing these operational screens is not evidence of adequate statistical power.

**Expanded-graph assessment blocks the proposed 320-job comparative campaign.** None of the same 95 test memberships passes the original screens at 0.7, 0.8 or 0.9 under either normalizer or grouping policy: zero passing combinations among 1,140. At threshold 0.8, for the two selected tests, 5,409/5,422 and 5,408/5,418 historical joint-training files connect to the test in the expanded graph. Correct joint restriction leaves only 13 and 10 eligible files: respectively 0/1 and 1/0 reentrancy/unchecked proxy positives. Preserve the prepared historical bundles as diagnostic evidence; do not treat them as independent comparisons. `design_feasibility/expanded_sensitivity_recovered_20261025_v1/CAMPAIGN_GATE.json` records the block. A separate controlled graph-scope ablation at 0.8 resolves the attribution for these memberships: replacing the historical search with exhaustive screening on the same 7,080 sources leaves the projected DAppSCAN partition and training counts unchanged. Adding uncapped upstream reference sources already reduces training to 13/10. Adding the external candidate changes no further training count. The projected DAppSCAN giant component grows from 5,408 to 5,879 files. This finding is conditional on the stated graph rules; it does not validate all edges as real-world family relationships. See `dependency_audit/graph_scope_ablation_recovered_20261025/`.

The recovered campaign integration reproduces the original joint-pilot predictions exactly, with maximum absolute score difference zero. Resuming it creates no additional fit attempt. This verifies implementation and recovery; it is not a new independent experiment.

See `normalization_audit/`, `dependency_audit/`, `design_feasibility/`, and `review_cycle2/` for configurations, source snapshots, outputs, comparison checks and automated review. No independent human vulnerability judgments have been added. The final focused implementation suite passes 81 tests; the additional automated review exercised 14 execution-guard cases without fitting models.

## Next concrete work

1. Resolve the external source identity and annotation disputes, keeping all evidence and explicit unknowns. Apply the blank review packet with a named primary assessor and independent Solidity specialist.
2. Inspect dependency edges and deployed/project families; perform a string-aware normalization sensitivity check. Build any training restrictions on the full transitive frozen graph, retaining test coverage and composition.
3. Review graph-scope and edge-discovery sensitivity, then choose a defensible population or explicitly narrow the research question. The current 95 designs are infeasible under the expanded graph at 0.8; do not split components merely to fill cells or run the blocked comparison. Keep the completed pilot separate.
4. Freeze eligible populations, label mappings, configurations, workload rounding and inference scope before any external model scoring. Then run the declared model set.

## Provenance

The branch was cloned at starter commit `f3e5bccd124def4e1f3e60478ad928a71acd5b53`; book baseline is `2c2c7723cb9fa42ff46fb6f252652056a74f9223`. Historical C1–C4 outputs are unchanged. They retain their original dirty/reused-result provenance limitations. New computations preserve complete used source snapshots, not just hashes of an unsaved diff. See `PROVENANCE_LEDGER.csv` and `VALIDITY_NOTES.md`.
