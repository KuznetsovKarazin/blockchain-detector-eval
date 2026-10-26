# External B integrity preflight, version 1

This is a read-only coordinator preflight and release-artifact contract. It binds files and checks their recorded sequence; it does not authenticate real reviewers, certify timestamps, freeze the actual protocol, grant execution permission, fit models, score contracts or invoke tools. The outputs `execution_authorized=false` and `human_identity_authenticated=false` are deliberate even when all mechanical checks pass.

The original draft and blank human forms remain unchanged. The separate [inference-policy gate](../INFERENCE_GATE_20261026.json) is closed: finite-population counterexamples do not support calibrated confirmatory AP intervals. Unit-test success cannot change that policy. A remedy or descriptive-only redesign needs an explicit prospective amendment.

## Strict replacement for the legacy guard

The historical `validate_gate.py` accepts a minimal forged dictionary that omits prerequisite/hash maps, repeats a fictional reviewer name and explicitly denies fitting/scoring. Its empty `.get(...,{})` defaults bypass those checks. That script and its snapshots are preserved as evidence; **do not use it for a future execution decision**.

`validate_gate_v2.py` requires the exact future schema `external_validation_protocol_B_frozen_v2`, all eight freeze conditions, four declarative score requirements, every hash binding, distinct normalized reviewer IDs/display strings, enumerated phases and explicit relevant permissions. Score requirements use `required_sealed_evidence`: a prospective freeze must not falsely record future reviews as completed. Actual completion is checked against separately sealed artifacts. Names and IDs are provenance fields, not authentication.

The current draft must be rejected:

```bash
.venv/bin/python papers/security_evaluation/revision1/external_protocol/orchestration_v1/validate_gate_v2.py --protocol papers/security_evaluation/revision1/external_protocol/protocol_B_draft.json --phase begin_scoring
```

Exit 2 is expected. A successful schema check alone would still not authorize execution. No real frozen-v2 protocol, human record or coordinator authorization is created here; consistent examples exist only as fictional temporary test fixtures.

## Binding contract

`prepare_current_binding.py --out NEW_DIRECTORY` records deliberately blocked current inputs, an empty release chain and exact copies of all 14 bound public source files. It writes only new metadata and source snapshots; it does not freeze, fit or create authorization. Its observed digest is not automatically trusted. The read-only CLI requires a separately supplied `--expected-binding-sha256`; the coordinator must select that anchor through the approved immutable version/release process. Hashing an arbitrarily altered bundle does not authenticate it.

The binding covers exact training/test membership and source bytes, ordered training proxy labels, source-status manifest, sample/allocation, method/job configuration, inference policy/evidence and runtime inventory. Code bindings include the live validators/review validator, adapters, feature definitions, corrected scanner, historical token/pattern code, both performance versions, compiler policy/catalog, toolchain verifier/provisioner and model-worker source. The strict gate and review estimator are compiled from exact trusted source bytes rather than imported through a possibly stale Python module or bytecode cache. Their loaded-byte digests and current files must agree with the binding; the worker likewise loads this preflight from exact source. Production population counts cannot be changed by JSON; reduced dimensions require an explicit synthetic Python profile unavailable through the production CLI.

The runtime check binds exact compiler versions to the saved planner, unique binary/dependency artifacts and packages, and original inventory/lock receipts. Paths resolve explicitly; no ambient executable lookup or version probe occurs. These checks do not establish compilation success or a hermetically secure operating system. The separate model worker also binds its live package environment.

## Recorded phase order

Each event binds the input digest, preceding event digest, exact artifacts and a timezone-aware seal time. The order follows the original B protocol:

| Requested phase | Required events | Check |
|---|---|---|
| `setup` | None | Inspect current inputs; draft/inference blockers stay visible |
| `begin_review` | Protocol freeze | No human review or fit/score was declared completed at freeze |
| `initial_reviews` | Freeze, both initial reviews | Every selected case, class and declared reviewer retained |
| `adjudication` | Freeze, initial reviews, adjudication | Original judgments preserved; unresolved remains unknown |
| `begin_scoring` | The same three events | Adjudication is sealed before considering fitting/scoring |
| `analyze` | Those three plus score release | Full scores/state/tool records and recorded times checked |

