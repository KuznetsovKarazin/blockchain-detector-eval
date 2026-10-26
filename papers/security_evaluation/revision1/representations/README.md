# Alternative lexical dependency representations

This is an **unscored sensitivity analysis**, not a new claim of semantic or family independence. All 24,131 source records and all existing project, raw-byte identity, candidate-identifier and optional address links remain in every graph. Masking changes lexical edges and representation availability; it never removes structural nodes or project dependencies. No models were fitted or external labels read in these runs.

The four original representations were frozen before outputs in `run_20261025_v1/config_before_outputs.json` (SHA256 `8f29bf5dd4565941fa5ca9aa9c12184a2bd013d22cd3ff5cf23d5d8ad4a83bcb`). After an implementation review identified adjacency introduced by deleting declarations, two additional segmented-mask controls were separately frozen before their outputs in `segmented_control_20261025_v1/config_before_outputs.json` (SHA256 `fbed56eda0aed66001332f71f7bc44e8418ba81ad14f88b018f0744268f1dc2a`). This additional control is **post hoc, not preregistered**. The original four outputs are preserved.

## Definitions and scope

The original variants are corrected full-file normalization, corrected full-file tokenization with identifiers and numbers preserved, top-level library/interface masking with normalization, and masking with identifiers and numbers preserved. Normalization retains the historical token regex and identifier/numeric collapse; preserving identifiers/numbers disables that collapse but retains the same lexical token regex. It does not retain full literal semantics or imply semantic equivalence.

Comment handling uses the previously frozen string-aware scanner, without changing the historical normalizer. Mask extraction uses a separate balanced lexical scanner with quoted literals treated atomically, escaped quotes respected, and comment text blanked. It recognizes top-level `contract`, `library` and `interface` declaration spans. Only `library` and `interface` spans are masked; retained free functions or other top-level constructs are not classified as application code. Imports and pragmas remain in an informative stream, but directive-only residue does not count as informative. This is structural lexical extraction, **not compiler AST parsing, compilation validation, verified library provenance or vulnerability localization**. Contract/function-unit graph representations were not implemented.

Each informative stream produces a set of five-token shingles, hashed with BLAKE2b-128. Nonempty files shorter than five tokens have one short window. Empty or unavailable streams have no lexical edges. All pairs with nonzero overlap are evaluated by sparse matrix multiplication, without LSH or candidate truncation. The saved pairs include every pair with containment at least 0.70, which includes every Jaccard pair at the evaluated thresholds 0.70, 0.80, 0.90, 0.95 and 0.99. Hash collisions are theoretically possible; sampled literal-window checks verify the saved intersections without relying on those hashes.

Jaccard is intersection divided by union. Undirected containment is intersection divided by the smaller shingle-set size, the maximum of the two directed inclusions. It therefore adds or retains links relative to Jaccard at the same threshold; it is not a mechanism for manufacturing fragmented graphs.

All graph results use the full combined 24,131-node population: 21,457 DAppSCAN, 350 SolidiFI, 143 SmartBugs reference and 2,181 external source records. Population-specific component counts are **projections of these full-graph memberships**, not recomputed induced-subgraph components. Training exclusions remove historical training nodes connected, including transitively, to any of the fixed 1,998 diagnostic candidate nodes. Both original base and address-expanded structural policies are exported. Address-expanded links conservatively connect syntactically valid same-address identifiers without verified network identity.

## Coverage and explicit unavailable representations

Full-file variants are informative for 24,125/24,131 records. Six DAppSCAN files have empty token streams. Masked and segmented variants are informative for 18,070/24,131 records, including 15,399/21,457 DAppSCAN files and 1,995/1,998 diagnostic candidate files. Of the 6,061 unavailable masked records, 6,060 have directive-only or no residual code, including the original six empty files; one fails structural scanning. Thus these records must not all be described as verified pure libraries.

The sole scan error is node 7119, `data/raw/DAppSCAN/DAppSCAN-source/contracts/Hacken-Hedgey Finance-V1/treasury_pools_core-7eb9dc8de364a1ab3b53ba0ad3194f380c03e94b/HedgeyAnySwap.sol`, with an unmatched closing brace at character 261. Its full-file representations remain available; masked representations fail closed with no partial masking or fallback. Its node and structural links remain present. Source pointers and hashes, not copied third-party source text, are published in `representation_metadata.csv`.

**Baseline amendment:** older graph construction represented the six empty streams with a shared empty shingle. The new explicitly frozen no-empty-edge policy removes their 15 pairwise lexical links. Nonempty corrected full-file Jaccard edges are identical to the preceding corrected audit. At Jaccard 0.80, address-expanded historical DAppSCAN graph retention changes from 691 to 712, of which 711 are informative. This change is an empty-representation policy sensitivity and must not be attributed to masking or identifier preservation.

## Main descriptive comparison

Jaccard 0.80, address-expanded full combined graph. The giant column counts DAppSCAN nodes in the largest projected component, out of 21,457. Training starts with the same 6,587 historical DAppSCAN files. Proxy-positive counts are among **informative retained** training files, not all graph-retained files. They are metadata aggregates, not adjudicated vulnerability labels.

| Representation | DAppSCAN giant | Graph-retained training | Informative retained | Reentrancy proxy positives | Unchecked proxy positives |
|---|---:|---:|---:|---:|---:|
| Full normalized | 20,565 (95.84%) | 712 | 711 | 23 | 18 |
| Full identifiers/numbers preserved | 18,769 (87.47%) | 1,504 | 1,502 | 37 | 29 |
| Concatenated mask, normalized | 18,745 (87.36%) | 1,520 | 1,086 | 36 | 25 |
| Concatenated mask, preserved | 17,177 (80.05%) | 2,150 | 1,539 | 49 | 36 |
| Segmented mask, normalized | 18,745 (87.36%) | 1,520 | 1,086 | 36 | 25 |
| Segmented mask, preserved | 17,177 (80.05%) | 2,150 | 1,539 | 49 | 36 |

