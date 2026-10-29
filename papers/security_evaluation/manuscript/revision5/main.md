# How Dependency-Graph Construction Changes Training Eligibility in Smart Contract Vulnerability Benchmarks

Oleksandr Kuznetsov¹˒²

¹ Department of Theoretical and Applied Sciences, eCampus University, Italy.

² Department of Intelligent Software Systems and Technologies, School of Computer Science and Artificial Intelligence, V.N. Karazin Kharkiv National University, Ukraine.

ORCID: [0000-0003-2331-6326](https://orcid.org/0000-0003-2331-6326)

## Abstract

Benchmark construction can omit source files that connect retained training and test groups. We examine how the population and representation used to construct a dependency graph change training eligibility while evaluation files remain fixed. A controlled ablation separates candidate discovery, source coverage and external candidate sources. Expanded coverage merges outside-giant holdouts with the historical giant component; for a test already within that giant, the eligible pool instead changes from 1,179 to 708 files. Exact-identity controls show that project closure connects 16.82% of the source population under raw-byte equality and 89.94% under identifier and number normalization with empty representations excluded. A formatting-only intermediate control and fixed informative-file projections separate representation changes from the loss of lexical participation under declaration masking. On the full historical component, expanded exclusion lowers mean AP for the tree baselines; random forest shows the most consistent contrast across training compositions. Review-yield effects depend on the model and budget. These policy comparisons retain differences in training composition and do not identify the semantic value of individual paths. The results show why benchmark reports need both the evaluated file set and the population used to construct dependencies, together with a relation justified by the intended generalization target.

**Keywords:** smart contracts; benchmark construction; training eligibility; code clones; dataset provenance; source coverage

## 1. Introduction

A detector evaluated on a held-out source file may still have access to closely related training code. The relationship can be direct, as when two files are duplicates, or indirect, as when one file belongs to the same project as a clone of another file. Consequently, splitting by project and splitting by clones address different relations. Closing their union transitively imposes a stricter separation rule and can place many otherwise separate observations in one component.

There is a further choice that is easy to overlook: which files participate in dependency construction. A study may cap the number of files from large projects to control computation or class imbalance, construct groups on that reduced population, and then evaluate models. Files omitted from the benchmark can nevertheless connect groups that remain in it. Adding these files need not change a single training example, test example or label to change which train/test combinations satisfy the stated separation rule. This paper investigates that distinction between the evaluation population and the population used to establish dependencies.

The question matters for smart-contract security because reuse is common and evaluation resources have different annotation origins. A manually annotated example, an injected defect and a finding extracted from an audit report support different interpretations. A source file with no recorded audit finding is not necessarily safe. Published detector scores can therefore mix dependence between files, selection of particular projects, model variability and uncertainty in the target labels. An evaluation should identify which of these quantities it actually measures.

Our starting point is a previously reported historical DAppSCAN experiment described in Chapter 13 of *Custom AI Solutions for Blockchain Systems: Detection and Prevention of Anomalies* [1]. That experiment supplies the capped population and initial joint partition retained here as a fixed projection. We extend the analysis to uncapped sources, exhaustive lexical screening, alternative representations and repeated training draws. A supplementary readiness audit retains the preparatory analysis of a proposed external cohort.

The study addresses three research questions:

- **RQ1:** How does the source population used to construct dependencies affect the component structure and admissible training sets of a fixed evaluation population?
- **RQ2:** Which explicit project and lexical relations account for large components, and how sensitive are the findings to thresholds and source representation?
- **RQ3:** How do training composition, estimator randomness and expanded-graph exclusion affect conditional model scores on fixed historical evaluation populations?

The main contribution is a population ablation on a fixed benchmark projection that separates changes in candidate discovery from changes in source coverage. Two complementary contributions identify the role of source representation through exact-identity controls and examine project–lexical interactions through contraction and bridge diagnostics. The model experiments compare historical training regimes, separate sources of score variation and directly test historical versus expanded joint exclusion at matched training support. Admissibility and conditional score changes under those policies are measured; semantic information transfer through individual paths remains a separate hypothesis.

## 2. Related work

Leakage and duplication are established evaluation problems. Kaufman et al. [2] relate leakage to legitimate prediction information and the modeling objective, while Kapoor and Narayanan [3] examine its consequences for scientific ML practice. DéjàVu maps duplication in source repositories [4], and Allamanis [5] studies the effect of duplicated code on model evaluation. We examine how the population used to construct transitive dependence changes eligibility among the same benchmark files.

Similarity-aware splitting has established precedents outside software. Petti and Eddy [6] show how bridging sequences can collapse single-linkage clusters; GraphPart [7] combines restricted clustering with reassignment and removal to obtain homology-separated partitions. These approaches distinguish preserving the full connected partition from enforcing direct pairwise separation after omitting objects. Our population ablation keeps evaluated Solidity files fixed and studies paths that can pass through omitted benchmark sources.

Multi-relation component collapse is also established. Atas Guvenilir and Doğan [8] combine compound similarity, protein similarity and interaction edges, obtaining a giant component that prevents a component-based split before graph modification. We build on these component-based analyses by measuring construction-population and representation effects on a fixed smart-contract benchmark projection.

The appropriate split depends on the prediction target. MoleculeNet [9] contrasts random, scaffold and temporal splitting. Roberts et al. [10] explain how blocking can change interpolation into extrapolation, while DataSAIL [11] ties similarity-aware splitting to the intended deployment setting. These works support specifying the evaluation target before selecting a relation, rather than treating stricter exclusion as automatically better. Cross-project defect prediction supplies a mature software setting for project-level transfer [12].

Concrete smart-contract learning studies report random holdouts: Deng et al. [13] use a 70/30 split, and Zhang et al. [14] use 70/20/10 after preprocessing that includes duplicate removal. These examples motivate reporting the sampling rule and scope of dependency construction. Their split descriptions alone provide no evidence of contamination or score inflation in those studies.

Vulnerability-detection research provides further reasons to separate benchmark scores from security capability. Chakraborty et al. [15] examine dataset artifacts, class distributions and realistic evaluation. Croft et al. [16] study annotation and duplication problems in vulnerability datasets. PrimeVul combines improved labeling, deduplication and chronological evaluation [17]. Risse and Böhme [18] use transformations and vulnerable/patched pairs to expose limitations that conventional evaluation misses. Risse, Liu and Böhme [19] examine missing context and spurious correlations in function-level benchmarks. These findings motivate separate reporting of file-level proxy-label scores, source relations and semantic vulnerability evidence.

For Solidity, Kondo et al. [20] analyze clone prevalence, clone clusters and OpenZeppelin reuse. Their clone and library analysis motivates our separate treatment of project grouping, exact source identity and alternative lexical representations. SmartBugs supports reproducible tool execution [21], alongside an earlier empirical comparison of analyzers [22]. SolidiFI evaluates tools using injected bugs [23], whereas DAppSCAN derives weaknesses from project audit reports [24]. These annotation regimes must remain distinguishable in a combined study.

Recent evaluations also challenge simple transfers between benchmarks. Salzano et al. [25] release line-level annotations and compare multiple tools. Khalid et al. [26] compare static and LLM-based tools on SmartBugs and an audit-derived FORGE subset. Our controlled population ablation complements these detector evaluations by constructing relations beyond a fixed evaluation subset and measuring the resulting training eligibility. It separates source coverage from candidate discovery and evaluates the consequences of combining project membership with code reuse.

## 3. Study design

### 3.1 Source populations and labels

The study fixes repository revisions rather than treating corpus names as immutable datasets. Table 1 distinguishes the source inventory used in this study from counts reported for other releases of the associated papers.

**Table 1. Source populations and their role.**

| Source | Files at the studied revision | Annotation origin | Role |
| --- | ---: | --- | --- |
| DAppSCAN | 21,457 | Published audit findings | Main graph population; historical subset for model diagnostics |
| SmartBugs-curated | 143 | Curated vulnerable examples and annotated locations | Reference source and historical graph context |
| SolidiFI-benchmark | 350 | Defect injection into 50 base contracts across seven folders | Reference source and historical graph context |
| Salzano replication corpus | 2,181 paths | Source-reported manual line annotations | Candidate external cohort; no model scoring |

The first three sources total 21,950 paths; including the external candidate gives 24,131. Their pins are respectively `66a56619c44770e05c2db600fa6468115ff0dcd5`, `230e649123477eff332742a59a1c7cc6dc286cab`, `4b0573e1b3f7031396de6f48f7f3e7380222ad3a` and `da079440bf2cf4fd803c864ef29aeea8a3da50c3`.

The historical population contains 6,587 DAppSCAN files and all 493 reference files. It retains every file linked to an audit-annotation record, plus at most 20 other files per project using a fixed sorted traversal and seeded shuffle. Its 948 metadata-linked and 5,639 other files therefore form a label-informed computational subset rather than a probability sample. The uncapped inventory contains the same 948 metadata-linked files and 20,509 others across 608 project-directory groups. Supplement S6 preserves the exact cap procedure.

The primary classes are reentrancy and unchecked calls. DAppSCAN SWC-107 and SWC-104 map to these classes. Both the historical and the full DAppSCAN populations contain 114 reentrancy-positive files and 74 unchecked-call-positive files. A zero means no corresponding published finding in the adapter, including files that have other findings. It does not mean expert-confirmed absence. Model results against these targets are called **proxy-label performance**. Source-reported negative annotations, unresolved records and confirmed negative judgments are not merged into this status.

### 3.2 Dependencies, projection and training eligibility

Let \(U\) be the population on which dependencies are constructed, and let \(G_U=(U,E_U)\) be an undirected graph defined by a fixed representation and relation. For project relations, each DAppSCAN directory is a group, each SolidiFI base-contract index links its injected variants, and each SmartBugs file is its own group. Candidate files with equal lowercase source identifiers are linked separately when the external population is present. Raw-byte equality and lexical similarity provide additional relations. Their connected components define operational separation groups. Reachability under these relations alone does not establish shared vulnerability information.

For an evaluation population \(S\subseteq U\), write \(\Pi_U|_S\) for the partition obtained by intersecting every connected component of \(G_U\) with \(S\) and discarding empty intersections. This is a **projection of a connected partition**. It differs from taking the induced graph \(G_U[S]\) and computing components afterward: an otherwise omitted file in \(U\setminus S\) can lie on a path between two members of \(S\).

For a fixed test \(T\subset S\), the admissible joint-disjoint training pool is

\[
A_U(S,T)=\{x\in S\setminus T: C_U(x)\cap T=\varnothing\},
\]

where \(C_U(x)\) is the component containing \(x\). Exact test objects are always excluded. Project-only and clone-only pools apply the corresponding relation rather than their union.

An elementary graph fact explains the direction of the population effect. If \(S\subseteq U\subseteq V\) and the pairwise relation is unchanged, then \(\Pi_U|_S\) refines \(\Pi_V|_S\), and \(A_V(S,T)\subseteq A_U(S,T)\). Every path available in \(U\) remains available in \(V\); adding vertices and edges can join existing components but cannot separate them. We use this elementary monotonicity property to interpret empirical changes. Component fractions can move in either direction when the construction population, and hence the denominator, changes.

We report component counts, largest-component size and the concentration summary

\[
D_2(S;U)=\frac{|S|^2}{\sum_j |C_j(U)\cap S|^2}.
\]

This inverse-Simpson quantity describes component-size balance; it has no role in confidence intervals or power calculations.

### 3.3 Lexical relations and population ablation

The historical graph used normalized token five-grams, MinHash LSH candidates and CRC32-shingle Jaccard verification at 0.8. New audits use exhaustive sparse set intersections with 128-bit BLAKE2b shingle digests. With shingle sets \(Q(a),Q(b)\), lexical Jaccard is

\[
J(a,b)=\frac{|Q(a)\cap Q(b)|}{|Q(a)\cup Q(b)|}.
\]

The exhaustive claim concerns this representation and digest scheme, not semantic equivalence. Exact raw-source hashes are checked separately. An additional control compares project closure with raw-byte equality, exact ordered normalized-stream equality, and normalized-stream equality restricted to nonempty streams. This separates approximate similarity from information lost during normalization. Project and identity groups are conceptual equivalence relations; their storage as compact star links does not alter the partition. When constructing a subpopulation, these links are regenerated rather than filtered through a possibly omitted star center.

The A–D ablation at threshold 0.8 separates four graphs: A, the saved historical graph; B, exhaustive construction on the same 7,080 files; C, exhaustive construction on all 21,950 reference files; and D, construction after adding the 2,181 candidate paths. Every comparison projects onto the same historical DAppSCAN files and tests. Thus A–B examines the changed discovery procedure, B–C examines uncapped reference coverage, and C–D examines the additional candidate sources.

For sensitivity analysis, we evaluate project-only, clone-only and joint relations at 13 thresholds: 0.70, 0.75, 0.80, 0.85, 0.90, 0.92, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99 and 1.00. Five deterministic path-hash rankings give nested 10%–90% DAppSCAN prefixes; the full population is the common 100% endpoint. The other 493 reference files remain present. These source selections use no labels. These prefixes model omitted files within a corpus, allowing parts of a project to remain. Omission of entire projects requires a separate project-level selection. The historical cap follows a different selection rule and is shown separately.

Post-review controls use ten deterministic label-blind path-hash tests in each of three frames: outside the historical giant, inside it, and across the full historical DAppSCAN population. Each test contains 1,062 files; membership is fixed before evaluating A and C. A separate source-coverage control selects whole project directories with five deterministic project-hash rankings and retains every file in a selected project, plus the other 493 reference files. Both controls were specified before their new calculations, after the original results and review had been observed.

To examine connectivity mechanisms, we contract declared projects into vertices and collapse cross-project lexical links into simple edges. Equal-byte groups connect every represented project pair, rather than choosing an arbitrary star center. We compute articulation vertices and bridges on this graph, weighting vertices by their DAppSCAN file counts. A removal statistic counts files separated from the largest remaining piece after excluding the removed project's own files. This measures structural fragility; it is not a recommendation to delete projects to obtain a preferred split.

### 3.4 Representation sensitivity

The legacy normalizer removes comments using regular expressions, then collapses most identifiers and numeric literals while retaining selected Solidity keywords, types and API names. A string-aware scanner changes comment recognition while leaving the other token rules unchanged. This isolates one implementation issue from the broader effect of identifier normalization.

A further two-by-two sensitivity design compares full source with source whose balanced top-level `library` and `interface` declarations are masked, and collapsed identifiers/numbers with preserved identifiers/numbers. The scanner is lexical structure extraction, not a compiler AST. Declared contracts, including abstract contracts, remain; source outside the masked blocks is retained. Masking does not remove inherited library implementations, copied library code inside contracts, or all third-party origins. The graph retains nodes and explicit identity/project relations even when a lexical representation becomes uninformative. A structural scan failure suppresses lexical representation in the masked variants, without a partial-mask fallback; the full-file variants retain the corrected source tokens.

Besides Jaccard, this analysis uses \(|Q(a)\cap Q(b)|/\min(|Q(a)|,|Q(b)|)\), the maximum of the two directional containment fractions. The resulting value is symmetric: it tests whether most of the smaller representation is contained in the larger one. It should not be described as a directed dependency proof. Both similarities are assessed at 0.70, 0.80, 0.90, 0.95 and 0.99. Extraction failures and missing lexical information are recorded explicitly. All four variants suppress lexical relations between empty representations, while retaining their graph nodes. The preceding threshold experiment preserves the inherited empty-shingle policy; its results are therefore reported separately from this controlled factorial comparison.

The availability-only masking control retains full-file similarities but removes lexical edges incident to any file that becomes uninformative or fails the masked scan. It preserves all graph nodes and explicit project/raw-identity relations. Comparing this control with actual masked representations measures the additional graph changes among surviving lexical participants.

We also project each unchanged full-graph partition onto the same 15,399 DAppSCAN files whose masked representations remain informative under both identifier conventions. This fixed counting set is used in every representation control, including full-file graphs. The operation changes the counted population, while all construction vertices and paths remain present. The unique largest component is the same under the complete and common-informative projections.

A formatting-only exact-identity control scans each DAppSCAN source into a sequence of lexical items, retaining every nontrivia lexeme, quoted string content and item boundary while removing comments and whitespace. It preserves identifiers, numbers, operators and punctuation, and excludes empty sequences from lexical equality. All DAppSCAN nodes and project relations remain present. This DAppSCAN-only identity control is distinct from the inherited token-preserving representation and from Jaccard equality of shingle sets. Scanner cases, file hashes and independent component reconstruction verify the implementation.

Because concatenating residual source can create five-grams across a removed declaration, a separately frozen post-hoc control forms shingles within each retained source segment. It preserves the masking decisions, token conventions, graph population and explicit relations; only boundary-spanning shingles are suppressed.

### 3.5 Fixed-test model variability

The model study predicts reentrancy proxy labels on the original 1,082-file development test, selected by a label-blind hash ranking of 20% of the largest historical component. It contains 21 positives and belongs to one historical joint component. The same test contains only three unchecked-call proxy positives, so this diagnostic is restricted to reentrancy; unchecked calls enter the feasibility analyses only. No candidate external file is scored. The four training regimes exclude exact test objects only, all represented projects, all represented clone components, or the full transitive project–clone components.

Every training draw contains 1,179 files and 31 proxy positives. Within each label value, the same deterministic path rank pairs the draw across regimes, and the minimum available class count determines the matched sample size. Twenty draw indices vary this ranking. The joint pool itself contains exactly 1,179 files, so its twenty draws have identical membership. The main panel fixes the estimator seed at zero; a separate panel varies tree-model seeds 0–19 on this one joint pool. This distinguishes variation from selecting training files from variation inside the estimator. Identical configurations and ordered memberships reuse a fitted model with explicit provenance.

**Table 2. Model configurations; no hyperparameter search.**

| Method or stage | Configuration |
| --- | --- |
| Raw-token LR | Historical tokenizer with comments removed and identifiers/numbers preserved; TF-IDF and logistic regression below |
| Normalized-token LR | Same historical tokenizer with identifier/number collapsing; TF-IDF and logistic regression below |
| TF-IDF, both LR methods | Token pattern `\S+`; 1–3-grams; minimum document frequency 2; at most 50,000 features; sublinear term frequency; no lowercasing |
| Scaling and LR | Training-fitted `StandardScaler(with_mean=False)`; `lbfgs`; C=1; balanced class weights; tolerance 0.0001; maximum 3,000 iterations |
| Pattern random forest | 43 source-pattern features; 500 trees; balanced-subsample weights; minimum leaf size 1; four worker threads |
| Pattern LightGBM | Same 43 features; 400 estimators; learning rate 0.05; 31 leaves; row fraction 0.8 every iteration; column fraction 0.8; balanced weights; four worker threads |
| Estimator randomness | Main panel seed 0; separate fixed-joint-pool tree panel seeds 0–19 |

The 43 pattern features summarize source constructs, a call-before-write heuristic, compiler-version indicators and source size. They are lexical proxies. Vectorizers and scalers are fitted on training data only. Model features retain the historical tokenizer, so graph-representation sensitivity does not silently alter the historical model experiment.

We report sklearn average precision, not trapezoidal precision–recall area, and review yield at 54, 108 and 216 files, corresponding to floor budgets of 5%, 10% and 20%. Boundary score ties use the expected positive count under uniform tie ordering and the attainable range. Failures retain missing scores and explicit status. Draw summaries and paired differences are descriptive conditional distributions, not intervals for unseen projects.

For a uniformly random distinct ranking of \(N>1\) files containing \(1\le K\le N\) positives, the exact finite-sample expectation is

\[
\mathbb E[\mathrm{AP}]=\frac{H_N}{N}+\frac{(K-1)(N-H_N)}{N(N-1)},
\qquad H_N=\sum_{r=1}^{N}\frac1r.
\]

For the fixed test, the expectation is 0.025363, whereas prevalence is 0.019409. At review budget B, uniform random ranking has expected yield BK/N: 1.0481, 2.0961 and 4.1922 findings at budgets 54, 108 and 216, respectively. Exhaustive small-case checks and a 10,000-permutation reference verify the calculation. The random-ranking reference is not an inferential permutation test: file-label exchangeability and independent-family replication have not been established.

A post-review linkage audit classifies each test file relative to each saved training membership, using the unchanged legacy relation at Jaccard 0.8 and conceptual project/raw-identity groups. Overlapping direct-project and direct-clone flags are retained, alongside exclusive classes prioritized as direct union, B-transitive-only, newly connected in C, and C-disconnected. The last two classes distinguish paths enabled by omitted reference files. Subgroup AP and contributions to the original full-test review budgets are recomputed from saved predictions; zero-positive groups retain undefined AP. This linkage audit is a descriptive reanalysis of saved scores; the separate new fitting experiment is specified next.

### 3.6 Matched exclusion and linked-file retention

The expanded-exclusion experiment evaluates the entire 5,408-file historical giant component, including its 83 reentrancy proxy positives. This primary evaluation population contains the earlier 1,082-file diagnostic test. Both tests induce the same joint-disjoint training pools: B permits 1,179 files with 31 positives; C leaves 708 files with 24 positives. The 471 files newly excluded by C contain seven positives. Evaluating the full historical component reduces dependence on the particular earlier test slice, although it remains one component from the same previously inspected corpus.

Fifty deterministic class-stratified draws from the B pool each contain 708 files and 24 positives, matching the complete C pool. The first five draws preserve the memberships of the preceding experiment, which is reported in Supplement S4. Both LR methods use seed zero; random forest and LightGBM use paired seeds zero through four. Configurations remain those in Table 2. For the primary composition summary, AP and review yield are computed separately for each tree seed, then their values are averaged within each training draw. The 50 B metric means are compared with the corresponding C mean. Seed-matched comparisons are reported separately. These empirical distributions describe the specified selection process; 250 tree comparisons are not 250 independent test replications.

A complementary retention analysis varies the number of newly C-linked files admitted to training: 0, 118, 236, 353 and 471. Five nested composition rankings expand the selected linked-file prefix and contract the C-disconnected prefix while retaining 708 total files and 24 positives. The linked subsets contain respectively 0, 2, 4, 5 and 7 positives. Thus retaining all 471 linked files places them in 66.53% of the training set, rather than making all training files linked. The zero-linked endpoint is the complete C pool. Every nonzero retention level already connects all giant test files to training under C; the levels vary the amount of linked training support, rather than the fraction of connected test cases. This analysis tests sensitivity to the composition of admitted files; linked status remains associated with their source content and is not randomized independently of it.

The composition study requires 612 distinct fits and the additional retention levels 240, for 852 total. The primary test is fixed throughout. Review budgets are floor fractions of 5%, 10% and 20%: 270, 540 and 1,081 files. Uniform random ranking gives expected AP 0.016836 and expected yields 4.1439, 8.2877 and 16.5908. We also score ten previously defined, label-blind 1,062-file slices of the same giant and the earlier 1,082-file test. These overlapping subsets are descriptive sensitivity checks, not independent external replications. The run plan and memberships were frozen before the new fitting, after earlier results and feedback had been observed.

### 3.7 Analysis chronology and computational verification

The population and representation controls and expanded-exclusion model studies were introduced after inspection of the historical results. They are revision-stage sensitivity analyses. Their saved run plans fix the selected inputs and configurations before the corresponding computations; this chronology is distinct from prospective preregistration. All contrasts are interpreted conditional on the stated corpus, labels and test populations.

OpenAI ChatGPT/Codex assisted in developing analysis code. Empirical quantities were generated by executed scripts. Verification uses separately implemented component reconstruction, source-hash checks and independent arithmetic recomputation of AP and review yield. These software checks do not constitute independent human vulnerability adjudication. Frozen configurations, memberships, outputs and the checks actually performed are included in the computational records.

## 4. Results

### 4.1 RQ1: Source coverage changes eligibility on fixed files

The historical DAppSCAN projection has 227 joint components at threshold 0.8, with 5,408 of 6,587 files in the largest component. This 82.10% result was already part of the book baseline. Table 3 reports the new controlled ablation on that same projection.

**Table 3. Population ablation at Jaccard 0.8.**

| Graph | Construction population | Components among the same 6,587 files | Largest projected component | Eligible training for test 2 / test 4 |
| --- | ---: | ---: | ---: | ---: |
| A: saved historical | 7,080 | 227 | 5,408 | 5,422 / 5,418 |
| B: exhaustive historical | 7,080 | 227 | 5,408 | 5,422 / 5,418 |
| C: uncapped references | 21,950 | 198 | 5,879 | 13 / 10 |
| D: references plus candidate | 24,131 | 197 | 5,879 | 13 / 10 |

A and B have identical projected partitions. Thus exhaustive discovery on the original population does not explain the observed change. C enlarges the projected largest component to 89.25% and reproduces the training collapse before the candidate external files are added. D merges another projected component without further changing the two eligible training counts. Both comment-removal implementations give the same result at 0.8. This controlled comparison attributes the eligibility change to source coverage within the fixed relation and projection. Monotonicity predicts its direction; the magnitude depends on the components touched by the test.

The two tests each contain 1,062 files outside the historical giant component, or 16.12% of historical DAppSCAN. They were identified from 95 deterministic proposals using proxy-positive counts and component-dispersion screens after the initial pilot. Under the historical graph they pass those screens, but under the expanded graph their training pools contain respectively zero/one and one/zero reentrancy/unchecked positives. The tests share 961 files and are not independent replications. Their selection outside the historical giant initially makes that large component eligible for training. Under C, 428 (40.30%) test-2 files and 425 (40.02%) test-4 files join its enlarged successor. Exclusion then removes the entire successor: the training loss for test 2 is 5,409 files, comprising the 5,408-file historical giant and one additional file; the test-4 loss is exactly the historical giant. The headline collapse is therefore a merger event conditional on where the test was selected, rather than thousands of independent exclusion effects.

Post-review controls selected ten tests by label-blind hashing in each of three prespecified sampling frames. Outside-giant tests have 5,415–5,424 eligible files under A and 7–16 under C. Inside-giant tests already exclude the giant under A; their eligible pool changes from 1,179 to 708. Tests selected across all historical DAppSCAN files retain 211–317 under A and 197–280 under C, with losses of 6–42 files. The original 1,082-file model test, which lies inside the giant, also changes from 1,179 to 708. These controls preserve the distinction between a large outside-giant merger effect and the smaller marginal exclusions for other test locations.

Constructive witness paths through 28 and 29 added files suffice to connect the affected historical components of tests 2 and 4 to the old giant; Supplement S6 gives the path construction and its nonminimality limitation.

Across all 95 proposals, neither normalizer nor address policy yields a passing design at thresholds 0.7, 0.8 or 0.9: zero of 1,140 design–graph combinations satisfies all original screens. The criteria required at least 500 matched training files, 20 training positives and 20 test positives per class, plus component-dispersion conditions. These are operational criteria rather than a power calculation. The failure concerns those proposals under that relation; it is not a proof that every group-disjoint evaluation is impossible.

![Population ablation on a fixed historical projection](figures_revision1/fig03_scope_ablation.png)

*Figure 1. The source population used for graph construction changes connectivity among the same original files. A–B holds population fixed, B–C adds uncapped reference sources, and C–D adds candidate sources. Training counts concern the two fixed 1,062-file tests selected outside the historical giant component; these are distinct from the tests used in the model analyses.*

### 4.2 RQ2: Large components arise from combining relations

On the complete 21,457-file DAppSCAN inventory, the largest project-only component has 1,132 files (5.28%), and the largest clone-only component at 0.8 has 100 files (0.47%). Their union connects 20,588 files (95.95%). This is an interaction between project membership and normalized lexical matching across projects. A large union component arises even though each constituent relation has small components.

The distinction persists at more restrictive thresholds. At 1.0, lexical edges require identical normalized shingle sets, but the largest joint component still contains 19,321 files (90.05%); the largest clone-only component contains 39 (0.18%). The joint concentration summary rises from 1.086 at 0.8 to 1.233 at 1.0. Exact equality of lossy shingle sets remains a representation-level relation, distinct from equality of source bytes or behavior.

Exact-identity controls sharpen this distinction. Project membership combined only with raw-byte equality yields a largest component of 3,608 files (16.82%). Replacing byte equality with exact ordered normalized-stream equality produces 19,321 (90.05%); excluding empty streams from that equality gives 19,298 (89.94%). The dominant component therefore already appears under exact normalized equality. Identifier and number collapsing, amplified by project closure, accounts for much of the concentration; the raw-byte control gives a substantially smaller component. The six empty normalized sources account for 23 attached full-corpus files, rather than the overall concentration. A new formatting-only equality control, constructed on the full DAppSCAN inventory with all nontrivia lexemes preserved, yields 10,922 files (50.90%) in the giant. The inherited identifier/number-preserving stream control yields 11,172 (52.07%), while normalized nonempty-stream equality yields 19,298 (89.94%). The intermediate control therefore separates similarity introduced by removing formatting and comments from additional merging introduced by the inherited token abstraction. Supplement S2 gives the identity controls and their construction population explicitly.

![Threshold sensitivity of project, clone and joint relations](figures_revision1/fig01_thresholds.png)

*Figure 2. (a) Largest-component shares across lexical thresholds on all 21,457 DAppSCAN files, with project-only and clone-only relations shown separately from their union on a logarithmic axis. (b) Eligible historical training for the two fixed 1,062-file tests. The full-population 95.95% and historical-projection 89.25% values have different denominators.*

Nested source coverage shows that the historical cap is not the only way to expose this behavior. At 0.8, the median largest-component fraction across five label-blind 10% prefixes is 59.11%, with a range of 45.59%–64.85%. At 50% coverage the median is 90.57%, and at 90% it is 95.27%. The complete-population value is 95.95%. The five rankings describe file-level source-selection sensitivity within this corpus, rather than independent-corpus uncertainty or a whole-project omission experiment.

Whole-project omission also produces concentration, with a different sampling mechanism. At the nominal 10% prefix, file sampling covers a mean of 339.8 of the 608 projects and gives a mean joint giant fraction of 57.70%; whole-project sampling retains 60 projects and gives 76.82%, ranging from 52.32% to 91.43% across rankings. The whole-project samples contain 1,256–2,777 files. Their project-only giant has mean 20.93% and maximum 33.63%, compared with 5.45% and 5.64% for the file prefixes. Joint concentration exceeds the project-only baseline under both mechanisms. The cross-mechanism contrast also changes project-size composition and file count, so it does not isolate the effect of clone relations.

![Component growth with source coverage](figures_revision1/fig02_population.png)

*Figure 3. Nested path-hash selections vary the share of DAppSCAN source files present during dependency construction. Other reference sources remain fixed. Lines show the median and shading the minimum–maximum across five specified rankings, not confidence intervals. The historical label-informed cap is a separate comparator.*

The contracted full-reference graph at 0.8 has 801 vertices and 6,848 simple cross-project links. Its 26 weighted articulation projects and 55 bridges do not identify a single project whose removal dismantles the dominant component. After excluding the removed project's own files, at most 82 DAppSCAN files separate from the largest remaining piece following one project removal. Connectivity is distributed across the contracted graph. The statistic identifies structural connectors under the relation; their security relevance requires separate semantic or predictive evidence.

Increasing the threshold restores some training support for the two fixed tests, but does not by itself validate a new experiment. At 0.95 the retained training counts are 513/510; at 1.0 they are 671/669. At the latter threshold the reentrancy/unchecked positive counts are only 11/9 and 12/8. These results explain why numerical train-size feasibility and adequate class support must be reported separately.

The factorial analysis shows that representation materially changes concentration (Table 4). Every control retains all graph nodes, project relations and raw-identity relations; empty lexical representations have no lexical edges. Applying that common empty-input policy changes the normalized full-file giant from 20,588 to 20,565 before masking or identifier preservation. A new availability-only control retains full-file token representations for informative files but removes lexical edges incident to any file that becomes unavailable under masking. This isolates the graph consequence of lost lexical participation before considering changed representations among surviving participants.

**Table 4. Availability controls with complete and common-informative denominators.** Every graph retains all 24,131 construction vertices. The complete DAppSCAN projection contains 21,457 files; the fixed common-informative projection contains the same 15,399 masked-informative files in every row. Cells give the largest component's counted files and share of the stated denominator. Jaccard is 0.8; empty representations have no lexical edges.

| Identifier/number convention | Lexical control | All DAppSCAN, N = 21,457 | Common informative, N = 15,399 |
| --- | --- | ---: | ---: |
| Collapsed | Full-file | 20,565 (95.84%) | 14,676 (95.30%) |
| Collapsed | Availability-only | 18,728 (87.28%) | 13,533 (87.88%) |
| Collapsed | Actual masking | 18,745 (87.36%) | 13,547 (87.97%) |
| Preserved | Full-file | 18,769 (87.47%) | 13,465 (87.44%) |
| Preserved | Availability-only | 17,154 (79.95%) | 12,417 (80.64%) |
| Preserved | Actual masking | 17,177 (80.05%) | 12,435 (80.75%) |

Masking leaves 6,058 DAppSCAN files lexically unavailable: six were already empty in the full-file representation, 6,051 become empty or retain only noninformative material, and one fails structural scanning. The other 15,399 remain informative. No graph vertex is deleted. Many lexically unavailable nodes remain in the giant through retained structural relations. Most of the observed full-to-masked reduction is already present in the availability-only control; the actual masked representation slightly increases the largest-component size relative to that control. This ordered comparison separates loss of lexical participation from changes to surviving representations without assigning a causal percentage to either mechanism.

The common-informative denominator preserves the concentration result: the actual masked giants contain 87.97% and 80.75% of the same 15,399 files under collapsed and preserved tokens. The availability-only fractions are 87.88% and 80.64%. Project-only grouping has a largest component of 824 common-informative files (5.35%); adding raw-source identity gives 2,652 (17.22%). Over all 21,457 DAppSCAN files, those baselines are 1,132 (5.28%) and 3,608 (16.82%). Unavailable vertices can still connect counted files through retained structural relations. These two denominators describe concentration among all files and among a fixed set with informative masked representations.

At Jaccard 1.0 with empty-input exclusion, preserving identifiers/numbers yields an 11,172-file giant (52.07%), compared with 19,298 (89.94%) under collapsed tokens. Exact ordered preserved-stream equality gives the same largest-component count, although equality of this summary does not establish equality of the complete partitions. The inherited tokenizer omits more than whitespace and comments, so this control is not a strict formatting-only canonicalization.

![Lexical availability and source-representation controls](figures_revision2/fig04_representation_controls.png)

*Figure 4. All DAppSCAN nodes remain present. The intermediate control removes lexical edges from sources made unavailable by masking, while keeping the surviving full-file representations. Comparing this control with actual masked representations distinguishes loss of lexical participation from changes among surviving sources. The component sizes are descriptive graph quantities.*

### 4.3 RQ3: Conditional model results under historical and expanded exclusion

#### 4.3.1 Historical regime comparison

Table 5 summarizes the historical 20-draw comparison on the 1,082-file test, using 1,179 training files with 31 positives in every regime. Each unrestricted, project-disjoint and clone-disjoint cell has 20 distinct training memberships. Each joint cell uses one complete pool and one fitted model; its zero selection variation follows from that fixed membership.

**Table 5. Conditional proxy-label AP across 20 paired training draws.** Cells give mean [minimum, maximum], with estimator seed fixed at zero. The joint column is one fixed score. These ranges describe training selection on the same 1,082-file historical test, not uncertainty over new projects.

| Method | Unrestricted | Project-disjoint | Clone-disjoint | Joint-disjoint |
| --- | ---: | ---: | ---: | ---: |
| Raw-token LR | 0.0965 [0.0256, 0.2600] | 0.0420 [0.0243, 0.0608] | 0.0603 [0.0204, 0.1371] | 0.0385 |
| Normalized-token LR | 0.1229 [0.0524, 0.2092] | 0.0740 [0.0478, 0.0993] | 0.1032 [0.0487, 0.2293] | 0.0546 |
| Pattern random forest | 0.2041 [0.0833, 0.3348] | 0.0876 [0.0611, 0.1099] | 0.1787 [0.0731, 0.3077] | 0.0730 |
| Pattern LightGBM | 0.1399 [0.0526, 0.2400] | 0.0680 [0.0567, 0.1029] | 0.1305 [0.0502, 0.2226] | 0.0616 |

Training selection can reverse the ordering seen in the initial draw. Raw-LR project-disjoint AP was initially below joint-disjoint AP, but its mean paired difference is +0.003573; it is positive in 12 of 20 draws. The descriptive 2.5% and 97.5% quantiles are −0.012647 and +0.018556. Raw clone-disjoint training likewise exceeds joint training in 12 draws. Unrestricted means exceed joint scores for all four methods, yet the raw-LR unrestricted range spans 0.025599–0.259966. These results measure conditional sensitivity to training composition. The unrestricted-to-project mean AP drop exceeds the unrestricted-to-clone drop for every method. Project exclusion is associated with the larger score change in this diagnostic. The regimes also select different source and project compositions, so this ordering does not isolate the predictive contribution of project edges versus clone edges (Section 6). The additional project-to-joint differences are 0.003573, 0.019421, 0.014573 and 0.006409 for raw LR, normalized LR, random forest and LightGBM. Clone exclusion is not effect-free: the raw-LR unrestricted-to-clone mean difference is 0.036135. None of these contrasts identifies the predictive value of paths introduced by uncapped sources. All six paired regime contrasts are retained in the accompanying tables.

![Conditional proxy-label AP across training draws](figures_revision1/fig05_sampling_variance.png)

*Figure 5. Twenty paired training draws per method and regime on the unchanged historical test. Dots show draw outcomes; boxes show medians and interquartile ranges; whiskers show observed extrema. Joint training uses one complete pool, displayed as a diamond. The dashed line is exact expected AP under a uniform strict random ranking, not prevalence or an inferential threshold. No interval represents uncertainty over unseen families.*

Estimator randomness contributes a different source of variation. Across 20 seeds on the same joint pool, random-forest AP has mean 0.079056, SD 0.003595 and range 0.073009–0.087179. LightGBM has mean 0.073541, SD 0.018984 and range 0.053175–0.113831. The LightGBM seed SD exceeds its project-to-joint mean difference. Random forest differs: its mean contrast is larger than its seed SD, although the main-panel seed gives the minimum AP in the joint seed panel. Descriptively substituting the joint seed means changes the project-minus-joint mean contrast to +0.008526 for random forest and −0.005556 for LightGBM. Those substituted values compare different panels, not matched experiments, and supply no significance test. The panels isolate different interventions rather than interchangeable error bars.

Review budgets provide a complementary interpretation. At 54 reviews, the fixed joint raw LR, normalized LR, random forest and LightGBM recover respectively 3, 3, 5 and 3 of the 21 recorded findings; at 216 reviews they recover 6, 9, 14 and 13. AP ordering need not hold at every budget: raw project-disjoint training has higher mean AP than joint training but retrieves only 2.65 findings on average at 54 reviews, compared with the joint model's 3. Uniform random ranking would recover 1.0481 and 4.1922 findings on average at those two budgets. The joint raw model’s yields of 3 and 6 should be interpreted against those references. All yields use the same historically inspected proxy labels.

A post-review linkage audit checks whether these saved predictions allow the expanded graph to be tested directly. Across all 80 original historical regime-by-draw training memberships, every one of the 1,082 test files is connected to at least one training file under C. In unrestricted, project-disjoint and clone-disjoint training, the connection already exists under B; in joint-disjoint training, all test files become connected only after including omitted sources. There is therefore no C-unconnected comparison stratum within these existing score queues. A within-model comparison of connected and unconnected test files is unidentifiable from them. Comparing models trained under different exclusion policies is a distinct estimand.

#### 4.3.2 Expanded exclusion on the full historical giant

The full-giant experiment compares the two exclusion policies on 5,408 files with 83 proxy positives (Table 6). Every B draw connects all test files to training under C; the C pool is disjoint from the test under that graph. Training size and positive count remain fixed at 708 and 24. The B mean AP exceeds the C mean for all four methods, but the relation to ordinary training-composition variation differs substantially by model.

**Table 6. Matched exclusion on the full historical giant.** The B mean averages 50 training compositions. Tree AP values are first averaged over five paired estimator seeds within each composition; C is the mean AP over its five seeds. LR uses seed zero. The final column is the empirical share of B composition scores at or below the C score, rather than a p-value. Differences are B minus C.

| Method | B mean AP | C AP | Mean B−C | B scores at or below C |
| --- | ---: | ---: | ---: | ---: |
| Raw-token LR | 0.014278 | 0.012256 | +0.002022 | 16% |
| Normalized-token LR | 0.027472 | 0.022531 | +0.004941 | 10% |
| Pattern random forest | 0.057351 | 0.041768 | +0.015583 | 0% |
| Pattern LightGBM | 0.049931 | 0.040843 | +0.009087 | 14% |

Random forest gives the most consistent composition contrast: its C score lies below all 50 B composition means. For LightGBM, seven B compositions score below C; C is at the 14th percentile of the empirical B distribution. The corresponding positions are 10% for normalized LR and 16% for raw LR. Seed-matched tree comparisons also vary: the C percentile ranges from 0% to 2% for random forest and from 2% to 34% for LightGBM. These distributions describe the tested selection policy on one component. They do not establish an effect for independent projects or isolate information carried by a particular edge.

Raw LR is a weak baseline on this larger evaluation population: its B and C mean AP are both below the exact random-ranking expectation, 0.016836. Its mean review yields are also below the random expectations at all three budgets. The small AP contrast therefore provides little evidence of useful detection capability. On the earlier 1,082-file test, extending the comparison to 50 B draws places C at the 44th percentile for raw LR, with 28 positive and 22 negative B-minus-C differences. The five-draw precursor does not support a stable directional raw-LR claim across test definitions and training compositions.

![Composition distributions for the full-giant policy comparison](figure6.pdf)

*Figure 6. Empirical AP distributions over 50 B training compositions on the fixed 5,408-file test. Tree AP values are averaged over five paired seeds within each composition; LR uses seed zero. The C AP is marked in orange; the grey dotted line gives the exact random-ranking expectation. The curves describe the sampled training compositions, not independent test replications or confidence intervals.*

Review yield is model- and budget-dependent (Supplement Table S6). At 270 reviews, normalized LR retrieves a mean of 8.32 findings under B and 10 under C, despite its higher B AP. At 1,081 reviews, the same comparison reverses to 30.94 versus 25. Both tree methods have higher B mean yield at all three budgets. Random forest retrieves 16.10 versus 10.45 findings at 270 reviews and 53.91 versus 42.45 at 1,081; LightGBM retrieves 13.30 versus 9.20 and 45.42 versus 35.20. Individual composition contrasts can still reverse. Raw LR retrieves 4.06 versus 4.00 findings at 270 reviews and 13.20 versus 9.00 at 1,081, compared with random expectations of 4.14 and 16.59. The complete table reports all four models at all three budgets.

The ten overlapping label-blind slices retain positive mean B-minus-C AP in eight cases for raw LR and nine for each other model. Supplement S4 gives every slice, including the negative contrasts. These checks describe test-selection sensitivity within the same giant; they supply no additional independent families.

#### 4.3.3 Retaining newly connected training files

The linked-file retention analysis changes the admitted training composition more broadly than the 50 ordinary B draws. Mean AP increases across the five retention levels for normalized LR and random forest. Their zero-to-full linked-retention means rise from 0.022531 to 0.032228 and from 0.041768 to 0.070310, respectively. LightGBM initially falls from 0.040843 to 0.038195 when 118 linked files are retained, then rises to 0.062354 with all 471. Raw LR is nonmonotone, and its mean AP remains below the random-ranking reference at every level. Supplement Table S7 and Figures S2–S3 report the complete AP and review-budget patterns.

These retention curves do not establish a monotone effect of graph connectivity. Every nonzero level already connects the full test to training under C, and the identities of admitted positive and zero-label files change with the level. Within the narrower ordinary B draws, linked-file count is only weakly associated with AP; its Pearson correlations range from −0.070 to +0.156 across methods. The count of linked positive examples has a stronger association for random forest and LightGBM (0.540 and 0.424). The result therefore concerns the amount and composition of admitted training support under the stated policy, rather than the causal contribution of reachability alone.

## 5. Discussion and implications

The graph study establishes an eligibility result: the same evaluation files admit different training pools when construction includes omitted source files. Monotonicity predicts the direction of the change. The empirical contribution is its controlled attribution to source coverage and the identification of the merger and representation mechanisms producing it. Tests inside and outside the historical giant have different baseline exclusions, so the very large outside-giant loss is a conditional design effect rather than a universal magnitude.

Graph concentration and predictive dependence are distinct. A path through project and lexical links suffices for exclusion under full closure, even when its distant endpoints share little information used by a particular model. The historical diagnostic shows larger mean AP reductions after project exclusion than clone exclusion, but its original score queues contain no expanded-graph-unconnected test stratum. The full-giant comparison connects graph-construction coverage to model behavior at matched training size and positive count. Random forest gives the most consistent B–C contrast; LightGBM and the lexical models overlap the B composition distribution to different degrees, and raw LR performs weakly against random ranking. The retention analysis likewise distinguishes monotone mean trends from nonmonotone cases. Source composition remains part of each intervention, so neither comparison identifies the causal value of a particular graph path. Model-specific review yields provide the practical interpretation of the AP contrasts.

The relation should follow the generalization target. A new file from a familiar project permits project reuse, while a genuinely unseen-project target calls for project separation. Duplicate-artifact transfer motivates raw-byte or formatting-only identity controls. Transfer to new implementation families requires a justified reuse relation, including an explicit decision about common libraries; project identity alone is insufficient for that target. Identifier-preserving similarity retains vocabulary distinctions, while collapsed-token similarity deliberately treats renamed or renumbered forms alike. We use full normalized closure as a conservative lexical stress scenario, not as the true vulnerability-dependence graph. No threshold is selected to optimize model scores. A detector-specific dependence claim requires separate predictive or semantic evidence.

For benchmark curators, construction-population manifests and final evaluation membership supply different information. A split description should record edge definitions, representation, closure and retained class support. This reporting recommendation follows from non-uniqueness of training eligibility given final membership alone; it does not require an assumption that every omitted-file path raises model accuracy. Score claims additionally need a test suited to the intended deployment target and separate treatment of training selection and estimator randomness.

A supplementary readiness audit records source reconciliation and compiler coverage for a provisional external cohort. Compilation succeeded for 1,807 of 1,998 candidate files under the pinned source-context policy. No external model scores or independent human vulnerability judgments were obtained. Supplement S1 gives the source, dependency and compiler audits. Supplement S3 reports separate computational diagnostics for AP with incomplete labels.

## 6. Threats to validity

**Dependency construct and representation.** Directory projects, source identity and lexical overlap encode different relationships. Collapsing identifiers/numbers can equate semantically different code; strict equality can miss adapted reuse. Transitive closure can overstate dependence relevant to a particular detector. Masking uses lexical structure rather than a compiler AST. Its availability-only control distinguishes two graph interventions, but does not establish semantic library removal or a uniquely correct evaluation relation.

**Test selection and source sampling.** The original two feasibility tests were selected after a pilot using proxy-positive and component-dispersion screens, and both lie outside the historical giant. The added label-blind location controls describe sensitivity to that design within this corpus; they do not turn it into a prospective independent benchmark. The 95 proposal screens are a bounded search rather than a feasibility theorem or power calculation. File-level source prefixes and whole-project omission are different interventions.

**Labels and model scope.** DAppSCAN proxy zeros mean absence of a corresponding published finding, rather than expert-confirmed safety. The model experiment covers reentrancy only and reuses a historically inspected test. Expanded-graph connections saturate the original historical score queues, leaving no unconnected stratum within them. The expanded full-giant comparison changes the training policy and enlarges the evaluated subset, but remains within the same previously observed component. Its overlapping slices and repeated training draws measure conditional sensitivity, rather than independent-family generalization. The retained-file analysis changes labeled-example composition alongside linked support. There is no independent external detector-performance evaluation.

**Statistical interpretation.** Training-draw ranges characterize the specified selection procedure conditional on one test, while the seed panel changes the estimator on one joint training pool. Draws share files and supply neither independent test replication nor confidence intervals for unseen projects. Random ranking is a workload and AP reference, rather than an exchangeability-based significance test. Regime contrasts can reflect composition beyond the declared relation; comparing seed and selection SDs is descriptive rather than a matched variance decomposition.

**Implementation, lineage and external validity.** Exhaustive intersections remove candidate-search omission for the stated digest representation, while software cross-checks and fixed inputs reduce implementation risk. Six original compressed representation-edge archives were lost. Separately identified rebuilt archives reproduce the saved partitions and tables, but do not establish identity of every original edge. New controls using those archives inherit that lineage. The pinned corpus and project definitions limit extrapolation to deployed contracts; the supplementary compiler and AP diagnostics have their own stated populations and assumptions.

## 7. Conclusion

Training eligibility under graph-based separation depends on the population used to construct the graph. On a fixed benchmark projection, expanded source coverage joins outside-giant test components to the historical training giant and sharply reduces the eligible pool. Label-blind location controls show why that magnitude differs for tests already inside the giant. Representation changes are equally consequential: raw-byte, preserved-token and collapsed-token relations produce different concentrations, while loss of lexical availability accounts for much of the masking contrast. The historical diagnostic shows larger mean score changes after project exclusion than clone exclusion. The full-giant comparison links expanded graph construction to conditional score changes at matched training support, with the most consistent composition contrast for random forest. Raw LR remains weak against random ranking, and review-yield and retained-file responses vary by model and budget. These findings concern training-policy consequences within the studied component; individual-edge semantics and external detector performance require separate evidence. Reporting the construction population, relation and retained training support makes these structural claims assessable without conflating them with detector generalization.

## Data and code availability

Code, pinned manifests, model configurations, predictions and analysis results are available in the [article replication release](https://github.com/KuznetsovKarazin/blockchain-detector-eval/releases/tag/article1-r5-2026-10-29), tagged `article1-r5-2026-10-29`. The full reproducibility artifact is archived at [10.5281/zenodo.23750089](https://doi.org/10.5281/zenodo.23750089). The GitHub release asset `Article_1_R5_Derived_Evidence_2026-10-29.zip` supplies the compressed evidence files. The included retrieval script verifies the asset and member hashes before restoring the recorded paths. Third-party source contracts and annotations are acquired from pinned upstream revisions; acquisition scripts verify the source and annotation hashes rather than redistributing those corpora.

The release preserves 23 original compressed graph archives with verified historical identities. Six original representation-edge archives were lost. Six separately identified canonical replacements reproduce 120 saved component partitions and 20 tables; these checks establish the reproduced partitions and tabular results, rather than identity of every historical edge. Analyses that use the rebuilt edges identify that lineage. Supplement S5 gives the reproduction scenarios, required inputs and scope of the executed verification.

## Funding

This work was supported by the Horizon Europe project PETs4DeFi (Privacy-Enhancing Technologies for Compliant Decentralised Finance). The project funded under Grant Agreement No. 101308999 is supported by the European Cybersecurity Competence Centre. Funded by the European Union. Views and opinions expressed are however those of the author(s) only and do not necessarily reflect those of the European Union or the European Cybersecurity Competence Centre. Neither the European Union nor the European Cybersecurity Competence Centre can be held responsible for them.

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

OpenAI ChatGPT/Codex in Work Mode (GPT-6 family) assisted with literature retrieval, reference checks and manuscript organization. Analysis-code assistance and computational verification are described in Section 3.7. Figures were rendered from data with Matplotlib. The author is responsible for the scientific interpretation and final content.

## References

[1] Kuznetsov, Oleksandr (forthcoming). *Custom AI Solutions for Blockchain Systems: Detection and Prevention of Anomalies*. CRC Press / Taylor & Francis. Chapter 13 supplies the historical baseline disclosed in this study.

[2] Shachar Kaufman; Saharon Rosset; Claudia Perlich; Ori Stitelman. Leakage in data mining: Formulation, detection, and avoidance. *ACM Transactions on Knowledge Discovery from Data*, 6(4), 2012, Article 15, 21 pp. DOI: [10.1145/2382577.2382579](https://doi.org/10.1145/2382577.2382579).

[3] Sayash Kapoor; Arvind Narayanan. Leakage and the reproducibility crisis in machine-learning-based science. *Patterns*, 4(9), 2023, Article 100804. DOI: [10.1016/j.patter.2023.100804](https://doi.org/10.1016/j.patter.2023.100804).

[4] Cristina V. Lopes; Petr Maj; Pedro Martins; Vaibhav Saini; Di Yang; Jakub Zitny; Hitesh Sajnani; Jan Vitek. DéjàVu: a map of code duplicates on GitHub. *Proceedings of the ACM on Programming Languages*, 1(OOPSLA), 2017, Article 84, 28 pp. DOI: [10.1145/3133908](https://doi.org/10.1145/3133908).

[5] Miltiadis Allamanis. The adverse effects of code duplication in machine learning models of code. *Proceedings of the 2019 ACM SIGPLAN International Symposium on New Ideas, New Paradigms, and Reflections on Programming and Software*, 2019, pp. 143–153. ACM. DOI: [10.1145/3359591.3359735](https://doi.org/10.1145/3359591.3359735).

[6] Samantha Petti; Sean R. Eddy. Constructing benchmark test sets for biological sequence analysis using independent set algorithms. *PLOS Computational Biology*, 18(3), 2022, Article e1009492. DOI: [10.1371/journal.pcbi.1009492](https://doi.org/10.1371/journal.pcbi.1009492).

[7] Felix Teufel; Magnús Halldór Gíslason; José Juan Almagro Armenteros; Alexander Rosenberg Johansen; Ole Winther; Henrik Nielsen. GraphPart: homology partitioning for biological sequence analysis. *NAR Genomics and Bioinformatics*, 5(4), 2023, Article lqad088. DOI: [10.1093/nargab/lqad088](https://doi.org/10.1093/nargab/lqad088).

[8] Heval Atas Guvenilir; Tunca Doğan. How to approach machine learning-based prediction of drug/compound–target interactions. *Journal of Cheminformatics*, 15, 2023, Article 16. DOI: [10.1186/s13321-023-00689-w](https://doi.org/10.1186/s13321-023-00689-w).

[9] Zhenqin Wu; Bharath Ramsundar; Evan N. Feinberg; Joseph Gomes; Caleb Geniesse; Aneesh S. Pappu; Karl Leswing; Vijay Pande. MoleculeNet: a benchmark for molecular machine learning. *Chemical Science*, 9(2), 2018, pp. 513–530. DOI: [10.1039/C7SC02664A](https://doi.org/10.1039/C7SC02664A).

[10] David R. Roberts; Volker Bahn; Simone Ciuti; Mark S. Boyce; Jane Elith; Gurutzeta Guillera-Arroita; Severin Hauenstein; José J. Lahoz-Monfort; Boris Schröder; Wilfried Thuiller; David I. Warton; Brendan A. Wintle; Florian Hartig; Carsten F. Dormann. Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography*, 40, 2017, pp. 913–929. DOI: [10.1111/ecog.02881](https://doi.org/10.1111/ecog.02881).

[11] Roman Joeres; David B. Blumenthal; Olga V. Kalinina. Data splitting to avoid information leakage with DataSAIL. *Nature Communications*, 16, 2025, Article 3337. DOI: [10.1038/s41467-025-58606-8](https://doi.org/10.1038/s41467-025-58606-8).

[12] Steffen Herbold; Alexander Trautsch; Jens Grabowski. A Comparative Study to Benchmark Cross-Project Defect Prediction Approaches. *IEEE Transactions on Software Engineering*, 44(9), 2018, pp. 811–833. DOI: [10.1109/TSE.2017.2724538](https://doi.org/10.1109/TSE.2017.2724538).

[13] Weichu Deng; Huanchun Wei; Teng Huang; Cong Cao; Yun Peng; Xuan Hu. Smart Contract Vulnerability Detection Based on Deep Learning and Multimodal Decision Fusion. *Sensors*, 23(16), 2023, Article 7246. DOI: [10.3390/s23167246](https://doi.org/10.3390/s23167246).

[14] Jie Zhang; Gehao Lu; Jia Yu. A Smart Contract Vulnerability Detection Method Based on Heterogeneous Contract Semantic Graphs and Pre-Training Techniques. *Electronics*, 13(18), 2024, Article 3786. DOI: [10.3390/electronics13183786](https://doi.org/10.3390/electronics13183786).

[15] Saikat Chakraborty; Rahul Krishna; Yangruibo Ding; Baishakhi Ray. Deep Learning Based Vulnerability Detection: Are We There Yet? *IEEE Transactions on Software Engineering*, 48(9), 2022, pp. 3280–3296. DOI: [10.1109/tse.2021.3087402](https://doi.org/10.1109/tse.2021.3087402).

[16] Roland Croft; M. Ali Babar; M. Mehdi Kholoosi. Data Quality for Software Vulnerability Datasets. *2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE)*, 2023, pp. 121–133. IEEE. DOI: [10.1109/icse48619.2023.00022](https://doi.org/10.1109/icse48619.2023.00022).

[17] Yangruibo Ding; Yanjun Fu; Omniyyah Ibrahim; Chawin Sitawarin; Xinyun Chen; Basel Alomair; David Wagner; Baishakhi Ray; Yizheng Chen. Vulnerability Detection with Code Language Models: How Far are We? *2025 IEEE/ACM 47th International Conference on Software Engineering (ICSE)*, 2025, pp. 1729–1741. IEEE. DOI: [10.1109/icse55347.2025.00038](https://doi.org/10.1109/icse55347.2025.00038).

[18] Niklas Risse; Marcel Böhme. Uncovering the Limits of Machine Learning for Automatic Vulnerability Detection. *33rd USENIX Security Symposium (USENIX Security 24)*, 2024, pp. 4247–4264. USENIX Association. [Official proceedings page](https://www.usenix.org/conference/usenixsecurity24/presentation/risse).

[19] Niklas Risse; Jing Liu; Marcel Böhme. Top Score on the Wrong Exam: On Benchmarking in Machine Learning for Vulnerability Detection. *Proceedings of the ACM on Software Engineering*, 2(ISSTA), 2025, Article ISSTA018, 23 pp. DOI: [10.1145/3728887](https://doi.org/10.1145/3728887).

[20] Masanari Kondo; Gustavo A. Oliva; Zhen Ming Jiang; Ahmed E. Hassan; Osamu Mizuno. Code cloning in smart contracts: a case study on verified contracts from the Ethereum blockchain platform. *Empirical Software Engineering*, 25(6), 2020, pp. 4617–4675. DOI: [10.1007/s10664-020-09852-5](https://doi.org/10.1007/s10664-020-09852-5).

[21] João F. Ferreira; Pedro Cruz; Thomas Durieux; Rui Abreu. SmartBugs: a framework to analyze solidity smart contracts. *Proceedings of the 35th IEEE/ACM International Conference on Automated Software Engineering*, 2020, pp. 1349–1352. ACM. DOI: [10.1145/3324884.3415298](https://doi.org/10.1145/3324884.3415298).

[22] Thomas Durieux; João F. Ferreira; Rui Abreu; Pedro Cruz. Empirical review of automated analysis tools on 47,587 Ethereum smart contracts. *Proceedings of the ACM/IEEE 42nd International Conference on Software Engineering*, 2020, pp. 530–541. ACM. DOI: [10.1145/3377811.3380364](https://doi.org/10.1145/3377811.3380364).

[23] Asem Ghaleb; Karthik Pattabiraman. How effective are smart contract analysis tools? evaluating smart contract static analysis tools using bug injection. *Proceedings of the 29th ACM SIGSOFT International Symposium on Software Testing and Analysis*, 2020, pp. 415–427. ACM. DOI: [10.1145/3395363.3397385](https://doi.org/10.1145/3395363.3397385).

[24] Zibin Zheng; Jianzhong Su; Jiachi Chen; David Lo; Zhijie Zhong; Mingxi Ye. DAppSCAN: Building Large-Scale Datasets for Smart Contract Weaknesses in DApp Projects. *IEEE Transactions on Software Engineering*, 50(6), 2024, pp. 1360–1373. DOI: [10.1109/tse.2024.3383422](https://doi.org/10.1109/tse.2024.3383422).

[25] Francesco Salzano; Cosmo Kevin Antenucci; Simone Scalabrino; Giovanni Rosa; Rocco Oliveto; Remo Pareschi. An empirical analysis of vulnerability detection tools for solidity smart contracts. *Empirical Software Engineering*, 31(5), 2026, Article 143. DOI: [10.1007/s10664-026-10867-7](https://doi.org/10.1007/s10664-026-10867-7).

[26] Shawal Khalid; Joaquin Tuckett; Chris Brown. Do Smart Contract Auditing Results Transfer Across Datasets? A Two-Benchmark Empirical Study of Static and LLM-Based Security Tools. *20th International Symposium on Empirical Software Engineering and Measurement (ESEM 2026)*. Leibniz International Proceedings in Informatics (LIPIcs), vol. 394, 2026, pp. 45:1–45:21. Schloss Dagstuhl – Leibniz-Zentrum für Informatik. DOI: [10.4230/LIPIcs.ESEM.2026.45](https://doi.org/10.4230/LIPIcs.ESEM.2026.45).
