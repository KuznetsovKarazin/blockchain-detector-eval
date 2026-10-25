# Security evaluation study

This directory continues the book experiments as a separate article study. Start with `STATUS.md`, `protocol.json`, `DECISIONS.md`, and `VALIDITY_NOTES.md`. The protocol is still a draft and external model scoring is blocked. Historical `results/contracts/` outputs are unchanged.

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
