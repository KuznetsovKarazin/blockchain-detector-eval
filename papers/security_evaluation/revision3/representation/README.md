# R5 fixed-informative-denominator verification

This work adds a denominator audit to R4 without modifying R4 files or rerunning lexical graphs. All computations are local; no Git or public-service mutation is performed.

`verify_informative_denominators.py` independently reads immutable node metadata and all saved component memberships, verifies identical node/file identities, derives the same 15,399-file informative set under both masking conventions, and recomputes every projected component count. Twelve projections (two policies × two conventions × three controls) reproduce all R4 counts. Every row has the same unique largest component under the all-DAppSCAN and common-informative projections. Counter grouping agrees with separate Boolean accumulation. The source and every input hash are fixed before calculation and rechecked afterward.

- `informative_denominator_v1/main_table_denominators.csv`: exact six main-table rows, with numerator, denominator, unrounded fractions and unavailable-vertex counts.
- `informative_denominator_v1/all_policy_denominators.csv`: all twelve rows.
- `informative_denominator_v1/common_informative_node_ids.csv`: the fixed denominator set.
- `informative_denominator_v1/PLAN_BEFORE_COMPUTE.json` and `CHECKS.json`: definitions, source/input/output hashes and verification outcomes.
- `verify_structural_baselines.py` and `structural_baselines_v1/`: separately frozen project-only, project-plus-identity and address-expanded structural baselines. Pure project maxima are independently checked from project identities.
- `ENGLISH_INSERTIONS.md`: ready-to-use methods/results text and one compact table.

The common-informative denominator is used even for the full-file control, whose own full-file informative set is larger (21,451 files). This prevents a changing node filter across the three controls. All graph vertices and connecting paths remain present; these results are not induced-subgraph results and do not establish detector accuracy or semantic independence.

Completed run directories are immutable and the scripts refuse to overwrite them. A repeat should receive a new output directory name before its plan is generated. The computations require the retained R4 metadata/memberships, not original source files or model fits.
