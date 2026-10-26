# Sampling membership recovery — 2026-10-26

Both missing `memberships.csv.gz` files were reconstructed **byte-for-byte** from their preserved frozen configurations and restored only after matching both the public Git blob identity supplied for recovery and the SHA256 in each original run manifest. No model was fitted, no prediction was regenerated, and no frozen executable source, configuration, manifest or metric was changed.

Recovered paths:

- `papers/security_evaluation/revision1/sampling_variance/run_20261025_v1/memberships.csv.gz`
- `papers/security_evaluation/revision1/sampling_variance/run_20261025_v2/memberships.csv.gz`

The two recovered files are identical:

| Check | Result |
|---|---|
| Bytes per gzip file | 274,671 |
| Public Git blob SHA1 | `e49ac7d9bdb79946ff772c4d5fe3bdd57cd53f44` |
| Frozen gzip SHA256 | `f6e79ecb693ced2d0a4f4b627bc919f19f84dd17b384ecfc9d0ef73e7edd4786` |
| Uncompressed CSV SHA256 | `33aae9f14bb18a58c063496d30db21dd0fd24260a1cdfdb8d661e19c4d2157fb` |
| CSV rows | 95,402: 94,320 training rows plus 1,082 common-test rows |
| Training cells | 20 draws × four regimes, 1,179 IDs per cell |

The reconstruction follows the row order in the frozen `prepare` source: select the `training_draw` jobs for `raw_tfidf_lr`, emit their training IDs in the saved order, then append the common T once with draw −1. Every job's T was checked for equality, and each training cell was checked for unique IDs and no exact train/test intersection. There was no label-based reselection or new sampling.

Python 3.12.14 and pandas 2.2.3 reproduced the original `to_csv(..., index=False, compression={"method": "gzip", "mtime": 0})` output. The staging file retained the basename `memberships.csv.gz`, which also preserves the gzip filename header. No original creation timestamp was needed. Differing candidates would have remained outside the repository; restoration uses exclusive creation and cannot overwrite a differing existing file.

Reproduction command, from the repository root:

```sh
python papers/security_evaluation/revision1/recovery_20261026/recover_sampling_memberships.py
```

The executed recovery record is [SAMPLING_RECOVERY.json](SAMPLING_RECOVERY.json). The script does not import any model or execution module. A repeated invocation recognizes already-identical files and does not alter their bytes.

## Preserved results verification

Read-only checks against the local public-recovery checkout at `e011968b4d92f407cc515993ef91441444c9fee0` passed:

- All **360 prediction files** and **360 result manifests** remain present.
- All **1,800 fit files** match the hashes saved in `resume_before.json` and their Git blob identities in the public-recovery checkout's index.
- All **1,440 artifacts** listed by the 360 per-fit result manifests match their recorded SHA256 hashes.
- All **seven summary files** match the completed run manifest.
- Every source in the executed run's frozen source list matches both the current source and its original snapshot.

Details are in [SAMPLING_RESULTS_VERIFICATION.json](SAMPLING_RESULTS_VERIFICATION.json). These are file-integrity checks, not a model rerun or a new evaluation. Independent review was asked to repeat the prediction/result verification after its parallel recovery work.

The original run meanings remain unchanged: v1 is an unused preparation with no scores; v2 is the completed conditional historical-pilot diagnostic with 360 logical evaluations and 282 original physical fits. Its fingerprint remains `d0b63a12a2ca839743e682b71a33ac138dd6a4d5feee7072c1f203d937652204`. All 360 predictions belong to the already-used historical T. This recovery performs zero new fits, zero external evaluations, and no changes to the blocked comparative/external gates. No external upload or commit was performed.
