# Article 1 status on 25 October 2026

Working title: **Project Dependence and Label Provenance in Smart Contract Vulnerability Evaluation**.

The first development cycle is complete. It produced a four-regime matched fixed-test pilot, an exhaustive external lexical/source audit, a blank specialist review packet, workload metric code, and measured CPU resource costs. It did not produce a confirmed independent external test or a submission-ready article.

## Current task state

| Task | State | Evidence and remaining condition |
| --- | --- | --- |
| P1.01 protocol | v0.2 draft, main freeze pending | `protocol.json`, `DECISIONS.md`; external eligibility and main test design unresolved |
| P1.02 external data | Source and exhaustive lexical audit completed | `external_audit/SOURCE_AUDIT_2026-10-25.md`; family provenance, source disputes and annotation semantics still require review |
| P1.03 controlled comparison | Four-regime development pilot completed | `runs/dev_fixed_t_20261025_v1/`; one test component and only three unchecked proxy positives prevent a broad main-study conclusion |
| P1.04 external confirmation | Not run | `external.scoring_allowed=false`; models must not be selected using external results |
| P1.05 workload and labels | Metric implementation tested; review packet prepared | 106 file-class cases from 25 proxy components, 51 initial second-reader cases, zero completed human reviews |
| P1.06 article and final analysis | Not ready | Needs eligible cohort, expert decisions, frozen main design and appropriate independent units |

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

## Next concrete work

1. Resolve the external source identity and annotation disputes, keeping all evidence and explicit unknowns. Apply the blank review packet with a named primary assessor and independent Solidity specialist.
2. Inspect dependency edges and deployed/project families; perform a string-aware normalization sensitivity check. Build any training restrictions on the full transitive frozen graph, retaining test coverage and composition.
3. Design the main fixed-test comparisons with sufficient positive cases and independently informative components. Report infeasible cells; do not split components merely to obtain training data. Keep this development pilot separate.
4. Freeze eligible populations, label mappings, configurations, workload rounding and inference scope before any external model scoring. Then run the declared model set.

## Provenance

The branch was cloned at starter commit `f3e5bccd124def4e1f3e60478ad928a71acd5b53`; book baseline is `2c2c7723cb9fa42ff46fb6f252652056a74f9223`. Historical C1–C4 outputs are unchanged. They retain their original dirty/reused-result provenance limitations. New computations preserve complete used source snapshots, not just hashes of an unsaved diff. See `PROVENANCE_LEDGER.csv` and `VALIDITY_NOTES.md`.
