# Response to the external audit of 2026-10-22 (snapshot 52bb04f)

The audit was read-only and reproduced the deterministic part of study B (bridges) to
machine precision. Every finding was checked against the code. The table
says what was done; "result" gives the effect on reported numbers after
re-running. P1 = could change a result or a central claim; P2 = protocol,
comparability or traceability limitation.

## Accepted and fixed in code (with a regression test)

| # | Finding | Fix | Test | Result after re-run |
|---|---|---|---|---|
| P1 | GAT softmax used a global maximum; with the denominator clamp, disconnected components became numerically coupled | per-destination maximum (`scatter_reduce` amax) | `test_gnn.py`: outputs and gradients of a component unchanged by another component (fails on the old code) | GAT test F1 0.463 → **0.500**, AUPRC 0.460 → 0.501 (5 seeds). Ranking unchanged: trees > GraphSAGE > GAT > GCN |
| P1 | Near-duplicate grouping verified only (first, other) pairs inside an LSH bucket; result depended on input order | exact duplicates merged unconditionally; every candidate pair verified | `test_features.py`: order invariance, brute-force pair coverage | SolidiFI unchanged (AUPRC ≈ 1.0 under every split); DAppSCAN: see the giant-group row below |
| P1 | `--aggregate` re-read its own `metrics_summary.csv` and failed on a second run after overwriting `metrics.csv` | parts in `RUN/parts/<tag>/`, duplicate check, atomic writes | `test_aggregate.py`: two runs give byte-identical files | historical table was not corrupted (78 unique rows) |
| P1 | Quantile threshold + `score >= t` let a tied block exceed the budget (ECOD-max: 0.33 % / 1.58 % / 2.6 % achieved at a nominal 0.1 %) | `threshold_at_budget`: achieved rate ≤ budget, ties never split; achieved rate and resolution 1/n reported | `test_eval.py` | **ECOD-max "recall 1.0, 0 % lost" on Ronin withdrawn**: at an achieved budget ECOD-max alarms on nothing at 0.1 %; with ties broken by the sum it equals ECOD (alarm on the second release) |
| P1 | solc chosen from the first minor of the pragma (0.4.26 for `>=0.4.22 <0.6.0` code using 0.5 syntax); errors not stored | newest allowed release per allowed minor, newest first; per-file status and error tail | `test_solc_selection.py` | files not analysed: 46/493 → **4/493** (three Slither crashes and one solc failure). SolidiFI reentrancy recall 0.82 → 1.00, F1 0.59 → 0.68; tx.origin F1 0.85 → 0.94; unchecked F1 0.58 → 0.67 |
| P1 | "0 % USD lost" ignored that the alarm-raising release had already executed | loss split into before alarm event / through alarm block / after alarm + d s | `test_eval.py` | Ronin rules: 0 % before the alarm, **95.5 % through the alarm block**; Nomad: 5.8 % through the first block, 82.7 % released more than 1 h after the first alarm |
| P1/P2 | USD of unmatched events used future observations (±3 d window, global fallback) and attack-specific enrichment | past-only estimator for every unmatched event; reference values only for loss accounting; prefix-invariance check of raw → features in every run | `test_eval.py::test_causal_usd_is_prefix_invariant`, run-time assertion | no headline number changed (as the audit's own ablation predicted) |
| P1 | Oracle-prior failure taken as proof of concept shift | oracle row documented as not an upper bound; new diagnostics: per-step ROC-AUC, class-conditional KS, step-optimal F1 | `test_eval.py` reproduces the counterexample | claim now rests on direct evidence: in steps 43–45 and 47 (step 46 has 2 illicit nodes) the illicit score distribution differs from validation with KS 0.94–1.00 (0.20–0.53 before the shutdown) while licit KS stays 0.09–0.33, ROC-AUC falls to 0.65–0.78 and even a step-optimal threshold gives F1 ≤ 0.14 |
| P2 | Headline feature set coincided with the test maximum for MLP and logreg | validation-AUPRC selection fixed in code; test-best shown beside it | — | MLP 0.557 → **0.517** (AF+NB selected), logreg 0.416 → 0.370; trees, GNNs and KAN unchanged |
| P2 | Manifests: dirty flag always true, `HEAD` as commit, empty data hashes, overwritten T1 manifest, Optuna undeclared | code state captured at start (commit, changed code files, diff SHA-256; results/ and data/ excluded), one manifest per part, Optuna in requirements, `requirements-lock.txt`, `slither` extra | — | — |
| P2 | C2 fold ids and per-file scores not saved | `folds.csv`, `assignments.parquet`, `oof_scores.parquet`, `cross_scores.parquet`, `groups.parquet` | — | — |
| P2 | Slither F1 compared with ML AUPRC | `c4_slither_vs_ml.py`: both on AUPRC and at Slither's alarm count | — | SmartBugs reentrancy: best transferred model AUPRC 0.784 vs Slither flags 0.728, but at Slither's 38 alarms Slither has precision 0.76 / recall 0.94 vs 0.70 / 0.85 (expected under random tie order; 0.71 / 0.87 in the first, order-dependent count). Unchecked: Slither better on both |
| P2 | LUT interpolation promoted float32 to float64 | weights cast to float32 | `test_kan.py` | — |

## Accepted as wording or new analysis

| # | Finding | Change |
|---|---|---|
| P1/P2 | Giant DAppSCAN group (82 % of files) mixes overlap removal with a smaller training set | confirmed (5,408 of 6,587 files). Added `project`, `random_matched` and `local_random` / `local_safe` (same 4,648 project-local files, balanced folds). At comparable training sizes, project-disjoint splitting lowers AUPRC 1.4× (reentrancy) and 2.3× (unchecked), not arithmetic (a split effect, not a pure duplicate-leakage measure); the earlier "up to 3×" from `random` vs `safe` mixed both effects and is withdrawn. FINDINGS_CONTRACTS §2 |
| P2 | "Conservative AUPRC" for DAppSCAN | removed; missing labels can bias AUPRC either way |
| P2 | Within-DAppSCAN (6,587 files) and cross-target DAppSCAN (948 annotated files) are different populations | stated next to both tables |
| P2 | KAN–MLP "tie" not established (F1 difference positive for 3/3 seeds) | pre-declared 10-seed analysis (`k3`): AUPRC −0.013 (MLP better), F1 +0.034 (KAN better), both inconclusive under the pre-set rule. Wording now: no stable KAN advantage; neither superiority nor equivalence shown |
| P2 | Latency excludes preprocessing and features; K1 agreement on all labelled nodes, K2 on test | stated; "≥ 99.9 % at 8 points" holds for quantile inputs (99.985 %) but not robust (99.88 %) |
| P2 | Elliptic++ split differences attributed to leakage | reworded as protocol sensitivity; several factors change at once |
| P2 | Elliptic aggregate features describe neighbours both ways | "offline snapshot benchmark", not an online pipeline |
| P2 | Nomad 382 attack *events* in 167 transactions; ordering without block / log index | stated; same-timestamp events treated as one block |
| P2 | ECOD here is a frozen, smoothed two-tail ECDF variant | renamed in docs and docstring |
| P2 | Nomad → Ronin transfer is retrospective and asymmetric | stated |
| P2 | Early stopping differs by family; KAN inputs scaled by 0.6 | stated in PROTOCOLS as part of each model's definition |

## Not changed, with reason

| Finding | Reason |
|---|---|
| Per-row Elliptic predictions for every run | committed for the headline run (`t1_20261022_v2/scores_labelled.npz`, 11 MB); other runs keep scores locally, as raw data, to keep the repository small |
| Full re-run of every experiment | as the audit recommends, only results a defect could affect were re-run; T3 (Optuna), T4 and T5 do not use the corrected functions (T4 reads RF scores that did not change). K1 and K2 do use the float32 LUT change and were re-run after the second review (below) |
| Hardware-level latency, online bridge monitor | outside this repository's scope; listed as future work |

## Second review (2026-10-22, after the fixes above)

| # | Finding | Fix | Check | Result after re-run |
|---|---|---|---|---|
| 4.1 | B: matched releases still carried the dataset USD value, the close of a candle that closes after the release (reviewer: 15,146 of 17,340 matched Ronin ETH releases; our count 15,429, median 27 h ahead); the valuation method depended on `matched`, so the D view used the cross-chain match indirectly; the prefix test cannot see a future value stored inside a row | one price source for every release: close of the last daily candle closed at or before it (`bal.data.prices`, raw candles snapped to their 16:00 UTC grid with a residual check); valuation no longer reads `matched` | row-level assertion `price_time_s <= ts` in every B1 run (0 violations), `test_asof_prices_are_available_and_ignore_matching`, `test_price_candles_snap_to_grid`; input files incl. price files hashed in the manifest | B1 and B2 re-run in full (all detectors, views, transfer). Rules unchanged; recall, first-alarm time and value released before / through the alarm unchanged for ECOD, ECOD-max (both tie rules) and Isolation Forest in the headline table; false-alarm rates move by ≤ 0.3/day; autoencoders change most (ROC-AUC up to ±0.13 under transfer). FINDINGS_BRIDGES "Price source" |
| 4.2 | `scores_labelled.npz` claimed committed but ignored (negation before the general rule); Quick start lacked the T1 aggregation step | rules reordered, file committed; Quick start runs `--aggregate` and says it is required | `git check-ignore` | T2 / T4 run on the committed directory |
| 4.3 | K1/K2 LUT measurements predate the float32 change in `LUTKAN.forward` | K1 (both preprocessings) and K2 re-run on the current code; K2 saves the trained models (`models.pkl`) and accepts `--models` | — | agreement unchanged (99.985 % quantile / 99.88 % robust at 8 points; 99.988 % on test, 2 of 16,670 decisions differ); latency re-measured on an idle machine: LUT 1.4–2.8× faster than the matched NumPy KAN, MLP 4.4–38× faster than the LUT |
| 4.4 | empty data field in C2 / B1 manifests | `data_sets` corpus digests (SHA-256 over sorted per-file hashes) and per-file hashes incl. price files; missing inputs listed | — | new runs carry them; the two C2 runs got `manifest_data_posthoc.json` (computed afterwards at the pinned data commits) |
| 4.4 | README extended best-step F1 ≤ 0.14 to all of 43–49 | restricted to 43–45 and 47; 48–49 recover to 0.42–0.47 best-threshold F1; step 46 not interpreted | — | — |
| 4.4 | C top-k depended on file order under ties | expected precision / recall under random tie order, with min / max true positives | `test_top_k_with_ties_is_order_free` | SmartBugs reentrancy model at k = 38: 0.70 / 0.85 (26–27 of 31), was 0.71 / 0.87 |
| 4.4 | local comparison described as a clean leakage measure | described as the effect of project-disjoint splitting at comparable training sizes | — | — |
| 4.4 | C1 corpus audit had the old group counts | re-run with the order-invariant grouping; old run removed | — | DAppSCAN 4,993 near-duplicate components (was 5,001), SolidiFI 214 (was 222) |
| 4.4 | no diagnostics for the 4 Slither failures | with `--json -` Slither 0.11.6 prints nothing on a crash; a failed file is rerun once without it and the full output stored in `logs/` | — | two SlithIR tuple-assignment assertions, one constant-folding `NotConstant`, one solc 0.4.11 internal error |
| 4.4 | stale wording on "zero loss" and KAN / MLP preprocessing | B2 header reworded; FINDINGS_TRANSACTIONS_KAN §5 and README state the only preprocessing difference (KAN input ×0.6 after the shared transform) | — | — |

## Third review (2026-10-22, snapshot 624bf92)

| # | Finding | Fix | Check | Result after re-run |
|---|---|---|---|---|
| 1 | code-state digest missed files inside new, untracked directories (`git status` folds them into one line) | `--untracked-files=all`; each untracked file enters the digest with its path and content | `test_code_state_covers_files_in_new_directories` | — |
| 2 | Slither's diagnostic rerun had no timeout handling | `TimeoutExpired` caught, `diagnostic_timeout` recorded | — | — |
| 3 | B1 attack ranks depended on the order of tied scores (ECOD-max Ronin D: 9 vs 15 for reversed rows, tie range 1–16) | midrank, plus `*_min` / `*_max` over all tie orders | `test_tie_ranks_give_midrank_and_range` | B1 / B2 re-run (`b1_20261022_163601`, `b2_20261022_164508`): only the rank metrics change (45 rows); thresholds, ROC-AUC, recall and loss accounting are identical. ECOD-max best attack rank: Ronin D 8.5 (1–16), X 34 (1–67) |
| 4 | compiler selection ignored OR ranges and versions newer than the known release list | OR ranges honoured; no admissible release → `unsupported_pragma`; compiler errors told apart from Slither crashes | `test_or_ranges_and_unknown_newer_releases`, `test_compile_failure_is_told_from_tool_crash` | C3 / C4 re-run (`c3_20261022_163601`, `c4_20261022_164256`): `parity_wallet_bug_1.sol` is now `compile_error`; 489 / 493 analysed, all metrics identical |
| 5 | wording: "15 % of training steps", MLP 0.542 vs headline 0.517, "8 × 3 × 5" fits, stale latency remark, KAN ×0.6 input not in PROTOCOLS / `tabular.py`, "isolates overlap leakage", "only option for integer arithmetic", DAppSCAN venue, three crashes + one solc failure, 0.71 / 0.87, "lowest threshold" | corrected in PROTOCOLS, FINDINGS, docstrings; 78-fit scheme written out | — | — |
| 6 | candle availability, intraday sensitivity, unpriced Nomad rows | stated as an assumption; "the sensitivity to intraday price data was not evaluated"; 5 + 1 unpriced rows and the two zero-USD attack rows documented | `test_price_asof_uses_last_closed_candle` (synthetic candles, runs in CI) | — |
| 7 | manifests did not hash every input (T4 Elliptic files, C4 `groups.parquet` and SmartBugs labels, C3 labels) | added | — | new runs carry them; older runs are not re-hashed after the fact |
| 8 | K3 kept per-seed metrics but not the scores | `scores.npz`: validation and test scores, validation thresholds and tx ids per model and seed (labels via the local copy, SHA-256 checked) | — | K3 re-run (`k3_20261022_163604`): per-seed metrics identical |
| 9 | scope of inference: K3 bootstrap, "pre-registration", target-selected best transfer model, two bridge incidents | K3: cluster bootstrap over observed test steps, a pre-declared follow-up analysis; C transfer table marked exploratory; B limits stated in PROTOCOLS and FINDINGS | — | — |
| 10 | overlap with Maganti 2026 | full reference (arXiv:2604.19514; RF 0.821 vs GraphSAGE 0.689 ± 0.017) | — | — |

## Review of the public release (2026-10-22, commit 07c01f5)

| # | Finding | Fix | Check |
|---|---|---|---|
| R1 | "82 % near-duplicates" and "templates give the label away" | 82 % described as the transitive union of project membership and near-duplicate links (near-duplicate components ≤ 51 files, projects ≤ 34, 227 `safe` groups, largest 5,408); SolidiFI: best mean AUPRC 1.000, consistent with template recognition, causal role not isolated | group sizes recomputed from `groups.parquet` |
| R2 | K3 header called the bootstrap "variability over future periods" | header now says cluster bootstrap over observed test steps; pre-declared follow-up analysis | — |
| R3 | manifests name development commits; two C4 input hashes differ from the public files | `results/PROVENANCE.md`: original hash → transformation → public hash for every file changed for the public release; C4 re-run on the public inputs (`c4_*_public`) with its own manifest; tag `v0.4.1` | numbers of the public C4 run equal the original |
| R4 | pragma parser read commented-out pragmas, no hyphen ranges, `0.5.*` gave 0.5.0 | comments stripped; hyphen ranges, wildcards and partial versions follow npm semver | `test_comments_hyphen_ranges_and_wildcards`; compiler candidates of all 493 files unchanged, so C3 is not re-run |
| R5 | `diagnostic_timeout` not saved | column in `slither_raw.csv` and line in each log | — |
| R6 | downloader skipped any directory with `.git` | checks HEAD against the pin: resumes an incomplete checkout, updates a clean other revision, refuses to touch local changes | `test_checkout_state` |
| R7 | `features_*.parquet` described as part of `results/` | DATA.md: local derived outputs of B1, read by B2 | — |

## Fourth review (2026-10-23)

| # | Finding | Fix | Check | Result after re-run |
|---|---|---|---|---|
| F1 | the compiler-version pattern features (`solc_version`, `pre_08`) read the first `pragma solidity` even when it was commented out | `_version` strips comments first, like the Slither compiler choice | `test_pattern_version_ignores_commented_pragma`; scan of all corpora: 10 of 6,587 DAppSCAN files change `solc_version` (5 change `pre_08`), no SmartBugs or SolidiFI file | C2 pattern rows re-fitted (`c2_20261024_004314`; lex rows copied after a fold check), C4 re-run (`c4_20261024_011448`): 47 of 288 mean AUPRCs move, 39 by at most 0.01. Largest changes: DAppSCAN → SolidiFI reentrancy pat/RF 0.461 → 0.613, pat/LightGBM 0.319 → 0.408; DAppSCAN → SmartBugs unchecked pat/LightGBM 0.694 → 0.721. Every best-model entry in FINDINGS_CONTRACTS moves by at most 0.008 (timestamp `safe` 0.058 → 0.050, the class with 33–36 positives); C4 unchecked pat/RF at k: P / R 0.61 / 0.67 → 0.64 / 0.71 |
| F2 | K2 timings limited threads only through torch; NumPy / OpenBLAS / OpenMP pools were not pinned, and CPU and library versions were not recorded | `threadpoolctl.threadpool_limits(1)` around the timing, thread environment variables set before import, `torch.set_num_interop_threads(1)`; CPU model, torch / NumPy versions and the thread pools during timing written to `info.json` and the manifest | — | five timing runs on the saved models (`k2_20261024_*`): batch-1 median LUT 73.0 µs, MLP 17.2 µs (before: 78.3 / 17.9); LUT vs NumPy float KAN 1.6–3.4×, MLP vs LUT 4.2–31× (before: 1.4–2.8×, 4.4–38×); LUT agreement unchanged |
| F3 | `import bal` failed in a clean environment outside `src/` | `pip install --no-deps -e .` in the quick start; CI imports `bal` from another directory | CI step | — |

## Fifth review (2026-10-24, K4)

| # | Finding | Fix | Check | Result after re-run |
|---|---|---|---|---|
| G1 | `has_flash` was 1 for every transaction in the `flash` or `attack` stratum, so the attack label set it (4 of 40 attacks have no recognised flash loan) | one rule for every transaction, `bal.data.defi.flash_hashes`, used for the stratum at extraction and for the feature | `test_flash_flag_does_not_use_the_stratum` (permuting strata leaves all features unchanged) | 4 attack rows change (`has_flash` 1 → 0) |
| G2 | `to_created_today` counted contracts created later the same day | `creations.parquet` with the creating transaction's (block, index); only earlier creations count | `test_created_today_only_counts_earlier_creations` (creations in later blocks change nothing) | 18 background rows change, no attack row |
| G3 | the point estimate (mean of per-seed AP) and the interval (AP of the seed-averaged score) were different statistics; leave-protocol-out reported the ensemble AP | the bootstrap recomputes the seed-mean AP in each resample, for sample and weighted AP, with base rates; leave-protocol-out reports the seed-mean out-of-fold AP and `ensemble_ap` separately | — | `k4_20261024_080035`: test AP LightGBM 0.230 [0.106, 0.423], KAN 0.072 [0.029, 0.178], logistic regression 0.082 → 0.022 (the leak helped it most) |
| G4 | the two permutation-importance numbers in `summary.json` disagreed (`nonce` 0.011 vs 0.020) | one computation, 20 permutations per feature, mean and SD; both tables read it | — | SD exceeds the mean for most features (9 validation attacks); relevance vs permutation Spearman 0.02 (was 0.31) |
| G5 | counts of dropped transactions not reported | kept rows contain no failed transaction; 1,493,192 of 61,580,886 transactions on the 49 days failed and were never sampled; 6 transactions of other exploits removed (`done.json`) | — | — |
