# New authored-only reproduction — 2026-10-28

The seven recovered owner files match the original frozen source hashes exactly. The original26October run artifacts remain missing. This report describes a **new dated execution**, `authored_check_20261028_v1`, with newly frozen runtime/plan and new receipts. It does not claim recovery or byte identity of the lost26October outputs.

The pinned runtime was restored from the original published immutable URLs:30 solc binaries,47 wheels and the official compiler catalog. Every downloaded artifact matched its original SHA-256. The current Python3.12.14 executable matches the original hash `fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7`; the installed Slither entry script matches `a0e23541a7bbe4ececb6b4f54bb28f46bf645acd6467c0be6af6ecd72ce80bab`. Offline installation reproduced the original installed distribution freeze. The unchanged worker accepted48 installed distributions and2735 file hashes, all47 wheel member checks and the declared six shared documentation paths. The original toolchain metadata and exact worker/policy/source pins were not changed.

New independent engineering checks passed114 tests (105 independent and9 owner) under the recorded current primary Python/pytest environment. A separate independent pre-execution seal verified the78 restored artifacts, runtime file closure,16 frozen source files and28 authored source files before the execution directory existed. The new plan SHA-256 is `ec7c7f3758a91bb194de02f1f9a2dfeacabe1d6945af08366fcbf570d0db22b5`.

The25 authored cases produced22 compiler attempts and21 complete Slither analyses. All21 successful analyses completed the seven detectors. Four cases retained their predeclared failure/unavailable status: unsupported pragma, missing import, compiler syntax error and missing pragma. **Zero predeclared expectations failed.** Runtime was42.454 seconds in this environment, an observation rather than a performance guarantee. No fixture expectation, detector mapping, compiler selection or source was changed after observing results.

The100 output rows contain84 successful binary scores and16 empty-score failure rows. Primary and broad-secondary rows share per-file statuses and trace hashes. The checked examples, all seven detector-positive contexts, import/inheritance attribution, historical0.4.19 case, interfaces/abstract contracts, inline-suppression policy, ordered-candidate stopping and CRLF/UTF-8 source mapping behaved according to the frozen regression expectations. These are software observations on authored sources, not expert vulnerability labels, exploitability claims or external model performance.

Complete-run resume verified203 artifact hashes without running the compiler or Slither again. The new execution receipt SHA-256 is `bd2c2ce8be4398343ba1a06420b4507bcc250c48350823e37106386466e40df5`. Independent post-run review rebuilt100 score rows and108 source mappings and confirmed all expected outcomes. The observed aggregate counts agree with the retained26October console transcript; raw-output identity across dates is unverified because the original outputs are absent.

The raw execution directory occupies approximately21.1MB, largely repeated per-case runtime bindings. Any distribution archive must extract the original bytes and paths exactly, including intentional CRLF. The new plan, runtime inventory, summary and receipt are separate from the lost original records. Authored AST/diagnostic output is public engineering material; equivalent future corpus output must remain private.

Actual corpus scans, actual corpus scores and model fits in this reproduction are all zero. No actual private annotation keys were used. Human semantic sign-off and the prospective inference/admission gates remain closed. Successful synthetic checks do not authorize real external execution.

## Commands and evidence

From the repository root, using the recorded primary Python interpreter:

```sh
python -m pytest -q papers/security_evaluation/revision1/external_protocol/slither_worker_v1/test_worker.py papers/security_evaluation/revision1/external_protocol/slither_worker_v1/independent_review/test_parser_independent.py papers/security_evaluation/revision1/external_protocol/slither_worker_v1/independent_review/test_worker_independent.py papers/security_evaluation/revision1/external_protocol/slither_worker_v1/independent_review/test_gate_independent.py
python papers/security_evaluation/revision1/external_protocol/slither_worker_v1/worker.py run-synthetic --plan-dir papers/security_evaluation/revision1/external_protocol/slither_worker_v1/authored_check_20261028_v1 --expected-plan-sha256 ec7c7f3758a91bb194de02f1f9a2dfeacabe1d6945af08366fcbf570d0db22b5 --resume
```

`restoration_20261028_v1/` contains the restoration source, plan written before downloads, artifact verification, offline installation log and new runtime/result records. `independent_review/reproduction_20261028_v1/` contains the new test, pre-execution and post-run seals. `REPRODUCTION_VERIFICATION_20261028.json` links their hashes to the new run. The restored historical README remains byte-exact and still names the original26October example directory; use this new report for the recovered execution's date and commands.
