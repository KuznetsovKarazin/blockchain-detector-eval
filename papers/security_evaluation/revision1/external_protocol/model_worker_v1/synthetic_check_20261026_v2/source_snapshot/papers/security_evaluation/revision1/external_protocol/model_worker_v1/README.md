# Learned-model worker: future production, synthetic verification only

This module implements the future **24 learned fits**: raw/normalized TF-IDF
logistic regression once per class (4 fits), and pattern Random Forest/LightGBM
for seeds0–4 per class (20 fits). It does not execute Slither; the orchestration
score seal separately requires both static-comparator class records. Current
draft, human-release and inference-policy gates remain closed. No real training
or external fit/score has been performed by this engineering task.

## Entry points and order of access

`worker.py preflight` performs read-only early admission. It validates the
caller-selected binding digest, prospective protocol/code/inference policy and
the freeze → initial reviews → adjudication release chain through
`orchestration_v1.integrity_preflight.admission_preflight`. That function may read
the private probability-sample key/allocation and sealed human forms; it does
**not** read training labels, source bodies or scores. A draft, blank/missing
review or blocked inference policy therefore fails before training-input access.

`worker.py execute` is the explicit future runtime action. It requires all of:

1. The early admission above, using the production profile only (691 train,
   1,998 external files, 180 cases, 17 strata and pinned toolchain counts).
2. A separate procedural coordinator instruction selected with an independently
   supplied expected SHA256. Its schema is
   `external_B_coordinator_execution_authorization_v1`; fields are `action` =
   `learned_fit_and_score`, `authorized` = true, `coordinator_id`, `issued_utc`,
   `authorized_job_ids`, `binding_sha256`, `release_sha256`,
   `reference_event_sha256`, and `worker_sha256`. The instruction must follow
   sealed adjudication and bind the requested job/current worker/release.
3. Full orchestration `check(..., phase="begin_scoring")`: source bytes,
   manifest/label identities, graph component exclusions, complete sampling
   metadata, code hashes and toolchain artifacts. Only after steps1–2 may this
   full check open training labels and source bodies.
4. Exactly the declared 24 learned jobs; parameter dictionaries equal the pinned
   `adapters_v1/adapter_plan.json` methods; live worker/adapter/scanner/features
   match the prospective code bindings; every raw status has an explicit frozen
   mapping. `method_config.learned_worker_environment` must equal `environment()`
   (Python build and numpy/pandas/scipy/sklearn/lightgbm/joblib/threadpoolctl
   versions). Matching wheel inventory hashes alone does not establish the
   installed learned-model environment.

The loaded worker source is pinned at import. Adapter/scanner/feature modules
are compiled from exact hashed source bytes (bypassing potentially stale
timestamp/size-valid `.pyc` files), and their import hashes are rechecked on
use; stale cached code cannot be recorded under a newly changed file hash.
Loaded library versions must match installed package metadata. Changed code in
a long-lived process is refused; start a fresh process for a new binding.

This is an integrity and procedural release boundary, **not** human identity,
timestamp or signature authentication. The coordinator must supply an authentic
runtime instruction and trusted digest in the actual workflow. A person able
to fabricate the protocol, reviews and all trusted anchors cannot be made into
an independent human expert by hashes. Internal Python helpers are not a
security sandbox. No synthetic switch exists on the production command.

The current failed confirmatory-AP inference policy also blocks production
admission. Passing software tests does not close that scientific prerequisite;
the rare-positive AP study found severe undercoverage in explicit synthetic
designs. The actual external design's coverage remains unknown. The worker
neither computes metrics nor modifies any protocol/gate/metric module.

Future command templates (not executed here):

```
.venv/bin/python papers/security_evaluation/revision1/external_protocol/model_worker_v1/worker.py preflight --root ROOT --binding BINDING --expected-binding-sha256 TRUSTED_BINDING_SHA --release RELEASE
.venv/bin/python papers/security_evaluation/revision1/external_protocol/model_worker_v1/worker.py execute --root ROOT --binding BINDING --expected-binding-sha256 TRUSTED_BINDING_SHA --release RELEASE --authorization AUTHORIZATION --expected-authorization-sha256 TRUSTED_AUTHORIZATION_SHA --job-id raw_tfidf_lr:reentrancy:0 --out ROOT/private_runs/raw_reentrancy
```

## Training, predictions and failure semantics

Training labels join by exact ordered `file_id,path` identities; record IDs are
manifest `node_id` strings. All691 records and their hashes are retained, with
23 reentrancy or18 unchecked positives. These are **published training proxies**;
absence is a proxy zero, not expert-confirmed absence. Model code never receives
external human reference labels. Duplicate/overlapping train/external IDs and
exact source hashes are rejected; expanded-component exclusions are checked by
orchestration. Sources are read and rehashed after admission to detect changed
bytes. Path traversal and source-root escape are rejected by orchestration.

