# External validation and independent assessment of source annotations

This is a prospective protocol draft for the second part of the study. The
sampling plan and metadata manifests have been executed, but no external model
score or human judgment has been produced. It is not a registered study. The
method configurations, human review rules, software versions and analysis code
must be sealed before the first human judgment or external model score. The
current execution guard deliberately refuses external scoring.

The external candidate consists of 1,998 source files after the previously
specified identity and exposure exclusions. It remains provisional: source
reconciliation establishes where an annotation came from, not whether the
annotation is correct. The expanded dependency graph permits training on 691
historical DAppSCAN files, with 23 reentrancy and 18 unchecked-call published
findings. The absence of a published finding remains a training proxy zero.
This is a feasible two-class fitting problem, not evidence of adequate power or
accurate training labels.

## Questions and targets

B1 asks how often independent expert assessment agrees with an explicit source
finding, and how often experts identify a relevant finding where the source
reports none or does not list that class. These three source statuses remain
separate. Source-class absence is not retrospectively called a verified
negative. B2 asks how the preselected methods rank and review the fixed external
population when assessed against expert-adjudicated references, accounting for
sampling, unresolved judgments and analysis failures. These questions concern
this fixed finite population; new-project generalization is a different target.

One decision unit is a source file by class. The primary classes are reentrancy
and unchecked low-level calls. A file can produce one case in each class. The
full probability sampling frame therefore has 3,996 cases. No price prediction,
DeFi exploit incident or IoT IDS observation substitutes for these cases.

## Fixed populations and source lineage

`packet_probability_20261025_v1/external_cohort_manifest.csv` fixes all 1,998
external source identities and hashes. The selection uses the pinned Salzano
repository at `da079440bf2cf4fd803c864ef29aeea8a3da50c3`, excludes the previously
used SmartBugs-curated source, retains only reconciled source/annotation keys,
and quarantines repeated identifiers or exact source identities. Nothing is
excluded using model performance. The 17 unresolved source identity/location
issues remain quarantined; resolving them does not automatically add them to
this test. Their inclusion would require a new prospective cohort amendment.

The corresponding train manifest contains the 691 DAppSCAN files retained by
the string-aware, address-expanded joint graph at threshold 0.8. This graph
contains all 24,131 objects: uncapped upstream sources and external candidate
files. Training restrictions are applied after graph construction. The manifest
check verifies zero intersection of retained training and test components. This
is independence under the declared observed lexical/project graph, not proof of
semantic, business-project or deployment independence. Unknown chain identity
makes address edges conservative proxies. Alternative graph policies and
thresholds are metadata sensitivities and will not be selected using scores.

Four lineage steps are auditable without a human vulnerability judgment:
source revision and bytes; source/contract key reconciliation; class/status
mapping; and selection into the fixed cohort. Correctness is a separate claim,
requiring source/context inspection and expert evidence. A machine-readable
annotation trail must not be described as a completed label-accuracy study.

## Probability sample and separate identity audit

The new packet contains **180 probability-sampled cases from 170 files** in
17 nonempty strata. Strata are source, class and original annotation status.
Both experts assess every probability case independently. The older purposeful
106-case packet is preserved and is not pooled into this estimator.

For each stratum h, the allocation initially takes min(N_h, 20) cases when the
source reports the selected class and min(N_h, 5) for other source statuses.
Remaining slots up to 180 are proportional to remaining stratum capacity, with
Hamilton integer rounding and lexicographic tie resolution. A seeded generator
then samples without replacement inside each stratum and randomly mixes the
reviewer case order. The seed and allocation rule were recorded before case
selection, human judgments and external scores. All allocation cells have at
least five cases or are a census; no non-census n_h=1 variance problem occurs.

Every case has inclusion probability pi_i=n_h/N_h and weight w_i=N_h/n_h.
`stratum_allocation.csv` records these quantities. Source-positive cases are
deliberately oversampled; unweighted error percentages from this packet would
not estimate corpus-wide rates. The census of seven ZEUS-vulnerable reentrancy
source positives has pi=1. There are no replacement cases chosen for easy
review, desired labels or disagreement. A case that cannot be assessed remains
selected and receives unknown.

A separate **17-case identity audit** examines all quarantined records. Its
unit is a disputed source/annotation identity, not a file-class probability case.
It has a separate key and forms, does not enter the 3,996-case denominator, and
cannot repair an external test identity silently. Each issue requires evidence
for any proposed source-key or line-number correction. The reviewer forms have
cohort_reentry_allowed=no. In total there are 197 case forms per reviewer, with
different purposes and denominators.

## Two human reviewers and adjudication

The author must designate two Solidity security specialists. They receive the
same 180 case IDs, requested classes and complete source copies renamed by case
ID. Model scores, model identities/rankings, source labels, source folder names,
selection strata and the coordinator key are withheld. Source comments or
contract names may still reveal context or annotation hints; reviewers record
such exposure. No claim of perfect blinding is made. The two independent initial
forms are sealed before they can view each other's judgments or the source key.
An AI-generated opinion is not an independent specialist assessment.

