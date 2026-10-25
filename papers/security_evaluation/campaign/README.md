# Development campaign runner and current execution block

**The planned comparative campaign must not run.** Expanded-source checks
invalidate the two selected tests' historical joint-disjoint training pools.
At Jaccard 0.8, only 13 or 10 admissible training files remain, with zero
reentrancy positives in one design and zero unchecked-call positives in the
other. Both checked normalisations give these counts. The complete 95-design
audit fails the declared count/dispersion screens at 0.7, 0.8 and 0.9.

The scientific assessment is
`../design_feasibility/expanded_sensitivity_recovered_20261025_v1/CAMPAIGN_GATE.json`.
`READINESS_20261025.json` records its hash and four actual execution-block
checks. No comparative model fits were performed and no external model scores
were computed.

## What is implemented

`run_development.py` separates preparation from execution. It consumes selected
membership CSV or gzip CSV bundles, verifies the entire original 7,080-object
project/clone graph, enforces one common T and equal training object/positive
counts, and saves exact configurations, source snapshots, environment and
input hashes before fitting. Only pinned DAppSCAN source paths and explicitly
declared proxy labels are accepted; external scoring is prohibited.

Defaults are raw and normalized TF-IDF/LR, pattern RF with 500 trees, pattern
LightGBM with 400 estimators, both primary classes, four regimes and five
paired sampling seeds. Hyperparameters are fixed and there is no tuning.
Deterministic LR fits are reused only when ordered training/test memberships
and class are identical. Stochastic tree fits retain separate seeds.

Each fit would save predictions without labels, explicit failure statuses,
convergence warnings and runtime/memory measurements. AP and workload are
reported per fixed T; scores are never pooled across tests. Seed variation
is not a confidence interval over independent projects. Failed files receive
missing scores, never safe/zero scores. Unknown labels remain unknown in the
shared metrics utility.

## Enforced execution assessment

Preparation defaults to blocked comparative execution. A selected bundle's
computed `CAMPAIGN_GATE.json` overrides its older `train_allowed: true` flag.
The runner checks that gate before loading model inputs. New prepared runs
also contain a hash-frozen `inputs/execution_assessment.json`.

Execution requires an allowed assessment tied to the selected bundle hash,
a passing computed expanded-graph gate covering all configured tests and
training memberships, and matching evidence input/output hashes. Merely
asserting approval cannot override a failed computed gate. Missing assessments,
changed configurations and changed evidence cause refusal. Unlocking requires
a new valid design and a new prepared run, never editing a frozen config.

The original `historical_graph_outside_seed{2,4}_prepared_20261025_v1` directories
remain unchanged. The current
`historical_graph_outside_seed{2,4}_blocked_20261025_v2` directories each contain
160 logical jobs and 144 planned physical fits after LR deduplication, with
`execution_allowed: false`. Together they describe the abandoned 320-job
grid, not executed results. Tests and direct checks confirm that both old and
new directories refuse execution without changing their frozen files or
creating fit directories.

## Diagnostic reproduction remains available

The narrow exception permits reproduction of the previously scored pilot
only: reentrancy, raw TF-IDF/LR, seed 0, exactly the original train/T memberships,
and the unchanged published prediction hash. It does not require an invalid
independence claim. Changing the test, class, method, seed or fixed model
configuration is rejected.

After workspace loss, a newly identified diagnostic run was executed at
`../runs/recovered_campaign_integration_20261025_v1/`. Its scores match the
original immutable pilot exactly (maximum absolute difference 0). A second
execution skipped the completed fit and left one attempt. The lost earlier
integration outputs were not fabricated; the new run is explicitly identified
as recovery validation. Its original manifest and source snapshot remain
unchanged following the execution-gate addition.

To prepare another diagnostic reproduction in new directories, from the
repository root with the development environment:

```bash
.venv/bin/python papers/security_evaluation/campaign/create_pilot_integration_bundle.py \
  --pilot papers/security_evaluation/runs/dev_fixed_t_20261025_v1 \
  --out INTEGRATION_BUNDLE
.venv/bin/python papers/security_evaluation/campaign/run_development.py prepare \
  --bundle INTEGRATION_BUNDLE --out INTEGRATION_RUN \
  --classes reentrancy --seeds 0 --methods raw_tfidf_lr \
  --regimes joint_project_clone_disjoint
.venv/bin/python papers/security_evaluation/campaign/run_development.py run \
  --out INTEGRATION_RUN --max-fits 1
```

For future valid comparative work, `prepare --assessment ASSESSMENT_JSON`
accepts a new immutable assessment. Running or resuming uses the same `run
--out RUN` command; completed artifacts are hash-checked before reuse, and
`--retry-failed` preserves previous attempts. The current failed designs are
not eligible for that route.

## Validation and scientific scope

The focused test file is `tests/test_security_campaign.py`: 22 tests passed,
including indirect joint links, matched counts, common tests, source rejection,
tamper detection, failure semantics, deterministic reuse, and missing/failed
assessment rejection before model data loading. The exact reproduction
exception is tested against the published pilot and rejects unseen memberships.

The two rejected development tests were selected after the pilot using class
counts, not comparative scores. Each covers 1,062 files, 16.12% of the historical
DAppSCAN population, outside the giant component. They share 961 files
(90.49% of each test), so they are not independent replications. These scope
restrictions remain relevant even apart from the decisive expanded-graph
failure. The result is evidence about split feasibility, not detector quality.
