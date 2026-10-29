# Supplementary material for the private Revision 4 working manuscript

This supplement reports the ancillary audits, diagnostics and implementation details. References are numbered independently of the main text. The external cohort remains provisional; AP-method material is a separate line of work rather than a detector result.

## S1. External-cohort readiness audit

### S1.1 Methods

We reconcile candidate records by source and identifier, check annotated locations against the saved source, and retain conflicting or unresolved cases. The diagnostic cohort excludes prior SmartBugs-curated exposure, then source-reconciliation disputes and repeated identities. These rules change the target population and are reported explicitly. We screen both direct lexical overlap and full transitive reachability before constructing training exclusions. The proposed response is to preserve test coverage where possible and restrict related training sources, rather than remove inconvenient external cases based on scores.

Human confirmation is a separate task. A prepared review form is not evidence that an annotation is correct. This study reports source consistency and recorded dependency, while a probability-based, independently assessed annotation review and external model evaluation remain prospective.

We also execute a compiler-only coverage check on the fixed 691-file DAppSCAN training pool and 1,998-file candidate cohort. Each file tries up to five compatible pinned compiler releases in a previously fixed order, stopping at the first success. Sources are unchanged. Training imports must resolve within the pinned project snapshot; external files have only their own saved source as verified context. We infer no remappings, fetch no packages and retain unavailable inputs in the denominator. Standard JSON requests AST, ABI and bytecode, with optimization disabled and each compiler's default EVM target. Success requires the expected outputs for root declarations and no error-severity compiler diagnostic; bytecode may be empty or unlinked. This tests the stated source-context policy, not the original project build, deployment or a detector pipeline.

### S1.2 Results

The candidate has 2,182 compact-manifest rows, 2,180 source/identifier keys and 2,181 saved source paths. Seventeen paths require reconciliation: fourteen annotated locations exceed saved source length, two repeated keys have differing annotations, and one path lacks a manifest row. An apparent identifier transcription mismatch remains quarantined. A location mismatch is evidence of inconsistent source mapping, not proof that a vulnerability finding is false.

Against all reference sources, 142 candidate paths match raw bytes, 148 match normalized streams, and 208 have a direct lexical relation at Jaccard 0.8. All exact-byte overlaps belong to the previously used curated source. The diagnostic selection leaves 2,039 files after curated-source exclusion, 2,023 after unresolved-source quarantine and 1,998 after repeated-identity quarantine. These remaining files contain 46 reentrancy and 200 unchecked source-reported positives.

![External candidate selection and dependency audit](figures_revision1/fig06_external_flow.png)

*Figure S1. Source-based selection of the diagnostic external cohort. The 1,998 retained files are a provisional population, not an independently verified test. Source exclusions and training restrictions are different decisions. Of 17 originally problematic paths, one is removed by the earlier curated-source exclusion.*

Direct screening is insufficient for transitive separation. Among the 1,998 retained files, 65 have a direct 0.8 lexical relation to reference data, whereas 186 in 11 proxy components are connected transitively. Retaining the entire diagnostic test and excluding connected historical training components leaves 691 DAppSCAN files, with 23 reentrancy and 18 unchecked proxy positives. Another 350 SolidiFI and 134 SmartBugs files remain, but their different annotation origins cannot be used to conceal the loss of DAppSCAN support in a pooled positive count. DAppSCAN retention changes from 418 at threshold 0.7 to 1,085 at 0.9.

The string-aware scanner changes 92 of 24,131 normalized streams without a scan failure. Fourteen lexical edges disappear at 0.7, none at 0.8 or 0.9, and no training-retention decision changes at those thresholds. Adding 80 equal-address links also changes no partition. These are useful robustness checks for this dataset, rather than evidence that representation choices or deployment provenance are generally unimportant.

