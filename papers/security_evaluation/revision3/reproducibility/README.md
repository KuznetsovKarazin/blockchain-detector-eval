# Article 1 reproducibility release

This directory documents the evidence for *How Dependency-Graph Construction Changes Training Eligibility in Smart Contract Vulnerability Benchmarks*. Historical records remain dated and immutable. Revision 2 contains the fourth manuscript's review-triggered controls; revision 3 contains the subsequent extension and this release workflow.

The working source is `https://github.com/KuznetsovKarazin/blockchain-detector-eval`, branch `paper/security-evaluation`. The last pre-release public checkpoint is `9dd44597d9dcb29caf31e0dbaebdcceab4185aff`. The full Article 1 reproducibility package has identifier [10.5281/zenodo.23750089](https://doi.org/10.5281/zenodo.23750089), reserved before release. The versioned GitHub tag is `article1-r5-2026-10-29`. Actual publication is established by the final GitHub/Zenodo receipts.

## What is distributed

The release contains authored code, frozen configurations, source and annotation checksums, file memberships, graph metadata/edges, predictions, aggregate metrics, manuscript sources and computational verification records. Small files live in Git; the versioned `Article_1_R5_Derived_Evidence_2026-10-29.zip` release asset supplies larger derived files and fit evidence at their original paths. `EVIDENCE_ASSET.json` pins that asset's name, download URL, size, SHA-256 and internal inventory hash. `ARTICLE1_RELEASE_MANIFEST.json` at the release root indexes checksum-verified manifest parts with the SHA-256 and byte count of every restored file.

The separate `Article_1_R5_Full_Reproducibility_2026-10-29.zip` contains the complete restored public tree in one archive. For that archive, skip the evidence-fetch step below: all evidence paths are already present. It excludes raw upstream corpora and per-file annotation values just like the Git-plus-asset distribution.

The 23 recovered historical gzip files retain their original bytes and Git blob identities. The six lexical NPZ arrays under `revision1/recovery_20261026/representation_edges_v1/` are **new canonical reconstructions**. The six original arrays remain lost. Matching 120 partitions and 20 summary CSV files supports component-level reproduction; it does not establish identity of the entire original edge lists. New pair-level controls explicitly use the canonical reconstructions.

Upstream raw contracts, annotation files, installed packages and package wheels are not included. DAppSCAN lacks a verified repository licence at the pinned commit. Public tables therefore omit its per-file proxy annotation columns, while retaining memberships, scores and aggregate counts. `PUBLIC_PROJECTION.json` lists every omission/transformation and both original and public hashes. Frozen original receipts are preserved with their original hashes. Use the local reconstruction command below before checking receipts that refer to withheld originals. This separation is deliberate and does not label transformed public bytes as original evidence.

## Environment and sources

Use Python 3.12 and Linux for the recorded resource measurements. From the repository root:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r papers/security_evaluation/requirements-development.txt
.venv/bin/python -m pip install threadpoolctl==3.6.0
.venv/bin/python papers/security_evaluation/revision3/reproducibility/fetch_release_evidence.py
.venv/bin/python papers/security_evaluation/revision3/reproducibility/verify_release_manifest.py
```

The asset can also be downloaded in a browser and supplied with `fetch_release_evidence.py --archive PATH_TO_ZIP`. All member hashes are checked before extraction; differing existing files are refused. Graph-only replay then uses the restored derived files. Source-dependent equality and model work additionally require DAppSCAN commit `66a56619c44770e05c2db600fa6468115ff0dcd5`:

```bash
.venv/bin/python papers/security_evaluation/revision3/reproducibility/fetch_pinned_dappscan.py --receipt reproduction/source_verification.json
.venv/bin/python papers/security_evaluation/revision3/reproducibility/materialize_annotations.py --receipt reproduction/local_annotations.json
```

The fetcher uses a sparse checkout of `DAppSCAN-source/contracts` and `DAppSCAN-source/SWCsource`, avoiding the unrelated bytecode and audit-PDF trees. It verifies all 21,457 source SHA-256 values (107,970,249 bytes) and 948 frozen annotation hashes. Git servers may ignore partial-clone filtering, so allow additional space for Git objects. Existing modified or unexpected checkouts are refused. Other historical sources are pinned by `scripts/00_fetch_data.py`; the scenarios below do not require downloading the unrelated bridge/transaction datasets.

## Executable scenarios

Each replay requires a fresh output folder within the checkout. Original programs are imported unchanged; only the output directory is redirected. New plans record current execution inputs and original program hashes. The wrapper compares all output table cells with the saved scientific outputs. Gzip timestamps can change compressed bytes; table values and component assignments must match.

| Scenario | Command suffix for `replay.py` | Inputs beyond the public release | Verified quantity |
|---|---|---|---|
| Fixed-test mechanism and 30 label-blind controls | `labelblind --out reproduction/labelblind_v1` | None | 231 test/graph outcomes, eligibility decomposition, bridge witnesses |
| Whole-project coverage | `project-prefix --out reproduction/project_prefix_v1` | None | 552 graph outcomes and 108 file/project comparisons |
| Ordered exact equality and masking availability | `metadata --out reproduction/metadata_v1` | None | 12 concentration rows, coverage categories and memberships |
| Full/availability-only/masked graph controls (Table 4) | `pairs --out reproduction/pairs_v1` | None; canonical NPZ included | 16 graph rows, edge changes and 24,131-node partitions |
| Trivia-only equality ladder | `equality --out reproduction/equality_v1` | Pinned DAppSCAN contract sources | 21,457 source/scanner checks; giant sizes 3,608, 10,922, 11,172, 19,298 |
| Common informative denominator | `informative-denominators --out reproduction/denominators_v1` | None | Fixed 15,399-node projections of the existing graphs |
| Project-only and raw-identity structural controls | `structural-baselines --out reproduction/structural_v1` | None | Three structural graph projections |

For example:

```bash
.venv/bin/python papers/security_evaluation/revision3/reproducibility/replay.py pairs --out reproduction/pairs_v1
```

Recompute all 480 AP/review-yield values of the fourth revision's B/C comparison after local annotation materialization:

```bash
.venv/bin/python papers/security_evaluation/revision2/reproducibility/audit_expanded_results.py --repo . --out reproduction/r4_model_metric_check.json
```

This checks 120 logical evaluations, 72 original physical fits and 48 valid score reuses. It does not train models. A fresh training repetition uses a new output directory:

```bash
.venv/bin/python papers/security_evaluation/revision2/model_link/expanded_contrast.py prepare --out papers/security_evaluation/reproduction/r4_models_v1
.venv/bin/python papers/security_evaluation/revision2/model_link/expanded_contrast.py run --out papers/security_evaluation/reproduction/r4_models_v1
```

The revision 3 extension has its own frozen design, 852 jobs and a 5,408-file primary evaluation population. Recompute all saved metrics, including nested test projections, with independent rational arithmetic:

```bash
.venv/bin/python papers/security_evaluation/revision3/reproducibility/audit_r5_public_scores.py --run papers/security_evaluation/revision3/model_link/run_20261029_v1 --out reproduction/r5_metric_check.json
```

To train and summarize a fresh repetition:

```bash
.venv/bin/python papers/security_evaluation/revision3/model_link/run_r5.py prepare --out papers/security_evaluation/reproduction/r5_models_v1
.venv/bin/python papers/security_evaluation/revision3/model_link/run_r5.py execute --out papers/security_evaluation/reproduction/r5_models_v1 --workers 2
.venv/bin/python papers/security_evaluation/revision3/model_link/analyze_r5.py --run papers/security_evaluation/reproduction/r5_models_v1
```

These commands are conditional historical-population diagnostics; they do not provide an untouched external test or independent-family confidence intervals. Runtime and model output equality can depend on numerical dependencies/platforms even with matching package versions.

## Boundaries

`CLEAN_TREE_CHECKS.json` records the release-preparation runs actually performed. A successful table replay is distinct from rebuilding every historical source representation or retraining every model. Original private recovery audits can refer to old private paths or Git objects; their dated receipts are historical evidence, not additional promised portable workflows.

The full repository snapshot also preserves earlier public general-project outputs, including DeFi feature tables with author-derived `y` fields and authored synthetic-fixture truth. The omission rule concerns raw third-party corpora and restricted upstream DAppSCAN annotations; it does not assert that every result in the broader snapshot is label-free.

The compiler audit and authored synthetic reporting/Slither fixtures remain supplementary. They are not evaluations of real external detector performance. Human expert judgments and real external detector scores are absent; no such study is claimed by this release.

Code is MIT-licensed. Author-created results and documentation in this article release are CC BY 4.0; see `LICENSE-RESULTS.txt`. Upstream datasets retain their own terms and must be acquired from their original sources.
