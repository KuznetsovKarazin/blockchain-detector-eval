# Revision 3 manuscript changes — 26 October 2026

New manuscript: [DRAFT_REVISION3.md](../../manuscript/DRAFT_REVISION3.md).
Revision 2 is preserved unchanged, SHA-256
`9b29d820a8f20a1ad6fd7bfece0b9fe322322680a1b25d023773f7804daa08ce`.
Final Revision 3 Markdown SHA-256:
`89a6acafb4a0ea941d20f77ba45110ca49f693086046adc07715fe22b9ff068a`.

The main contribution remains population-dependent graph projection and
training eligibility, with conditional historical model variability. No
external detector performance or completed human reference review is added.

## Changes

- Sections 3.6 and 4.4 add the completed compiler-only check under its fixed
  source-context and version-selection policy: 2,137/2,689 fixed files,
  comprising 1,807/1,998 external and 330/691 training successes. Attempted-file
  denominators are reported separately. Input limitations and compiler errors
  remain in the cohorts. The 101 successful training files without nonempty
  root bytecode and unlinked-bytecode cases prevent interpreting compilation
  as deployability, Slither coverage or semantic validation.
- Section 3.7, the discussion and a distinct validity paragraph separate
  probability-sampling uncertainty from AP completion bounds. Appendix A
  reports the 59 prespecified synthetic scenarios and 795,934 sample states,
  including 53.04% and 22.22% conditional coverage counterexamples for the
  tested nominal 95% percentile procedure. These do not estimate coverage for
  the proposed external review or invalidate every bootstrap method.
- Appendix A defines the tie-group dynamic program, sufficient state, exact
  integer scaling and attaining completions. Its 27,993 partial-label cases
  and 149,796 binary completions verify an exact logical envelope, not a
  confidence interval or independently verified vulnerability truth. A
  possible all-negative completion remains undefined. The complete proof and
  synthetic artifacts are linked; no priority claim is made.
- Two verified primary references are added in first-citation order:
  Yilmaz–Aslam (2008), incomplete-judgment AP estimation, and HFCN (2023),
  finite-population rescaled weights. Neither is cited as an AP coverage
  theorem or proof of the completion-bound implementation.

## Checks and scope

The manuscript has **five unchanged tables, six unchanged figures, nineteen
references and six keywords**. The abstract has 237 words. Numbered citations
follow first appearance; the original seventeen reference entries are
unchanged. Figure/table numbering and local artifact links were checked.
The AI-methods cross-reference now points to Section 3.8.

Both data-availability paragraphs are byte-identical to Revision 2: compressed
outputs remain absent from the public checkpoint; six original edge-archive
byte hashes and original full-edge-list identity remain unrecovered. No full
public reproducibility claim is introduced.

Scientific evidence is the [compiler review](../recovery_20261026/COMPILER_EXECUTION_INDEPENDENT_REVIEW.md),
[interval diagnostic](../external_protocol/performance_validation_v1/REPORT.md)
and [completion-bound validation](../external_protocol/ap_bounds_v1/RESULTS.md).
No protocol, execution gate, historical result, Word file or public repository
was changed by this manuscript edit. Word layout and final author review are
separate subsequent steps.

An additional [scientific review](../recovery_20261026/scientific_review_stage3/REVIEW.md)
checked the new primary references, compiler denominators, AP counts and
interpretation. Its sole wording clarification distinguishes the original
without-replacement sample design from with-replacement bootstrap draws and
is incorporated. This is software/mathematical review with AI assistance, not
independent human assessment of vulnerability cases.
