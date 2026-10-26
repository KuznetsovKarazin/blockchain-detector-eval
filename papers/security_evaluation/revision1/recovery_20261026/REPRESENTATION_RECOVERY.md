# Representation artifact recovery, 26 October 2026

Completed locally without fitting models, computing new detector scores, changing historical scientific definitions, uploading or publishing. Six missing membership archives were restored **byte-for-byte**; six missing lexical-edge archives were **recomputed separately, not restored as their historical bytes**.

## Inputs and execution

`recover_representation_artifacts.py` called the unchanged primary and segmented preprocessing/graph functions. Every current scientific source and executed-source snapshot matched its frozen SHA256. The original node/edge inputs, four clean upstream commit pins, historical annotation input hashes, and recorded Python 3.12.14 / NumPy 2.3.5 / pandas 2.2.3 / SciPy 1.17.0 environment matched. The independent `INPUT_VERIFICATION.json` additionally verifies all 24,131 raw-file hashes and byte lengths.

New computation outputs are under `data/derived/representation_recovery_20261026_v1/`, an ignored directory. Its `recovery_config_before_compute.json` records the wrapper/source/input hashes before computation and the only runtime adaptations: fresh output/cache paths, a fresh primary parent directory for the segmented control, and explicit `PYTHONHASHSEED=0`. The original run did not record its hash seed. Original configurations, manifests, timings, summaries and surviving results were not rewritten.

## Exact restorations and separate recomputations

Each membership gzip was generated anew, then its header timestamp was searched only within the original manifest's execution interval. A candidate was restored to its missing historical path only when its **entire SHA256 and Git blob SHA1 both matched** the independently recorded original values. Decompressed contents were also checked unchanged by the header reconstruction. This is documented reconstruction of historical bytes, not a claim that the new computation occurred at the historical time.

| Representation | Saved lexical pairs in new archive | Membership archive | Historical lexical archive |
| --- | ---: | --- | --- |
| corrected_file_normalized | 2,039,310 | Exact, restored | Hash differs; missing original not replaced |
| corrected_file_preserved | 278,628 | Exact, restored | Hash differs; missing original not replaced |
| library_interface_masked_normalized | 1,021,065 | Exact, restored | Hash differs; missing original not replaced |
| library_interface_masked_preserved | 158,076 | Exact, restored | Hash differs; missing original not replaced |
| library_interface_segmented_normalized | 966,320 | Exact, restored | Hash differs; missing original not replaced |
| library_interface_segmented_preserved | 158,381 | Exact, restored | Hash differs; missing original not replaced |

The pair universe is the original saved candidate universe with containment at least 0.7, not the count of Jaccard edges at 0.8. Full original/actual SHA256 values, Git blob identities, header timestamps, restoration decisions and fresh canonical graph digests are in `REPRESENTATION_RECOVERY.json`. Fresh arrays are in the `primary/<representation>/lexical_edges.npz` and `segmented/<representation>/lexical_edges.npz` subdirectories of the new recovery directory.

All **120 reported component partitions** are recovered through the six exact membership archives. All **20 surviving result CSVs**—threshold edge counts, component concentrations, training feasibility and segmented edge changes—match byte-for-byte. Primary representation metadata and coverage, segmented boundary diagnostics, node identities and structural edges also match their surviving originals.

Unrecorded iteration over Python sets can change edge-row order and hence archive bytes. It has not been isolated as the actual cause of these differences: the original arrays no longer exist locally for a direct content comparison. Matching partitions, counts and other summaries does **not** prove identity of the complete original edge lists. The six regenerated arrays remain separate artifacts with their own hashes; none is labelled an exact historical recovery.

## Reviewable canonical replacement package

The six new edge arrays are also available under `representation_edges_v1/<representation>/lexical_edges.npz`, prepared for repository inclusion at new paths. `package_representation_edges.py` sorts complete edge rows by node pair without changing their contents, preserves the node-size vector, rejects duplicates, writes deterministic numeric-only ZIP/NPY archives and checks full unordered-row identity against the fresh replay. The original missing NPZ paths remain absent.

`representation_edges_v1/manifest.json` records original lost hashes, fresh replay hashes, new canonical archive/array hashes and the exact partition/table lineage. All six arrays passed full equality checks before and after serialization; the independent predicate checks therefore carry over to their sorted counterparts. This is a **new independently verified computational reproduction**, with the same limitation about unestablished original full unordered edge identity. Packaging did not upload or publish the files.

## Independent checks of the new arrays

`verify_representation_recovery.py` ran both unchanged original independent verification scripts. Explicitly labelled post-result views supplied adapted private paths; their legacy `config_before_outputs.json` filenames are verifier interface requirements, not a new claim of prospective freezing. The original files were not edited.

`REPRESENTATION_INDEPENDENT_CHECK.json` records **PASS** for all six variants:

- 12 primary graphs independently reconstructed with union-find, two per representation;
- 600 sampled edge intersections checked using literal token tuples, including an independent flattened-token/segment-ID construction for the segmented variants;
- edge endpoints, informative-node coverage, threshold refinement and all saved threshold edge counts checked;
- the corrected full-file baseline reproduced all 133,859 nonempty baseline lexical edges at Jaccard 0.7 and omitted precisely the previously documented 15 empty–empty edges;
- the existing empty-policy difference from the earlier dependency baseline remains explicit; it was not erased by recovery.

These checks validate the newly recomputed graph calculations and their agreement with the surviving reported results. They do not supply human vulnerability adjudication, semantic family independence, new external performance, or the missing original full-array identity.

Separately, `INDEPENDENT_SAMPLING_VERIFICATION.json` records another successful check of all 360 AP values and 1,080 tie-aware workload values against preserved predictions and independently joined source annotations. All 1,800 model-result files match the public clone's Git index. No fits were executed.

Reproduction commands (each requires a new output directory; existing receipts are preserved):

```bash
PYTHONHASHSEED=0 python papers/security_evaluation/revision1/recovery_20261026/recover_representation_artifacts.py data/derived/representation_recovery_NEW
python papers/security_evaluation/revision1/recovery_20261026/verify_representation_recovery.py data/derived/representation_recovery_NEW
```

The independent verifier deliberately refuses to overwrite its published receipt; choose a new receipt destination in a separately versioned verifier for an additional audit.
