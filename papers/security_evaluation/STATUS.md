# Article 1 status — 25 October 2026

Working title: **Project Dependence and Label Provenance in Smart Contract Vulnerability Evaluation**.

## Verified starting point

Repository: `KuznetsovKarazin/blockchain-detector-eval`; branch: `paper/security-evaluation`.
Book/source baseline: `2c2c7723cb9fa42ff46fb6f252652056a74f9223`.
At the initial check, the paper branch and main were identical. This starter package is an additive continuation in the paper branch. The main branch and historical experiment outputs are not modified by this work.

## Task state

| Task | State | Evidence / next condition |
| --- | --- | --- |
| P1.01 protocol | Draft saved, not frozen | `protocol.json`; resolve cohort eligibility, grouping and exact configurations before external scoring |
| P1.02 external data | Preliminary inventory completed; independence unresolved | `external_audit/`; reconcile identities and labels, check cross-corpus hashes/clones/projects, establish redistribution terms |
| P1.03 controlled comparison | Existing folds audited; new fixed-T experiment not implemented | `preflight/`; construct four pools from actual groups and file identities |
| P1.04 confirmatory external evaluation | Not run | Freeze models and eligible test manifest first |
| P1.05 labels/workload | Historical C3/C4 available; new human audit not performed | Blind review package and an independent subject specialist are needed |
| P1.06 final analysis/manuscript | Not ready | Depends on controlled and external results |

No models were trained, no external scores were computed, and no new accuracy/AP claim is made by this starter package.

## New readiness findings

For DAppSCAN/reentrancy/seed 0, the historical `safe` fold with training size 1,179 generates 5,408/6,587 = 82.10% of OOF predictions. The corresponding minimum-sized `random_matched` fold generates 1,318/6,587 = 20.01%. Other training-fold sizes also differ. The old control therefore does not match how much of the test population is scored by small-training models. This is a reanalysis of split metadata, not a causal estimate of leakage or a new model experiment.

The Salzano candidate's pinned repository has 2,182 compact-manifest rows, 2,180 distinct source/contract pairs, 2,181 Solidity paths and 2,178 distinct Solidity Git blobs. These quantities describe different units. Duplicate keys, cross-source identities and one source/manifest mismatch must be reconciled. Folder names `safe` and `vulnerable` do not substitute for final class labels. No residual cohort is yet designated independent.

## Historical provenance limitation

The selected C2 manifest records execution at commit `40e792530b98dd8a83f291d95197d7cd55d981d0` with `git_dirty=true`, a diff hash and reused lexical rows. The present snapshot preserves the historical outputs and current source; it is not by itself proof of a clean recreation of every historical run. Retain this distinction. New runs require a clean commit or the complete source patch/archive, plus environment and input hashes.

## Next executable work

1. Reconcile the external source/manifest identities; obtain original corpus snapshots locally and perform exact/normalised/clone/project overlap checks.
2. Inspect the actual schema of `results/contracts/c2_20261024_004314/groups.parquet` and `assignments.parquet`. Build fixed T and four feasible training pools; match training object and positive counts without splitting joint dependency components.
3. Prepare blinded label-review records with evidence. AI checks do not replace an independent human reviewer.
4. Run one development-only pilot with one class, one model and two valid matched regimes; record runtime, RAM and cache size.
5. Freeze the main protocol before external scoring.

New results belong under `papers/security_evaluation/runs/<unique_run_id>/`. Preserve `results/contracts/`. Record unsuccessful runs and infeasible cells. Store third-party raw data outside tracked paper outputs unless redistribution is explicitly permitted.

