# Input recovery, 26 October 2026

The runtime reset removed ignored raw and derived inputs. They were restored against published checkpoint `e011968b4d92f407cc515993ef91441444c9fee0`; frozen public run outputs and input hashes were not changed by this recovery. The committed configurations and inventories, rather than remembered counts, were the comparison authority.

## Recovered pinned repositories

All four working trees are clean and have the exact frozen commits. Pins for the three historical corpora are in `scripts/00_fetch_data.py` and the frozen representation configuration; the candidate pin/URL are also in `protocol.json`.

| Directory under `data/raw/` | Repository | Commit | Git tree |
|---|---|---|---|
| DAppSCAN | InPlusLab/DAppSCAN | `66a56619c44770e05c2db600fa6468115ff0dcd5` | `33a3e34dc846db1e4fb8de3d83e58480c1cfd920` |
| smartbugs-curated | smartbugs/smartbugs-curated | `230e649123477eff332742a59a1c7cc6dc286cab` | `ed3f7899860529313ceabd745a36b1445b2d3d0f` |
| SolidiFI-benchmark | DependableSystemsLab/SolidiFI-benchmark | `4b0573e1b3f7031396de6f48f7f3e7380222ad3a` | `a5e5fd4c1846155b40910cfef68c0b98e1fddfab` |
| salzano | fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts | `da079440bf2cf4fd803c864ef29aeea8a3da50c3` | `6c0d44ef03847129939d14cc612fdfc036cb30fc` |

Recovery used the existing `fetch()` implementation in `scripts/00_fetch_data.py`: initialize missing repository, depth-one fetch of the exact commit, checkout `FETCH_HEAD`, then require a clean pinned state. The historical sources may equivalently be restored with:

```bash
python scripts/00_fetch_data.py --only smartbugs-curated SolidiFI-benchmark DAppSCAN
python -c 'import runpy; m=runpy.run_path("scripts/00_fetch_data.py"); m["fetch"]("salzano","fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts","da079440bf2cf4fd803c864ef29aeea8a3da50c3")'
```

## Verified source identity and ordering

`verify_recovered_inputs.py` passed on the restored tree. Its machine-readable receipt is `INPUT_VERIFICATION.json`.

- Every one of the **24,131** raw source SHA256 values and byte lengths equals the frozen corrected dependency node inventory; total source bytes are 136,309,005.
- All **21,950** upstream rows from the unchanged uncapped loader have exactly the same path, dataset and project ordering as the upstream portion of the frozen node table. The 2,181 external source rows also match the original metadata ordering and identity fields.
- All **7,080** historical rows, including **6,587** DAppSCAN rows, match the frozen pilot inventory in file ID, path, dataset, project and raw source hash. The historical node flags and 1,998 diagnostic candidate flags are unchanged.
- All **949** historical annotation input file hashes and their manifest ordering match the frozen annotation manifest.
- The committed loader SHA256 is `4ea6ad2685e2124a0377a30fad61ffa8918cb14c968a8e65e0f010502f22597a`, identical to the frozen representation configuration.

Hashes of exact newline-delimited path order are `21e41b116b3d779f962e8a197a98f8ca89732a1fe72cc473cc6338aa70d41bff` for the full upstream ordering and `a15240586af6d9fa37fdb2590aa4792d840ae3180d3a9d260f96887e2215b856` for historical ordering. These are explicitly recorded recovery checks, not substituted hashes for existing manifests.

The original corrected dependency inputs remain:

| Input | SHA256 |
|---|---|
| `dependency_audit/string_aware_recovered_20261025/nodes.csv` | `e3add177b983b4c7455912640100839a8da50458dfb59546fc492ba4a0081cb0` |
| `dependency_audit/string_aware_recovered_20261025/edges.csv` | `847882e8b09c6bc2bdf53df0a37b5f1f5d8027d3ed71c652a5a0e84efc620237` |
| Historical pilot `source_inventory.csv` | `26d23cc683ebfd9cd983d6348e98a048a26c5bcff21b27a2797938c6c30e26da` |
| Representation `training_label_input_hashes.json` | `6ab252ba5ebf9cb364bbe56cdc1fdacd73dfc1a5c3135859faaac465d4d4a418` |

## Recovered private annotation manifest

`recover_private_manifest.py` executes the literal committed AST statements of `audit_external_sources.py` through source/label parsing and stops before `train = load_all(...)`. It does not run pairwise similarity, graph construction, review selection, fitting or scoring. It retains the committed source-directory insertion order, sorted source paths, annotation reconciliation precedence, class order and CSV writer settings. Recovery staging is under ignored `data/derived/recovery_20261026/source_prefix/`; the script refuses to overwrite that existing staging directory.

The resulting 4,362-row `provisional_label_manifest.csv` has exact expected SHA256:

`72fceb79cacca51253eabdb7e3ed26a54e7863f4b5be4430071ef9b14d5d0236`

Identical bytes were restored to both required ignored paths:

- `data/derived/security_external_full_20261025/provisional_label_manifest.csv`
- `data/derived/security_external_recovered_20261025/provisional_label_manifest.csv`

The source annotation CSV hash is `b9e17c5e88188f518491d381b4a2991b5809e8b356e7e861c50e33420d362fb6`. The executed committed audit script hash is `bc0339047d5a87fe36cd046a9cd64c6ad2c1ac0ca78f0fe37e1d4cedfbb0d772`. All 2,181 candidate path/source/raw-hash/normalized-hash/reconciliation records match the frozen source metadata. `PRIVATE_MANIFEST_RECOVERY.json` records the checks without copying private labels into public outputs.

The separate probability-review private packet and representation caches are recovered by their owning tasks. This receipt does not certify them. In particular, equality of decompressed normalized streams is not automatically equality of gzip bytes, whose historical header timestamps must also match if a frozen compressed hash is required. No frozen hash should be replaced to accommodate a different serialization.

Verification can be repeated from the repository root with:

```bash
python papers/security_evaluation/revision1/recovery_20261026/verify_recovered_inputs.py
```

No package installations were needed. This input-recovery task ran no model, external detector or dependency-graph computation, published nothing, and changed no external eligibility or scoring gate.
