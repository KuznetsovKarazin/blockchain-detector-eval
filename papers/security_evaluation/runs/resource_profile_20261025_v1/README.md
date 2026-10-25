# Development resource profile

This run measures computation only. The training membership is the saved
joint-disjoint development pool: 1,179 DAppSCAN files, including 31 SWC-107
proxy positives. The 1,082 test files provide source code only. No test
annotation files were read, no accuracy metrics were computed, and no
predictions were persisted. No Salzano candidate files were used.

The source snapshots and fixed model configurations were saved before timing.
Membership, source inventory, selected code files and training annotations were
checked against the development pilot hashes and the clean pinned DAppSCAN
checkout. The training-only annotation extraction reproduces the saved training
count. Configurations retain the declared historical hyperparameters, with no
tuning.

| Method | Train preprocessing s | Test preprocessing s | Fit s | Predict s | Total s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw TF-IDF LR | 2.947 | 1.052 | 1.098 | 0.001 | 5.104 |
| Normalized TF-IDF LR | 1.562 | 1.042 | 0.132 | 0.001 | 2.742 |
| Pattern RF 500 trees | 2.663 | 1.642 | 1.250 | 0.088 | 5.650 |
| Pattern LightGBM 400 estimators | 3.243 | 1.664 | 0.381 | 0.009 | 5.301 |

The cumulative process peak was **322.16 MiB**. This is the Linux `ru_maxrss`
high-water mark across sequential measurements, not isolated per-model memory
or the memory needed for all downloaded corpora. Setup and input validation
took 1.81 seconds, outside the per-method totals. Both LR models converged.
LightGBM emitted a feature-name warning when predicting from the same numeric
matrix representation; the warning is preserved in the measurement table.

The environment exposes nine logical CPUs and a cgroup quota equivalent to
eight CPUs. LR native pools were observed at one thread. Tree estimators use
`n_jobs=4`, OpenMP pools were observed at four threads, and BLAS pools were
observed at one. These are configured and observed native pool limits, not a
measurement of concurrent core utilization throughout every operation.

For **one fixed test and one training-size point**, four regimes times two
classes times five paired sampling seeds give 40 evaluations per method,
160 fits in total. Linear extrapolation from this profile gives approximately
**12.5 minutes of model computation**. This is not a runtime guarantee: training
composition, vocabulary, class and other workload can alter the cost. It
excludes data acquisition/audit, expert review, Slither, bootstrap, tuning,
additional tests and learning-curve sizes. GPU is not required for this profile.

## Reproduction

From the repository root, after installing the development requirements and
obtaining the pinned data and saved pilot manifests:

```bash
.venv/bin/python papers/security_evaluation/resource_profile.py \
  --pilot-run papers/security_evaluation/runs/dev_fixed_t_20261025_v1 \
  --out papers/security_evaluation/runs/resource_profile_reproduction
```

The output directory must not exist. This command reproduces the four-method
resource measurement; it does not launch the projected 160-fit scientific
experiment or the external evaluation.

## Preserved preliminary attempts

`../resource_profile_20261025_v1_failed_psutil/` preserves a failed attempt:
instantaneous RSS collection raised `psutil.NoSuchProcess` in the PID namespace
after the first model. The final implementation uses the working cumulative
`resource.getrusage` peak and does not report instantaneous RSS.

`../resource_profile_20261025_v1_openmp_default/` preserves a completed profile
with estimator `n_jobs=4` but observed default OpenMP pools of nine outside the
fit calls. Its linear projection was 10.6 minutes. The final run explicitly caps
OpenMP at four. Neither timing is an accuracy result, and their difference does
not establish a thread-scaling effect; no controlled resource comparison was
designed.
