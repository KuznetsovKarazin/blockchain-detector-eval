# Verifier amendment v2

This amendment addresses two independent-review findings without rewriting the earlier executed receipt: the v1 verifier described itself as read-only while generating metadata files, and its assertions could be disabled by `python -O`.

The historical `verify_toolchain.py`, `provision_toolchain.py` and `manifest.json` remain byte-identical and have exact copies in `source_snapshot_v1/`. The original manifest SHA256 remains `548b8937fa01ea5f0a994a737fd52fd518960b8a9538f6076c008a16216e6ff6`. The historical verifier is retained as execution evidence, not the current validation entry point.

The new `verify_toolchain_v2.py` separates operations explicitly:

- `validate()` reads frozen metadata and artifact bytes and returns a result in memory. It creates or updates no files and invokes no executable or network operation. The default CLI emits that result to stdout.
- Optional `--receipt NEW_PATH` separately creates one receipt with exclusive-create mode. An existing path is refused; validation failure creates no receipt.
- Every integrity condition uses an explicit `ValueError` check. The module contains no `assert` and imports no assertion-based provisioning or verifier helper. Checks therefore remain active with optimized Python.

The source snapshot in `source_snapshot_v2/` precedes the new execution receipt. `verification_receipt.json` is a separate v2 receipt generated with `python -O -B`, and records zero tool invocations, zero compilations and zero Slither analyses. All 30 compiler artifact hashes and 47 Python wheel hashes still match the frozen metadata. The original version probes were not repeated.

Seven additional focused tests passed: default validation with and without optimization, unchanged frozen-file hashes, tampered receipt rejection with and without optimization, no output on validation failure, exclusive receipt creation/refusal to overwrite, explicit exception/no-assert structure, and exact preservation of legacy snapshots. There are seven original toolchain tests plus seven amendment tests; the original test receipt is unchanged.

Current entry point:

```bash
python papers/security_evaluation/revision1/external_protocol/toolchain_v1/verify_toolchain_v2.py
python -O papers/security_evaluation/revision1/external_protocol/toolchain_v1/verify_toolchain_v2.py
```

Use `--receipt` only with a new path when an additional dated receipt is intended. This amendment establishes neither compilation/analysis coverage nor external scientific readiness. `amendment_manifest.json` records the source, snapshots, test receipt and new verification receipt hashes.
