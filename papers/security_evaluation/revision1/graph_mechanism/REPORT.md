# How project and lexical relations concentrate the corpus

This revision measures the interaction between project membership, lexical reuse, and source-population coverage. It does not establish a universal impossibility of leakage-free evaluation or a formal percolation transition. All results are conditional on a stated graph definition. No models were fitted or scored, no components were cut to obtain a desired sample size, and no human label or semantic-library judgments were supplied.

## Controlled questions and design

1. **How do the individual relations and their union change concentration?** Compare project-only, clone-only, and their union at 13 predeclared Jaccard thresholds: .70, .75, .80, .85, .90, .92, .94, .95, .96, .97, .98, .99, and 1.00. Clone-only includes byte equality and normalized token-five-gram set similarity. Project-only includes upstream project groups and, where external files are present, equal source identifiers.
2. **Does incomplete source coverage hide connectivity?** Compare the historical 7,080-file reference cohort, all 21,457 DAppSCAN sources, all 21,950 reference sources, and all 24,131 sources including the external candidate. Five seeds (1301–1305) determine nested SHA256 path rankings of DAppSCAN, sampled at 10–90%; the complete corpus supplies the common 100% endpoint. The other 493 reference sources remain fixed. Labels do not enter these rankings.
3. **Which cross-project connections are structurally critical?** Contract actual project groups, then analyze the resulting simple graph. Equal-byte groups induce cliques among represented projects, avoiding artificial articulation points caused by an arbitrary star anchor. Vertex weights are counts of DAppSCAN files. Remove each project only as a diagnostic; do not use these removals to construct a favorable evaluation split.
4. **What training remains for already fixed tests?** Keep the two 1,062-file development tests unchanged and restrict their historical DAppSCAN training population by each graph. Separately hold the diagnostic external 1,998-file cohort fixed. Source-reported positives and proxy zeros are counted separately; a zero is not a verified clean label.

The main run has 49 cohorts × 13 thresholds × 3 policies × 2 comment normalizers = **3,822 graph outcomes**. Runtime was 118.88 seconds. Configurations, input hashes and executable snapshots precede all outcomes. The historical selector retains files with a published SWCsource entry and adds at most 20 remaining files per project using `random.Random(0)` and sorted project traversal. It is a label-informed, capped comparator, unlike the new hash samples.

## Concentration comes from the union of relations

On all 21,457 DAppSCAN files, with the other 493 reference files available as potential intermediates:

| Jaccard threshold | Project-only giant | Clone-only giant | Joint giant | Joint components | Effective joint components |
|---:|---:|---:|---:|---:|---:|
| .70 | 1,132 (5.28%) | 269 (1.25%) | 20,934 (97.56%) | 167 | 1.051 |
| .80 | 1,132 (5.28%) | 100 (0.47%) | 20,588 (95.95%) | 198 | 1.086 |
| .90 | 1,132 (5.28%) | 60 (0.28%) | 20,025 (93.33%) | 235 | 1.148 |
| .95 | 1,132 (5.28%) | 50 (0.23%) | 19,622 (91.45%) | 259 | 1.196 |
| 1.00 | 1,132 (5.28%) | 39 (0.18%) | 19,321 (90.05%) | 287 | 1.233 |

The effective count is (N^2/\sum_c n_c^2), calculated on the DAppSCAN projection. A project connects its distinct files; lexical reuse then connects different projects. Their transitive union can therefore join many projects even when neither relation alone has a large file-level component. At .80, DAppSCAN alone and DAppSCAN plus the other reference corpora give the same 198 DAppSCAN components and 20,588-file giant.

**Denominators matter.** The earlier 89.25% was 5,879 of the *historical 6,587* DAppSCAN files after projecting the expanded graph onto that historical cohort. The new 95.95% is 20,588 of *all 21,457* DAppSCAN files. The original capped graph itself had 5,408/6,587 = 82.10%. These are different projections, not conflicting measurements.

## Exact-identity controls distinguish representation from approximate matching

A Jaccard threshold of 1 means equality of normalized shingle **sets**, not byte identity or equality of ordered source text. An additional frozen control compares stricter equality relations directly:

