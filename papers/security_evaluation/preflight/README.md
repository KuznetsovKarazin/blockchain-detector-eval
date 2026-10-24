# Existing split readiness audit

Handoff date: **2026-10-25, Europe/Rome**. The actual execution time is saved
separately as `generated_utc` in `summary.json`.

This script rereads the historical C1/C2 metadata at repository snapshot
`2c2c7723cb9fa42ff46fb6f252652056a74f9223`. It does not train a model, run a
new fixed-test experiment, construct four matched training pools, inspect
an external corpus, or estimate a leakage effect.

## Reproduce from the repository root

Python 3 standard library only. If this directory is placed at
`papers/security_evaluation/preflight/`, run:

```bash
python papers/security_evaluation/preflight/audit_existing_splits.py \
  --folds results/contracts/c2_20261024_004314/folds.csv \
  --audit results/contracts/c1_20261022_141306/audit.json \
  --manifest results/contracts/c2_20261024_004314/manifest.json \
  --source-commit 2c2c7723cb9fa42ff46fb6f252652056a74f9223 \
  --handoff-date 2026-10-25 \
  --out papers/security_evaluation/preflight
```

The source files are read-only. SHA-256 and byte length of each input are
recorded in `summary.json`. The first local execution used flattened download
filenames; the downloaded bytes were verified against the Git blob hashes.
Rerunning from the repository changes the recorded basenames and execution
timestamp, but the source SHA-256 values and numerical results should agree.

## Outputs and observed result

- `fold_inventory.csv`: all **720** historical dataset/class/protocol/seed/fold
  rows with the actual train/test and positive counts.
- `protocol_summary.csv`: minima, medians, maxima and run counts by dataset,
  class and protocol.
- `matched_size_comparison.csv`: training-size multisets and the share of
  predictions produced by the smallest-training fold, separately for
  `random_matched` and `safe`.
- `summary.json`: source hashes, original run provenance, observed protocols,
  the dominant joint-group fold and explicit limits of the audit.

The inputs contain DAppSCAN and SolidiFI folds for four classes, three seeds
and six protocols. SmartBugs is present in the corpus inventory, but it is
not a within-corpus fold population in this CSV.

For DAppSCAN, the `safe` protocol includes a test fold of **5,408 / 6,587
files (82.10%)** with only **1,179 training files**. In the representative
reentrancy/seed-0 comparison, the training sizes are:

| Protocol | Sorted training sizes | Test predictions using the smallest training pool |
| --- | --- | --- |
| `safe` | 1,179; 6,292; 6,292; 6,292; 6,293 | 5,408 / 6,587 (82.10%) |
| `random_matched` | 1,179; 5,269; 5,270; 5,270; 5,270 | 1,318 / 6,587 (20.01%) |

Thus the existing `random_matched` condition is a **partial** training-size
control. It does not match the number of test predictions exposed to each
training size. Equal fold IDs or counts would not establish equal test
membership in any case.

`project`, `random_matched`, `local_random` and `local_safe` are present.
There is no named clone-only protocol in these folds. A shared fixed test
and four pools matched for both total size and positive count are **not
demonstrated** by these inputs. This is a statement about available evidence,
not a claim that hidden or unpublished experiments do not exist.

The 5,408-file figure describes a fold under the joint grouping constraint.
It does not mean that those files are pairwise clones. The script does not
reconstruct the dependency graph or establish a causal effect of leakage.
DAppSCAN no-finding labels remain proxy labels rather than verified negatives.

## Inputs for the next fixed-test experiment

Start with `results/contracts/c2_20261024_004314/groups.parquet` for file
identities and grouping fields. The C2 exporter writes `file_id`, `dataset`,
`path`, `group` (project/base-contract), `comp` (clone component),
`safe_group` (joint component) and `local`; verify the actual Parquet schema
before use. `assignments.parquet` in the same directory retains historical
assignments and can be used to validate reproduction of earlier folds.

Load code and labels from the original pinned datasets documented in
`docs/DATA.md`; retain source-specific label status and provenance. Build
new fixed-T inclusion/exclusion manifests from these file identities and
constraints. Counts alone cannot construct or verify that experiment.

The snapshot commit identifies the files read for this audit. The historical
C2 manifest separately records its original run commit, dirty-file list,
diff hash and reused lexical results. These provenance records describe
different stages and must not be collapsed into a single execution commit.
