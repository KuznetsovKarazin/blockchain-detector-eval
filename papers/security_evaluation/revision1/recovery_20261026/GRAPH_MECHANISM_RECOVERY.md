# Graph artifact recovery, 26 October 2026

All **15 missing graph-mechanism artifacts** listed in the partial checkpoint's `publication_omissions.json` have been recomputed locally and restored to their original paths. Every restored file matches both its original recorded SHA-256 and its original Git blob SHA-1. No existing frozen file was overwritten. No model was fitted or scored, and this recovery performed no upload or publication.

The starting checkpoint was `e011968b4d92f407cc515993ef91441444c9fee0`. Original frozen configurations and executed source snapshots, rather than remembered conversational counts, controlled reconstruction. The eight graph inputs and three original source-code hashes matched their recorded values. NumPy 2.3.5, pandas 2.2.3 and SciPy 1.17.0 also matched the recorded environment.

## What was replayed

| Stage | Fresh computation | Missing files restored | Comparison |
|---|---|---:|---|
| Graph tables | 312 complete-cohort partitions, six contracted project-edge tables, five deterministic population rankings | 13 | All 15 generated gzip tables matched original SHA-256, including two existing files used as controls |
| Identity controls | Unchanged original `identity_controls.py`, into a new ignored directory | 1 | All five stable outputs matched original SHA-256 |
| Declaration inventory | Unchanged original `describe_mechanism.py`, checking all 24,131 raw-source hashes | 1 | Source inventory, two numeric metadata tables and both copied source files matched original SHA-256 |

The graph stage regenerates the precise missing binary artifacts from the saved exhaustive lexical pairs and node metadata. It rebuilds project/hash equivalence links within each selected population. It does not claim a new all-pairs lexical search or a rerun of the 45 sampled-cohort label aggregates, neither of which is needed to reconstruct these files. No scientific rule, threshold, seed, candidate membership or label mapping changed.

There are **26 stable-output comparisons, 25 byte-exact matches**. The sole difference is the fresh description configuration: its replay command uses absolute input paths where the old configuration used relative paths. The old configuration remains unchanged. This difference does not affect numeric tables, code or the restored compressed source inventory. Fresh recovery configurations and runtimes are recorded separately; they are not represented as surviving original execution records.

## Evidence

- `graph_mechanism_recovery_summary.json` lists every restored path, size and both verified hashes.
- `graph_mechanism_{graph,identity,description}_recovery_config.json` records the recovery source hashes and checked inputs before each computation.
- `graph_mechanism_{graph,identity,description}_recovery_result.json` records every comparison, restoration decision and fresh runtime.
- `recover_graph_artifacts.py` is the local recovery wrapper. It exclusively creates a missing original path only when both original hashes match. It refuses a changed existing artifact and performs no network operation.

The fresh intermediate outputs remain in ignored `data/derived/recovery_20261026/graph_mechanism/{graph,identity,description}_stage_v1/`. The original frozen summary/configuration files remain intact. The historical omission list is also preserved; this new receipt records that its 15 graph entries are now locally restored. Publication status is a separate decision and is not changed by this local reconstruction.

To reproduce the recovery, use a fresh ignored output directory for each stage:

```bash
python papers/security_evaluation/revision1/recovery_20261026/recover_graph_artifacts.py --stage graph --out data/derived/recovery_20261026/graph_mechanism/graph_stage_repeat
python papers/security_evaluation/revision1/recovery_20261026/recover_graph_artifacts.py --stage identity --out data/derived/recovery_20261026/graph_mechanism/identity_stage_repeat
python papers/security_evaluation/revision1/recovery_20261026/recover_graph_artifacts.py --stage description --out data/derived/recovery_20261026/graph_mechanism/description_stage_repeat
```

Omitting `--restore-exact-missing` performs comparison only. Adding it permits local restoration under the two-hash rule; it never overwrites an existing file or uploads anything.
