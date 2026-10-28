# Synthetic validation result — 26 October 2026

The current exact implementation passed the separately frozen
[v2 run](run_20261026_v2/results.json). No empirical model scores, target sources,
expert responses or survey weights were used. This is algorithm validation,
not external detector evaluation or confidence-interval calibration.

- **27,993 partial-label cases**: every ordered score-tie composition and every
  `0/1/unknown` vector for `N=1..6`.
- **149,796 binary completions**, including **147,066 positive completions**:
  an independent exact threshold formula matched every fixed-total and global
  endpoint; reconstructed endpoint witnesses preserved all known labels and
  attained their bounds. All-negative possibilities were kept undefined.
- **2,667 sklearn comparisons** on complete positive-label configurations:
  maximum absolute difference from the exact rational formula was
  `1.1102230246251565e-16`. The `1e-14` comparison tolerance applies only to
  sklearn's floating result; the implemented bounds are exact fractions.
- **100 seeded permutation checks**, **10 rejected invalid-input cases**, and
  four additional census/undefined/large-integer/identified-AP checks passed.

| Wholly synthetic queue | Items | DP transitions | Runtime in v2 |
|---|---:|---:|---:|
| All unknown; distinct scores | 1,998 | 3,994,002 | 6.026 s |
| All unknown; two equal-size tie groups | 1,998 | 1,001,000 | 0.709 s |
| All unknown; one tie group | 1,998 | 1,999 | 0.038 s |

Each large example has positive-completion bounds `[1/1998, 1]` and separately
allows an undefined all-negative outcome. Both endpoint witnesses were checked.
These broad intervals illustrate nonidentification without labels; they are
not evidence about the real 1,998-file cohort. Timing depends on the shared
runtime and is not a comparative performance benchmark. Total v2 validation
runtime was 26.065 seconds.

The original greedy fixed-positive-count rule fails on the tied examples in
the [proof note](README.md). The replacement dynamic program is exact by the
prefix-count recurrence, not because its synthetic examples happen to pass.
No theorem-priority claim is made.

The preserved v1 run passed the same exhaustive/large tests before input review
identified a precision-contract problem: arbitrary `Real` values were coerced
to float. The v2 amendment rejects unsupported nonintegral numeric types so
distinct high-precision scores cannot silently become ties. It adds a
`Fraction` regression case; it does not change the integer recurrence or the
previously tested score values. Both frozen snapshots and configurations remain.

Current API SHA256:
`71147a09cec0f755a735224f127ef379d7b4e78c17094d3ee48c3635df54ef2c`.
V2 configuration SHA256:
`0ed80f2d505c48bf52f6417d741202bc1f4d2f3f70d618fe068dd9e0face3933`.

An AP point is returned only when identified by every admissible completion
with no undefined possibility; a positive complete census is the simplest
case. A survey-weighted partial-sample point estimate and these completion bounds
can concern the same target finite-population AP, but are different inferential
objects: a sampling-based estimator and a logical identification envelope. The
point estimator is not computed by this API. Human label correctness, missing model scores,
new-family generalization and paired sharp-difference bounds remain outside it.

A separate reviewer subsequently passed six sealed synthetic tests on the
amended API, including 96 seeded toy cases with every completion enumerated,
both tied-score counterexamples, endpoint witnesses, undefined outcomes,
large-integer ordering and rejection of lossy `Fraction` conversion. The
[independent receipt](../../recovery_20261026/engineering_independent_stage2_ap_bounds_20261026_v1/result.json)
records the unchanged API hash, and the reviewer separately confirmed the
Bellman proof and exact integer scaling. This is additional software/mathematical
review, not independent human vulnerability assessment.

Editorial correction, 26 October 2026: the preceding paragraph now distinguishes
the estimator from the completion envelope, rather than calling them different
estimands. No source snapshot, frozen configuration or numerical result changed.