The pinned adapters fit vocabulary/IDF/sparse scaler on training only, or
construct the fixed43 pattern features without a fitted scaler. Failed training
preprocessing aborts the entire fit; no row is removed. LR uses C1, balanced
weights, lbfgs/tol1e−4/max_iter3000; RF500 and LGBM400 preserve the predeclared
tree settings and seeds. The sole added LGBM parameter `verbosity=-1` suppresses
library console logs; effective model parameters are recorded. No tuning occurs.
BLAS is limited to1 thread; LR OpenMP1, tree OpenMP4 and n_jobs4 are explicit.

`scores.csv` always preserves every external file for the job, with `job_id`,
`method,class,seed,node_id,path,source_sha256,execution_status,status,score`.
Successful probabilities must be finite in[0,1]. Failed preprocessing or zero
vocabulary vectors receive their original execution reason, canonical
`preprocessing_error`, and a **blank score**. Inference failures retain
`model_error` and blank scores; there is no safe-value fallback or label-based
deletion. A failed training fit has no invented fitted model: every external
row is `model_error`, `fit_status=failed`, `fitted_object=null`, and the failure
log is bound. A fitted model with a subsequent transform/predict failure is
still honestly marked fitted and retains the resulting error rows.

## Artifacts and resume

Before the first feature fit each job saves `config.json`, executable source
snapshots and a prepared receipt. The config binds ordered source identities and
hashes, the training-label digest, fixed estimator parameters, runtime versions,
all source dependencies and coordinator/protocol/reference anchors.

Completed jobs save full score rows, preprocessing coverage, warning/convergence
records, fit/transform/predict/wall/CPU seconds, configured/observed thread pools,
and Linux cumulative process peakRSS. That memory statistic is a high-water
mark, not isolated incremental allocation for the job. Fitted jobs save a model,
adapter and combined joblib bundle; TF-IDF also saves the scaler. Their hashes,
training-fit metadata and equal pre/post-external adapter-state hashes enter
`fitted_state.json`, compatible with the orchestration schema. **Never load an
untrusted joblib artifact.** Resume verifies bytes without unpickling objects.

`--resume` rechecks admission for production and skips fitting only if the
completed configuration, source/code/environment, exact artifact set and every
artifact hash match. Changed/extra/missing artifacts or incomplete runs are
refused, not overwritten. An intentionally different execution needs a new
output directory and prospective authorization; the worker does not retry a
failed model as if it were the same completed run. Paths are rooted in the
selected binding root; relocating an existing run changes its bound config and
is refused. Failed fits with complete receipts can be verified without retrying.

## Synthetic tests and engineering receipt

The only executable fixture mode generates12 fictional training records and6
fictional external records **inside the code**, including invalid UTF-8 and an
unterminated comment. Its CLI accepts only job ID, output and resume; it has no
source, label, binding or dataset argument. It cannot accidentally consume a
real external cohort. All classifier hyperparameters remain full-sized.

```
.venv/bin/python -m pytest papers/security_evaluation/revision1/external_protocol/model_worker_v1/test_worker.py -q
.venv/bin/python papers/security_evaluation/revision1/external_protocol/model_worker_v1/run_synthetic.py --out papers/security_evaluation/revision1/external_protocol/model_worker_v1/synthetic_check_20261026_v2
```

The engineering runner freezes config/source/test/doc hashes before its24
fictional jobs, verifies every completed job with resume and no refit, and saves
a final receipt. It records these as synthetic fits, never zero total fits or
real external fits. Neither fixture results nor trained fictional models are
scientific external performance evidence.

The first completed `synthetic_check_20261026_v1` is preserved under its original
source snapshots. Independent review then reproduced a generic Python-loader
edge case using a temporary fictional module: timestamp/size-valid stale `.pyc`
could execute old bytes while disk hashes described new source. No source drift
was observed in that completed run. The current loader compiles exact source
bytes and adds a dedicated regression; `synthetic_check_20261026_v2` is the
post-amendment engineering verification. Model parameters/features are unchanged.
The current worker correctly refuses to resume old v1 jobs under its new code
hash; original receipts/snapshots remain intact.

Tests exercise all four model types, the exact24 inventory and full parameters,
full score/failure coverage, train-only state, label/source identity violations,
training aborts, resume/tamper/environment guards, and actual orchestration
draft/blank-review denial with intercepted file reads proving training keys and
source bodies were untouched. The full production happy path is intentionally
not exercised on the real cohort; legitimate human release, a revised adequate
inference policy and coordinator authorization are outstanding.
