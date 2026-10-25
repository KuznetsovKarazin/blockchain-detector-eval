# Independent assessment of candidate vulnerability labels

This is a diagnostic audit protocol prepared before any external model scoring.
No human assessment has yet been completed. The source annotations are not
accepted as independently verified labels by this work.

## Assessment unit and evidence

One case is a source file and one of two classes: reentrancy or unchecked
low-level calls. Read the entire relevant function, state changes, call context,
and available compiler constraints. A source line containing `call`, `send`, or
`transfer` alone does not prove either vulnerability. Record the active language
semantics, exploit preconditions, affected lines, and a short reproducible reason.
Use `unknown` when source dependencies, runtime assumptions, or identity cannot
be established. A negative judgment is bounded to the selected class and stated
assumptions; it is not a certificate that the contract is safe.

The source taxonomy maps `reentrancy` to `reentrancy` and
`unchecked_low_calls` to `unchecked`. A `no` or `no;` source marker means no
reported finding within the source study's taxonomy. It is not a tool failure
and is not evidence of universal safety. A class absent from a nonempty tag list
is recorded separately from an explicit no-finding source record.

## Identity and annotation problems

The source CSV is keyed by `(source identifier, contract identifier)`, not by
contract identifier alone. All repeated rows are retained in a private evidence
key. The upstream evaluation code's first-match-by-contract behavior must not be
reused. Duplicate keys with different annotations, a source missing its manifest
row, unparsed annotations, and out-of-range source locations are quarantined in
the conservative adapter; none becomes a negative target.

One ZEUS repeated-key record has locations consistent with a different unmatched
source file. This is a candidate transcription error, not an authorized
correction. Both identities need specialist adjudication against the preserved
source/annotation evidence before they can enter a frozen test. The SmartBugs
curated repeated-key record appears to annotate two classes in one file. Even
if that union is confirmed, the curated source remains previously exposed data.

## Diagnostic sample and inference

The first packet targets 25 proxy dependency components and up to six cases per
component. Components are prioritized by source reconciliation problems, then
available case count; pseudorandom ordering resolves equal priorities, using
the recorded seed. Within a component, identity/annotation problems and
source-reported positives receive priority. The actual case count is reported;
it is not padded with repeated cases or synthetic examples.

This is purposeful diagnostic sampling. Population inclusion probabilities are
not claimed, design weights are not invented, and the resulting label-error
fraction must not be interpreted as a corpus-wide error estimate. Record every
reviewed case and report conclusions only for this diagnostic sample. A later
population error estimate requires a separately fixed probability sampling
design and adequate independent component coverage.

The component identifier is a lexical/project-dependency proxy. It does not
establish the actual business project, deployment family, or semantic code
family. Large components are reported rather than split to meet the sampling
target. Additional disputed cases discovered outside the packet are reviewed as
an explicit supplemental stratum, never silently added to an estimated rate.

## Two assessors and blinding

The primary assessor reviews every selected case. An independent Solidity
security specialist reviews every selected source-reconciliation dispute and
a random quarter (rounded up) of the other selected cases. The conditional
selection probability for this second assessment is saved. All remaining
disagreements or uncertain primary judgments are then independently adjudicated
and marked as an additional disagreement stratum.

Neither assessor receives any model score, model identity, ranking, or
comparative metric. The source-label key is held separately until the initial
judgments are saved. The generated reference sheet retains upstream paths for
traceability, so source category names are visible: this is model-score blinding,
not complete source-provenance blinding. If stricter label blinding is required,
give assessors local copies renamed by case identifier and keep the path key
with the coordinator. Source comments may also reveal original annotations;
record this limitation rather than claiming complete blinding.

An AI-generated second opinion is not an independent specialist assessment.
No invitations or requests to third parties are sent by this workflow.

## Required saved decisions

For each assessor preserve reviewer identity, date, class, judgment
(`positive`, `negative`, `unknown`), affected lines, compiler assumptions,
reason, and confidence/remaining uncertainty in prose. Preserve both initial
judgments. After reconciliation record the final decision and who resolved it;
never overwrite the initial evidence. Keep the source annotation and
source-to-file identity correction as separate fields from the expert's
substantive vulnerability judgment.

External scoring remains blocked until the class mapping, eligible source
identities, group rules, model configurations, and evaluation protocol are
frozen. This packet alone does not satisfy that gate.
