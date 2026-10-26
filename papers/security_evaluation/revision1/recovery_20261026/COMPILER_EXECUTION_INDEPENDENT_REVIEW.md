# Independent review of completed compiler-only execution

Result: **pass**, read-only verification on 2026-10-26. The [machine-readable receipt](compiler_execution_review_20261026_v1/result.json) binds the exact plan, completed outputs and verifier source. No compiler was rerun and no source, annotation, human-reference or score data was edited.

All **2,689 files** remain in their original order with unchanged identities and hashes. All **3,514 attempts** follow the fixed candidate prefixes, stop at the first success and stay within the five-attempt cap. Every final failed compilation exhausted its declared candidates. The 385 files unavailable before execution retain their original explicit status. Private per-file receipts equal the public metadata records.

| Cohort | Fixed files | Attempted | Compiler success | Success / fixed cohort | Success / attempted |
|---|---:|---:|---:|---:|---:|
| Training | 691 | 336 | 330 | 47.76% | 98.21% |
| External | 1,998 | 1,968 | 1,807 | 90.44% | 91.82% |
| Total | 2,689 | 2,304 | 2,137 | 79.47% | 92.75% |

There are 167 final compiler errors: six training and 161 external. Attempt-level accounting contains 2,137 successful and 1,377 failed attempts; earlier failures before a successful compatible version are retained. Before compilation, 346 training files lacked an accepted local import context and 39 files had no usable original compiler plan. No file was dropped from the denominator.

The verifier hashed **all 7,028 private stdout/stderr files**, covering 552,536,751 stdout bytes and zero stderr bytes. It independently parsed every compiler JSON result, checked diagnostic counts and error severity, matched root AST declarations to requested outputs, and recomputed ABI/bytecode metadata. No diagnostic text, source excerpts, ASTs or ABIs were copied into this review artifact. Binary digests, source/configuration snapshots and raw repository pins remain unchanged; both raw checkouts are clean. The largest recorded attempt took 43.52 seconds against the 180-second limit. The execution took 733.11 seconds and left no rows unattempted because of the global budget.

“Compiler success” is deliberately narrower than a complete detector pipeline. Of the 330 successful training files, 101 have no nonempty root bytecode, consistent with interface/abstract-only sources. Ten training and ten external successes contain unlinked root bytecode. The check requested AST, ABI and unlinked bytecode under the frozen source-context policy; it does not establish deployment, Slither analysis, semantic correctness or expert labels. These counts do not change the fixed 691/1,998 method cohorts.

The reviewed plan SHA-256 is `7f5da3a7cf0a9fcef75d3b4c1f071552dca7d42dcf8fdb98855a514b90aafa80`. The completed per-file metadata SHA-256 is `2f86d433af460571c6aa6f1c7d73cbd5230c394d3a57f7f31d47132d6bb8896e`; the completed summary SHA-256 is `da53549fe1a91e75f1e7ed9807476860d78ced9616687ec0cdcbd64786b2f149`. The [verifier](verify_compiler_execution.py) and its pre-check plan/source snapshot make this accounting reproducible without executing any compiler.
