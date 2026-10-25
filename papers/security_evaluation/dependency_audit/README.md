# Full dependency graphs and training feasibility

This cycle makes the training restriction executable. The diagnostic external
population remains fixed at 1,998 files. The graph is built **before** that
restriction, over all 24,131 source files: 2,181 external candidate paths plus
21,457 DAppSCAN, 350 SolidiFI and 143 SmartBugs files. Complete typed edges,
membership assignments and historical-training exclusion manifests are saved.
No model fitting, predictions, external scores or final eligibility decision
are part of this audit.

## Decisive finding

At the historical primary lexical threshold 0.8, restricting training by full
transitive components leaves **1,175 of the 7,080 historically used training
files**. Of the 6,587 historical DAppSCAN files, only **691 remain** (10.49%):
23 reentrancy proxy positives and 18 unchecked proxy positives. Those positives
occupy respectively 23 and 17 retained proxy components. All 350 injected
SolidiFI files and 134 of 143 SmartBugs files remain at this threshold.

The restricted two-class training problems are nonempty, but their composition
changes substantially. Mixing the retained sources gives 99 reentrancy and 170
unchecked positives; these include 50 and 100 injected SolidiFI cases. These
numbers are not evidence that the combined training labels have equal meaning.
DAppSCAN zero remains no published finding, not verified absence. The following
counts establish executable feasibility, not adequate statistical power or
confirmed external validity.

| Jaccard threshold | All retained training files | DAppSCAN retained | DAppSCAN reentrancy positives | DAppSCAN unchecked positives |
| --- | ---: | ---: | ---: | ---: |
| 0.7 | 836 | 418 | 17 | 15 |
| 0.8 | 1,175 | 691 | 23 | 18 |
| 0.9 | 1,570 | 1,085 | 29 | 22 |

These thresholds were defined before any external comparative score. Choosing
one because it gives a preferred model result would invalidate that separation.
The complete class/source counts, including proxy-zero counts, are available in
each run's `training_feasibility.csv`.

The external 1,998-file population retains 46 reentrancy and 200 unchecked
source-reported positives. At threshold 0.8 they occupy 43 and 129 proxy
components. Before training exclusion, 186 candidate files share components
with historical training data, including five reentrancy and two unchecked
positives. The exclusion manifests remove the entire connected upstream
components. Candidate files are not discarded to make that training feasible.

## Graph definitions and normalization sensitivity

Two grouping policies are reported for every threshold:

* `base`: original upstream project membership, repeated candidate identifiers,
  identical raw-source bytes, and normalized lexical clone edges. Project,
  identifier and equality relations are represented by deterministic star edges;
  their transitive connectivity equals that of the corresponding cliques.
* `address_expanded`: the same graph plus equal syntactically valid 20-byte
  address basenames across all sources. Chain identity is unknown, so these
  80 recorded links represent a conservative possible dependency. They do not
  assert verified deployment identity. In these data, they do not change the
  components or any training retention decision.

`legacy_full_20261025/` reproduces the historical regex comment-removal rule.
`string_aware_full_20261025/` uses the independently tested scanner from
`normalization_audit/solidity_scanner.py`. Its scope is limited to comment
handling inside string literals; token extraction and identifier/numeric-literal
collapse remain unchanged. UTF-8 decode replacement follows the inherited
loader policy; the separate normalization inventory flags one affected file.

The scanner changes 92 normalized streams and reports no lexical scan errors
on any of the 24,131 files. At threshold 0.7 it removes 14 lexical edges and
changes two canonical component representatives. At 0.8 and 0.9 the edge sets
and partitions are unchanged. **No historical training-retention decision
changes at any of the three thresholds.** Both sets of results are preserved;
the historical artifacts are not overwritten. This is a measured sensitivity
result for these particular sources, not proof of semantic clone correctness.

All 2,181 legacy candidate component IDs at threshold 0.8 reproduce the previous
full-source audit exactly. All 24,131 legacy and corrected normalized hashes
also agree with the independently generated normalization inventory.

## Outputs and safeguards

Each run provides:

* `config_before_graph.json`, source snapshots and hashes, upstream clean pinned
  revisions, all raw and normalized source hashes, and annotation-input hashes.
* `nodes.csv`, `edges.csv`, and `memberships.csv` covering the complete source
  population. No upstream row-level annotation targets are redistributed.
* Six `training_exclusion_*.csv` manifests covering all 7,080 historical training
  records, with component IDs, retained/excluded state, and exclusion reasons.
* `training_feasibility.csv`, `candidate_component_counts.csv`, and a measured
  resource/run summary.

The generator checks threshold monotonicity, full membership of every persisted
edge, and an empty intersection between retained-training components and
candidate components. A separate verifier reconstructs all twelve graph
partitions with SciPy's undirected `connected_components`, checks every retained
training decision, independently rejoins historical labels for aggregate
positive counts, and verifies the executed source snapshots. All checks passed.
The 7,080 historical training paths, dataset names and project IDs also match
the original `c2_20261024_004314/groups.parquet` exactly; counts alone are not
used as evidence that the historical population was restored.

If the scanner encounters malformed input in a future run, the node remains in
the graph with its known project/address/raw-equality links, has no invented
lexical stream, and is quarantined from usable training. Missing lexical links
would remain unresolved; this fallback cannot certify independence. There were
zero such errors in the current run.

Remaining limits are substantive: candidate project/library provenance,
annotation adjudication, language/compiler assumptions, and semantic clone
coverage are not resolved by these lexical graphs. The 995 candidate components
at threshold 0.8 are **not 995 established independent real-world families**.
The diagnostic 1,998-file population is not a frozen confirmatory test. The next
model configuration must use an explicitly chosen retained source population
and train-only tuning; this report does not select one on external performance.

## Reproduction

Run from the repository root after obtaining the four pinned source checkouts
and regenerating the private provisional annotation manifest from the external
audit. Use new output directories; existing runs are never overwritten.

```bash
python papers/security_evaluation/dependency_audit/run_dependency_audit.py \
  --normalization legacy --out /path/to/new-legacy-run
python papers/security_evaluation/dependency_audit/run_dependency_audit.py \
  --normalization string_aware \
  --scanner papers/security_evaluation/normalization_audit/solidity_scanner.py \
  --out /path/to/new-corrected-run
python papers/security_evaluation/dependency_audit/verify_dependency_audit.py /path/to/new-legacy-run
python papers/security_evaluation/dependency_audit/verify_dependency_audit.py /path/to/new-corrected-run
python papers/security_evaluation/dependency_audit/compare_dependency_runs.py \
  --legacy /path/to/new-legacy-run --corrected /path/to/new-corrected-run \
  --scanner-audit papers/security_evaluation/normalization_audit/run_20261025_v1/source_normalization_audit.csv \
  --prior-candidate papers/security_evaluation/external_audit/source_audit_full_20261025/candidate_source_metadata.csv \
  --out /path/to/new-comparison
```

The measured complete graph runs took 86.16 seconds and 110.94 seconds, with
maximum resident sizes of approximately 705 MiB and 725 MiB for legacy and
string-aware normalization respectively. These measurements include input
loading, provenance export and graph construction in this environment. Snapshot
copies are evidence artifacts; use the original script path for execution.