Preserving identifiers/numbers and masking declared library/interface spans reduce concentration under these definitions, but a large component remains. This does not validate any variant as the correct independence relation or establish a viable inferential sample. The effect of masking is also inseparable from lost representation coverage unless graph-retained and informative-retained counts are reported separately.

Containment at 0.80 is substantially more restrictive: full normalized/preserved variants retain only 3/411 informative historical DAppSCAN training files. Concatenated masked normalized/preserved variants retain 22/739, and segmented controls retain 41/740. Containment therefore does not resolve the observed concentration.

## Boundary-window control

Deleting an intervening declaration concatenates originally nonadjacent retained token regions. The original masked definitions include those new adjacency windows. The segmented control keeps only original concatenated-stream windows whose tokens all belong to one retained segment. It does not create short shingles for each small segment. For a whole file shorter than five tokens, the original short window survives only if all tokens belong to one segment. The surviving shingle set is a subset of the concatenated set; Jaccard can nevertheless increase because its denominator can shrink, so pair comparisons were recomputed exhaustively.

There are 2,191 files with a total of 11,128 boundary-spanning window occurrences in each mask variant. Removing boundary-only unique shingles affects 2,070 normalized files and 2,191 preserved files, with 8,428 and 9,859 unique-shingle removals summed per file, respectively. No additional files become unavailable: informative coverage remains 18,070.

At Jaccard 0.80, segmentation adds 16 and removes 76 normalized lexical edges; for preserved tokens it adds 114 and removes 3. The giant and training aggregates in the table are unchanged, but **the component partitions are not identical**: normalized full-graph component count changes from 1,403 to 1,407; preserved count remains 1,570 with membership changes. At all evaluated thresholds the full partitions change, so unchanged aggregate values must not be presented as identical graphs or universal robustness.

Containment 0.80 changes more: normalized lexical edges change by +918/−31,835, the DAppSCAN giant shrinks from 21,430 to 21,411, and informative retained training changes 22→41 with proxy positives (1,1)→(3,4). Preserved edges change +475/−251, the giant shrinks 19,336→19,335, and informative retained training changes 739→740 with positives (19,26)→(20,26). Full threshold-specific comparisons are exported.

## Validity limits

A detector that still sees masked library/interface code cannot be declared independent merely because the grouping representation ignores that code. Any later detector comparison must explicitly align the evaluated representation and target scope, or explain the mismatch. File-level labels can refer to removed code, and this analysis does not resolve that localization problem. Project and identity rules are conservative operational definitions, not verified latent families. Lower lexical similarity after identifier preservation may miss renamed reuse. Raw-identity links and project dependencies remain regardless of representation availability.

The 1,998 candidate files remain diagnostic and unscored here; only 1,995 have informative masked content. No external readiness approval, new blind test or statistical-power claim follows from these results.

## Verification and artifacts

Eighteen scanner/masking/segmentation tests pass. `verify_representations.py` checks all 80 original graph connectivity/refinement conditions, independently reconstructs eight primary graphs with Python union-find and checks 400 literal shingle intersections. `verify_segmented_control.py` checks all 40 control graphs, independently reconstructs four primary graphs, and checks 200 literal segmented intersections using flattened tokens plus segment IDs. Both verify unavailable nodes have no lexical edges. A separate reviewer also checked frozen hashes, all node/structural identities, output hashes and 80 changed-file segmented-window reconstructions. Verification establishes implementation consistency, not semantic independence.

- `primary_comparison.csv`: the six variants for both metrics at 0.80, address-expanded.
- `all_threshold_comparison.csv`: both metrics, both policies and all five thresholds.
- `comparison_provenance.json`: hashes of table-generating script, inputs and outputs.
- `run_20261025_v1/`: frozen config, executed code snapshots, coverage, metadata, complete lexical pair arrays, graph memberships and aggregate feasibility.
- `segmented_control_20261025_v1/`: separate frozen config/snapshots, complete control outputs, per-file boundary diagnostics, boundary summary and partition/edge changes.
- Both run folders contain `independent_verification.json`; the control verification also records hashes of common outputs absent from its original top-level manifest.

Normalized source/segment caches remain private under ignored `data/derived/`; tracked outputs contain metadata, hashes, graph memberships and aggregates, not raw or normalized third-party source. The runs took approximately 460 seconds (original four) and 204 seconds (two controls) on this runtime. Existing completed directories are immutable run records; reproductions must use fresh output and cache paths.

From the repository root, verification and table regeneration are:

```bash
python -m pytest -q papers/security_evaluation/revision1/representations/test_representations.py
python papers/security_evaluation/revision1/representations/verify_representations.py --run papers/security_evaluation/revision1/representations/run_20261025_v1
python papers/security_evaluation/revision1/representations/verify_segmented_control.py --run papers/security_evaluation/revision1/representations/segmented_control_20261025_v1
python papers/security_evaluation/revision1/representations/summarize_comparison.py
```

`run_representations.py prepare` and `run_segmented_control.py prepare` freeze configurations and executed code before their respective `run` commands. The control additionally pins the original config, metadata and private stream-cache hashes. Source repository revisions and original population hashes are retained in the original frozen config and underlying dependency audit.