| Relations added to project membership | DAppSCAN giant | Components | Historical DAppSCAN in giant |
|---|---:|---:|---:|
| Exact raw-byte equality | 3,608 (16.82%) | 454 | 936 |
| Exact normalized-stream equality, nonempty streams | 19,298 (89.94%) | 288 | 5,034 |
| Exact normalized-stream equality, including empty streams | 19,321 (90.05%) | 287 | 5,055 |

Thus approximate near-match links are not necessary for a giant component under this lossy representation. The representation and project closure jointly matter. This control does not isolate identifier collapse, numeric collapse, comment removal, or formatting individually; the separate representation experiment addresses those alternatives.

Six DAppSCAN sources have an empty corrected normalized stream. The inherited shingle construction gives each empty stream a common empty shingle. Explicitly suppressing empty-stream equality in the identity control changes the giant by 23 full-corpus files and 21 historical files. This is a meaningful edge-policy sensitivity, but does not explain the giant itself. The separate representation audit keeps the empty nodes and suppresses their lexical edges; it must be described as an explicit policy change, not as a rerun of an identical baseline. The main threshold experiment here intentionally preserves the earlier policy.

## Source coverage changes the observed graph

At Jaccard .80, the mean giant fraction across five independently ranked, nested file samples is:

| DAppSCAN retained | Mean giant fraction | Minimum–maximum across five seeds |
|---:|---:|---:|
| 10% | 57.70% | 45.59–64.85% |
| 20% | 77.30% | 73.18–79.84% |
| 30% | 84.15% | 81.99–85.69% |
| 50% | 90.59% | 89.72–91.47% |
| 70% | 93.89% | 93.59–94.60% |
| 90% | 95.33% | 94.77–95.73% |
| 100% | 95.95% | Complete corpus; common endpoint |

The corresponding mean is 20.10% at 10% coverage and 90.05% at complete coverage for threshold 1.00. These are descriptive sampling ranges, not inferential confidence intervals. Uniform sampling of files changes the representation of projects; it is not uniform sampling of projects, a temporal deployment model, or an estimate of a formal critical threshold. The full per-seed curves permit that distinction to remain visible.

## Project bridges are heterogeneous and mostly peripheral

At .80 the full reference graph contracts to 801 vertices: 608 DAppSCAN projects, 50 SolidiFI base-contract groups and 143 SmartBugs groups. It has 6,848 simple cross-project links, 55 topological bridges and 26 articulation vertices whose removal separates positive DAppSCAN file mass. Deleting one project separates at most **82 additional DAppSCAN files**, excluding the deleted project's own files. The corresponding maximum smaller side after deleting one simple bridge is also 82 files. This does not support an explanation in which one obvious bridge alone holds the giant together.

The highest-impact .80 project bridge connects Tenderize and Livepeer. Its witness pair is `Faucet.sol` and `LivepeerTokenFaucet.sol`, with Jaccard 0.804878 and two supporting lexical file pairs. The smaller side has 82 files. Neither witness contains a lexical `library` or `interface` declaration. The next example connects PieDAO's `IAToken.sol` and Fei's `IFeiRewardsDistributor.sol`, with Jaccard 0.809524 and one supporting pair; both have interface declarations and the smaller side has 36 files. A bridge is a **project-to-project relation**; the selected witness does not establish that either file is individually indispensable.

The 80 distinct selected endpoint witnesses for the DAppSCAN-only .80 bridge set include 45 files with a library or interface declaration; only 16 have such declarations without any contract declaration. In the full DAppSCAN corpus those counts are 7,157/21,457 and 6,023/21,457. These are lexical declaration counts, not validated semantic-library roles or an estimated prevalence among all causal connectors. The witness set is purposive; filenames and declarations alone cannot distinguish reusable infrastructure, application logic, tests, mocks or inherited wrappers reliably.

`description_20261025_v1/ranked_bridge_evidence.csv` supplies node IDs, source paths, raw hashes, support counts and `not_reviewed` semantic status for 60 ranked diagnostic cases. No third-party source text or annotations are copied. The source inventory verifies the raw hashes of all 24,131 local files before collecting declaration metadata.

## Training feasibility is conditional on the fixed test and graph rule

The two earlier development tests remain fixed at 1,062 files each. Training is drawn from the historical 6,587 DAppSCAN files, after excluding every component touching the test:

