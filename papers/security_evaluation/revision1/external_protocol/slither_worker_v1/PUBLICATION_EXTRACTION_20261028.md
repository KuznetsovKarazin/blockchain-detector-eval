# Distribution of the new 28 October authored-fixture run

The 200 raw case files are packaged losslessly in `authored_execution_reproduction_20261028.zip`; `REPRODUCTION_ARCHIVE_20261028.json` records their exact paths, lengths and SHA-256 hashes. These are newly authored software fixtures, not real-corpus sources or human reference judgments. The lost26October outputs are not replaced under their original identity.

The binary package is not publicly released: automatic approval review blocked its upload. A fresh clone alone is insufficient. If the author supplies the verified private package, first restore the original ZIP and runtime inventories using the [lossless publication payload](../../recovery_20261028/publication_payload/README.md). Then, from the repository root:

```sh
python -m zipfile -e papers/security_evaluation/revision1/external_protocol/slither_worker_v1/authored_execution_reproduction_20261028.zip papers/security_evaluation/revision1/external_protocol/slither_worker_v1
```

Verify extracted hashes before using the post-run verifier or resume. Original new-run files, plan, summary, score CSV and receipt remain unchanged. Resume requires the pinned runtime and original absolute paths, so extraction alone does not make resume portable to a relocated environment. Use a new named directory for any subsequent execution. The package does not include the unrelated restricted graph archives.
