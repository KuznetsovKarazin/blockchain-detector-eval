> **Current state, 26 October 2026:** inputs and 23 gzip files are verified locally; six original NPZ files remain missing, with new canonical reproductions separately identified. The compressed outputs are excluded from the public update. Read [publication status](revision1/PUBLICATION_STATUS.md) and [current B engineering readiness](revision1/external_protocol/ENGINEERING_READINESS_20261026.md).

# Security evaluation study

This directory continues the book experiments as a separate article study. The current manuscript is [DRAFT_REVISION2.md](manuscript/DRAFT_REVISION2.md), *Population Coverage and Dependency-Aware Evaluation of Smart Contract Vulnerability Detectors*. Start with [STATUS.md](STATUS.md) and [revision1/README.md](revision1/README.md), then `protocol.json`, `DECISIONS.md` and `VALIDITY_NOTES.md`. The overall protocol remains a draft and external model scoring is blocked. Historical `results/contracts/` outputs and earlier paper runs are unchanged.

## Completed revision 1

The revision contains 3,822 population/threshold/grouping graphs, identity and lexical-representation controls, project-contracted bridge diagnostics, and a completed historical-test sampling experiment. The latter uses 20 paired training draws for four methods and four regimes, plus a separate estimator-seed panel: 360 logical evaluations, 282 physical fits and no failures. It measures conditional variation on the original 1,082-file/21-positive test, not independent external performance. See [the model results](revision1/sampling_variance/run_20261025_v2/RESULTS.md) and [the mechanism report](revision1/graph_mechanism/REPORT.md).

[The external protocol package](revision1/external_protocol/README.md) fixes a prospective 1,998-file cohort and prepares a 180-case probability sample for two independent specialists. All human forms are blank; external fits and scores remain zero. The previous purposive packet and blocked outside-giant campaigns remain separate. [Independent verification](revision1/independent_verification.json), [the evidence map](manuscript/REVISION1_EVIDENCE_MAP.md), and [figure provenance](manuscript/figures_revision1/README.md) connect the revised article to its artifacts.

Current B engineering has 24 adapter tests, 24 performance tests and 21 independent synthetic checks, plus separately recorded toolchain validation. Thirty solc versions and Slither 0.11.6 were inventoried with version-only probes. No real-source model fit, contract compilation or Slither scan was added. Complete external comparison still requires authenticated integration, semantic and human sign-off, prospective protocol freeze, sealed reviews and adjudication.

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

`manuscript/DRAFT.md` and `manuscript/DRAFT_REVISION1.md` preserve earlier drafts; `manuscript/DRAFT_REVISION2.md` is current, with five tables, six figures, 17 references and explicit AI-assisted-method/declaration text. Neither reports a completed external evaluation. The second-cycle string-aware normalization check, full graph sensitivity and 95-design feasibility audit are in `normalization_audit/`, `dependency_audit/` and `design_feasibility/`. Their READMEs document commands and recovery provenance. `dependency_audit/graph_scope_ablation_recovered_20261025/` distinguishes exhaustive screening from population expansion.

All 1,140 combinations of the 95 proposed tests and 12 graph variants fail the declared operational screens. The two prepared comparative campaigns are blocked by an executable assessment gate; their configurations are evidence of preparation, not completed fits. The exact published pilot reproduction remains separately supported. See `campaign/` and `review_cycle2/REVIEW.md` for implementation and guard verification. No external model scores or human expert judgments have been added.