The compiler check succeeds for 2,137 of the 2,689 fixed files (79.47%): 1,807/1,998 external files (90.44%) and 330/691 training files (47.76%). Conditioning on attempted compilation gives different figures: 1,807/1,968 (91.82%) and 330/336 (98.21%), respectively. We retain the fixed-cohort denominators because input-context failures are part of practical coverage. The 552 other files comprise 385 unavailable inputs or compiler plans and 167 final compiler errors. In particular, 346 training files lack an accepted import context; this does not establish that their sources are invalid. No file is dropped because compilation fails.

Of the 330 successful training files, 101 have no nonempty root bytecode. Interface or abstract-only sources can compile without providing a deployable target. Twenty successes, ten in each cohort, contain unlinked root bytecode. Compilation therefore establishes neither executable-contract coverage nor successful Slither analysis. These results leave the fixed training and external populations unchanged; they do not justify restricting a detector's reported denominator to successful compilations.

For this proposed external evaluation, no Slither corpus analysis, independent human vulnerability assessment or external ML fit or score has been completed. The source, dependency and compilation audits establish specific readiness conditions, while annotation correctness, deployment-family identity and external performance remain separate empirical questions.

## S2. Auxiliary representation-based training eligibility

This calculation uses a fixed provisional candidate cohort as a geometric query set. It measures historical training support after graph exclusion rather than detector performance.

**Table S1. Representation sensitivity at Jaccard 0.8.** All variants retain 24,131 graph nodes and the same 1,998 candidate test files. The largest component is projected onto all 21,457 DAppSCAN files. Training columns concern the historical 6,587-file DAppSCAN population after excluding components touching that fixed candidate test; positive counts are among informative retained files.

| Source representation | Identifiers and numbers | Largest DAppSCAN component | Graph-retained training | Informative retained training | Retained proxy positives, reentrancy / unchecked |
| --- | --- | ---: | ---: | ---: | ---: |
| Full file | Collapsed | 20,565 (95.84%) | 712 | 711 | 23 / 18 |
| Full file | Preserved | 18,769 (87.47%) | 1,504 | 1,502 | 37 / 29 |
| Library/interface declarations masked | Collapsed | 18,745 (87.36%) | 1,520 | 1,086 | 36 / 25 |
| Library/interface declarations masked | Preserved | 17,177 (80.05%) | 2,150 | 1,539 | 49 / 36 |

The common empty-input policy changes graph-retained historical DAppSCAN training from 691 to 712 files, of which 711 are informative, before the factorial contrasts. Masking suppresses lexical participation while preserving graph nodes and explicit project/raw-identity relations; graph retention therefore differs from usable lexical support. The new availability-only control in the main text further separates these mechanisms. Indeed, 5,198 and 4,742 unavailable DAppSCAN nodes still belong to the actual masked giant under collapsed and preserved tokens, respectively, through the retained structural relations. The masked giant also changes membership: it loses eight DAppSCAN nodes and gains 25 or 31 relative to the availability-only giant under collapsed or preserved tokens, respectively.

The segmented-mask control preserves Jaccard 0.8 largest-component and candidate-separated training counts in both masked variants, although some component memberships change. With containment, informative training changes from 22 to 41 files for collapsed tokens and from 739 to 740 for preserved tokens.

### S2.1 Exact-identity controls on DAppSCAN

All four controls construct the graph on the same 21,457 DAppSCAN files. Project relations are retained. The nonempty lexical variants exclude six empty sources from equality links while retaining their vertices.

| Identity relation combined with project membership | Largest component | Share of DAppSCAN |
| --- | ---: | ---: |
| Raw bytes | 3,608 | 16.82% |
| Exact nontrivia lexeme sequence, preserving all lexemes and boundaries | 10,922 | 50.90% |
| Exact inherited identifier/number-preserving token stream | 11,172 | 52.07% |
| Exact inherited normalized token stream, nonempty | 19,298 | 89.94% |

