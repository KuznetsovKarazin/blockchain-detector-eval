# Post-review representation controls — 28 October 2026

These private working additions address the representation and masking criticisms of R3. See `REVIEW_FINDINGS_RU.md` for the complete interpretation. They preserve all old run directories and original scientific code.

New findings: on all 21,457 DAppSCAN nodes, project plus exact raw identity gives a 16.82% largest component; a new token-spelling-preserving comment/whitespace control gives 50.90%; the inherited identifier-preserved ordered stream gives 52.07%; normalized nonempty ordered streams give 89.94%. Jaccard=1 on the replay arrays gives 52.07% with preserved identifiers and 89.94% with collapsed identifiers, without implying equivalence between set and ordered-stream definitions.

The new availability-only control explains most of the masking-associated giant reduction: normalized 95.84%→87.28%→87.36% and preserved 87.47%→79.95%→80.05%, for full representation→availability only→actual masking. Every graph retains all vertices and structural edges. The middle-to-final step rewires edges; it is not monotone. This is a fixed-order descriptive decomposition.

## Run records

Each `*_run_20261028_v1` directory is immutable and contains its pre-compute plan, inputs/source hashes, results and memberships. The scripts currently use those exact output directory names and refuse to overwrite them. For a new execution, copy the script and use a new output directory/version before freezing it.

- `run_metadata_controls.py`: retained public metadata; no raw sources required.
- `run_pair_controls.py --archive-root PATH`: the separately identified verified canonical replay edge archives are required; they are not the six lost original NPZ files.
- `run_trivia_control.py`: pinned DAppSCAN source checkout required. It verifies all 21,457 source hashes, preserves token spellings/literals/boundaries and explicitly records scanner failures.
- `verify_controls.py`: independent union-find check, partition refinements and 23 targeted scanner tests.
- `plot_controls.py`: regenerates the PNG/PDF/SVG figure from the saved graph-control CSV.

The graph experiment does not establish a universally correct dependency relation, detector leakage, semantic equivalence, expert vulnerability labels or external performance. Whole-project population prefixes are handled by the parallel graph-mechanism workstream.
