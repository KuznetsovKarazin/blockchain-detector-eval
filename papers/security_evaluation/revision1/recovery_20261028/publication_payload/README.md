# Lossless publication payload, 28 October 2026

**Public distribution blocked:** automatic approval review rejected uploading the binary payload to the public GitHub repository, citing insufficient explicit authorization for this specific archive. The seven binary parts and nine large original files are not included in this public commit. No alternative public route was attempted. The author retains the verified private package; a fresh clone alone cannot reconstruct these files.

The manifest and helper below describe the prepared package. Run the helper only after obtaining the verified parts privately and placing them beside `MANIFEST.json`; it cannot run from the public checkout alone.

Repeated `Invalid conversation body` errors interrupted the large upload requests.
The nine largest new distribution files are therefore stored as one losslessly
compressed tar archive in seven small binary parts. This is a packaging change:
all scientific results, original receipt hashes and output bytes remain unchanged.

From the repository root, with Python 3.12 and its standard library:

```sh
python papers/security_evaluation/revision1/recovery_20261028/publication_payload/restore.py
```

The helper verifies every part, the complete archive and each member against
`MANIFEST.json`, then restores the original repository-relative paths. It refuses
to overwrite different existing files. The nine members are six fictional reporting
reports, two identical runtime inventories and the original authored-fixture ZIP.
No historical restricted graph archive is included.

After this command, follow the reporting and Slither extraction instructions.
The reconstructed Slither ZIP retains its original SHA-256
`38fed9893801651d8b2e459c43f8c4eebf96ae97cf1eb9c1d04253f911796d12`.
Its 200 raw case files are extracted in a separate documented step. The large
reporting audit is restored from its already published, separate ZIP.

For an isolated extraction check, pass `--root /path/to/empty-directory`.
Extraction checks stored evidence only; it does not rerun experiments or establish
portable runtime compatibility. Real human judgments and real external evaluation
remain unperformed.
