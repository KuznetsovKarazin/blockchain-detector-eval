# External protocol and two-expert probability packet

The concrete preparation is complete; external validation is not. No model has
been fitted or scored on the external cohort, and no human judgment is present.

The fixed provisional cohort is 1,998 files / 3,996 file-class cases. After full
24,131-node graph exclusion at threshold 0.8, the DAppSCAN training manifest has
691 files with 23 reentrancy and 18 unchecked published findings. Its graph
component intersection with the test is zero under this observed grouping rule.
Alternative graph thresholds remain metadata sensitivities, not score-based
choices; the principal B draft stays at 0.8.

The new probability packet has 180 cases from 170 files: 74 reentrancy and 106
unchecked cases, drawn from 17 source/class/status strata. Both independent
human specialists review all 180. Inclusion probabilities and design weights
are recorded. A separate 17-case identity census preserves every unresolved
source issue without adding it to the estimation denominator. The old purposeful
106-case packet is unchanged and is not combined with this sample.

Public forms contain anonymous case IDs and requested classes, with every
judgment field blank. Original annotations, case-to-source keys and renamed
complete sources are kept in ignored `data/derived/revision1_external_review_probability_20261025_v1/`.
Separate private identity evidence includes exact source rows and alternative
identity candidates, without automatically correcting any record. This private
material must not be added to a public Git commit or release.

`PROTOCOL_B.md` distinguishes annotation lineage, expert correctness assessment,
reviewer agreement and model performance. It specifies weighted finite-population
rates, unknown bounds, boundary-valid intervals, all four learned methods,
Slither/compilation failures, model-score blinding and prospective amendments.
Kappa is supplementary and is not a measure of truth. The observed proxy labels
are not relabelled as confirmed negatives.

`protocol_B_draft.json` is deliberately not frozen. The executable guard reports
exact remaining prerequisites: named specialists and review sign-off, final
feature adapters/tests, compiler inventory/policy tests, weighted performance
and interval tests, and semantic class mapping. The two initial human reviews
and adjudication must subsequently be sealed before external scoring. Sampling, gate, exact finite-population estimator, compiler-policy and saved
readiness regression tests are implemented. An independent agent also reproduced the case draw,
verified all inclusion probabilities/hashes and confirmed that all forms are
blank. This computational check does not replace the two human reviewers.

The completed engineering and exact remaining prerequisites are recorded in
`ENGINEERING_READINESS.md`. The read-only check verifies all 2,689 source inputs;
compiler candidate plans exist for 1,968 external files, without any compilation.
The actual Slither/compiler dependencies still require provision and hash
verification. `review_estimators.py` implements weighted human annotation
assessment, exact finite-population confidence envelopes and unknown bounds;
blank review forms correctly refuse analysis. Model AP/workload uncertainty
remains a separate implementation prerequisite.

## Reproduction and guard

Use new public/private output directories; creation never overwrites a packet.

```bash
python papers/security_evaluation/revision1/external_protocol/build_packet.py --out papers/security_evaluation/revision1/external_protocol/packet_probability_reproduction --private data/derived/revision1_external_review_probability_reproduction
python -m pytest -q papers/security_evaluation/revision1/external_protocol/test_external_protocol.py
python papers/security_evaluation/revision1/external_protocol/validate_gate.py --protocol papers/security_evaluation/revision1/external_protocol/protocol_B_draft.json --phase score
```

The final command is expected to exit 2 with allowed=false while the draft
conditions remain open. It never executes a model. No registration, DOI, third-party
message, author permission request or submission was created. The public deliverable contains
our code, aggregates and references/hashes; permission
to redistribute third-party raw sources or row annotations remains unresolved.