The strict formatting-only scanner preserves quoted content, punctuation, operators, identifiers and numbers. It records zero scan failures and passes 23 scanner checks, independent union-find reconstruction and three partition-refinement checks. The inherited token-preserving relation omits constructs excluded by its tokenizer and is therefore a different control. Jaccard 1.0 and exact ordered-stream equality yield the same reported largest-component counts in the new controls, which does not imply identical partitions or relation definitions.

## S3. Separate incomplete-label AP methodology

These computational diagnostics are retained for assessment as a distinct methods contribution. They do not repair the missing external validation in the detector study and are not a completed separate article. Yilmaz and Aslam [1] develop statistical AP estimates from incomplete relevance judgments; the calculation below distinguishes estimation from logical bounds conditional on fixed known labels.

Before external scoring, we examine a proposed survey-weighted AP percentile procedure on 59 prespecified artificial finite populations and sampling designs. The rescaled bootstrap for stratified sampling without replacement uses the finite-population correction in Section 7.2 of the Household Finance and Consumption Network report [2]. Its variance motivation is not an AP coverage guarantee. We enumerate every sample and the finite bootstrap support, keeping interval issuance, coverage conditional on issuance, and the probability of issuing a covering interval separate. No actual external score or expert response enters this diagnostic.

A distinct calculation assumes finite scores for every item and partial labels in {positive, negative, unknown}. It gives sharp AP endpoints over all feasible binary completions, treating unsampled and unresolved labels as unknown. These are logical identification bounds, not confidence intervals or survey-weighted estimates. The following subsections specify both calculations, the tied-score dynamic program and their synthetic results. Neither calculation changes the interpretation of the complete proxy labels used in the main manuscript’s fixed-test model section or supplies external vulnerability validation.

### S3.1 Prespecified interval diagnostic

The main synthetic factorial has 20 items, three designs (simple random sampling of four without replacement; two strata of sizes 16 and 4 with two sampled from each; and census), three score patterns (distinct, tied in groups of five, and all tied), and six positive-label patterns. Two no-positive guards and three 50-item, one-positive examples complete the 59 scenarios. We enumerate all 795,934 sample states, with their design probabilities, rather than approximate the sampling distribution. All scores and labels are artificial.

Survey-weighted AP substitutes design-weighted positive and item totals into the grouped-threshold AP formula. Within stratum \(h\), base weights are \(w_h=N_h/n_h\). Drawing \(m_h=n_h-1\) items with replacement gives multiplicities \(r_{hi}\) and replicate weights

\[
w^*_{hi}=w_h\left(1-\lambda_h+\lambda_h\frac{n_h}{m_h}r_{hi}\right),
\qquad \lambda_h=\sqrt{\frac{m_h(1-n_h/N_h)}{n_h-1}}.
\]

Census weights remain fixed. The finite-correction formula follows [2]; no AP coverage theorem is assumed. Exact-bootstrap endpoints use the discrete inverse CDF at 0.025 and 0.975. The production procedure also uses 2,000 replicates with each of three prespecified seeds and its saved quantile convention. All four calculations give the same coverage and mean-width summaries in this grid. Undefined AP is never replaced by zero.

Among the 39 positive-population noncensus scenarios, conditional coverage of nominal 95% intervals ranges from 22.22% to 100%; 16 scenarios fall below 95%. These counts characterize the chosen grid, not the prevalence of failures elsewhere. All 18 positive census controls give exact point intervals; both no-positive guards retain undefined AP.

One example is countable directly. A single positive belongs to the highest tied group of five among 20 items, giving true AP 0.2. An SRS of four includes it with probability 20%. Conditional on inclusion, the other three items have \(\binom{19}{3}=969\) possible selections. In \(\binom{15}{3}=455\), no other highest-group item is sampled; every positive-weight replicate then has AP one, and the interval is the incorrect \([1,1]\). The other 514 selections cover, giving conditional coverage \(514/969=53.04\%\), and a 10.61% probability of issuing a covering interval. An unequal-strata example with two positives gives 22.22% conditional coverage. More bootstrap draws cannot repair the first example's loss of ranking information.