Because the identity census necessarily reveals source annotations, its private
evidence is released to the experts only after both initial probability-sample
forms are sealed. This reduces cross-contamination between the two review tasks.
A class-level positive means at least one qualifying issue in the complete file;
missing imported context leads to unknown where it prevents a defensible judgment.

Each judgment is positive, negative or unknown. Positive requires an affected
operation, an executable or otherwise explicit control/data-flow argument and
stated exploit preconditions. For reentrancy, a callback must permit an adverse
state/asset outcome under stated conditions; an external call alone is not
sufficient. For unchecked calls, explain the unhandled failure and its relevant
state/application consequence; a call token alone is not sufficient. A negative
judgment is restricted to that class and stated assumptions, not universal
contract safety. Unknown covers unresolved imports, compiler/runtime semantics,
missing dependencies, insufficient context or an unresolved substantive dispute.
Line references, compiler assumptions, reasoning and review time are required.

After initial judgments are sealed, the experts discuss disagreements and
uncertain cases, preserving both initial answers. Consensus supplies an
expert-adjudicated reference. Persistent disagreement remains unknown, or a
separately named third specialist may adjudicate with a recorded reason. This
reference is evidence-based expert assessment, not infallible ground truth.
Identity corrections and substantive vulnerability judgments remain distinct.
Any source-label reveal occurs only after independent judgments have been saved.

## Annotation accuracy and agreement analysis

For a known finite-population domain D, such as explicit no-finding cases for one
class, its size N_D is known from the full frame. For a binary assessed outcome y,
the Horvitz-Thompson estimate is

    p_hat_D = sum(sample in D, w_i y_i) / N_D.

For a domain made of whole sampling strata, the stratified finite-population
variance is

    Var_hat(p_hat_D) = sum_h [(N_h/N_D)^2 (1-n_h/N_h) s_h^2/n_h].

This is sampling-design inference conditional on the fixed population. It does
not assume that source files within a family have independent vulnerabilities;
selection is randomized within strata. An additional naive family bootstrap is
not a replacement for the sampling design. Generalization beyond this corpus
would require a separate family-level estimand and appropriate design.

Report separately: contradiction of an explicit positive finding; expert-positive
cases among explicit no-finding records; expert-positive cases where the class
was not listed; and unresolved expert judgments. These are separate rates, not
one pooled label-error count. The term false zero is used only when describing a
specified binary-benchmark convention; the conservative adapter itself never
converts source-unknown status to a confirmed negative.

Zero observed disagreements must not produce a zero-width Wald confidence
interval. The implemented `review_estimators.py` uses finite-population interval
inversion with exhaustive small-population coverage tests. Its conservative
method is exact hypergeometric inversion within each stratum,
Bonferroni simultaneous coverage across the contributing strata, and weighted
aggregation of their bounds. Census strata have no sampling uncertainty, but
still have expert-judgment uncertainty. Unknown outcomes are not dropped as
random nonresponse: report observed-confirmed lower and unresolved-inclusive
upper bounds. The estimator and design variance have been verified on known
finite toy populations; blank human forms are rejected. No human accuracy
estimate exists now. These intervals cover the stated finite-population outcome,
not a collection of all distinct outcomes or a new-family superpopulation.

Show the initial 3-by-3 reviewer agreement table, marginal counts and positive,
negative and unknown-specific agreement. Raw sample agreement and design-weighted
finite-population agreement are distinct. Cohen's kappa is supplementary: it
measures agreement beyond the marginal model, not correctness. If its expected
agreement is one, kappa is undefined and must not be forced to one or zero.
Sparse/one-class outcomes, prevalence effects and any interval instability must
be reported. Adjudication must not overwrite the initial agreement data.

## Preselected methods and training

The four learned methods are raw TF-IDF logistic regression, normalized TF-IDF
logistic regression, Random Forest on the fixed pattern features, and LightGBM
on those features. Slither is a separate static-analysis comparator. No new
architecture or paid LLM is needed. All methods use the same 691 training files
and the complete same 1,998-file external inference population for each class.

TF-IDF uses token 1–3 grams, min_df=2, max_features=50,000, sublinear_tf=True,
lowercase=False and the recorded tokenization adapter. Vocabulary and sparse
StandardScaler(with_mean=False) are fitted on training only. Logistic regression
uses C=1, max_iter=3,000, balanced class weights, lbfgs and tol=1e-4. It is fitted
once per representation/class, not repeated solely to inflate a seed count.
Random Forest uses 500 trees, balanced_subsample weights and minimum leaf size 1.
LightGBM uses 400 trees, learning rate .05, 31 leaves, subsample .8 with frequency
1, colsample_bytree .8 and balanced class weights. Stochastic model seeds are
0–4. These seeds describe fitting variation on one source history, not independent
external validation datasets. No hyperparameter tuning is planned; every declared
method is reported, without choosing a new winner from external results.

