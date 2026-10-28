# Security evaluation study

**Current checkpoint, 28 October 2026:** the current scientific manuscript is [DRAFT_REVISION3.md](manuscript/DRAFT_REVISION3.md), *Population Coverage and Dependency-Aware Evaluation of Smart Contract Vulnerability Detectors*. Its original SHA-256 and the saved 20-page Word are restored exactly. See [the recovery and scientific status](revision1/recovery_20261028/STATUS_RU.md) for what is available and what remains missing.

The completed graph study has 3,822 outcomes. The historical-test model study has 360 logical evaluations through 282 fits; it remains conditional on one fixed proxy-labelled test. The completed compiler-only audit accounts for all 2,689 inputs, with 2,137 successful files (1,807/1,998 external and 330/691 training). Revision 3 integrates those compiler results, the synthetic AP interval diagnostic and exact AP completion bounds. These are not real external detector-performance results.

Seven reporting source files and seven Slither implementation files were restored to their recorded original hashes. The reporting audit ZIP was recovered byte-exact from its uploaded GitHub blob. Additional original dynamic reporting outputs and Slither run outputs were removed during workspace maintenance before the interrupted branch update completed; they are not claimed as recovered. Read [reporting recovery](revision1/external_protocol/reporting_v1/RECOVERY.md) and [Slither recovery](revision1/external_protocol/slither_worker_v1/RECOVERY_20261028.md). Original run counts reported in the session are distinguished from currently available evidence.

New dated reproductions completed the execution evidence locally: [reporting](revision1/external_protocol/reporting_v1/REPRODUCTION_20261028.md) passes 62 tests and six fictional reports; [Slither](revision1/external_protocol/slither_worker_v1/REPRODUCTION_20261028.md) passes 114 tests and all predeclared expectations for 25 authored contracts. The full reporting audit is byte-identical to the preserved original. The Slither raw case outputs have a verified lossless distribution package and extraction inventory, but the binary package is not publicly released. These new runs do not impersonate the missing old run receipts.

**Public evidence limitation:** automatic approval review blocked publication of the binary package. This commit includes code, summaries, receipts and inventories; nine large evidence files remain in the author’s private package. A fresh public checkout cannot restore them without that package. See [distribution status and restoration instructions](revision1/recovery_20261028/publication_payload/README.md).

Real human judgments, external model fits/scores and real-corpus Slither scans remain zero. The protocol and inference amendment remain drafts. The prepared 180-case probability sample requires two real independent specialists, agreed semantics, prospective freezing and sealed initial reviews before external evaluation. [Publication limitations](revision1/PUBLICATION_STATUS.md) remain explicit; no journal submission or DOI was created.

## Reproduce the development pilot

Use Python 3.12 on Linux, including WSL on Windows. Resource measurements use Linux `resource.getrusage`; they are not Windows-native measurements. From the repository root:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r papers/security_evaluation/requirements-development.txt
.venv/bin/python scripts/00_fetch_data.py --only smartbugs-curated SolidiFI-benchmark DAppSCAN
.venv/bin/python -m pytest -q tests/test_security_fixed_t.py tests/test_security_metrics.py tests/test_features.py
.venv/bin/python papers/security_evaluation/code/fixed_t_development.py prepare --out papers/security_evaluation/runs/dev_fixed_t_reproduction
.venv/bin/python papers/security_evaluation/code/fixed_t_development.py run --out papers/security_evaluation/runs/dev_fixed_t_reproduction
```

The preparatory stage saves the exact configuration, memberships, input hashes and complete used source files before fitting. The run stage verifies them and refuses a scored or changed run directory. Use a new directory for each repetition. These commands reproduce a development experiment; they do not create a new independent test.

The original run is `runs/dev_fixed_t_20261025_v1/`. Its four matched training sets have 1,179 files and 31 reentrancy proxy positives each. The common test has 1,082 files and 21 proxy positives, all from one joint component. No confidence interval is justified. See its README for the separately recorded post-hoc floor-workload analysis and two-class feasibility.

## Inspect external data and labels

`external_audit/` contains scripts and source metadata, exact and normalized overlaps, an exhaustive lexical similarity screen, source reconciliation issues and an independent label-review protocol. The full-source audit uses all upstream DAppSCAN files, not only the historical capped sample.

The blank reviewer forms contain references and our assessment fields. Original annotations and the review key are kept outside version control; no human judgments have been filled in. Neither source-reported negatives nor absence of a class annotation is silently converted into an independently verified negative. The source license and family identity remain unresolved.

## How to interpret evidence

`PROVENANCE_LEDGER.csv` distinguishes historical book results, new audits, development measurements, and unperformed confirmation. The new pilot controls test identities and training object/positive counts. Its training composition still differs, so its AP differences are not a pure causal estimate of leakage. Joint-disjointness refers to the frozen observed dependency graph, not proven semantic independence.

`evaluation_metrics.py` preserves unknown labels and failures. It reports conditional AP with coverage and full-population known-positive recall at review budgets. Failed files never receive a fabricated safe score. The original pilot used ceiling budget rounding; the separately marked reanalysis and proposed main protocol use floor rounding.

## Second-cycle audits and manuscript

`manuscript/DRAFT.md` and `manuscript/DRAFT_REVISION1.md` preserve earlier drafts; `manuscript/DRAFT_REVISION2.md` is preserved as an earlier draft. Current `manuscript/DRAFT_REVISION3.md` has five tables, six figures, 19 references and explicit AI-assisted-method/declaration text. Neither reports a completed external evaluation. The second-cycle string-aware normalization check, full graph sensitivity and 95-design feasibility audit are in `normalization_audit/`, `dependency_audit/` and `design_feasibility/`. Their READMEs document commands and recovery provenance. `dependency_audit/graph_scope_ablation_recovered_20261025/` distinguishes exhaustive screening from population expansion.

All 1,140 combinations of the 95 proposed tests and 12 graph variants fail the declared operational screens. The two prepared comparative campaigns are blocked by an executable assessment gate; their configurations are evidence of preparation, not completed fits. The exact published pilot reproduction remains separately supported. See `campaign/` and `review_cycle2/REVIEW.md` for implementation and guard verification. No external model scores or human expert judgments have been added.
