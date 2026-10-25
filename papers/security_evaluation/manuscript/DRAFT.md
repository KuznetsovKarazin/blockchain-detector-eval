# Project Dependence and Label Provenance in Smart Contract Vulnerability Evaluation

**Development manuscript — 25 October 2026. Not submission-ready.** This version reports completed development experiments and data audits. The main protocol is not frozen, no independent external model evaluation has been performed, and no human vulnerability reviews have been completed. Author details, related work, final references and the main confirmatory study remain to be completed. Repository links below are an evidence map, not a finished publication bibliography.

## Abstract

Smart-contract vulnerability evaluation requires decisions about related source files, annotation provenance and test populations. We examine these decisions using a matched development experiment and an external-corpus audit. On a common test of 1,082 DAppSCAN files, four training restrictions each retain exactly 1,179 training files and 31 reentrancy proxy positives. Raw-token logistic regression obtains average precision from 0.0277 to 0.0766, but the single test dependency component prevents a causal or independent-project interpretation. Auditing 2,181 proposed external paths against 21,950 reference paths identifies 17 source-reconciliation problems and 208 direct lexical overlaps at Jaccard 0.8. A diagnostic residual of 1,998 files still includes 186 transitively linked to reference data. String-aware comment removal changes 92 of 24,131 normalized streams without changing training-retention decisions. Of 95 development test designs, two pass operational screens under the historical graph; neither survives expansion to uncapped reference data, which leaves only 13 and 10 eligible training files at threshold 0.8. No candidate passes the expanded-graph screens at any tested threshold, 0.7, 0.8 or 0.9. The resulting feasibility failure, rather than a further model ranking, is the principal methodological finding. Independent external performance and verified vulnerability precision remain unestablished.

## 1. Introduction

A file-level benchmark can contain related project files, repeated code and annotations from different procedures. Comparing split policies also changes meaning when each policy uses a different test or training size. Conversely, enforcing observed dependencies can leave too little training data or too few informative test groups.

Annotation provenance creates a separate interpretive issue. In the DAppSCAN adapter used here, a zero indicates that no corresponding finding was published for the file. It is not an independently confirmed absence of a vulnerability. Metrics computed against these values therefore describe agreement with a proxy benchmark. Source-reported annotations in a proposed external corpus require their own identity and location checks; they do not become adjudicated ground truth merely because the corpus is external.

We ask what descriptive score differences remain under a common test and matched training counts; how source reconciliation and transitive dependencies affect a candidate external evaluation; and which fixed-test designs remain feasible. Workload and independent external evaluations remain incomplete.

**Related work placeholder.** A source-verified synthesis of smart-contract benchmarks, clone-aware evaluation, label validity and workload-based assessment is required before submission. This draft makes no priority or literature-wide prevalence claim.

## 2. Materials and methods

### 2.1 Data versions and annotation scope

The historical development population contains 7,080 paths: 6,587 DAppSCAN, 350 SolidiFI and 143 SmartBugs. The uncapped reference audit includes all 21,457 DAppSCAN paths, giving 21,950 reference paths. The proposed external candidate is the Salzano repository's saved contract corpus, comprising 2,181 paths. The combined audit population is therefore 24,131 paths. These are source-path counts, not counts of independently verified contracts, projects or deployments.

| Source snapshot | Pinned revision |
| --- | --- |
| DAppSCAN | `66a56619c44770e05c2db600fa6468115ff0dcd5` |
| SolidiFI-benchmark | `4b0573e1b3f7031396de6f48f7f3e7380222ad3a` |
| SmartBugs-curated | `230e649123477eff332742a59a1c7cc6dc286cab` |
| Salzano candidate | `da079440bf2cf4fd803c864ef29aeea8a3da50c3` |

Reentrancy and unchecked calls are the primary classes. The source category `unchecked_low_calls` maps to `unchecked`. Candidate source positives, explicit no-finding markers, absence of a class in a nonempty annotation, and unresolved identity or location are retained as distinct provisional statuses. Binary external targets remain unassigned. No pooled accuracy result combines the different annotation regimes.

### 2.2 Fixed-test development comparison

The historical project and clone relations are joined transitively over all 7,080 original rows before restricting the experiment to DAppSCAN. Clone discovery used LSH candidates and CRC32-shingle Jaccard verification. The largest joint component contains 5,408 files. A label-blind hash ranking selects 1,082 files, the ceiling of 20%, as the common test. It contains 21 reentrancy proxy positives and only three unchecked-call proxy positives; the scored pilot addresses reentrancy only.

