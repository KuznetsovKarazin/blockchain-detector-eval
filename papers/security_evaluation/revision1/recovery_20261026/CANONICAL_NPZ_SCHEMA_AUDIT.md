# Independent canonical NPZ schema/content audit

**PASS — 26 October 2026.** A separate read-only auditor checked all six canonical archives, all 24 arrays, all 4,621,780 edge rows and all 6,357,241 archive bytes. The auditor does not import the packaging or graph-generation functions.

Every archive contains exactly `left`, `right`, `intersection` and `node_shingle_sizes`, each a one-dimensional little-endian `int32` NumPy array. Loading with `allow_pickle=False` agrees with an independent explicit NPY-header/raw-byte decoder. There are no object/string arrays, extra entries, comments, extra fields, unexplained gaps, trailing data or unused compressed payloads. The complete ZIP local headers, central directory and end record were also checked.

For every edge, endpoint bounds, nonnegativity, `left < right`, aligned lengths, strictly increasing unique node pairs, positive intersections, `intersection <= min(size_left,size_right)` and containment at least 0.7 all hold. Each node-size vector has exactly 24,131 elements. A binary-search bijection independently confirms every complete edge row and node size against the fresh replay; it does not reuse the packager's sorting permutation.

Archive, per-array, canonical-content, configuration, source-code, receipt and surviving-result lineage hashes passed. The audited package manifest SHA256 is:

`662b91e95bf21a78a6652c32386305d4af3b1ec1e2283ba721ffed71cc2b8756`

The decoded payload consists only of derived integer graph records and fixed ZIP/NPY schema metadata. It contains no source-body, private-key, label, score or arbitrary-text fields or entries. The established lineage retains all 120 reported partitions and 20 result CSVs.

The six historical NPZ files remain absent. This audit establishes the schema and contents of the **new computational reproductions**, including equality to their fresh replay; it cannot establish full unordered edge-list identity with the lost historical originals. It is automated code/content verification, not human vulnerability adjudication or permission to publish.

Reproducible auditor: `audit_canonical_representation_arrays.py`. Full results, bounds and array hashes: `CANONICAL_NPZ_SCHEMA_AUDIT.json`. Existing receipts are protected from overwrite. No upload, publication, commit, model fitting or new human judgment was performed.
