# Runs

Current runs, as cited in `docs/FINDINGS_*.md`. Every other run folder is kept
for the record and is superseded, except the superseded K4 runs (50–100 MB
each), which are kept only in the release named in the table.

The runs were produced in the development repository before this public
release. Their manifests record that repository's commit. Runs made before
the studies were renamed (all except B1, B2, C3, C4 and K3) also record the
old script names; the code is the same apart from file names:

| Now | In manifests |
|---|---|
| `b1_bridge_detection.py`, `b2_saturation_and_hybrid.py` | `e15_01_…`, `e15_02_…` |
| `c1_corpus_audit.py` … `c4_slither_vs_ml.py` | `e13_01_…` … `e13_04_…` |
| `t1_temporal_benchmark.py` … `t4_drift_monitor.py`, `t5_ellipticpp_wallet_splits.py` | `e10_01_…` … `e10_04_…`, `e10_05_ellipticpp_wallet_leakage.py` |
| `k1_kan_analysis.py` … `k3_kan_mlp_uncertainty.py` | `e17_01_…` … `e17_03_…` |

Files changed for the public release (labels and local paths removed) are
listed with their original and public SHA-256 in [PROVENANCE.md](PROVENANCE.md).

Licence of the result files: CC BY 4.0 (`LICENSE`); see docs/DATA.md for the
underlying datasets.

| Study | Current run(s) | Superseded |
|---|---|---|
| T1 temporal benchmark | `transactions/t1_20261022_v2` (incl. `scores_labelled.npz`) | `t1_20261021_full` (GAT softmax defect) |
| T2 label shift | `transactions/t2_20261022_113332` | `t2_20261021_232124` |
| T3 Optuna | `transactions/t3_{lgbm,rf,mlp,kan}_*` | — |
| T4 drift monitors | `transactions/t4_20261022_014938` | — |
| T5 Elliptic++ wallets | `transactions/t5_20261022_022444`, `t5_20261022_023415` | — |
| C1 corpus audit | `contracts/c1_20261022_141306` | — |
| C2 benchmark | `contracts/c2_20261024_004314` (pattern rows re-fitted after the pragma fix; lex rows copied from the two runs on the right after a fold check) | `c2_20261022_092004` and its `local_*` rows `c2_20261022_113242` (pattern feature read commented-out pragmas), `c2_20261021_160726` (order-dependent grouping) |
| C3 Slither | `contracts/c3_20261022_163601` | `c3_20261022_142713` (one solc failure labelled tool_error), `c3_20261021_163759`, `c3_20261022_092255` |
| C4 Slither vs ML | `contracts/c4_20261024_011448`; same tables re-run on the public inputs: `c4_20261024_012615` | `c4_20261022_164256` and its public re-run `c4_20261022_191915` (C2 inputs before the pragma fix), `c4_20261022_143422` (same numbers, inputs not all hashed), `c4_20261022_113408` (order-dependent top-k) |
| V1 SolidiFI template audit | `contracts/v1_20261030_181838` | — |
| V2 template controls (seen / LOTO / pairs) | `contracts/v2_20261030_183559` | — |
| V3 frozen transfer | `contracts/v3_20261030_182906` | — |
| V4 analysers (Slither, Mythril, SmartCheck) | `contracts/v4_20261030_180940` (resumed after two container restarts; Mythril on SolidiFI sampled, amendment 3), `contracts/v4_20261030_185950` (Slither, all detectors) | — |
| V5 scoring units, budgets | `contracts/v5_20261030_234245` | — |
| V6 paper tables and figures | `contracts/v6_paper` (generated from V1–V5) | — |
| B1 bridges | `bridges/b1_20261022_163601` | `b1_20261022_141005` (attack ranks depended on tie order), `b1_20261022_093114` (dataset prices), `b1_20261021_161056` |
| B2 saturation, hybrids | `bridges/b2_20261022_164508` | `b2_20261022_142045`, `b2_20261022_094142`, `b2_20261021_162632` |
| K1 KAN analysis | `kan/k1_{quantile,robust}_20261022_142521` | `k1_*_20261021_232204` (float64 LUT) |
| K2 LUT latency | timing: `kan/k2_20261024_011451`, `…_011806`, `…_011911`, `…_012008`, `…_012105` (one thread, threadpoolctl); models: `kan/k2_20261022_144836/models.pkl` | timing of `k2_20261022_144836` (threads limited through torch only), `k2_20261022_021810` (float64 LUT) |
| K3 KAN vs MLP, 10 seeds | `kan/k3_20261022_163604` (incl. per-seed `scores.npz`) | `k3_20261022_113301` (same numbers, scores not saved) |
| K4 DeFi flash-loan exploits | `kan/k4_20261024_204829` (incl. `features.parquet`, `scores.npz`); feature check against the previous run: `kan/k4_feature_diff_v0.6.0` | `k4_20261024_080035` (pool token pairs from the whole day; prep chosen outside the held-out folds; modified working tree; in release 0.5.1), `k4_20261023_200340` (`has_flash` from the stratum, `to_created_today` saw later creations; in release 0.5.0) |