Four eligible training pools exclude, respectively: the exact test objects; every project represented in the test; every observed clone component represented in the test; or every full joint project-and-clone component represented in the test. For each proxy-label value, the minimum eligible count across the pools is selected using a common deterministic ranking. Each fitted training set contains 1,179 files and 31 proxy positives.

The raw-token TF-IDF vocabulary and sparse scaler are fitted on training data only. Logistic regression uses fixed historical settings without tuning, preserved with memberships and executed source snapshots before scoring. Average precision (AP) is computed against proxy labels. With one test component and one paired training draw, we report no confidence interval or significance test.

### 2.3 Source and dependency audit

Candidate records are reconciled by source and identifier rather than by an unqualified first identifier match. Source line counts are compared with annotated locations. Exact-byte hashes, equal normalized token streams and lexical similarity are separate checks. The exhaustive screen computes intersections of normalized token five-gram sets represented by 128-bit digests, at Jaccard thresholds 0.7, 0.8 and 0.9. It has no LSH retrieval stage; its exactness is conditional on this representation, not semantic equivalence.

Reference project relations, repeated candidate identifiers and lexical edges are joined over the complete audit population before restricting a cohort. The diagnostic cohort excludes the previously used curated source, quarantines unresolved source records and then repeated identities. It is not an adopted final external test. A preferred response to dependency is to examine feasible training restrictions while preserving the intended test population; direct-neighbor removal alone does not establish transitive separation.

### 2.4 Normalization and design sensitivity

A separate lexical scanner recognizes comments while preserving quoted strings and escapes. It replaces only the legacy comment-removal stage; historical identifier, number and token collapsing remain unchanged. Scanner errors would be explicit failures, without fallback to an empty stream or legacy normalization. No historical feature file is modified.

The design audit enumerates 95 deterministic candidates across five seeds, varying test fraction and whether the sample comes from the whole historical population, its giant component, its remainder, or whole components of that remainder. Individual candidate construction is label-blind. Subsequent screening uses proxy-label counts, so selecting designs that pass is label-informed. The screens require, for both classes, at least 20 test positives, 20 matched training positives and 500 training files, plus component dispersion and a nonidentical restriction contrast. These are operational criteria, not a power calculation. They were recorded before enumeration but after the earlier development pilot; the exercise is not an untouched confirmation.

## 3. Results

### 3.1 Matched development pilot

| Training restriction | Eligible files | Matched training files | Reentrancy proxy positives | AP |
| --- | ---: | ---: | ---: | ---: |
| Exact test objects excluded | 5,505 | 1,179 | 31 | 0.076554 |
| Project disjoint | 1,362 | 1,179 | 31 | 0.028044 |
| Clone disjoint | 4,706 | 1,179 | 31 | 0.027697 |
| Joint project and clone disjoint | 1,179 | 1,179 | 31 | 0.038475 |

All four fits converged. Test proxy prevalence is 0.019409; this is contextual prevalence, not an exact finite-sample random-ranking AP expectation. The unrestricted score is higher in this experiment, but joint restriction scores above project-only and clone-only restriction. The results do not show a monotonic penalty as restrictions accumulate. Matching fixes test objects, training size and positive count; it does not equalize training composition. Median nonempty training-file lengths are 42, 60, 43 and 60 lines across the four regimes. These differences, prior development-data inspection and the single test component preclude a pure causal interpretation.

### 3.2 External source reconciliation and overlap

The candidate's 2,182 compact-manifest rows correspond to 2,180 source/identifier keys and 2,181 paths. Seventeen paths require reconciliation: fourteen have annotated lines beyond saved source length, two have repeated keys with differing annotations, and one has no manifest row. An apparent ZEUS identifier mismatch is quarantined rather than silently reassigned. Location inconsistency does not by itself disprove the reported vulnerability.

| Check against the uncapped reference population | Candidate paths |
| --- | ---: |
| Equal raw bytes | 142 |
| Equal normalized stream | 148 |
| Direct Jaccard ≥ 0.7 | 328 |
| Direct Jaccard ≥ 0.8 | 208 |
| Direct Jaccard ≥ 0.9 | 166 |

All exact-byte overlaps come from the curated source. The diagnostic flow leaves 2,039 files after curated-source exclusion, 2,023 after source-reconciliation quarantine, and 1,998 after repeated-identity quarantine. The final diagnostic stage contains 46 reentrancy and 200 unchecked source-reported positives. At threshold 0.8, 65 files have a direct lexical relation to reference data, whereas 186 files in 11 proxy components are transitively connected. These include five reentrancy and two unchecked source positives. Thus the direct and transitive screens produce materially different dependency accounting. None of these proxy-component counts establishes independent real-world families.

