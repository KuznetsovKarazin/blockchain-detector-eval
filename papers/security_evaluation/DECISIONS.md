# Article 1 decisions

These entries record implementation choices on 25 October 2026. They are not a preregistration. Historical development scores were already inspected before this study began. The external scoring gate remains closed.

## D01 Continue the existing branch

The remote branch `paper/security-evaluation` was cloned at `f3e5bccd124def4e1f3e60478ad928a71acd5b53`. It contains the starter package described in the author's prompt. Historical runs under `results/contracts/` remain immutable. New code, aggregate evidence, and run manifests belong to this paper's directory.

## D02 First compare feasible training pools

Use a label-blind hash-ranked 20 percent subset of the largest historical joint component as a development test. The complete joint component remains excluded from joint-disjoint training, including its files not selected for the test. This respects the full graph while permitting unrestricted training to contain related files. Testing on the entire component would make unrestricted and joint pools identical and would not provide the intended contrast.

The pilot uses the historical DAppSCAN population, reentrancy proxy labels, one fixed raw TF-IDF/LR method and sampling seed 0. Exact hash salt, rounding, paths, source snapshot, and configurations must be recorded before fitting. For each proxy-label value, all four regimes use the minimum eligible count. The selected test is only one joint component. Report descriptive differences, without bootstrap intervals, significance tests, or claims about new projects. Feasibility tables also retain unsuccessful designs.

## D03 Keep incomplete labels explicit

DAppSCAN zeros mean no published finding. Metrics against these zeros measure agreement with a proxy benchmark, not confirmed false-positive rates. Source-reported negative annotations in the external candidate are not independently adjudicated negatives. Unknowns and conflicting records remain separate. External category mappings and line-number validation must be resolved before a scoring population is frozen.

## D04 Preserve failures and review workload

Tool errors retain missing scores and explicit statuses. AP is reported on successfully scored, known-label records with coverage, and on a common-success subset for direct comparisons. Full-pipeline known-positive recall includes missed positives among failures. Unknown-label records consume review budget; their warnings are not false positives. Uniform tie handling reports expected counts and attainable ranges. Ratios of expected counts are identified as such.

## D05 Preserve rights and source evidence

Third-party Solidity files, compact labels, and private reviewer keys stay in git-ignored data directories. Published paper outputs contain our audit code, hashes, path references, derived predictions without copied labels, and aggregate findings. This is not a determination that source redistribution is permitted. Source snapshots and complete patches must accompany new computation, not merely a dirty-diff hash.

## D06 Freeze remains pending

The main protocol remains a draft until the eligible external population, family links, class mappings, reviewer decisions, configurations, workload policy and inference scope are resolved. Preparing a controlled development pilot does not authorize external scoring. No correspondence, manuscript submission, visibility change, DOI or release is performed by this cycle.

## D07 Preserve recovery provenance

The second-cycle working checkout and result files were lost. Recover sources from recorded edits, checkpoint them publicly, and rerun into new identified directories. Compare only against earlier hashes or aggregates actually recorded. A matching regenerated table does not imply all original runtime artifacts survived. See `RECOVERY_2026-10-25.md` and module-specific notices.

## D08 Isolate normalization sensitivity

Keep the historical normalizer unchanged. The alternative scanner changes comment recognition while retaining historical tokenization and identifier/numeric normalization. Compare every source and full dependency graph at thresholds 0.7, 0.8 and 0.9. Do not silently replace historical model inputs with corrected inputs. This remains lexical sensitivity, not proof of semantic equivalence.

## D09 Count-based development design selection

Enumerate 95 deterministic test candidates and save operational count/concentration screens before evaluation. Membership selection uses hashes; choosing among candidates subsequently uses proxy-label counts after an observed pilot. The two passing historical designs are complementary development samples, not untouched confirmation or independent replications. Their 1,062-file tests share 961 files, cover only 16.12% of the historical DAppSCAN population, and exclude its giant component. Freeze both bundles before comparative scores and assess full-graph restrictions before any expanded campaign. Operational screens are not a power calculation.

## D10 Publication and scientific gates are distinct

The author explicitly authorized continued research and publication to the existing branch without repeat permission prompts. Publish our code, aggregate results, hashes and path metadata; preserve the exclusion of third-party source copies and private annotation keys. The authorization does not remove external eligibility, expert-adjudication or inference requirements. Preparatory configurations and automated reviews must not be counted as completed model experiments or independent human reviews.

## D11 Publish infeasibility instead of scoring invalid comparisons

