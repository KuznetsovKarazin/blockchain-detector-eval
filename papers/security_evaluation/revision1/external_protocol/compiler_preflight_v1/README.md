# Compiler-only coverage preflight

This module prepares and, only with a separate reviewed permit, executes compiler readiness for the fixed **691 training + 1,998 external** files. No Slither, detector, model, annotation-file, expert-judgment or score operation is implemented. The original protocol, compiler inventory and candidate plan are unchanged. `PROTOCOL_SCOPE.md` explains the separate engineering-stage interpretation and its limits.

The final prepared plan is `plan_20261026_v2/plan_before_execution.json`, SHA256 `7f5da3a7cf0a9fcef75d3b4c1f071552dca7d42dcf8fdb98855a514b90aafa80`. Source/input hashes and source snapshots were captured **before** enumeration and checked unchanged afterward. The earlier metadata-only preparation was interrupted before any plan output to incorporate review fixes; it executed no compiler. Thirty-two synthetic tests pass, including timeout/output/memory/CPU enforcement and review-driven malformed-output regressions.

## Concrete input readiness, before compilation

| Cohort | Ready to attempt | Original unavailable compiler plans | Additional import/context limitations | Total |
|---|---:|---:|---:|---:|
| Training | 336 | 9 | 346 | 691 |
| External | 1,968 | 30 | 0 | 1,998 |
| Combined | 2,304 | 39 | 346 | 2,689 |

The 346 training limitations are 336 imports unresolved under the fixed context policy, five remote/absolute import paths, four paths outside the snapshot and one unsupported import syntax. These are **input-context statuses, not actual compiler errors and not evidence that the Solidity source is invalid**. Missing build remappings or dependencies can explain them. No file is removed from the denominator. The original 39 unavailable plans remain: 32 missing pragmas, four unsupported constraints and three without a compatible catalog release.

Sixty-five ready training files have nonempty resolved import closures. The largest prepared closure contains 45 files / 694,546 source bytes. The 1,968 planned external files have no active imports requiring another source under this scanner. Ready jobs contain 3,543 ordered candidate slots, a maximum if every attempt fails; the runner stops after the first success. The overall candidate inventory still includes the original 30 versions and retains the original per-file ordering. Preparation itself is not successful compilation coverage.

## Exact compilation policy

All attempts use the verified absolute compiler path and SHA256 from `toolchain_v1/solc_inventory.json`. The command is `solc --standard-json --allow-paths <fresh-private-workspace>`. Standard JSON contains source `content` only, no URLs, no inferred remappings, optimizer disabled, and requests AST, ABI and `evm.bytecode.object`. Each compiler's default EVM target applies; no original project build configuration is claimed. Bytecode can remain unlinked. Compiler success does not imply successful Slither analysis or deployment.

Training context is the exact pinned DAppSCAN `<audit-project>/<repo-snapshot>` root. Relative imports stay within that root; direct imports must be exact canonical source-unit names within it. All closure files must appear in the frozen full-source inventory with matching hashes. The runner rejects symlinks, snapshot escape, ambiguous exact keys, unsupported import syntax/literals and absolute/remote imports. There is no cross-project basename/suffix search, inferred npm directory, package installation, network fetch or source rewriting. External sources have only their own file as verified context; an import of another source would be unavailable.

For ready jobs, source bytes are verified again and copied without edits into a new private workspace. Only this workspace is supplied to the host filesystem callback. The inline closure, no-URL rule and argument restrictions are application controls, not a kernel sandbox claim. Landlock and bubblewrap isolation probes were unavailable in this runtime. No unrecorded alternative isolation or proxy mechanism is used.

The frozen bounds are 180 seconds wall and CPU per attempt, 2 GiB address space, 64 open files, no core dumps, 16 MiB stdout plus 1 MiB stderr, at most 128 source units / 8 MiB source bytes / 16 MiB input JSON, and two hours for the complete run. Each file tries at most its original five candidates, with no outside-pragma fallback and no diagnostic rerun. Remaining files at a total-budget limit are explicitly unattempted; they are not dropped or assigned a safe result.

A zero process exit alone is insufficient. JSON compiler diagnostics with severity error fail. Requested outputs must cover all AST-declared root contract definitions; missing output for a concrete contract is a schema failure. Malformed nested JSON becomes a per-file schema status. Interface/abstract bytecode omissions, empty bytecode, nonempty bytecode, unlinked bytecode and no-root-contract successes have explicit counts/statuses. All remain in the population.

## Public and private records

`jobs.jsonl` records source identities, hashes, exact context/source-unit names, ordered versions and preparation dispositions. It contains no source text or row annotations. The unapproved permit template is not execution permission.

A real execution writes raw stdout (AST, literals, ABI and bytecode) and stderr/error text **only** under ignored `data/derived/security_compiler_preflight_20261026_v2/`. Public `execution_results/` would contain fixed source pointers, status/category/count metadata, version and artifact hashes, diagnostic hashes, exit codes and durations. Diagnostic text and compiler source excerpts are not copied into public results. Unknown diagnostic types are mapped to `OtherDiagnostic`.

## Review gate and reproducible entry points

Preparation is complete; no actual-corpus execution is recorded by this module at this stage. The root task requires independent engineering review and explicit root authorization bound to this exact plan before execution. The permit is an operational acknowledgment, not cryptographic authentication of a human expert, and does not open the original scientific scoring gate.

The reviewer receipt must contain `status: pass` and this exact `plan_sha256`. A separately created permit must contain:

```json
{
  "approved": true,
  "scope": "compiler_readiness_only",
  "plan_sha256": "7f5da3a7cf0a9fcef75d3b4c1f071552dca7d42dcf8fdb98855a514b90aafa80",
  "independent_review_receipt": "<repository-relative receipt path>",
  "independent_review_sha256": "<exact receipt SHA256>",
  "parent_authorization_reference": "<concrete authorization reference>"
}
```

Only after those records exist may the root run:

```bash
.venv/bin/python papers/security_evaluation/revision1/external_protocol/compiler_preflight_v1/runner.py execute --plan papers/security_evaluation/revision1/external_protocol/compiler_preflight_v1/plan_20261026_v2 --permit <new-permit-path> --permit-sha256 <exact-permit-sha256>
```

The runner verifies the permit, all frozen code/input hashes, raw repository pins, job manifest and each compiler artifact. The private execution directory must be new; this version does not silently resume or repeat an interrupted attempt. A later run needs a distinct reviewed plan/work directory.

Synthetic verification command:

```bash
.venv/bin/python -m pytest -q papers/security_evaluation/revision1/external_protocol/compiler_preflight_v1/test_preflight.py
```

The root's separately recorded `compiler_smoke_v1/` uses a self-authored fixture to check actual compiler JSON compatibility. It is distinct from this synthetic runner test suite and from any future corpus execution.
