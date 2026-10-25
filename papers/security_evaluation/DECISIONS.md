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
