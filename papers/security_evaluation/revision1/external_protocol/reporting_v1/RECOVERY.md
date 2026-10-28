# Reporting source recovery — 28 October 2026

Seven files have been restored with **exact matches to their recorded pre-loss SHA-256 digests**: `reporting.py`, `test_reporting.py`, `synthetic_inputs.py`, `run_synthetic.py`, `verify_outputs.py`, `README.md` and `conftest.py`. Recovery used the preserved original patches and subsequent edits, then compared the resulting bytes with the previously recorded source hashes. The frozen README has not been amended.

The eighth restored file, `VERIFICATION.md`, is a historical narrative reconstructed from its preserved text. No pre-loss digest was available for that narrative, so byte identity is not independently established. Its statements about prior test runs and six fictional reports describe work observed before the workspace loss. **They do not establish that the associated dynamic receipts or report files are currently restored.**

The [recovery inventory](RECOVERY_INVENTORY_20261028.json) records the per-file digests, proof status and source-copy verification. The reporting audit ZIP that was already present in this directory was retained byte-for-byte. No numerical output was regenerated to populate missing files, and no old timestamps or run receipts were fabricated.

At this source-recovery checkpoint, the original `READINESS.json`, dynamic synthetic design/preparation/result receipts, six report JSON files and output-verification JSON were not recreated by this recovery operation. The separately recovered audit ZIP is not a substitute for those other artifacts. Any later reconstruction or fresh computation needs its own dated evidence and must distinguish restored original bytes from newly generated results.

No module imports, tests, model fits, tool scans, human judgments or external evaluation were performed during this recovery. The inference amendment remains inactive and the original execution gates remain unchanged. This checkpoint restores source provenance; it does not release the study or repeat the historical validation claims.
