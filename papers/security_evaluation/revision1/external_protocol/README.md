# External protocol B: current preparation

The current entry point is [ENGINEERING_READINESS_20261026.md](ENGINEERING_READINESS_20261026.md). The unchanged [25 October report](ENGINEERING_READINESS.md) records the earlier stage. External human judgments, model fits/scores, contract compilation and Slither scans remain zero; the B draft and execution gates have not been frozen or opened.

The fixed provisional cohort contains 1,998 files / 3,996 file-class cases. Full observed-graph exclusion at threshold 0.8 retains 691 training files with 23 reentrancy and 18 unchecked source-reported findings. The probability packet selects 180 cases from 170 files in 17 source/class/status strata; two independent specialists must assess every case. All public and private working forms remain blank. The separate 17-case identity census and prior purposive 106-case packet remain separate.

All pinned raw inputs and private packet materials were restored exactly. [The restoration receipt](adapters_v1/private_restoration_receipt.json) verifies the sampling-key hash, source copies, deterministic public artifacts and identity dossiers. Original annotation keys and renamed source bodies remain ignored/private; unresolved records are not reintroduced into the cohort.

The current engineering comprises [feature adapters](adapters_v1/README.md), [selected probability-sample performance primitives](performance_v1/README.md), and [verified toolchain artifacts](toolchain_v1/README.md), with an [independent review](../recovery_20261026/ENGINEERING_INDEPENDENT_REVIEW.md). The adapters have 24 passing synthetic tests, performance 24, and independent review 21. Toolchain verification has 7 original + 7 amendment tests; only 31 version probes were executed for 30 solc versions and Slither 0.11.6. The [combined receipt](../recovery_20261026/FINAL_VERIFICATION_20261026.json) records 251 unique tests, including the rerun historical suites without double counting.

These modules are not a complete external comparison. The performance API currently requires complete successful score vectors, treats weighted AP as a nonlinear plug-in, labels intervals approximate, and retains unknowns without safe-score substitution. Several proposed comparison/coverage estimands and an authenticated runner remain outside its scope. Named real reviewers, semantic agreement, prospective protocol freeze, sealed initial reviews and adjudication remain required. See the current readiness report for precise limits.

The executable historical draft guard remains closed:

```bash
python papers/security_evaluation/revision1/external_protocol/validate_gate.py --protocol papers/security_evaluation/revision1/external_protocol/protocol_B_draft.json --phase score
```

Exit 2 with `allowed=false` is expected. Its old prerequisite booleans are intentionally not retroactively edited; incorporating the new modules requires a separately reviewed prospective integration/freeze. New computations require new output directories. No registration, DOI, journal submission or third-party message has been made, and permission to redistribute third-party source code or row annotations is not inferred.
