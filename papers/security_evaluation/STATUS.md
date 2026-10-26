> **Current checkpoint, 26 October 2026:** all pinned inputs/private packet and 23 gzip artifacts are verified locally. Six original NPZ files remain unrecovered; six new canonical reproductions have separate lineage. Compressed graph artifacts are excluded from the public update after automatic publication rejection. See [publication status](revision1/PUBLICATION_STATUS.md).

# Article 1 status on 26 October 2026

Current manuscript title: **Population Coverage and Dependency-Aware Evaluation of Smart Contract Vulnerability Detectors**. Earlier cycles used *Project Dependence and Label Provenance in Smart Contract Vulnerability Evaluation*.

The current scientific manuscript is [DRAFT_REVISION2.md](manuscript/DRAFT_REVISION2.md), with five tables, six figures, 17 references and AI-assisted-method/declaration text. Revision 1 completed the graph-mechanism and conditional historical-test model-stability study; those results remain unchanged. New work restores inputs and graph artifacts with explicit provenance and completes additional scoped B engineering. Start with [revision1/README.md](revision1/README.md), [current engineering readiness](revision1/external_protocol/ENGINEERING_READINESS_20261026.md) and [publication status](revision1/PUBLICATION_STATUS.md). External expert validation remains prospective: zero real human judgments and zero external model fits/scores. Neither the main protocol nor B has a new overall freeze.

## Current task state

| Task | State | Evidence and remaining condition |
| --- | --- | --- |
| P1.01 protocol | v0.3 draft and B draft; overall freeze pending | Existing execution gates remain closed; module configurations document completed diagnostics, not an external validation freeze |
| P1.02 data and dependence | Source audit, graph mechanisms and representation sensitivities completed | `revision1/graph_mechanism/`, `revision1/representations/`; semantic-family identity and annotation disputes remain unresolved |
| P1.03 controlled comparison | Conditional historical-test sampling experiment completed | `revision1/sampling_variance/run_20261025_v2/`: 320 main-panel plus 40 estimator-seed logical evaluations; 282 physical fits; no failures |
| P1.04 external confirmation | Scoped engineering prepared; evaluation not run | Fixed 1,998-file cohort / 691-file training manifest; adapters, selected weighted-performance primitives and toolchain verified; authenticated integration and human/semantic gates remain open |
| P1.05 workload and labels | Computation verified; human review pending | New probability packet: 180 file-class cases, 170 files, 17 strata, both reviewers assigned every case; zero completed judgments. Earlier purposive 106-case packet preserved separately |
| P1.06 article and analysis | Revision-2 text and Word presentation updated | `manuscript/DRAFT_REVISION2.md`, five tables / six figures / 17 references; 18-page Word final visual QA passed after availability/layout fixes; no submission, registration or DOI created |

## Recovery and engineering update on 26 October

Four clean raw commit pins, historical input ordering and source hashes, the provisional annotation manifest, private 180-case probability package and 17 identity dossiers were restored. Twenty-three gzip artifacts match original bytes; a full content audit covers 1,083,747 rows. The six original NPZ archives remain missing. Six new canonical reproductions are separately identified: all 120 reported partitions and 20 surviving result CSVs match, but full original unordered edge identity is not proved. [Recovery](revision1/recovery_20261026/REPRESENTATION_RECOVERY.md) and [publication status](revision1/PUBLICATION_STATUS.md) distinguish these claims. The original omissions list is unchanged. Public upload of compressed artifacts was again automatically rejected after the audit; the current update is code/text metadata only. The verified 42-file recovery bundle was successfully saved privately for the author, as was the final 18-page Word manuscript; these private deliveries are not public publication.

The new B modules pass 24 adapter, 24 performance and 21 independent synthetic tests. Toolchain checks pass 7 original plus 7 amendment tests; 30 solc binaries and Slither 0.11.6 have 31 recorded version-only probes, with zero contract compilation/scans. The optimized-Python v2 verifier checks artifact hashes without tool execution or default writes. The [final combined verification](revision1/recovery_20261026/FINAL_VERIFICATION_20261026.json) records 251 unique passing tests: 237 main (168 rerun prior + 24 adapter + 24 performance + 21 independent) and 14 toolchain, with zero failures/errors. The original 28-test engineering record remains historical and is included within the prior checks, not counted again.

All 2,689 fixed train/test inputs pass raw, normalized and pattern43 preprocessing; no real vocabulary, scaler or classifier was fitted. Performance tooling currently requires complete successful score vectors and supplies nonlinear weighted AP with approximate finite-population bootstrap intervals, HT tie-aware workload and explicit unknown bounds. It does not supply failed-tool/common-success analysis, weighted recall ratios, paired differences, cross-class/training uncertainty or rare-positive coverage guarantees. The future runner must authenticate manifests, model/adapter/tool hashes, fitted state, complete scores and sealed references; tests and recorded reviewer names cannot do that alone. See [the precise readiness boundaries](revision1/external_protocol/ENGINEERING_READINESS_20261026.md).

## Revision 1 findings and their scope

The mechanism experiment evaluates 3,822 graphs: 49 populations, 13 thresholds from 0.70 to 1.00, three grouping rules and two comment normalizers. Five predeclared hash rankings supply nested 10–100% DAppSCAN source-coverage curves without label-based selection. At Jaccard 0.8, the complete DAppSCAN population has 20,588/21,457 files (95.95%) in the joint giant, versus 5.28% with project relations alone and 0.47% with clone relations alone. The earlier 89.25% is a different denominator: 5,879/6,587 historical files projected through the complete graph.