### S3.2 Sharp completion bounds and exact verification

For a declared population of \(N\) items with finite scores, sort its \(G\) equal-score groups from highest to lowest. Group \(g\) has \(a_g\) known positives and \(u_g\) unknown labels; \(N_g\) and \(A_g\) are cumulative item and known-positive counts. Choosing \(z_g\in\{0,\ldots,u_g\}\) unknown positives gives group count \(p_g=a_g+z_g\), cumulative positives \(T_g\), and total positives \(P\). Grouped-threshold AP, with ties retained, is

\[
\operatorname{AP}=\frac{1}{P}\sum_g\frac{p_gT_g}{N_g},\qquad P>0.
\]

A dynamic program keeps the two extreme numerators for each cumulative unknown-positive count \(t\):

\[
F_g^{\min/\max}(t)=\min/\max_z\left\{
F_{g-1}^{\min/\max}(t-z)+\frac{(a_g+z)(A_g+t)}{N_g}
\right\},\qquad F_0(0)=0.
\]

The optimization uses feasible preceding states and \(0\le z\le u_g\). Every prefix decomposes into one preceding count and one current count; subsequent terms depend on the earlier assignment only through its cumulative positives. Thus retaining these extrema loses no optimum. At the final group, division by the fixed denominator \(P=A_G+t>0\), followed by optimization across terminal states, gives attainable global endpoints. Saved choices reconstruct feasible label completions at both bounds. A greedy earliest/latest assignment of unknown positives is not generally optimal when scores tie.

The implementation scales terms by \(\operatorname{lcm}(N_1,\ldots,N_G)\), uses integer transitions and returns rational endpoints. It needs \(O(Nm)\) transitions for \(m>0\) unknown labels, plus sorting; the bit cost depends on the scaling integer. A possible all-negative completion is reported separately as undefined. A point AP is returned only if every feasible completion identifies the same defined value. The interval is an envelope: not every interior real value must be attainable. It carries no sampling probability or 95% interpretation, and makes no claim of mathematical priority.

Exhaustive validation through six items covers every ordered tie pattern and partial-label vector: 27,993 cases and 149,796 binary completions. An independent exact threshold formula agrees with every fixed-total and global endpoint, including their attaining completions. The full proof, input restrictions, executable implementation and dated validation are supplied in the artifact's [AP completion-bound module](../revision1/external_protocol/ap_bounds_v1/README.md); the [interval diagnostic](../revision1/external_protocol/performance_validation_v1/REPORT.md) supplies the complete synthetic grid. These are completed computational studies, not evaluations of the actual external cohort.

The artificial interval diagnostic neither estimates coverage for the planned review of 180 file/class cases from the 1,998-file external population nor invalidates every bootstrap approach. Completion bounds condition on correct known labels and finite scores for the declared population. They exclude reviewer error, training variability and unseen families. If a method fails to score an intended file, a success-only bound concerns a changed population. Separate AP bounds give a conservative, generally nonsharp difference envelope rather than a confidence statement about superiority.

## S4. Supplementary model-linkage diagnostics

The graph-model audit belongs to the main study rather than the partial-label AP calculations above. For the 1,082-file historical test, all files are connected to training under C in all 80 original historical draw/regime cells. The exclusive categories use direct project-or-clone relations first, then B-transitive-only paths, then newly connected C paths, and finally C-disconnected status. Direct flags are also retained separately.

| Historical training regime | Direct-union test files across draws | B-transitive-only files | Reentrancy positives in direct / transitive groups |
| --- | ---: | ---: | --- |
| Unrestricted | 1,001–1,049 | 33–81 | 17–20 / 1–4 |
| Project-disjoint | 66–78 | 1,004–1,016 | 0 / 21 |
| Clone-disjoint | 978–1,022 | 60–104 | 17–20 / 1–4 |
| Joint-disjoint | 0 | 0 | All 21 occur in the newly C-connected group |