### 3.3 Full-graph training restrictions

Holding the 1,998-file diagnostic candidate fixed, we exclude historical training files connected to it in the complete 24,131-node graph. At threshold 0.8, only 691 of 6,587 DAppSCAN files remain, containing 23 reentrancy and 18 unchecked proxy positives. Retention is 418 files at 0.7 and 1,085 at 0.9. At 0.8, another 350 SolidiFI and 134 SmartBugs files remain; combining their annotation regimes would obscure the small DAppSCAN support.

Independent SciPy component reconstruction verifies all 12 partitions across two normalizers, three thresholds and two address-link policies. String-aware normalization removes 14 lexical edges at 0.7 and changes none at 0.8 or 0.9; no historical training-retention decision changes. Adding 80 equal-address edges changes no partition. Equal-looking addresses remain conservative proxies because deployment networks are unknown. These restrictions establish separation only relative to the recorded graph, while demonstrating a substantial cost in retained training coverage.

### 3.4 Normalization and feasible tests

The string-aware analysis changes 92 of 24,131 normalized streams: 35 candidate files, 50 DAppSCAN files and seven SolidiFI files. It produces zero scanner errors. Fifty changed files contain comment-like markers within literals. The remaining 42 expose a separate ordering problem: the legacy block-comment pass can begin at `/*` inside a true line comment. The rerun's complete metadata CSV matches the previously recorded SHA-256, as does the 42-case diagnostic CSV. This supports deterministic reproduction of those outputs, not semantic validation of the normalizer.

Only `outside_p90_seed2` and `outside_p90_seed4` pass every operational design screen under the historical graph. Each selects 1,062 files, or 16.12% of historical DAppSCAN, outside its giant component. They contain 29/27 reentrancy and 20/22 unchecked proxy positives in 213/216 historical joint components. Matched training sizes are 5,422/5,418. Joint restriction removes only 103/107 additional eligible files relative to unrestricted training, approximately 1.86%/1.94%. The tests share 961 files, or 90.49% of each test; they are not independent replications.

Rechecking these fixed test objects against the expanded graph reverses their feasibility assessment. At threshold 0.8, the historical joint training sets contain 5,409/5,408 files connected to the respective tests. Valid expanded-graph joint exclusion leaves only the following:

| Fixed development test | Historical joint train | Expanded joint train | Reentrancy positives retained | Unchecked positives retained |
| --- | ---: | ---: | ---: | ---: |
| `outside_p90_seed2` | 5,422 | 13 | 0 | 1 |
| `outside_p90_seed4` | 5,418 | 10 | 1 | 0 |

All 95 frozen candidate tests fail the original operational count-and-dispersion screen at every tested threshold: 0.7, 0.8 and 0.9, under both normalizers and both address policies (1,140 design–graph combinations). At 0.8 the two selected designs cannot support both binary classifiers because one class has no training positives. At 0.9, retained training rises to 310/308 files but still fails the screens. The proposed comparative campaign is blocked before scoring; frozen memberships remain diagnostic evidence. This establishes failure for these 95 proposals under the declared conservative graph, not universal impossibility of a valid design.

A bounded ablation at 0.8 separates the changed edge-discovery procedure from population expansion. It regenerates project and identifier links within each population before computing components, avoiding lost connections from merely filtering a star-shaped edge list. The table projects each graph onto the same 6,587 historical DAppSCAN files; training counts refer to the two fixed tests above.

| Graph | Graph population | Projected DAppSCAN components | Largest projected component | Joint train, seed 2 / seed 4 |
| --- | ---: | ---: | ---: | ---: |
| A: saved historical graph | 7,080 | 227 | 5,408 | 5,422 / 5,418 |
| B: exhaustive, historical population | 7,080 | 227 | 5,408 | 5,422 / 5,418 |
| C: exhaustive, uncapped references | 21,950 | 198 | 5,879 | 13 / 10 |
| D: exhaustive, references plus candidate | 24,131 | 197 | 5,879 | 13 / 10 |

Both normalizers yield these results. A and B have identical projected partitions, while C reproduces the training collapse before external-candidate files enter the graph. D adds a projected merge without further changing these training counts. Thus, within this construction, adding uncapped reference paths is sufficient to explain the collapse for the two selected tests. This is graph attribution, not confirmation of real-world project identity or a causal detector-performance effect.

