# Evaluation protocols

All splits, thresholds and budgets below are encoded in code, not in configs,
so that a script cannot be re-run with a silently different protocol. Each run
writes a manifest (`manifest*.json`) with the git commit, the list of code files
that differed from it and a SHA-256 of that diff, package versions, SHA-256 of
the input files and the full CLI configuration. Revisions of a protocol after
the external audit of 2026-10-22 are listed in [archive/AUDIT_RESPONSE.md](archive/AUDIT_RESPONSE.md).

**AUPRC** everywhere in this repository is average precision as computed by
`sklearn.metrics.average_precision_score` (the non-interpolated step sum
Σ (Rₙ − Rₙ₋₁) Pₙ), not a trapezoidal area under the PR curve. Its chance
level is the base rate, which is always reported next to it.

## T / K — Elliptic transactions

| Part | Time steps | Used for |
|---|---|---|
| train | 1–30 | fitting |
| validation | 31–34 | early stopping (GNNs), max-F1 threshold, Platt calibration, model selection |
| test | 35–49 | reported; split into **pre** 35–42 and **post** 43–49 (dark-market shutdown) |

* Elliptic edges never cross time steps, so test sub-graphs are disconnected
  from training sub-graphs. `tests/test_gnn.py` checks that adding a
  disconnected component changes neither the outputs nor the gradients of
  GCN, GraphSAGE and GAT.
* This is an offline snapshot benchmark: the 72 aggregate features of the
  dataset summarise neighbours on both sides of a transaction, so a correct
  temporal split does not prove that every feature is available at
  transaction time.
* Scalers are fitted on training nodes only. KAN inputs are additionally
  multiplied by 0.6 after scaling, so that they stay inside the spline grid;
  MLP inputs are not.
* Early stopping is part of each model's definition and differs by family:
  MLP/KAN hold out a stratified random 15 % of the labelled training nodes
  (rows, not time steps), GNNs use the validation steps, trees and logistic regression do not stop early.
* Headline rule: for each model the feature set with the highest mean
  validation AUPRC is reported (`headline_by_validation.csv`); the test-best
  set is shown next to it only for transparency.
* Seeds 0–4 for every stochastic model. Seeds measure training randomness on
  one fixed history, not uncertainty over new periods. K3 adds a cluster
  bootstrap over the observed test time steps: it keeps the objects of a step
  together but not the dependence between neighbouring steps, and it does not
  create new histories. K3 (10 seeds) is a pre-declared follow-up analysis: it
  was fixed before it ran, but after the first look at the same test period,
  and seeds 0–2 repeat T1; it is not a confirmatory preregistration.
* Label-shift correction (T2) never reads test labels. The oracle-prior row
  keeps the validation F1 threshold and is therefore **not** an upper bound on
  F1; the step-optimal F1 in `shift_diagnostics.csv` is.

## T5 — Elliptic++ wallets

Four splits of the same labelled wallet rows: random rows, random addresses,
temporal rows, temporal and address-disjoint (with and without block/lifetime
features). The 55 wallet features are constant within an address; the
transitions change several things at once (address weighting, training size,
prevalence, period), so differences are protocol sensitivity, not a measured
amount of leakage.

## C — Smart-contract vulnerability classification

* Classes: reentrancy, arithmetic, timestamp dependence, unchecked low-level call.
* Representations: TF-IDF of raw tokens; TF-IDF of tokens with user
  identifiers → `ID` and numbers → `NUM`; 43 hand-written pattern features
  (38 regex counts and the call-before-write count, each per 100 non-empty
  lines, plus solc version, a pre-0.8 flag, log1p(lines) and
  log1p(functions)).
  TF-IDF is fitted inside each training fold.
* Near-duplicates: identical normalised files are always merged; MinHash
  (token 5-gram, 16 bands × 4 rows) proposes candidates and **every** candidate
  pair is verified with the exact Jaccard index (≥ 0.8). The partition does not
  depend on input order (`tests/test_features.py`).