For project-disjoint training the direct-clone subgroup has zero positives, so AP is undefined; the small transitive-only groups of the unrestricted and clone regimes contain only one to four positives. These subgroup populations differ in both size and composition. Review-yield contributions retain the original full-test budgets and sum to the original total, including expected tie handling. Every full-test AP reproduces its stored value within 1e−14. These checks validate the descriptive decomposition without creating an unconnected expanded-graph comparison group.

### S4.1 New matched B–C policy experiment

The new experiment uses the unchanged 1,082-file test and the same historical model configurations. B supplies five distinct class-stratified 708-file/24-positive draws; C supplies its one complete 708-file/24-positive pool. LR uses seed zero and tree methods use paired seeds zero through four. There are 72 distinct physical fits and 120 logical evaluations, with 12 C fits reused across draw indices. The run has zero failed fits and zero convergence warnings. Thirty nonfatal LightGBM feature-name warnings are preserved in the execution records; none were filtered from the audit trail.

A separate arithmetic implementation independently recomputed all 120 AP values and all 360 budget-yield values. Every comparison passed. Complete paired outcomes, training memberships, source hashes, plans and warning records are retained under `revision2/model_link/expanded_contrast_20261028_v1/`. Table 6 reports B-minus-C AP contrasts. The repeated use of the C pool and test means that 25 tree comparisons are not 25 independent model families or test replications.

## S5. Artifact status and lineage

