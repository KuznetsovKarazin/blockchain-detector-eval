# Scientific review for Revision 3 — 26 October 2026

The added scientific scope is defensible: a compiler-coverage audit, a finite-population counterexample study, and a separately proved completion-envelope calculation. These are not new externally validated detector scores. A targeted primary-source check found no reason to enlarge the paper into a general survey or claim methodological priority. This is an AI-assisted scientific/computational review, not independent human vulnerability adjudication.

## Literature and claim calibration

`PRIMARY_SOURCES.json` records original URLs, exact short support, access scope and limits. The two added R3 references are appropriate: Yilmaz–Aslam (2008) establishes prior AP estimation from randomly incomplete judgments; HFCN (2023), section 7.2, supplies the precise finite-correction replicate weights. The first paper's online date is 2007 but its journal volume year is 2008. The second is a 2023 report about the 2021 survey wave.

The broader prior context should prevent overstatement, not force additional experiments. Yilmaz–Kanoulas–Aslam (2008) already discusses stratified sampling and infAP intervals. Boyd–Eng–Page (2013) already studies AUCPR interval undercoverage. Neither validates this implementation's weighted AP percentile intervals. Their estimators, score models and sampling procedures must not be treated as interchangeable. The Boyd erratum is a technical correction to the interpolated-area integral on page 455; the corrected author PDF was inspected. Our noninterpolated AP and integer DP do not use that expression.

The exact synthetic counts, including conditional coverage `514/969` and the `455/969` forced miss event, are results of this repository's declared counterexample. Cite the study's own design and verification for them. Earlier literature supplies context, not those numbers. This targeted search cannot establish whether an equivalent completion DP has appeared elsewhere; retaining the explicit absence of a priority claim is appropriate.

## Methodological review

The completion proof is sufficient for its stated target. For a fixed cumulative unknown-positive count, the current tie-group contribution depends only on that count and the current allocation. Later contributions likewise need only the cumulative count. Terminal denominators are fixed within each state, so retaining extreme numerators preserves all global endpoints. Integer scaling avoids floating comparisons; endpoint witnesses demonstrate attainability. The `O(Nm)` statement counts transitions, with integer bit cost explicitly excluded. A possible zero-positive completion remains undefined. The interval between sharp endpoints is an envelope, not necessarily a set in which every interior value is attainable.

Known labels must be treated as correct constraints, all unsampled/unresolved labels must remain unknown, and every declared population item must have a finite score. R3 states these limitations and does not turn failed analyses into low scores. A pairwise envelope made from separate endpoint ranges is generally nonsharp because endpoints can require incompatible label completions. Neither envelope is a confidence interval or a repair of percentile coverage.

One terminology error in the live `ap_bounds_v1/RESULTS.md` was corrected with explicit parent authorization: an estimator and a completion envelope can concern the **same finite-population AP**. They are different inferential objects, not necessarily different estimands. A dated editorial note records the change. Frozen source/configuration snapshots and numerical results were not changed. Old document SHA256: `1d465674d7458a0fc9d2bd45594c7724d86abdf6cb9e788b60ed6b77ee891b89`; corrected SHA256: `3169f6a62d890c92594fefe73c90e0b5f1e5bb2f53f931a869ab591137eb7fbe`.

## Revision 3 checks

The reviewed draft correctly separates:

- the 21,457-file DAppSCAN population from the fixed 6,587-file historical projection;
- the two 1,062-file feasibility tests from the reused 1,082-file model diagnostic;
- graph-retained from informative lexical training, and compilation success from detector success;
- operational screens over 95 proposals from universal split impossibility or a power calculation;
- 180 file/class review cases from 1,998 candidate files, with no completed human assessment or external scoring;
- the synthetic coverage study from actual coverage of that prospective review design.

The new compiler denominators and AP counts are independently recomputed from saved metadata in `CHECKS.json`. The AP proof and countable miss event were reviewed mathematically; this stage did not rerun the full graph audit, compiler, model fitting or bootstrap enumeration. Earlier sealed checks remain the evidence for those computations. There is no new scientific blocker in the reviewed R3 additions.

The manuscript author adopted one clarity edit: “rescaled bootstrap for stratified sampling without replacement”. Its original sampling design is without replacement, but the bootstrap resamples are drawn with replacement. Appendix A already gave the correct construction; this was wording precision, not a calculation error. Final reviewed draft SHA256: `89a6acafb4a0ea941d20f77ba45110ca49f693086046adc07715fe22b9ff068a`.

Only two new references are necessary for the current narrow additions. More citations may be useful if the related-work claims expand, but reference quotas or claims of a comprehensive survey are unwarranted.