| Joint threshold, complete reference graph | Seed-2 test: training files | Reentrancy / unchecked positives | Seed-4 test: training files | Reentrancy / unchecked positives |
|---:|---:|---:|---:|---:|
| .80 | 13 | 0 / 1 | 10 | 1 / 0 |
| .90 | 310 | 4 / 1 | 308 | 5 / 0 |
| .95 | 513 | 8 / 7 | 510 | 9 / 6 |
| 1.00 | 671 | 11 / 9 | 669 | 12 / 8 |

Higher thresholds restore both proxy classes for some settings, but none restores the prior 20-positive training screen for both tasks in these tests. This is not a prohibition on every possible evaluation design. The tests were selected during development; no new confirmatory status is claimed.

For the separate fixed **external diagnostic 1,998-file cohort**, the corrected complete joint graph retains 691 historical DAppSCAN training files at .80, with 23 reentrancy and 18 unchecked positives. At .95 it retains 1,345 with 35/28 positives; at 1.00, 1,502 with 37/30. These are metadata sensitivities. They neither choose a preferred threshold using scores nor certify external labels or eligibility. Project-plus-byte-equality alone retains all 6,587 historical DAppSCAN training files for this external cohort, illustrating how strongly the declared dependence rule changes the task.

## Verification and limits

- Six focused graph tests cover removed star anchors, raw-equality clique contraction, weighted chains, cycles, zero-weight connecting vertices and disconnected graphs. Three additional declaration tests check strings/comments and mixed application/library files.
- The main computation reproduces all six previously saved complete joint graphs at .70/.80/.90 and verifies threshold refinement and contracted/file partition equivalence.
- A separate union-find implementation reproduces 96 graph partitions across four cohorts, four thresholds, three policies and two normalizers. It independently reconstructs group relations, but reuses the saved exhaustive lexical pairs; it is not an independent all-pairs source search.
- All five complete SHA256 sampling rankings are recomputed independently.
- The independent review agent removed all 801 contracted vertices and checked all 55 reported bridges using SciPy at corrected .80, reproducing all weighted articulation and bridge counts exactly. The generator docstring's phrase “edge weights” is imprecise: the implementation and all reported removal weights are **vertex DAppSCAN file counts**.
- Comment-aware normalization does not change either fixed-test training count or its positive counts anywhere in this grid, nor the external training counts. Some clone partitions and external component counts change. At .94 a single external source separates from a large component, changing many canonical representative IDs; pairwise partition comparisons distinguish this from thousands of independently moved sources.

Lexical components remain dependency proxies rather than proven semantic families. Normalized similarity can collapse distinct code, while file-level comparisons can miss partial reuse. Published findings do not make proxy zeros reliable negatives. The sample experiment investigates file coverage within one pinned corpus, not an unseen future population. Human semantic review, alternative representations and model comparisons are distinct tasks; this package makes no claims on their behalf.

## Reproduction and files

Run from the repository root with the pinned raw corpora available:

```bash
.venv/bin/python -m pytest -q papers/security_evaluation/revision1/graph_mechanism/test_mechanism.py papers/security_evaluation/revision1/graph_mechanism/test_describe.py
.venv/bin/python papers/security_evaluation/revision1/graph_mechanism/run_mechanism.py --out NEW_RUN_DIRECTORY
.venv/bin/python papers/security_evaluation/revision1/graph_mechanism/verify_and_external.py --run NEW_RUN_DIRECTORY --out NEW_VERIFICATION_DIRECTORY
.venv/bin/python papers/security_evaluation/revision1/graph_mechanism/describe_mechanism.py --run NEW_RUN_DIRECTORY --out NEW_DESCRIPTION_DIRECTORY
.venv/bin/python papers/security_evaluation/revision1/graph_mechanism/identity_controls.py --out NEW_IDENTITY_CONTROL_DIRECTORY
```

The main run directory contains component and training curves, population ranks, complete memberships for four reference scopes, threshold-specific articulation and bridge metadata, and .80 contracted graph links/vertices. The verification directory contains graph checks, actual partition comparisons and fixed-external-test sensitivities. The description directory contains source-reference-only evidence. The identity-control directory separates byte equality from normalized-stream equality. All existing earlier experiment directories remain unchanged.