Extra events at an earlier phase are rejected rather than permitting re-entry. Timestamp ordering is checked as recorded; hashes do not prove when events occurred. An immutable-record reference is procedural evidence, not an authenticated third-party timestamp or substitute for real human review.

## Early admission versus full integrity

`admission_preflight(root, binding_path, expected_sha256, release_path, profile=Profile())` is the worker's first step. Drafts, incomplete schemas, closed permissions/inference policy and missing/blank human releases are rejected before training labels or model-source contents are accessed. After header checks it may read the private sample key, allocation and sealed review/adjudication forms. It never reads training proxy labels, the complete source-label manifest, source bodies or scores.

The worker subsequently needs a separately anchored procedural coordinator instruction and `check(..., phase='begin_scoring')`, which verifies all source bytes, training labels and tools. Fitting inputs may be consumed only after those checks. Thus coordinator setup is read-only but **not annotation-file-blind**; it is not the compiler-only metadata path. Names/hashes in coordinator instructions likewise cannot establish actual human identity or authority.

The checker writes nothing; its CLI prints JSON and exits nonzero on failure. Receipts/snapshots are written separately at new paths. Validation uses exceptions and remains active under `python -O`.

## Complete job and failure records

There are **24 learned-fit jobs**: two classes times one raw LR, one normalized LR, five RF seeds and five LightGBM seeds. Two additional Slither class-comparison slots prevent silently omitting the static comparator. They do not imply two independent tool executions; a shared trace may support both class mappings.

Every job/file score row carries `job_id,path,class,execution_status,status,score`. An explicitly frozen mapping converts detailed execution reasons into the performance-v2 vocabulary while preserving the original reason. Unknown statuses, failure-to-success mapping, missing rows and fabricated safe scores are rejected. Success requires a finite score; failure requires an empty score. A future common-success analysis must consume the full failure inventory rather than silently deleting jobs or files.

Successful learned jobs bind ordered training IDs/source hashes, configuration/input digests, fitted-state JSON and the separately hashed model object. Failed training requires a failure log, no invented fitted model, and all external rows marked `model_error`. Static slots bind tool inventory, trace, complete source coverage and no outside-pragma attempts. Fit/scan times must follow sealed adjudication. These are checks on recorded evidence, not proof that arbitrary supplied logs tell the truth.

The separate `model_worker_v1` owns learned-model dispatch, persistence and resume. This preflight does not implement those operations. Static execution and estimation are separate consumers. Artifact consistency does not validate the inference policy, authenticate reviewers or automatically choose a favorable subset/seed comparison.

## Tests and current status

`test_preflight.py` uses fictional temporary sources, reviewers, judgments, executable bytes and model bytes. It tests the legacy fail-open counterexample, required schema/permissions, phase order, source/config/reference/score mutation, missing training members, sampling and runtime inventories, explicit failures, early-access boundaries and read-only behavior. Real blank forms are never populated.

Current real scoring is blocked by the draft, absent genuine sealed reviews/release and negative inference policy. Tests do not complete B validation, legal/semantic sign-off or human assessment.

The [current v2 binding](current_binding_20261026_v2/binding.json) and [read-only observation](current_binding_20261026_v2/read_only_preflight_receipt.json) cover 691 training files, 1,998 external files and 180 sampled cases in 17 strata. Setup checks source and tool identity; it is not study release. The expected binding digest is `352de7c7b88d84cedfa1659739920207d3d82c17612f6a83653acf56e2802de2`.

The [loader amendment plan](loader_amendment_20261026_v1/plan_before_amendment.json) preserves the earlier reviewed source before the cache-hardening change. Its old binding and independent review remain historical observations. [Verification v2](verification_20261026_v2/plan_before_checks.json) records the amended checks under optimized Python; the two added regression cases cover same-size/same-timestamp bytecode and a preloaded stale module. None of these hashes establish genuine human identity or the honesty of an arbitrary supplied log.
