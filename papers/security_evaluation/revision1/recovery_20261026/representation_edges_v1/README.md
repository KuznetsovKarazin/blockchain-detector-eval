# Canonical representation-edge reproductions

These six archives are **new independently verified computational reproductions**. They are separately identified replacements for use with the preserved component and result tables; they are not the lost historical NPZ bytes. The historical archive paths remain absent. Original complete unordered edge-list identity cannot be proved from the surviving artifacts.

The unchanged frozen scientific code was rerun from verified source inputs. All 120 reported partitions and 20 surviving result CSVs match the historical results. The independent checks reconstructed 12 primary graphs with union-find and checked 600 literal-shingle pair intersections, alongside coverage, endpoints and threshold refinement. See `../REPRESENTATION_RECOVERY.md`, `../REPRESENTATION_RECOVERY.json` and `../REPRESENTATION_INDEPENDENT_CHECK.json`.

`../package_representation_edges.py` only sorts the fresh edge rows by `(left,right)` and applies exactly the same permutation to `left`, `right` and `intersection`. It leaves `node_shingle_sizes` in node-ID order. Every complete unordered row and every node size was checked for exact equality with the fresh replay before and after archive serialization. Duplicate pairs are forbidden. No scientific predicate, threshold or score was changed.

Each `lexical_edges.npz` contains exactly four one-dimensional numeric arrays, all little-endian `int32`, with no pickle/object data:

| Array | Meaning | Length |
| --- | --- | --- |
| `left` | Smaller endpoint node ID | Number of saved pairs |
| `right` | Larger endpoint node ID | Number of saved pairs |
| `intersection` | Shared shingle count | Number of saved pairs |
| `node_shingle_sizes` | Shingle set size at each node ID | 24,131 |

Rows are strictly increasing by `left * 24131 + right`. Saved pairs satisfy the original candidate predicate, containment at least 0.7. Use the original frozen threshold and structural-edge rules to obtain the reported graphs; these archives alone are not the complete structural-plus-lexical graph.

`manifest.json` records every original lost archive SHA256/Git identity, fresh replay SHA256, new canonical archive SHA256, canonical array-content digest, per-array shape/digest, and the unchanged partition/table lineage. ZIP entries use fixed order, timestamp 1980-01-01, empty extra/comment fields, and deflate level 9; identical archive encoding was checked twice. The package contains 6,357,241 archive bytes in total.

The artifacts are prepared locally for review. This packaging step performs no upload, publication, Git mutation, model fitting, new detector scoring or human adjudication.
