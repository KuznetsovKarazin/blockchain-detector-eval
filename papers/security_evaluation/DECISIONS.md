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
