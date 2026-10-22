# Data

`python scripts/00_fetch_data.py` clones every public source at a pinned commit
into `data/raw/` (git-ignored):

| Source | Commit | Used in |
|---|---|---|
| AndreAugusto11/XChainWatcher | 4cc1ff173c18f80d275d7af6cbd318cdd3906e77 | B |
| smartbugs/smartbugs-curated | 230e649123477eff332742a59a1c7cc6dc286cab | C |
| DependableSystemsLab/SolidiFI-benchmark | 4b0573e1b3f7031396de6f48f7f3e7380222ad3a | C |
| InPlusLab/DAppSCAN | 66a56619c44770e05c2db600fa6468115ff0dcd5 | C |

Manual download (not hosted on GitHub):

* **Elliptic** → `data/raw/elliptic/`
  (<https://www.kaggle.com/datasets/ellipticco/elliptic-data-set>):
  `elliptic_txs_features.csv`, `elliptic_txs_classes.csv`, `elliptic_txs_edgelist.csv`.
* **Elliptic++** (optional, T5) → `data/raw/ellipticpp/`: `wallets_features_classes_combined.csv`,
  see <https://github.com/git-disl/EllipticPlusPlus>.

## Licences and what this repository redistributes

No raw dataset is redistributed: every script reads the sources from
`data/raw/`, which is git-ignored. Results contain metrics, model scores and
aggregate statistics; row-level labels of sources without an open licence
are not included and are read back from the local copy when a script needs
them (`bal.data.elliptic.load_scores`, `scripts/c4_slither_vs_ml.py`).

| Source | Licence (at the pinned commit / source page) | In `results/` |
|---|---|---|
| XChainWatcher (incl. its daily token price files) | MIT (repository `LICENSE`) | per-event features and labels of both bridges (`b1_*/features_*.parquet`) |
| SmartBugs-curated | Apache-2.0 (repository `LICENSE`) | file paths, scores, Slither statuses; labels are read from the local copy |
| SolidiFI-benchmark | MIT for the benchmark; the original contracts keep their Etherscan licences (repository `LICENSE`) | file paths, scores |
| DAppSCAN | no licence file in the repository | file paths, near-duplicate groups, fold ids and scores; no labels |
| Elliptic | no licence stated in a form we could verify; obtain it from the Kaggle page and follow its terms | per-node model scores in dataset order, without ids, labels or time steps (a SHA-256 of the labels checks the local copy) |
| Elliptic++ | no licence file in the repository | aggregate metrics only |

Code: MIT (`LICENSE`). Results and documentation (`results/`, `docs/`):
CC BY 4.0 (`results/LICENSE`). Users of the data must cite and follow the
terms of each original source.

## Bridge event construction (B)

* Matched releases: `analysis/<bridge>/data/cctxs_withdrawals.csv`
  (destination side; latency = destination timestamp − source timestamp).
* Unmatched releases: `datalog/<bridge>/results/SC_WithdrawalsWithoutMatch.csv`.
  All attack transactions are in this file.
* Label = 1 iff the transaction hash is in XChainWatcher's `attacks.csv`.
* `value_usd` (features, rules): every release, matched or not, gets
  amount / 10^decimals × the close of the last daily candle that closed at or
  before it, from the raw candles in `token-price-data/<bridge>/bitget/*.csv`
  (close at 16:00 UTC; the rounded time stamps in the files are snapped to
  that grid). Token → series and decimals follow the maps in the
  XChainWatcher notebooks. 6 Nomad releases get 0 (`usd_unknown`): five of
  tokens without a series, one before the first closed candle. Two attack
  rows already have zero reference USD in `attacks.csv`. `price_time_s` records the close time used.
  `value_usd_ref` (loss accounting only) uses the attack values of
  `attacks.csv`. The dataset's own `value_usd` of matched releases (close of
  the candle labelled with the request date, usually closing after the
  release) is kept as `value_usd_dataset` for the ablation only.
* One event = one release. Order: (timestamp, tx hash, withdrawal id); there
  is no block number or log index in the data.

| Bridge | Events | Attack events (transactions) | Attack USD (reference) | Unmatched non-attack |
|---|---|---|---|---|
| Ronin | 25,470 | 2 (2) | 565.4 M | 2,638 |
| Nomad | 4,869 | 382 (167) | 159.6 M | 5 |
