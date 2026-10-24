# Provenance of the public result files

The runs in `results/` were produced in the development repository of this
project. Their manifests record that repository's commits, which are not part
of this repository's history; the code is the same apart from file names (see
`README.md` in this folder) and from the commits that followed.

To publish the results, a few files were changed after the runs. Their
manifests still show the hashes of the original bytes; they were not edited
after the fact. The table gives, for every changed file, the first 16 hex
digits of the SHA-256 of the original file, the transformation and the
SHA-256 of the file published here. All other files are byte-identical to the
development repository.

| File | Original SHA-256 | Transformation | Public SHA-256 |
|---|---|---|---|
| `results/contracts/c1_20261022_141306/near_dup_components.csv` | `e8d2d7d1577b514e` | label columns removed (DAppSCAN labels) | `bec31e423e9c5950` |
| `results/contracts/c2_20261022_092004/cross_scores.parquet` | `37dfb57b0ab19c90` | label column `y` removed | `2799bf3088a35301` |
| `results/contracts/c2_20261022_092004/groups.parquet` | `3ee450a59cf00038` | label columns removed | `46d43eb88b73d759` |
| `results/contracts/c2_20261022_092004/oof_scores.parquet` | `2e0f201ec6eec5fc` | label column `y` removed | `31c3e92859e049ea` |
| `results/contracts/c2_20261022_113242/groups.parquet` | `3ee450a59cf00038` | label columns removed | `46d43eb88b73d759` |
| `results/contracts/c2_20261022_113242/oof_scores.parquet` | `59fdc94e2e23a56b` | label column `y` removed | `29f504d8d3dfe6bf` |
| `results/contracts/c2_20261024_004314/cross_scores.parquet` | `80c5b7fab8dffb43` | label column `y` removed | `1654fff4b8c8b919` |
| `results/contracts/c2_20261024_004314/groups.parquet` | `3ee450a59cf00038` | label columns removed | `46d43eb88b73d759` |
| `results/contracts/c2_20261024_004314/oof_scores.parquet` | `753c2d5ababf4f84` | label column `y` removed | `e3d25352138bf43c` |
| `results/transactions/t1_20261022_v2/scores_labelled.npz` | `1fbe6d290c17958a` | Elliptic `y` and `step` removed (`labels_sha256` kept; `load_scores` reloads them) | `4e018dec57c5d1ec` |
| `results/kan/k3_20261022_163604/scores.npz` | `ad87922f61be179e` | `val_txid` and `test_txid` removed (rows follow the labelled validation / test nodes in file order) | `081f836090c55cd3` |
| `results/contracts/c3_20261022_142713/logs/0x89c1b3807d4c67df034fffb62f3509561218d30b.log` | `d214aab3831dae83` | absolute path of the development checkout removed | `a3dd059f235135f6` |
| `results/contracts/c3_20261022_142713/logs/parity_wallet_bug_1.log` | `86b132cf670e8c3e` | absolute path of the development checkout removed | `721ee1f08049f2d2` |
| `results/contracts/c3_20261022_142713/logs/reentrancy_bonus.log` | `223af41784837d1a` | absolute path of the development checkout removed | `01a6af159b08cca2` |
| `results/contracts/c3_20261022_142713/logs/reentrancy_cross_function.log` | `a56aaa0a787c8fa9` | absolute path of the development checkout removed | `67c5f1132bcb5ea9` |
| `results/contracts/c3_20261022_163601/logs/0x89c1b3807d4c67df034fffb62f3509561218d30b.log` | `d214aab3831dae83` | absolute path of the development checkout removed | `a3dd059f235135f6` |
| `results/contracts/c3_20261022_163601/logs/parity_wallet_bug_1.log` | `a0597ed501d24921` | absolute path of the development checkout removed | `ec429bade091b89f` |
| `results/contracts/c3_20261022_163601/logs/reentrancy_bonus.log` | `223af41784837d1a` | absolute path of the development checkout removed | `01a6af159b08cca2` |
| `results/contracts/c3_20261022_163601/logs/reentrancy_cross_function.log` | `a56aaa0a787c8fa9` | absolute path of the development checkout removed | `67c5f1132bcb5ea9` |

## Re-run on the public files

`contracts/c4_20261024_012615` repeats the current C4 run `contracts/c4_20261024_011448`
in the same way on the public files of `c2_20261024_004314` (commit `eb9fc2e`);
its tables are identical to the original.

Earlier:

`contracts/c4_20261022_191915` repeats C4 inside this repository (commit
`abffd90`, clean) on the public `cross_scores.parquet` and `groups.parquet`;
its manifest hashes the public bytes. Its tables are identical to the original
run `contracts/c4_20261022_164256`.

Scripts that need the removed labels read them from the local copy of the
dataset (`data/raw/`), and check them against `labels_sha256` where one is
stored.
