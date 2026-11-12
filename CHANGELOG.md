# Changelog

Each release is tagged on GitHub. Superseded runs are listed in
`results/README.md`; the large superseded K4 runs are removed from the working
tree and remain in the release that produced them (0.5.0, 0.5.1).

## 0.7.0 (2026-11-12)

Study V (what smart-contract security benchmarks measure; `docs/PROTOCOLS.md`,
section V, with amendments 1–6). It extends study C and is reported in
Chapter 13 of the book. Earlier studies and their runs are unchanged.

* V1 SolidiFI decomposition into 44 templates (`v1_20261030_181838`) and a
  three-level reading of the templates (operation / weakness / exploit,
  `data/audit/template_three_levels.csv`); V7 builds a blinded reading form,
  V7b compares readers (`v7b_llm_20261103_233429`: LLM readers only, no human
  readers yet).
* V2 template controls with leave-one-template-out (`v2_20261030_183559`).
* V3 models fixed on source validation and scored once on each target
  (`v3_20261030_182906`).
* V4 static analysers: Slither (`v4_20261030_180940`, `v4_20261030_185950`
  with all detectors), SmartCheck, Mythril with an explicit compiler version
  (`v4m_20261103`; without `--solv` Mythril offline silently disables its
  integer module), Slither on annotated DAppSCAN (`v4d_20261103`).
* V5 scoring units and alarm budgets (`v5_20261104_043212`; replaces
  `v5_20261031_115227`, which used the Mythril runs without `--solv`).
* V8 analyser controls on 15 hand-written contracts (`v8_20261103_222943`),
  V9 transfer statistics with permutation nulls and cluster bootstrap
  (`v9_20261103_222854`), V10 paired fixed and renamed templates
  (`v10_20261103_224807`), V6 tables and figures (`v6_paper`).
* SolidiFI "Unchecked-Send" is scored as an unprotected Ether transfer
  (SWC-105), not as an unchecked call (amendment 1); the C2/C3 merge is kept
  as `unchecked_merged` for comparison.

## 0.6.0 (2026-10-25)

K4 (DeFi exploits):

* Pool metadata is causal. A Uniswap V2 pool's token pair is known only from
  token transfers up to the end of the transaction being scored
  (`pair_tokens.parquet`, `bal.features.defi_features.causal_pairs`), and a
  pool counts as V2 only after its first `Sync` or a V2 `Swap` in the same
  transaction. Up to 0.5.1 both came from the whole day, so a feature could
  use events of later blocks. Regression tests:
  `test_later_block_changes_no_earlier_feature`,
  `test_pair_map_uses_only_transfers_up_to_the_transaction`.
* The input transform of MLP and KAN (quantile or robust) is chosen inside
  each outer fold of the leave-days-out evaluation by an inner grouped split
  (`prep_choice_by_fold.csv`); up to 0.5.1 it was chosen once on data that
  included the evaluation folds.
* The grouped evaluation is named for what it does: `leave_days_out.csv`
  (days, not protocols, are held out).
* The cohort is described as keyword-selected (README headings that name a
  price or oracle manipulation and PoCs that fork mainnet with a flash loan),
  not as a census of such exploits.
* `k4_defi_kan.py --resume <run>` continues an interrupted run in its folder:
  finished fits are cached in `<run>/_cache` (removed at the end) and reused;
  every fit sets its own seed, so the outputs equal those of an uninterrupted
  run (checked on a reduced run). The manifest records `resumed` and the
  number of reused fits.
* The day bootstrap of K4 weights a day drawn k times by k instead of
  concatenating k copies of its rows. The resampled APs equal sklearn's on
  the concatenated rows up to 1e-16 (`tests/test_k4_bootstrap.py`), and the
  2,000 resamples take minutes instead of most of an hour.
* `scripts/tools/k4_feature_diff.py` compares the features of the previous run
  with the recomputed ones and checks that the re-extracted inputs are
  byte-identical to the previous manifest (output for this release:
  `results/kan/k4_feature_diff_v0.6.0`). Against `k4_20261024_080035`:
  the day files were re-extracted (the earlier ones were not kept); 45 of 49
  days hold the same transactions, while on four days the flash stratum has
  7 more transactions and the background sample differs (6,649 rows replaced).
  On the 331,215 common rows the causal pool metadata changes 4,868 rows
  (1.5 %), almost all in the flash stratum: `n_flash`, `flash_to_pool`, and
  `has_flash` of five transactions; one attack changes (`flash_to_pool`).
* New run `k4_20261024_204829` from a clean tree (continued twice with
  `--resume`; see `docs/FINDINGS_DEFI.md`). Temporal test AP: LightGBM 0.212,
  random forest 0.209, KAN 0.140, MLP 0.094 (KAN vs MLP inconclusive);
  held-out days: the MLP falls from 0.146 to 0.066 with its transform chosen
  inside each fold. It supersedes
  `k4_20261024_080035` (made from a modified working tree whose diff cannot be
  reproduced) and `k4_20261023_200340`.

Other:

* `bal.__version__` follows the package version (it still read 0.4.1).
* `bal.models.kan.input_relevance`: docstring states that edge functions are
  complete (SiLU and spline terms) and summed over hidden units.
* Local virtual-environment paths in recorded thread-pool information and
  Slither logs are replaced by `<venv>`; `results/PROVENANCE.md` gives the
  original and the public SHA-256 of each edited file; recorded input
  checksums are unchanged.
* Review notes moved to `docs/archive/`; `.zenodo.json` added.

## 0.5.1 (2026-10-24)

* K4: `has_flash` is computed from events, not from the sampling stratum;
  `to_created_today` counts only contracts created before the transaction;
  bootstrap intervals over the seed mean. Run `k4_20261024_080035`.

## 0.5.0 (2026-10-24)

* K4: DeFi exploit study on DeFiHackLabs and the AWS public Ethereum data.
* C: compiler selection follows the pragma; contract benchmark re-run.
* K3: single-thread timing of MLP, spline KAN and LUT KAN.

## 0.4.1 (2026-10-22)

* Fixes R1–R7 of the review of the public release (provenance of public
  result files, C4 re-run on public inputs). Details in
  `docs/archive/AUDIT_RESPONSE.md`.

## 0.4.0 (2026-10-22)

* First public release: studies B (bridges), C (contracts), T (transactions)
  and K1–K3 (KAN on Elliptic).
