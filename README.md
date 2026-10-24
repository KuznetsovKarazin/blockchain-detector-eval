# blockchain-detector-eval

**When can you trust a blockchain anomaly detector, and what does it cost to run?**

[![tests](https://github.com/KuznetsovKarazin/blockchain-detector-eval/actions/workflows/tests.yml/badge.svg)](https://github.com/KuznetsovKarazin/blockchain-detector-eval/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.12-blue)
[![code: MIT](https://img.shields.io/badge/code-MIT-green)](LICENSE)
[![results: CC BY 4.0](https://img.shields.io/badge/results-CC%20BY%204.0-lightgrey)](results/LICENSE)
![CPU only](https://img.shields.io/badge/hardware-CPU%20only-orange)

This repository evaluates detectors for four blockchain security tasks under
deployment-like protocols: future time periods, unseen addresses and projects,
fixed false-alarm budgets, and released funds counted in USD. Each experiment
pits learned models against strong simple baselines (tree ensembles,
transparent rules, a static analyser) under the same protocol. Every
number below comes from a numbered script in `scripts/` and is stored with a
manifest under `results/`.

| Study | Question | Data | Scripts |
|---|---|---|---|
| **B · bridges** | Can a detector without attack labels raise an alarm early enough on a bridge exploit, at a false-alarm rate an operator accepts? | XChainWatcher (Ronin, Nomad) | `b1`, `b2` |
| **C · contracts** | How much of a vulnerability detector's benchmark score survives duplicate control, new projects, a different labelling regime and compilation failures? | SmartBugs-curated, SolidiFI, DAppSCAN | `c1` – `c4` |
| **T · transactions** | Which models keep working on future periods and new addresses, and do label-free monitors notice when they stop? | Elliptic, Elliptic++ | `t1` – `t5` |
| **K · KAN** | Do Kolmogorov–Arnold networks buy accuracy, explanations or cheaper inference over a same-size MLP? | Elliptic | `k1` – `k3` |
| **K4 · DeFi exploits** | Can a model find a flash-loan price-manipulation exploit among the transactions of its day, at an alarm budget, and do KAN explanations say why? | DeFiHackLabs, AWS public Ethereum data | `k4` |

> **Five findings in one line each**
>
> 1. A bridge detector with ROC-AUC 0.99 can still alarm only after 95.5 % of the stolen value has left; two-condition rules alarm first.
> 2. On a popular injected-bug benchmark (SolidiFI) the best models reach AUPRC 1.0 under every split, consistent with recognising the bug templates; on real audit labels AUPRC is 0.04–0.15.
> 3. Tree ensembles beat graph neural networks on Elliptic under a strict temporal protocol, and every model collapses after the dark-market shutdown, unnoticed by label-free monitors.
> 4. KANs show no stable advantage over a same-size MLP; their LUT form is faster than a spline KAN but still slower than the MLP.
> 5. On 13 recent DeFi exploits, tree ensembles rank the attack near the top of its day, but alarm budgets set a year earlier are exceeded 2–19×, and the KAN learns the attacker's set-up rather than the manipulation.

**Contents:** [Who this is for](#who-this-is-for) · [Results](#results) ·
[What this project does NOT claim](#what-this-project-does-not-claim) ·
[Quick start](#quick-start) · [Repository layout](#repository-layout) ·
[Reviews](#reviews) · [Citation](#citation) · [References](#references) ·
[License](#license)

---

## Who this is for

**Bridge operators and monitoring services (B).** Use it to choose a
detector for a fixed alarm budget, see how many seconds or releases pass
before the first alarm, and test rules, learned detectors and their OR
combination on the same stream. The bridge pipeline is causal: a feature at
event *t* uses only earlier events and prices whose daily candle had closed
by *t*, and every run checks both (prefix invariance and price time ≤ event
time, row by row).

**Smart-contract auditors and tool builders (C).** Use it to check whether a
tool's or model's score holds on new projects. It shows how exact and near
duplicates, shared library code, compilation failures and incomplete audit
labels move the measured score. Fold assignments, per-file scores and Slither
statuses are saved, so another tool can be added to the same comparison.

**Blockchain analytics teams (T, K).** Use it to test a model on later
periods and unseen addresses, to choose between simple and complex models by
accuracy and inference cost, and to see why a label-free monitor can report
"no illicit activity" while the model has gone blind.

**What the project does not provide yet:** evidence of prevented losses, an
online deployment, measured analyst workload or hardware-level latency. The
natural next step is a streaming pilot with real ingestion and finality
delays, load and triage costs.

---

## Results

### Bridges (B): early alarms on Ronin and Nomad

Nominal 0.1 % false-positive budget, set on a 14-day calibration window
without splitting tied scores. The achieved calibration rate is 0.076 % on
Ronin; Nomad's 421 calibration events cannot resolve 0.1 % (one alarm =
0.24 %), so 0 % is achieved there. Full tables: [docs/FINDINGS_BRIDGES.md](docs/FINDINGS_BRIDGES.md).

| Bridge | Detector | ROC-AUC | Attack recall | Value released before the alarm event | … through the alarm block | False alarms / day |
|---|---|---|---|---|---|---|
| Ronin | ECOD (destination view) | 0.988 | 0.50 | 95.5 % | 100 % | 0.29 |
| Ronin | Isolation Forest (cross-chain view) | 0.985 | 0.50 | 95.5 % | 100 % | 0.04 |
| Ronin | rule R3: no source request ∧ > training p99 | — | 1.00 | 0 % | 95.5 % | **0.00** |
| Nomad | ECOD (destination view) | 0.999 | 0.997 | 1.4 % | 5.8 % | 3.5 |
| Nomad | rule R1: no source request | — | 1.00 | 0 % | 5.8 % | **0.00** |

* **A ROC-AUC of 0.99 does not guarantee an early alarm.** ECOD misses the
  173,600 ETH Ronin release and alarms 115 s later on the 25.5 M USDC one.
  The ETH release ranks 77th of 3,368 because each per-feature tail score
  saturates at log(n + 1). Max-aggregation removes the dilution, but the
  release then ties with calibration events at the cap, so a budget that is
  actually met cannot separate it.
* **Two-condition rules give the earliest alarm in both incidents, with zero
  false alarms.** OR-ing them with a detector keeps that alarm.
* **An alarm is not a prevented loss.** The release that raises the alarm has
  already executed. On Ronin that is 95.5 % of the value. On Nomad the attack
  runs for hours: 83 % of the value leaves more than one hour after the first
  alarm, so response time is what matters there.
* These are two incidents, not detection rates.

### Smart contracts (C): what the benchmarks measure

Details: [docs/FINDINGS_CONTRACTS.md](docs/FINDINGS_CONTRACTS.md).

* **SolidiFI cannot rank learned detectors.** The best mean AUPRC is 1.000
  for every class under every split, including identifier normalisation,
  project groups and the restriction to project-local code, and most other
  models are near-perfect too (0.979–1.0 over all 288 runs). This is
  consistent with recognising the injected bug templates; their causal role
  was not isolated (no held-out-template or buggy/patched control). 100 % of
  positive files also carry an identifier stem naming the bug type.
* **On real audit labels (DAppSCAN) AUPRC is 0.04–0.15 at base rates of
  0.5–2 %.** Near-duplicate components alone are small (at most 51 files)
  and projects have at most 34 files, but combining project membership and
  near-duplicate links transitively for the `safe` split puts 5,408 of 6,587
  files (82 %) into one group. This is a joint grouping constraint, not
  evidence that 82 % of the files are near-duplicates of each other. Grouped
  evaluations therefore have to be read with their fold sizes, which are
  saved for every run.
* **Static analysis vs learned models, measured the same way (SmartBugs,
  `c4`).** The "best transferred model" is chosen on the target, so its
  column is exploratory:

| Class | Slither AUPRC | Best transferred model AUPRC | At Slither's alarm count: Slither precision / recall | Model precision / recall |
|---|---|---|---|---|
| reentrancy | 0.73 | 0.78 (raw-token TF-IDF, trained on SolidiFI) | 0.76 / 0.94 | 0.70 / 0.85 |
| unchecked call | 0.89 | 0.74 (pattern RF, trained on DAppSCAN) | 0.90 / 0.98 | 0.61 / 0.67 |
| timestamp | 0.22 | 0.59 | 0.22 / 1.00 | 0.22 / 1.00 |
| arithmetic | no detector | 0.54 | — | — |

  Slither runs on 489 of 493 files once the compiler is chosen inside the full
  pragma range. The first version used the lowest allowed minor and lost 46
  files.
* **Transfer works toward small hand-labelled sets and barely toward audit
  labels.** Models gain 1.4–17× over the base rate on SmartBugs, but only
  1.3–2.4× on DAppSCAN.

### Transactions (T): future periods and new addresses

Elliptic, train steps 1–30, validation 31–34, test 35–49. Feature set chosen
on validation. Details: [docs/FINDINGS_TRANSACTIONS_KAN.md](docs/FINDINGS_TRANSACTIONS_KAN.md).

| Model | Test F1 | Test AUPRC | F1 after the dark-market shutdown (steps 43–49, default) |
|---|---|---|---|
| LightGBM (all + neighbour features) | **0.807** | **0.801** | 0.026 |
| Random forest (all + neighbour features) | 0.798 | 0.792 | 0.027 |
| GraphSAGE | 0.581 | 0.569 | 0.022 |
| MLP (default / Optuna-tuned) | 0.517 / 0.681 | 0.530 / 0.765 | 0.045 |
| GAT | 0.500 | 0.501 | 0.018 |
| KAN (default / Optuna-tuned) | 0.488 / 0.655 | 0.474 / 0.764 | 0.061 |
| GCN | 0.459 | 0.425 | 0.015 |

* **Trees beat message passing** under the inductive temporal protocol.
  Cheap neighbour aggregates give trees the graph signal.
* **After the shutdown every model fails, and prior correction cannot fix
  it.** In steps 43–45 and 47 the score distribution of illicit transactions
  shifts almost completely (KS 0.94–1.00 against validation), ROC-AUC falls
  to 0.65–0.78, and even the best threshold chosen with that step's labels
  gives F1 ≤ 0.14. This is not consistent with pure label shift. In steps
  48–49 the ranking partly recovers (ROC-AUC 0.78–0.90, best-threshold F1
  0.42–0.47), but the validation threshold still gives F1 near 0. Step 46
  has two illicit transactions and is not interpreted.
* **Label-free monitors mislead.** The estimated illicit share drops to zero
  and stays there when the true share returns to 8–12 %. Input-drift scores
  flag every step, before and after the shutdown alike.
* **Address-level scores depend on the split.** On Elliptic++ wallets, F1
  is 0.95 with random rows, 0.88 with random addresses and 0.27–0.39 with
  a temporal, address-disjoint split. All 55 wallet features are lifetime
  aggregates.

### KAN (K)

* With robust input scaling the KAN loses to a parameter-matched MLP in all
  four sizes tested. With rank-based (quantile) inputs they are close: in a
  pre-declared follow-up analysis with 10 seeds the MLP has a higher AUPRC (−0.013 for the
  KAN), the KAN a higher F1 (+0.034), and neither difference is stable or
  small enough to call the two equivalent. **No stable KAN advantage.**
* Spline relevance agrees only weakly with the KAN's own permutation
  importance (Spearman 0.33–0.39).
* A lookup-table (LUT) KAN keeps 99.985 % of decisions at 8 points per
  interval with quantile inputs, but only 99.88 % with robust inputs
  (re-measured on the current float32 LUT code). It is 1.6–3.4× faster than a
  matched NumPy B-spline KAN, but a same-size MLP is 4.2× (batch 1) to 31×
  (batch 1024) faster still (one thread, median of five runs). Timings cover
  the kernel only; the trained models are saved with the run.
* Preprocessing differs in one documented step: both models get the same
  fitted transform clipped to ±5, and the KAN input is then scaled by 0.6 to
  fit its spline grid.

### DeFi exploits (K4): flash-loan price manipulation on Ethereum

40 DeFiHackLabs exploits (2021–2026) against all other flash-loan
transactions of the same days, transactions touching the same contracts and
a background sample from the AWS public Ethereum data (338k kept
transactions, weighted to about a million per day). Details:
[docs/FINDINGS_DEFI.md](docs/FINDINGS_DEFI.md).

* Temporal test (2025–2026, 13 attacks; mean AP over seeds): LightGBM 0.230
  [0.106, 0.423], random forest 0.189, MLP 0.101, KAN 0.072 [0.029, 0.178],
  logistic regression 0.022; a flash loan × price move rule is near random
  (0.002). Tree models put the median attack at rank 3–6 of its day.
* Alarm budgets set on 2024 do not hold on 2025–2026: a 1/day threshold gives
  2.0–18.9 alarms per day.
* The KAN mostly uses the attacker's set-up (fresh sender, contract deployed
  the same day, gas), not the manipulation features. Its edge functions match
  its partial dependence only when signed by the second layer (Spearman +1.0,
  −1.0 for the plain first-layer sum).
* Detection is after execution: all features come from the mined transaction.

---

## What this project does NOT claim

* No general ranking of model families: each claim is tied to one dataset,
  one protocol and one budget.
* No prevented-loss or production-readiness claim. The bridge study replays
  historical data offline.
* Seeds measure training randomness on fixed histories, not uncertainty over
  new attacks, chains or periods.
* Slither results are for one version with default detectors, and are not a
  ranking of static analysers.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # or, for the published environment (Python 3.13): -r requirements-lock.txt
pip install --no-deps -e .                  # the `bal` package itself, so that `from bal ...` works anywhere
pytest -q                                   # 45 unit tests, < 2 min on CPU
python scripts/00_fetch_data.py             # public sources at pinned commits → data/raw/
```

Run all commands from the repository root. Elliptic and Elliptic++ must be downloaded by hand (see [docs/DATA.md](docs/DATA.md)).

```bash
# bridges
python scripts/b1_bridge_detection.py
python scripts/b2_saturation_and_hybrid.py --b1-run results/bridges/<b1 run>
# smart contracts (Slither: pip install -r requirements-slither.txt)
python scripts/c1_corpus_audit.py
python scripts/c2_vuln_benchmark.py --seeds 3
python scripts/c3_slither_baseline.py
python scripts/c4_slither_vs_ml.py --c2-run results/contracts/<c2 run> --c3-run results/contracts/<c3 run>
# transactions
python scripts/t1_temporal_benchmark.py --run results/transactions/R --seeds 5   # parts → R/parts/
python scripts/t1_temporal_benchmark.py --run results/transactions/R --aggregate # REQUIRED: writes R/scores_labelled.npz
python scripts/t2_label_shift.py --t1-run results/transactions/R      # or the committed results/transactions/t1_20261022_v2
python scripts/t3_optuna_tuning.py --model kan --trials 40      # also lgbm, rf, mlp
python scripts/t4_drift_monitor.py --t1-run results/transactions/R
python scripts/t5_ellipticpp_wallet_splits.py --data data/raw/ellipticpp
# KAN
python scripts/k1_kan_analysis.py --seeds 3 --prep quantile   # and --prep robust
python scripts/k2_lut_latency.py
python scripts/k3_kan_mlp_uncertainty.py --seeds 10
# DeFi exploits (reads 49 days of public Ethereum data from AWS over HTTPS)
python scripts/k4_extract_days.py --workers 1
python scripts/k4_defi_kan.py --seeds 5
# ... or the models only, from the committed feature table
python scripts/k4_defi_kan.py --seeds 5 --features results/kan/k4_20261024_080035/features.parquet
```

All runs are CPU-only. Each run writes a manifest with the git commit, the
code files that differed from it and a hash of that diff, package versions,
SHA-256 hashes of the inputs and the full configuration. Protocols are
fixed in code ([docs/PROTOCOLS.md](docs/PROTOCOLS.md)); each script's header
states its hypotheses.

## Repository layout

```
src/bal/
  data/       elliptic.py, xchain.py (causal USD), contracts.py, defi.py  loaders + fixed splits
  features/   xchain_features.py (causal), contract_features.py (tokens, patterns, near-duplicates), defi_features.py
  models/     kan.py (B-spline KAN + LUT inference), tabular.py, gnn.py, anomaly.py
  eval/       metrics.py, alarm.py (budget thresholds, loss accounting), labelshift.py, stats.py
  utils/      repro.py (seeds, manifests, atomic writes)
scripts/      00_fetch_data.py, b*_ (bridges), c*_ (contracts), t*_ (transactions), k*_ (KAN, DeFi)
results/      one folder per run: metrics, folds, per-row scores where small, manifest
docs/         PROTOCOLS.md, DATA.md, FINDINGS_*.md, AUDIT_RESPONSE.md
tests/        GNN isolation, near-duplicates, thresholds and ties, loss accounting,
              causal features, label shift, KAN/LUT exactness, solc selection, aggregation
```

## Reviews

Three independent read-only reviews (2026-10-22) found defects in GAT
attention, near-duplicate grouping, threshold and rank ties, compiler
selection, price timing, repeated aggregation and manifest coverage, and
several interpretations stronger than the evidence. All were fixed or
reworded and the affected experiments re-run.
[docs/AUDIT_RESPONSE.md](docs/AUDIT_RESPONSE.md) lists each finding, the fix,
its test and the old → new numbers; [results/README.md](results/README.md)
lists the current and superseded runs.

## Citation

```bibtex
@software{blockchain_detector_eval,
  title  = {blockchain-detector-eval: When Can You Trust a Blockchain
            Anomaly Detector, and What Does It Cost to Run?},
  author = {Kuznetsov, Oleksandr},
  year   = {2026},
  url    = {https://github.com/KuznetsovKarazin/blockchain-detector-eval}
}
```

## References

* Augusto et al. XChainWatcher: Monitoring and identifying attacks in cross-chain bridges. ACM Middleware 2025; arXiv:2410.02029 (data: Ronin, Nomad).
* Durieux et al. (2020). Empirical review of automated analysis tools on 47,587 Ethereum smart contracts. ICSE 2020 (SmartBugs-curated).
* Ghaleb & Pattabiraman (2020). How effective are smart contract analysis tools? Evaluating smart contract static analysis tools using bug injection. ISSTA 2020 (SolidiFI).
* Zheng et al. (2024). DAppSCAN: Building large-scale datasets for smart contract weaknesses in DApp projects. IEEE Transactions on Software Engineering, doi:10.1109/TSE.2024.3383422.
* Feist, Grieco & Groce (2019). Slither: A static analysis framework for smart contracts. WETSEB 2019.
* Weber et al. (2019). Anti-money laundering in Bitcoin: Experimenting with graph convolutional networks for financial forensics. KDD Workshop on Anomaly Detection in Finance (Elliptic).
* Elmougy & Liu (2023). Demystifying fraudulent transactions and illicit nodes in the Bitcoin network for financial forensics. KDD 2023 (Elliptic++).
* Maganti (2026). arXiv:2604.19514. Strict inductive evaluation on Elliptic: RF F1 0.821 vs GraphSAGE 0.689 ± 0.017.
* Li et al. (2023). ECOD: Unsupervised outlier detection using empirical cumulative distribution functions. IEEE Transactions on Knowledge and Data Engineering 35(12).
* Liu et al. (2024). KAN: Kolmogorov–Arnold Networks. arXiv:2404.19756.

## Related

* [lut-kan](https://github.com/KuznetsovKarazin/lut-kan): LUT inference for KANs (the LUT scheme in `bal.models.kan` follows it).
* [lut-kan-ids](https://github.com/KuznetsovKarazin/lut-kan-ids): on-device LUT-KAN intrusion detection.

## License

Code: MIT (`LICENSE`). Results and documentation: CC BY 4.0
(`results/LICENSE`). The datasets are not redistributed and keep their own
terms; [docs/DATA.md](docs/DATA.md) lists each source's licence and what the
result files contain.