* Within-corpus protocols (5 folds, out-of-fold scores): `random`,
  `random_matched` (training folds sub-sampled to the size of the `safe`
  folds), `project`, `safe` (project ∪ near-duplicate components),
  `local_random` / `local_safe` (files whose near-duplicate component stays in
  one project). Fold sizes and positives: `folds.csv`; fold ids:
  `assignments.parquet`; per-file scores: `oof_scores.parquet`.
* Cross-corpus: train on one corpus, test on another (labelling regimes:
  manual = SmartBugs-curated, injected = SolidiFI, audit = DAppSCAN). The
  DAppSCAN target is its 948 annotated files. The "best transferred model" in
  the tables is chosen on the target itself, so that column is exploratory,
  not the estimate of a model frozen on source validation before the test.
* DAppSCAN negatives mean "no published finding of this class", not "verified
  safe". Missing labels can move AUPRC up or down.
* Metric: AUPRC with the base rate next to it, ROC-AUC. A static analyser's
  binary flags are compared with learned scores on AUPRC and at the
  analyser's own alarm count (`c4_slither_vs_ml.py`), never F1 against AUPRC.
* Slither: the compiler is chosen inside the full pragma range (newest allowed
  minor first); every file has a status (ok, compile_error, timeout,
  tool_error, unsupported_pragma; OR ranges in pragmas are honoured) and metrics are given end-to-end and for analysed files only.

## V — What smart-contract security benchmarks measure (study C extended)

Written on 2026-10-30, before any V run. Changes after the first run are
listed at the end of this section with their reason.

**Data.** SolidiFI-benchmark @4b0573e (350 buggy files), the SolidiFI tool
repository @ebb02e3 (the 50 original contracts and the snippet files of the
injector), SmartBugs-curated @230e649, DAppSCAN @66a5661. Classes:
reentrancy, arithmetic, timestamp, unchecked (SolidiFI Unchecked-Send +
Unhandled-Exceptions) and tx_origin.

**V1 SolidiFI decomposition** (`bal.data.solidifi`). Snippet files are
normalised (comments removed, numbers → `N`, trailing digits of identifiers
→ `#`); equal sequences form one template (44 templates). Every template is
located in every buggy file (longest first, no overlap). Checks per file:
removing all located snippets gives the original contract token for token;
the number of snippets equals the BugLog rows; the share of snippet lines
that the BugLog line ranges cover.

**V2 Template controls for learned detectors** (within SolidiFI, 5 folds
grouped by base contract, 3 seeds; lex_raw / lex_norm with logistic
regression, pat with RF and LightGBM, the same code as C2).
* `standard`: positives are the buggy files of the class, negatives the
  buggy files of the other six types (the C2 setting), plus the 50 original
  contracts as extra negatives (`+clean`).
* Pair test: in each test fold, the share of base contracts whose buggy file
  of the class scores above the original contract (ties count ½).
* `loto` (leave one template out), for every template with at least 20
  occurrences in a class with at least two such templates: training positives
  are the buggy files of the class with every snippet of the held-out template
  removed (files left without a snippet are dropped); test positives are the
  buggy files of the test bases reduced to the held-out template only.
  `seen` is the same test set with models trained on the full buggy files.
  Negatives as in `standard` + `+clean`. Reported per template: AUPRC, pair
  test, and `seen − loto`.
Hypothesis HV.1: `loto` drops below `seen` for most templates of
reentrancy and unchecked; the pair test stays near 1 (the models detect
injected code, not necessarily the vulnerable construct).

**V3 Models frozen on source validation.** Candidates: lex_raw and lex_norm
with logistic regression (C ∈ {0.1, 1, 10}), pat with RF and LightGBM
(library settings of C2), pat with MLP. Selection per (source, class) on
grouped 5-fold CV inside the source only (SolidiFI: base contract; DAppSCAN:
project), by mean AUPRC; ties within 0.005 go to the earlier candidate in the
list above. The selected model is refitted on the whole source and scored once
on each target (SmartBugs-curated; the 948 annotated DAppSCAN files;
SolidiFI). Reported: frozen AUPRC with a file-level bootstrap 95 % CI
(2,000 resamples), the best candidate on the target (oracle, exploratory) and
the frozen model's rank among candidates on the target. Seeds 0–2 for
stochastic models; selection on the seed mean.
Hypothesis HV.2: on SolidiFI as source, validation cannot separate the
candidates (all ≈ 1), so the frozen choice is arbitrary on the target.

