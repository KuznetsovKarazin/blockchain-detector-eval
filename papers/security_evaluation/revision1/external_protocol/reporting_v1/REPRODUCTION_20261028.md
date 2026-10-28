# New reporting reproduction — 28 October 2026

Distribution: public binary upload is blocked by automatic approval review. The six complete report JSON files remain in the author’s private package. If that package is available, first [restore the six complete report JSON files](../../recovery_20261028/publication_payload/README.md) from the lossless publication payload. Their original hashes and receipt records are unchanged.

This is a **new run**, made after source recovery and the public checkpoint `76789ea`. It does not restore or recreate the lost dated design/result receipts from 26 October. The seven implementation/test/documentation sources matched their recorded original hashes before execution. The frozen source files, original protocol, inactive inference gate and original audit archive were unchanged throughout this run.

The [plan and runtime inventory](recovery_verification_20261028_v1/PLAN_BEFORE_EXECUTION.json) preceded both tests and report generation. The current runtime is Python 3.12.14, NumPy 2.3.5, pandas 2.2.3, SciPy 1.17.0 and scikit-learn 1.8.0. These numerical version strings match the earlier record; the historical binary environment is not reconstructed merely by matching versions. Current pytest is 9.2.0, versus the previously recorded 8.4.2.

- **28 owner tests passed in 33.78 seconds**, with a new [JUnit record](recovery_verification_20261028_v1/owner_pytest.xml).
- **34 independent tests passed in 19.15 seconds**. Their source was itself recovered with an exact original hash; the [independent receipt](../../recovery_20261028/reporting_independent_reproduction_20261028_v1/result.json) is newly dated and does not replace the lost old receipt.
- The unchanged generator produced **six fictional reports in 69.49 seconds**, under [recovered_check_20261028_v1](recovered_check_20261028_v1/receipt.json). They retain the two classes, three declared scenarios, 13 primary vectors, 12 raw-LR contrasts and original queue policy. Only the declared baseline reentrancy report invokes the 2,000-replicate exploratory calculation; the other five use the primary path without bootstrap.
- The unchanged [output verifier](recovery_verification_20261028_v1/output_verification.json) passed source/output hashes, exact inventories, budget rounding, unknown handling and the fictional HT total/variance checks.

The [audit comparison](recovery_verification_20261028_v1/AUDIT_COMPARISON_20261028.json) establishes **exact byte identity and JSON equality** between the newly generated full exploratory audit and the original audit member recovered from GitHub: each is 20,804,725 bytes, SHA-256 `044243fa44bb70f496629d6d9b0210b7ee291dff2806fbb93790415513baa15d`. This is stronger than approximate numeric agreement for that one audit. No corresponding old bytes are available for the six complete report files, so their original byte identity is not claimed. New configuration timestamps, runtime observations and receipts are explicitly new evidence.

## Restoring the deduplicated audit before verification

The public distribution reuses the already published original ZIP; it need not store a second 20.8 MB copy of identical audit bytes. The exact mapping is:

| Item | Path relative to this directory |
|---|---|
| Existing archive | `synthetic_engine_audit_20261026.zip` |
| Original member inside that archive | `synthetic_check_20261026_v1/engine_audit_baseline_reentrancy.json` |
| Destination required by the new receipt | `recovered_check_20261028_v1/engine_audit_baseline_reentrancy.json` |

The [mapping manifest](recovery_verification_20261028_v1/AUDIT_RESTORE_MAPPING.json) binds the archive and member checksums. From the repository root:

```bash
python papers/security_evaluation/revision1/external_protocol/reporting_v1/recovery_verification_20261028_v1/restore_identical_audit.py
python papers/security_evaluation/revision1/external_protocol/reporting_v1/verify_outputs.py --folder papers/security_evaluation/revision1/external_protocol/reporting_v1/recovered_check_20261028_v1
```

The restoration helper verifies both checksums, accepts an already identical destination and refuses to overwrite differing bytes. It performs no report generation and creates no old run receipt. Ordinary extraction to the member's original path alone would not satisfy the new receipt's destination path.

All inputs were fictional. No actual dataset labels, human judgments, model fits, Solidity compilation, Slither scans or external performance evaluations were used. The scientific amendment is still inactive; these numerical engineering checks do not authenticate experts, adopt an inference policy or release a real study.
