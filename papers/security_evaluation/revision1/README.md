> **Current continuation, 28 October 2026:** Revision3 and the core reporting/Slither sources have been restored with their original hashes after workspace maintenance. Some uncommitted dynamic outputs remain missing. See [the current status](recovery_20261028/STATUS_RU.md). Dated26October sections below are preserved historical checkpoints, not proof of current local artifact availability.

> **Current state, 26 October 2026:** local recovery and public availability differ. Twenty-three gzip files match original bytes; six original NPZ files remain unrecovered and have separate new canonical reproductions. Compressed artifacts remain excluded from the public update. Read [publication status](PUBLICATION_STATUS.md).

# Article 1: scientific evidence and current reproduction status

The revised article is [Population Coverage and Dependency-Aware Evaluation of Smart Contract Vulnerability Detectors](../manuscript/DRAFT_REVISION2.md). It reports completed dependency-mechanism and conditional model-stability analyses. External human validation remains prospective: no completed expert judgments, external model fits or external scores. The overall protocol and protocol B remain drafts; module-level execution configurations do not constitute an external validation freeze.

## Read the evidence

| Scientific question | Main entry | Detailed artifacts |
|---|---|---|
| How do project relations, lexical similarity and source coverage concentrate components? | [Mechanism report](graph_mechanism/REPORT.md) | `graph_mechanism/run_20261025_v1/`: 3,822 outcomes, nested sample ranks, memberships, threshold curves and project-contracted cuts |
| Is concentration already present under exact identity? | [Identity-control table](graph_mechanism/identity_controls_20261025_v1/identity_control_concentration.csv) | Byte equality, normalized-stream equality, explicit empty-stream control |
| What changes when identifiers/numbers are preserved, declarations are masked, or containment is used? | [Primary comparison](representations/primary_comparison.csv) | `representations/run_20261025_v1/`, `segmented_control_20261025_v1/`, `all_threshold_comparison.csv`; all graph nodes remain present |
| How much does training-subset selection change scores on the original fixed development test? | [Completed results](sampling_variance/run_20261025_v2/RESULTS.md) | 20 paired draws × four regimes × four methods; separate estimator-seed panel; 360 logical evaluations / 282 physical fits |
| What is the exact random-ranking AP reference? | [Sampling results and limitations](sampling_variance/run_20261025_v2/RESULTS.md) | Exact expectation 0.025363 for 1,082 files / 21 positives; descriptive Monte Carlo, not an exchangeability p-value |
| What is ready for external assessment? | [External package](external_protocol/README.md) and [protocol B](external_protocol/PROTOCOL_B.md) | 1,998 files; 691 training files under the declared graph; 180 probability-sampled cases, two blank reviewer forms and a separate 17-case identity census |
| Which external engineering prerequisites are implemented? | [Current engineering readiness](external_protocol/ENGINEERING_READINESS_20261026.md) | 24 adapter + 24 performance + 21 independent tests; 30 solc versions and Slither 0.11.6 inventoried; no contract compilation, scan or external scoring |
| How was the evidence checked? | [Independent scientific verification](independent_verification.json) and [current 251-test receipt](recovery_20261026/FINAL_VERIFICATION_20261026.json) | Independent graph cuts, sample replay, 360 AP / 1,080 workload recalculations; recovery identity/content checks and separate synthetic engineering tests |
| What is new relative to prior work and the book? | [Related-work evidence](related_work/EVIDENCE.md) and [book relationship](book_novelty.md) | Verified bibliography, source checks and disclosure boundaries |
| How does the text map to results? | [Evidence map](../manuscript/REVISION1_EVIDENCE_MAP.md) | [Figures and provenance](../manuscript/figures_revision1/README.md); [review response](review_response.md) |

The current revision-2 manuscript has five tables, six figures, 17 references and explicit AI-assisted-method/declaration text. The revised 18-page Word document passed [final visual QA](recovery_20261026/MANUSCRIPT_DOCX_QA.json). Earlier scientific analyses and source snapshots remain unchanged. [Recovery records](recovery_20261026/REPRESENTATION_RECOVERY.md) distinguish exact membership archives from newly generated edge arrays; the old omissions list is retained as history.

## Interpretation boundaries

The full-corpus giant at Jaccard .8 is 20,588/21,457 (95.95%). The earlier 5,879/6,587 (89.25%) refers to the historical evaluation projection. Project plus byte equality connects 16.82%; project plus exact normalized-stream equality connects 90.05%. These are consequences of specified dependence rules, not proof that all connected files are semantically equivalent.

The model experiment uses the original, already inspected 1,082-file/21-positive test within one historical joint component. The joint training pool has one unique membership; repeated main-panel rows reuse its fit. Quantiles describe training variation, not new-family confidence intervals. The unused `sampling_variance/run_20261025_v1` is preserved preflight material; only `run_20261025_v2` was scored. The two rejected outside-giant campaigns remain blocked.

The representation study's no-empty-shingle baseline explicitly differs from the earlier empty-shingle policy. Its 712 graph-retained / 711 informative DAppSCAN files do not silently replace protocol B's 691-file training manifest. Masking explicit library/interface declarations is lexical extraction, not validated semantic removal. Public review forms are blank; source labels and unknowns are not converted into expert truth.

## Reproduction

Use Python 3.12 and the repository's pinned raw corpora. Module commands and dependencies are documented in the mechanism report, external README and model run files. New computations require new output directories: frozen configurations, source snapshots, input hashes and output receipts are part of each experiment. `verify_revision1.py` checks the completed evidence without fitting models; its saved result is `independent_verification.json`. The current public update contains new code and textual metadata. Previously published development predictions remain available; the recovered compressed memberships and new canonical edge archives are excluded from this update after automatic publication rejection. Third-party Solidity, book text, original row annotations and private reviewer keys remain outside the public package.

See [PLAN.md](PLAN.md) for the revision questions and [../STATUS.md](../STATUS.md) for completed work versus the remaining prospective external study. No protocol registration, DOI, journal submission or third-party correspondence has been performed by this revision.