The adapter choices and executable hashes must be settled before the protocol
is sealed. The planned lexical adapter uses the tested string-aware comment
scanner, with the historical token regex and identifier/number normalization.
Pattern feature definitions remain the historical 43-feature family, but the
comment/pragma adapter must be checked against the corrected scanner to avoid
silently reintroducing the known comment-order problem. Until those concrete
adapters and regression checks are saved, the execution guard remains closed.
This is a code-completion condition, not permission to optimize using test scores.

## Slither and compiler policy

Pin Slither 0.11.6 for comparability and freeze its executable/dependency hashes.
Freeze a finite official-solc release inventory and binary checksums before
execution. Parse active pragmas using the validated scanner; never extract a
pragma from a comment or string literal. Intersect every active pragma constraint
and try the newest allowed patch per compatible minor, newest minor first.
Record every candidate and attempt. No outside-pragma fallback is allowed.
Missing or unsupported pragmas, unavailable binaries and missing imports have
explicit statuses. Imports resolve only from the pinned source tree and recorded
local dependencies; no unrecorded network rescue or source edit is permitted.

Use a 180-second timeout per compiler attempt, at most five compatible-minor
attempts per file, plus at most one diagnostic rerun of a failed attempt that
cannot change the scored outcome. Record end-to-end time, compile time where
available, coverage, successful version, compiler errors, tool errors, timeouts
and missing dependency status. A failed file receives no synthetic safe score.
The strict read-only compiler planner and its regression tests are complete.
It uses the historical finite catalog through patches 0.4.26 / 0.5.17 / 0.6.12 /
0.7.6 / 0.8.26, without claiming these are current latest versions. The saved
input-readiness check found lexical inputs for all 1,998 external and 691
training files, but only compiler candidate plans for 1,968 external and 682
training files. Neither planning nor lexical readiness is execution coverage.
The selected Slither package and recorded compiler binary paths were absent;
a verified executable/dependency inventory is still required. See
`ENGINEERING_READINESS.md` and the read-only run receipt for all statuses.

Reentrancy detector mapping and the human adverse-outcome definition must be
aligned semantically before sealing. The draft primary mapping is
reentrancy-eth, reentrancy-no-eth and reentrancy-unlimited-gas; the historical
broad mapping additionally includes reentrancy-benign and reentrancy-events as a
predeclared secondary sensitivity. Unchecked maps to unchecked-lowlevel and
unchecked-send. These mappings cannot be selected using external metrics.

## External metrics and uncertainty

Do not report all 1,998 source annotations as independently confirmed truth.
The primary expert-reference assessment uses the probability sample and its
weights. Any all-source annotation agreement table is secondary, separately
labelled source-reported agreement, with class absence/no-finding/unknown semantics
preserved. The primary evaluation is not allowed to turn unassessed cases into
negative labels.

AP is sklearn average_precision_score, with sampling weights in the
expert-reference sample; trapezoidal PR area is separate. Weighted sample AP is
a nonlinear estimate, not an exactly unbiased population AP. Report its assessed
population, prevalence, weight distribution, unresolved coverage and uncertainty.
The full inference population determines review queues at floor(5%,10%,20% of
1,998), not the sample size. Boundary ties use a label-independent uniform subset
in expectation. Weighted totals/ratios of expert-confirmed positives in those
queues estimate review yield and recall; publish their precise estimator and
finite-sample limitations before scoring. Unknown judgments retain unknown mass.

Report the full pipeline with failures and the common successfully scored
subset. Ranking metrics conditional on known/scorable references must be named
as conditional; workload recall includes failed known positives in its denominator.
Report point estimates, per-seed results and paired differences on the same
sample/queues. Survey resampling must preserve strata, without-replacement
sampling fractions and shared model comparisons; an ordinary unweighted bootstrap
is not valid for this design. The weighted AP/workload interval implementation
and validation are a remaining prerequisite. No confidence interval, superiority
claim or final sample-size adequacy claim is made by preparing this protocol.

## Release, execution order and rights

First finalize adapters, analysis tests, compiler inventory, reviewer identities
and the protocol; then record hashes in a dated immutable commit or registration
without claiming retrospective preregistration. Conduct the two independent
human reviews and seal initial/adjudicated records. Fit the fixed methods and
score only after these prerequisites and the execution guard pass. Amendments
must give the reason, timing and whether labels/scores had already been viewed.
No optional stopping on model effects and no seed selection on external results
is allowed. Any increase of the audit sample needs an explicit prospective
sampling amendment with updated inclusion probabilities.

Pinned DAppSCAN and Salzano root trees/READMEs contain no identified global
repository/data license. The Salzano article's CC BY 4.0 statement explicitly
licenses the article; its link to a replication repository is not a separate
grant for third-party code or annotations. See the independent checks in
`../related_work/license_checks.json`. Raw source copies, original row annotations
and coordinator keys remain under ignored data/derived. Public artifacts contain
our code, aggregate allocations, hashes, source references and blank forms.
Redistribution rights remain unresolved; local preparation does not assert a
right to relicense the corpora. No emails, author requests or manuscript
submissions have been sent.
