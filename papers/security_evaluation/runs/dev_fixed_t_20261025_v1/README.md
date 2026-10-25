# Fixed test development pilot

This run establishes that a four-regime comparison is executable on one shared
DAppSCAN test with exactly matched training size and proxy-positive count. It is
a development experiment, not a confirmatory external test and not a causal
estimate of leakage. No external model scores were computed.

## Design fixed before scoring

`pilot_config.json`, `memberships.csv`, input hashes and complete snapshots of the
three used source files were saved before fitting. The selected test consists of
the first 1,082 paths in a label-blind SHA-256 ranking of the largest historical
joint component, using the salt in the config. This is ceil(20% of 5,408 files),
16.43% of all 6,587 DAppSCAN development files. The test contains 21 published
reentrancy findings and belongs to one joint component.

The joint graph is reconstructed from all 7,080 original C2 rows and its partition
is checked against historical `safe_group` values before restriction to DAppSCAN.
The clone partition is inherited from normalized-token LSH candidate generation
and CRC32 token-shingle Jaccard verification at 0.8. It is an observed dependency
graph, not a certified absence of all code or project relationships.

Each training pool excludes the exact test objects. The project regime excludes
all projects represented in the test; the clone regime excludes its clone
components; the joint regime excludes every complete transitive project/clone
component represented in the test, including the unsampled remainder of the
5,408-file component. Matching uses the minimum available count separately for
proxy labels 0 and 1, with a shared deterministic path ranking. All four actual
training sets contain 1,179 files, including 31 published reentrancy findings.

The raw-token TF-IDF vocabulary and sparse StandardScaler are fitted on each
training set only. Logistic regression uses the historical fixed configuration,
no tuning and seed 0. All four fits converged. Predictions contain identifiers
and scores, without redistributing source labels.

## Observed development results

| Training restriction | Raw eligible pool | Matched train | Proxy positives in train | AP against proxy labels | Fit and score seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Other files only | 5,505 | 1,179 | 31 | 0.076554 | 3.63 |
| Project disjoint | 1,362 | 1,179 | 31 | 0.028044 | 4.77 |
| Clone disjoint | 4,706 | 1,179 | 31 | 0.027697 | 3.96 |
| Full joint disjoint | 1,179 | 1,179 | 31 | 0.038475 | 5.65 |

The common test proxy prevalence is 0.019409. This is contextual prevalence,
not the exact finite-sample expected AP of a random ranking. The comparison
controls test objects, training size and proxy-positive count. Composition still
differs: for example, median nonempty lines in the matched training sets are
42, 60, 43 and 60; the counts with any SWC annotation are 176, 357, 196 and 348.
`composition.csv` and `compiler_ranges.csv` document these differences. Library
flags are declaration/path screens, not verified origin labels.

The unrestricted AP exceeds the three restricted values in this run. The joint
value is higher than the project-only and clone-only values, so these observations
do not support a monotonic penalty from stronger restrictions. One test component
and one training draw do not support uncertainty estimates over independent
projects. No bootstrap interval is reported. DAppSCAN proxy zero means no
published finding, not a confirmed negative; these metrics are not verified
vulnerability precision, recall or false-positive rates.

`feasibility.csv` also shows two design limits. Using the entire largest component
as T makes all four eligible pools identical and cannot contrast their dependence
constraints. Using each historical random test fold leaves only 177–228 files and
10–13 proxy-positive cases in the joint training pool. Those alternatives were
not trained or selected using AP.

## Resources and budget amendment

Validation plus the four fits/scoring stages took 19.95 seconds on this execution
host, with a cumulative process peak RSS of 394.42 MiB. Individual fit/scoring
stages took 3.63–5.65 seconds. These are pilot measurements, not estimates for
Slither, RF, LightGBM, clone-threshold sensitivity or a full study. The original
artifact before the later metadata analysis was approximately 4.31 MB. Source
corpus checkout storage is separate. Exact environment and timestamps are in
`environment.json` and `manifest.json`.

The original development config uses ceil(fraction × test size), giving review
counts 55, 109 and 217 at 5%, 10% and 20%. During parallel protocol alignment the
main policy was set to floor; the pilot had already begun scoring. Its config
and outputs are retained unchanged. `posthoc_floor_and_class_feasibility/`
contains an explicitly post-hoc reanalysis of the same predictions with floor
budgets 54, 108 and 216, plus metadata-only feasibility for both primary classes.
It is not a new model experiment. AP is unchanged; no choice of model, test or
training set was made using the reanalysis.

## Reproduction

Run from the repository root with the pinned source corpora present and the
versions listed in `environment.json`. Use a new output directory; the runner
refuses to overwrite an existing run or score it twice.

```bash
python scripts/00_fetch_data.py --only smartbugs-curated SolidiFI-benchmark DAppSCAN
python -m pytest -q tests/test_security_fixed_t.py
python papers/security_evaluation/code/fixed_t_development.py prepare --out papers/security_evaluation/runs/dev_fixed_t_reproduction
python papers/security_evaluation/code/fixed_t_development.py run --out papers/security_evaluation/runs/dev_fixed_t_reproduction
python papers/security_evaluation/code/analyze_fixed_t_development.py --pilot papers/security_evaluation/runs/dev_fixed_t_reproduction --out papers/security_evaluation/runs/dev_fixed_t_reproduction/posthoc_floor_and_class_feasibility
```

This run was executed from a dirty working tree based on `f3e5bccd`. The full
used source files, not just a diff hash, are preserved under `code_snapshot/`,
and each source, config, membership, input corpus file and output is hashed.
The additional post-hoc analysis has its own code snapshots and manifest.
Historical `results/contracts/` files are unchanged.
