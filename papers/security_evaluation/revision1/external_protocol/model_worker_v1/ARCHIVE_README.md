# Public synthetic state archive

`synthetic_model_states_20261026.zip` preserves all 152 serialized states from the two wholly fictional verification runs. No real corpus training source or annotation was used for these models. `SYNTHETIC_STATE_ARCHIVE.json` lists every relative path, byte length and SHA256. The ZIP was round-trip verified against all entries before publication.

For exact resume verification of the recorded fictional runs, extract the archive into this directory, preserving paths. The individual `.joblib` files are kept locally and are distributed in this archive rather than duplicated as separate Git blobs. Source snapshots, scores, feature matrices, timings, configurations, verification receipts and artifact manifests remain ordinary files beside their original paths. The archive's SHA256 is `2b8ad71d5e5e20e94816d375166f40417635ed5ffb3369eb128dbbbbae47ae82`.

This archive is unrelated to the older graph recovery artifacts whose public upload remains blocked. It contains only newly generated fictional verification states.