The public checkpoint is [9dd44597d9dcb29caf31e0dbaebdcceab4185aff](https://github.com/KuznetsovKarazin/blockchain-detector-eval/tree/9dd44597d9dcb29caf31e0dbaebdcceab4185aff). Revision 4 and its new analyses remain private. No article-specific release tag or DOI is asserted. The following availability audit checks files and lineage; it does not claim a fresh execution of every listed scenario.

| Reproduction scenario | Public checkpoint supplies | Additional requirements and status |
| --- | --- | --- |
| Inspect graph and model summaries | Tables, code, configurations, hashes and receipts | Available for inspection; reading a table is not a recomputation |
| Recompute baseline string-aware components | Complete `nodes.csv`, `edges.csv` and code | Numerical environment; pinned annotations for label aggregates; inputs are public, full rerun not claimed by this audit |
| Check saved component memberships and fixed-test mechanisms | Code and text results | Private compressed memberships/contracted graph files, or controlled regeneration |
| Check representation and segmented controls | Metadata, summary tables, code and replacement manifests | Six original membership gzip files, six new canonical NPZ files and pinned sources; verifies the replacement execution rather than original complete-edge identity |
| Recompute historical AP and review yield | Saved predictions for 360 logical evaluations and configurations | Pinned annotations; membership evidence for selection checks; arithmetic verification differs from refitting |
| Refit historical models | Executable code and frozen configurations | Pinned raw corpora, dependencies and a newly named run; no numerical identity is promised without execution |
| Repeat artificial AP-bound calculations | Code, synthetic inputs and results | Numerical environment; no real expert judgments are required for these separate methodological checks |
| Inspect 28 October reporting and authored Slither run outputs | Code, summaries, receipts and inventories | Private package of nine large files and the separate preserved reporting-audit ZIP; fresh public checkout is insufficient |
| Conduct external detector evaluation | Draft protocol and blank forms | Actual independent review, prospective protocol freeze and subsequent scoring; no completed external result exists to reproduce |

The private recovery package contains 23 original gzip files matching their recorded Git blob hashes and internal checksums. Six original representation-edge NPZ archives remain lost. Six separately named canonical NPZ replacements reproduce 120 saved partitions and 20 tables, while six membership archives retain their original hashes. This supports partition and table quantities rather than recovery of every original edge. New edge-level claims must identify the replacement archive used.

For the new review controls, all 21,457 DAppSCAN Solidity files (107,970,249 bytes) and 948 annotation files were reacquired from commit `66a56619c44770e05c2db600fa6468115ff0dcd5` and verified against frozen hashes. The acquisition uses the source and annotation directories only; unrelated bytecode and document payloads are unnecessary. Other pinned corpora are distinct inputs and were not reacquired in this availability audit. A complete public release needs explicit source-acquisition commands, independent run directories, scenario-specific expected outputs and a clean-checkout verification. An archival DOI identifies that completed package; it does not repair missing inputs by itself.

## S6. Additional implementation and sensitivity detail

The highest-impact project bridge is supported by Tenderize's `Faucet.sol` and Livepeer's `LivepeerTokenFaucet.sol` at Jaccard 0.804878; neither witness declares a library or interface. A second bridge joins PieDAO's `IAToken.sol` and Fei's `IFeiRewardsDistributor.sol` at 0.809524; both declare interfaces, and the smaller side contains 36 files. These deliberately selected witnesses illustrate heterogeneous connectors. They do not estimate the prevalence of semantic libraries or prove that an individual witness file is indispensable.

Containment produces larger components than Jaccard under every variant at 0.8: 21,454, 20,824, 21,430 and 19,336 DAppSCAN files for full collapsed, full preserved, masked collapsed and masked preserved representations, respectively. Its ability to connect a small representation to a much larger file therefore does not resolve concentration here. It changes which reuse patterns count as dependencies and can make transitive exclusion more restrictive.

A separately frozen segmented-shingle control preserves the main Jaccard 0.8 largest-component counts while preventing shingles from spanning removed declarations. Some memberships change, so equal summary counts do not imply partition invariance; the auxiliary training-support results are retained in Supplement S2.

Historical source-cap detail: The historical population contains 6,587 DAppSCAN files and all 493 reference files, totaling 7,080. The adapter retains every DAppSCAN file linked to a source-annotation record, including records for weaknesses outside the selected classes. This gives 948 metadata-linked files. It then retains at most 20 other files per project directory. Project directories and source paths are sorted; a single Python `random.Random(0)` generator shuffles each directory's unannotated list before truncation. The result adds 5,639 files without annotation records. The cap was a computational choice intended to prevent large repositories from dominating; it is label-informed and is not a probability sample of the full corpus. The uncapped inventory contains the same 948 metadata-linked files and 20,509 others, across 608 observed project-directory groups.

Historical pattern-feature detail: The pattern vector includes 38 counts of calls, checks, authorization, arithmetic, state and control-flow constructs, normalized per 100 nonempty source lines; a call-before-write heuristic; a parsed compiler-version value and pre-0.8 indicator; and log-transformed line and function counts. These are lexical heuristics, not formal vulnerability predicates. Vectorizers and scalers are fitted on training data only. The model feature code remains historical, including its legacy comment removal, so a graph-normalization sensitivity does not silently change the model experiment.

Random AP expectation derivation: To see this, expand AP as \(K^{-1}\sum_r I_r(\sum_{j\le r}I_j)/r\), using \(\mathbb E I_r=K/N\) and \(\mathbb E I_rI_j=K(K-1)/(N(N-1))\) for distinct positions. 

## References

[1] Emine Yilmaz; Javed A. Aslam (2008). Estimating average precision when judgments are incomplete. *Knowledge and Information Systems*, 16, 173–211. [10.1007/s10115-007-0101-7](https://doi.org/10.1007/s10115-007-0101-7).

[2] Household Finance and Consumption Network (2023). *Household Finance and Consumption Survey: Methodological report for the 2021 wave*. European Central Bank, Statistics Paper Series No. 45, Section 7.2. [Official report](https://www.ecb.europa.eu/pub/pdf/scpsps/ecb.sps45~4bbcfb02eb.en.pdf).