The full observed graph at Jaccard 0.8 invalidates both selected historical joint-disjoint bundles: only 13 and 10 training files remain, with one primary class lacking positives in each. None of the same 95 candidate tests passes the original operational screens. Block the two prepared 160-job comparative campaigns, retain their frozen manifests and add an enforceable execution gate. This is a feasibility result, not a failed model-performance experiment. A future design must address the evidence without breaking transitive components to obtain desired sample sizes. Population expansion and exhaustive edge discovery change together in the initial historical-versus-full comparison; distinguish them with a metadata-only graph-scope ablation before attributing the result.

## D12 Study the mechanism under multiple stated dependency definitions

The author requested both the graph-mechanism and model-comparison directions of the scientific review. Revision 1 therefore examines 13 lexical thresholds, project-only/clone-only/joint relations, and five deterministic nested source samples without choosing a graph because it yields favorable scores or training sizes. Preserve all prior graph outputs. Contract actual projects and expand equality groups correctly before interpreting articulation points; an arbitrary star encoding is not evidence of a real bridge. Report file-population and historical-projection denominators separately. Large connected components establish a consequence of the stated grouping rule, not semantic equivalence or a formal percolation transition.

The completed exact-identity controls show why the representation must be explicit: project plus byte equality has a 16.82% full-DAppSCAN giant, versus 90.05% for project plus normalized-stream equality. Do not attribute this whole difference to a single normalization operation without its own control. `revision1/graph_mechanism/` contains the pre-execution configurations, results and independent checks.

## D13 Keep representation and empty-stream policy changes explicit

Compare string-aware full-file normalization, identifier/number preservation, explicit library/interface masking, containment and retained-segment shingling without deleting graph nodes or known structural relations. Lexical masking is not validated semantic library identification. An empty or unparseable representation has explicit status; the new representation experiment supplies no lexical links from such a representation. This differs from the inherited empty-shingle policy and is isolated as a sensitivity, not silently substituted into the earlier graph or protocol B. The six empty streams explain a 21-file historical training/giant difference in the relevant comparison, not the main giant-component result. Segmented shingling is a separately identified implementation control; it is not an undisclosed replacement of concatenated outputs.

## D14 Measure conditional training variation without reopening blocked campaigns

The new executed sampling diagnostic retains the original 1,082-file/21-positive development test and matches each training set to 1,179 files/31 positives. It uses 20 paired training draws × four historical regimes × four methods with estimator seed zero, plus a separate tree-estimator seed panel on the fixed joint pool. The joint pool is the entire eligible pool and has one unique membership, so identical evaluations reuse its fit. Distinguish 360 logical evaluations from 282 physical fits. The unused v1 preflight remains unscored; v2 is the completed run.

AP ranges, quantiles and paired differences measure training variation conditional on this already inspected, dependent test. They are not new-project confidence intervals, causal leakage estimates, or independent replications. Report the exact finite-sample strict-random-ranking AP expectation rather than treating prevalence as its exact value. No exchangeability p-value is asserted. Both previously blocked outside-giant campaigns and the external-scoring gate remain unchanged.

## D15 Prepare a probability-based external review without inventing judgments

Retain the fixed diagnostic 1,998-file external cohort and the 691-file training manifest under the previously declared complete graph at 0.8. Prepare 180 probability-sampled file-class cases from 170 files in 17 strata, with recorded inclusion probabilities and design weights. Two independent human specialists must review every case. Keep the 17-case identity census and the previous purposive 106-case packet separate from this estimation sample. Preserve unknowns and disagreements; kappa is supplementary, not a test of truth.

Protocol B remains a draft, with blank forms, unnamed reviewers and no external fits or scores. Lexical input and compiler-plan checks do not count as model, compiler or Slither execution. Complete the feature/compiler/weighted-metric/class-mapping prerequisites and prospective review sign-off before an overall protocol freeze. Seal both initial reviews and adjudication before external scoring. Module-level executable freezes for preparatory computations do not satisfy these later scientific prerequisites.

## D16 Revise the article around completed evidence and disclose prior work

The current manuscript is `manuscript/DRAFT_REVISION1.md`, titled *Population Coverage and Dependency-Aware Evaluation of Smart Contract Vulnerability Detectors*. The earlier draft remains available. The revision combines the controlled population ablation, graph/representation mechanisms, conditional model variation, source audit and prospective external protocol; it does not claim completed human label validation or independent external performance. Source-verified literature, figure provenance and the relationship to the forthcoming book and existing Zenodo results are recorded separately. Publication of this research package does not register a protocol, mint a DOI, send correspondence or submit the manuscript.