**V4 Static analysers** (Slither 0.11.6, Mythril 0.24.8, SmartCheck 2.0.1) on
SmartBugs-curated, the 350 SolidiFI buggy files and the 50 original
contracts. Slither and Mythril use the C3 compiler choice (newest allowed
minor of the pragma range first, fall back to older minors on failure).
SmartCheck parses source without compiling. Mythril: `analyze -o json`,
`--execution-timeout 90`, wall timeout 600 s per compiler try, other options
default. Every file gets a status (ok, compile_error, timeout, tool_error,
unsupported_pragma). Mapping to classes, fixed before the run:

| Class | Slither | Mythril (SWC) | SmartCheck |
|---|---|---|---|
| reentrancy | reentrancy-eth/-no-eth/-unlimited-gas/-benign/-events | 107 | — |
| arithmetic | — | 101 | — |
| timestamp | timestamp | 116 | SOLIDITY_EXACT_TIME |
| unchecked | unchecked-lowlevel, unchecked-send | 104 | SOLIDITY_UNCHECKED_CALL |
| tx_origin | tx-origin | 115 | SOLIDITY_TX_ORIGIN |

File-level metrics end-to-end (a failed file has no finding) and on analysed
files. On SolidiFI also: **located** detection (at least one mapped finding
on a line of a snippet of the class), snippet recall (share of snippets of
the class with a mapped finding on one of their lines), mapped findings
outside snippets, and the flag rate on the 50 original contracts (no
injected bug; a flag there is either a false alarm or a real issue of the
original code; not adjudicated).
Hypothesis HV.3: file-level recall on SolidiFI overstates located recall for
at least one tool and class.

**V5 Budget curves** on SmartBugs-curated (manual labels) and annotated
DAppSCAN (audit labels; SmartCheck only, it needs no compilation; the
compile-based tools are not run on DAppSCAN). Tool score = number of mapped
findings (ties broken in expectation, as in C4); model score = V3 frozen
model. Recall and precision at k = 1 … n, with recall at k = the tool's own
alarm count, and a hybrid ranking (files flagged by the tool first, ordered
by the model, then the rest by the model). Differences at a fixed k are
reported with a paired file-level bootstrap CI.

**Separation from the graph study.** V uses no dependency graphs and no
source ablation; DAppSCAN appears only as an audit-label target.

**Amendment 1 (2026-10-30, before any V result for these classes was
read).** SolidiFI's own evaluator (`inspection.py` of the tool repository)
scores "Unchecked-Send" with Mythril's *Unprotected Ether Withdrawal*
(SWC-105) and Securify's *UnrestrictedEtherFlow*, and "Unhandled-Exceptions"
with the unchecked-call detectors (SWC-104); the only Unchecked-Send template
is `msg.sender.transfer(1 ether)` in an unprotected public function, which
reverts on failure and has no return value to check. C2 and C3 merged both
types into `unchecked`. In V, `unchecked` is Unhandled-Exceptions only, the
new class `unprotected_send` is Unchecked-Send (Mythril SWC-105; no Slither or
SmartCheck rule is mapped), and the C2/C3 mapping is kept as
`unchecked_merged` (standard setting and tools only, no loto) to show how much
the mapping changes the numbers. V3 uses the corrected label by default
(`--solidifi-unchecked merged` reproduces the C2 label).

## K4 — Flash-loan price-manipulation exploits (Ethereum)

* Unit: one transaction. Positives: the attack transactions linked by the
  keyword-selected DeFiHackLabs entries (README heading names a price or
  oracle manipulation; the PoC forks mainnet and takes a flash loan); every other transaction of an incident day
  is a negative, in strata (all flash-loan transactions; transactions
  touching the attacked contracts, sampled; uniform background, sampled)
  with weight = stratum population / kept rows. Transactions of other
  DeFiHackLabs exploits are removed.
* Temporal split by incident date: train ≤ 2023-12-31, validation 2024,
  test 2025–2026. Leave-days-out: GroupKFold(8) by incident day,
  out-of-fold scores, no thresholds.