### 3.5 Computation and review status

The pilot took 19.95 seconds, with peak RSS 394.42 MiB. A resource-only profile measured raw LR, normalized LR, RF and LightGBM at 5.10, 2.74, 5.65 and 5.30 seconds on the saved joint pool. It computed no performance metrics. Its 12.5-minute projection for 160 fits is not a completed campaign or runtime guarantee.

A diagnostic review packet contains 106 file-class cases from 83 files and 25 proxy components, with 51 initial second-reader cases. Completed human assessments remain zero. Its purposive sampling cannot support a population label-error estimate. Automated code review and agent checks are not independent expert vulnerability adjudication.

## 4. Threats to validity

The principal label limitation is the distinction between a missing published finding and a verified negative. Lexical and project relations are incomplete proxies for dependency; historical LSH screening, lossy normalization and unknown deployment networks further limit independence claims. The 1,998-file residual is provisional and includes explicit population-changing exclusions. The two historically feasible tests omit the giant component, strongly overlap and fail expanded-graph feasibility. Their historical component counts cannot justify a new-project performance claim. Expanded-graph edges may also join semantically distinct code through the lossy representation, so component failure is conditional on that declared screen.

The pilot controls several quantities but leaves composition differences and uses one test component. No external model comparison or four-method scientific campaign has been completed. Runtime measurements are host- and workload-specific. Source redistribution permissions remain unresolved; tracked outputs contain original audit code, hashes, path metadata and derived results, not third-party source files or row-level annotation keys.

The original scratch checkout was lost during development. First-cycle evidence was restored from a saved Git bundle. Second-cycle sources were reconstructed from recorded edits and rerun in separately named directories; recovery notices distinguish regenerated outputs, matching prior hashes and unavailable original artifacts. Historical results were not silently replaced. This recovery provenance must remain attached to the reproducibility package.

## 5. Completion requirements

Before submission, the study requires verified related work, source-identity resolutions, human label assessment and defensible family evidence or explicitly bounded dependency claims. The demonstrated full-graph feasibility failure requires a scientific scope decision or newly frozen valid manifests; relaxing components merely to fill training cells is not an acceptable repair. Any future external population must be frozen after eligibility review. Final metrics should preserve failures and unknowns, use the declared floor workload budget and tie policy, and separate source-proxy from adjudicated performance. Both the proposed complementary comparative campaign and external scoring remain blocked under their documented scientific gates.

## Evidence map

| Material in this draft | Repository evidence |
| --- | --- |
| Protocol and unresolved gates | [protocol.json](../protocol.json), [DECISIONS.md](../DECISIONS.md) |
| Matched pilot and composition | [pilot README](../runs/dev_fixed_t_20261025_v1/README.md), `composition.csv`, `pilot_config.json` in that directory |
| Source reconciliation and overlap | [source audit](../external_audit/SOURCE_AUDIT_2026-10-25.md), [full audit outputs](../external_audit/source_audit_full_20261025/) |
| String-aware sensitivity | [new normalization manifest](../normalization_audit/run_recovered_20261025/manifest.json), [recovery verification](../normalization_audit/run_recovered_20261025/RECOVERY_VERIFICATION.json) |
| Full-graph restrictions and checks | [training feasibility](../dependency_audit/string_aware_recovered_20261025/training_feasibility.csv), [graph verification](../dependency_audit/string_aware_recovered_20261025/independent_verification.json), [sensitivity comparison](../dependency_audit/comparison_recovered_20261025/verification.json) |
| Ninety-five designs and overlap | [design table](../design_feasibility/audit_recovered_20261025_v2/design_summary.csv), [design verification](../design_feasibility/audit_recovered_20261025_v2/recovery_verification.json) |
| Expanded-graph feasibility failure | [all-design sensitivity](../design_feasibility/expanded_sensitivity_recovered_20261025_v1/all95_joint_sensitivity.csv), [campaign gate](../design_feasibility/expanded_sensitivity_recovered_20261025_v1/CAMPAIGN_GATE.json) |
| Graph-population ablation | [ablation summary](../dependency_audit/graph_scope_ablation_recovered_20261025/summary.json), [partition transitions](../dependency_audit/graph_scope_ablation_recovered_20261025/partition_transitions.csv) |
| Resource measurements | [resource profile](../runs/resource_profile_20261025_v1/README.md) |
| Recovery provenance | [recovery notice](../RECOVERY_2026-10-25.md) |