The result depends strongly on the representation. Project membership plus exact raw-byte equality connects 3,608/21,457 files (16.82%), while project membership plus exact normalized-stream equality connects 19,321 (90.05%). Approximate near-match edges are therefore not required for a giant under this lossy normalization. Proper project contraction and independent removal checks identify 26 weighted articulation projects and 55 simple bridges at 0.8; removing one project separates at most 82 additional DAppSCAN files, excluding that project's own files. These are conditional graph mechanisms, not a proof of semantic identity or a formal percolation threshold.

The alternative representation study preserves all 24,131 nodes and known structural relations. Identifier/number preservation, explicit library/interface masking, containment and a segment-boundary control are separate, recorded sensitivities. The explicit no-empty-shingle baseline changes the historical DAppSCAN projection of the giant from 5,879 to 5,858 and the external-training count from 691 to 712 (711 informative sources). This is an intentional empty-representation policy change; it does not overwrite the earlier baseline or silently alter protocol B. Masking is structural lexical extraction, not validated semantic library removal.

The completed sampling experiment keeps the original 1,082-file test, 21 reentrancy proxy positives and one historical joint component fixed. Each training set has 1,179 files and 31 positives. The main panel has 20 paired training draws × four regimes × four methods, with estimator seed zero; a separate 40-evaluation panel varies the two tree estimators' seeds on the fixed joint pool. All 360 logical evaluations completed through 282 physical fits with zero failures or convergence warnings. The joint pool has only one unique training membership and its repeated main-panel results reuse the same fit. All four raw-LR draw-zero prediction vectors reproduce the pilot exactly.

For raw LR, project-minus-joint AP averages +0.003573 across draws, with descriptive 2.5%/97.5% quantiles −0.012647/+0.018556 and 12/20 positive differences. Thus the earlier single-draw ordering is not stable to training-subset selection. These are conditional training-variation summaries, not confidence intervals for unseen projects or causal leakage effects. The exact expected AP for a uniform strict random ranking is 0.025363, versus prevalence 0.019409. All scores remain against proxy labels. The unused `run_20261025_v1` preflight has no scores; the executed run is `run_20261025_v2`.

`revision1/independent_verification.json` records graph/cut, identity-control, representation, probability-sampling and model-metric checks, including 360 independent AP and 1,080 tie-aware workload recalculations. Actual resume verification preserved all 1,800 physical-fit artifact hashes and summary outputs without fitting again. The 25 October revision record reports 168 tests: 166 in the combined suite plus two input-readiness tests; the 28 external-engineering tests are included, not added again. Automated verification is not human vulnerability adjudication.

The prospective external packet contains 180 probability-sampled cases from 170 files and 17 source/class/status strata, with known inclusion probabilities and design weights. Both independent specialists would review all cases. A separate 17-case identity census preserves unresolved records; it is not pooled with the probability sample or the earlier purposive packet. All human forms remain blank. The unchanged 25 October engineering record reported 28 tests and compile-plan readiness. The 26 October update above records implemented adapters, selected performance primitives and verified executables. Only version probes have executed; successful compilation/Slither coverage remains unmeasured. Semantic mapping, named experts, prospective freezing and authenticated execution integration remain prerequisites.

## Historical first-cycle controlled pilot

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

See `normalization_audit/`, `dependency_audit/`, `design_feasibility/`, and `review_cycle2/` for configurations, source snapshots, outputs, comparison checks and automated review. No independent human vulnerability judgments have been added. The second-cycle focused implementation suite passed 81 tests; the additional automated review exercised 14 execution-guard cases without fitting models.

## Next concrete work

1. Complete the authenticated B runner/integration and explicitly implement or narrow any additional estimands intended for reporting. Preserve the complete-score/failure and unknown-handling constraints; use verified executable paths. Synthetic tests do not establish rare-positive AP interval coverage.
2. Obtain semantic class/detector sign-off, name two independent specialists and approve the human-review protocol. Freeze the complete protocol prospectively before collecting judgments or external scores; keep the 691-file training design unchanged unless a separately disclosed amendment is made.
3. Obtain and seal both initial human review sets, adjudicate with unresolved outcomes retained, and verify unchanged inputs before considering external scoring. Resolve the 17 identity cases separately.
4. Keep the two outside-giant campaigns blocked. The 20-draw experiment remains conditional on the original historical test and does not create independent external test families.
5. Preserve the completed 18-page [Word QA](revision1/recovery_20261026/MANUSCRIPT_DOCX_QA.json) and perform any later journal-specific formatting checks on new versions. Keep compressed graph artifacts outside the current public update after automatic rejection; preserve private recovery delivery separately. The publishing agreement has been reviewed privately, without publishing its contents/personal/financial terms and without claiming legal clearance or third-party redistribution permission.


## Provenance

The branch was cloned at starter commit `f3e5bccd124def4e1f3e60478ad928a71acd5b53`; book baseline is `2c2c7723cb9fa42ff46fb6f252652056a74f9223`. Historical C1–C4 outputs are unchanged. They retain their original dirty/reused-result provenance limitations. New computations preserve complete used source snapshots, not just hashes of an unsaved diff. See `PROVENANCE_LEDGER.csv` and `VALIDITY_NOTES.md`.