* Features are causal at transaction level: pool state before the
  transaction comes from the last state event of an earlier transaction of
  the same day (or, for a V2 pool without one, from its first swap in the
  transaction), and a V2 pool's token pair from token transfers up to the end
  of the transaction (`causal_pairs`). They are available only after the block is mined.
* MLP / KAN input normalisation (quantile or robust) is chosen per model on
  validation AP for the temporal split, and again inside every leave-days-out
  fold on an inner day-grouped split of that fold's training days
  (`prep_choice_by_fold.csv`); the MLP hidden width matches the KAN parameter
  count.
* Budgets: 1 and 10 alarms per day. The threshold is a conservative observed
  validation score whose weighted alarms per validation day do not exceed the
  budget; achieved validation and test rates are reported
  (`thresholds.csv`, `temporal_summary.csv`).
* AP = sklearn `average_precision_score`, on the kept rows and
  population-weighted, each with its base rate. Point estimate: mean over
  seeds of the per-seed AP (leave-days-out: of the per-seed out-of-fold
  AP); 90 % interval: bootstrap over days (2,000 resamples) recomputing the
  same seed mean in each resample. The AP of the seed-averaged score is
  reported separately (`seed_mean_score_test_ap`, `ensemble_ap`). Rank of an attack among its
  day's weighted transactions, ties counted half.
* KAN edge check: signed edge path (first-layer function × mean slope of the
  second-layer function, summed over hidden units) against partial dependence
  of the logit on validation rows, and relevance against permutation AP drop
  (mean and SD of 20 permutations per feature).
* Features never read the stratum or the label: `has_flash` uses the same
  rule for every transaction (`bal.data.defi.flash_hashes`), and creation of
  the called contract counts only before the transaction's (block, index).
  `tests/test_defi_features.py` checks both.

## B — Cross-chain bridge outflows

* Event stream: every release of funds on Ethereum by the bridge (matched
  withdrawals + releases without a source-chain request). One event is one
  release; Nomad's 382 attack events come from 167 transactions. Order:
  (timestamp, tx hash, withdrawal id); the data have no block number or log
  index, so events with one timestamp are treated as one block.
* Train: normal events before `attack_day − 21 d`; calibration window:
  `[attack_day − 21 d, attack_day − 7 d)`; test: from `attack_day − 7 d`.
* Features and rules value every release, matched or not, with the close of
  the last daily price candle that closed at or before it (raw candles of
  XChainWatcher, `bal.data.prices`). Every B1 run asserts, row by row,
  that the price time is not later than the release, and checks prefix
  invariance of raw → features. That a candle is usable once it has closed is
  an availability assumption: the provider's real publication time was not
  measured, and the sensitivity to intraday price data was not evaluated.
  Six Nomad releases get no price (five tokens without a series, one before
  the first closed candle); two attack rows have zero reference USD already
  in the source. Loss shares use the reference values of
  `attacks.csv`; they are accounting only and never enter a feature.
* Detectors never see attack labels. The threshold for a nominal budget of
  0.1 % or 1 % is a conservative threshold taken from the observed calibration
  scores whose achieved calibration rate does not exceed the budget (not
  necessarily the lowest admissible value); tied scores are never split. The achieved rate and the
  resolution 1/n of the calibration set are reported (`thresholds.csv`).
* Loss accounting: attack value released before the alarm event, through the
  alarm event, through its block, and after alarm + d seconds
  (d = 0, 60, 600, 3600). All of these are released, executed transfers;
  none is a measured prevented loss.
* Transfer: fit + threshold on bridge A, evaluate on bridge B. The Nomad
  training period is later than the Ronin attack, so Nomad → Ronin is a
  retrospective transfer.
* Scope: two incidents give no detection rate for future attacks. The split is
  historical, the rules were written after the data had been seen, and signal
  delays were not measured; no false alarm in the chosen window does not mean
  none in operation.
* Attack ranks (`best_attack_rank`, `median_attack_rank`) give tied scores the
  midrank; `*_min` / `*_max` give the range over all orderings of the ties.
* The `ecod*` detectors are a frozen, train-only, smoothed two-tail ECDF
  variant in the spirit of ECOD, not the PyOD implementation.
