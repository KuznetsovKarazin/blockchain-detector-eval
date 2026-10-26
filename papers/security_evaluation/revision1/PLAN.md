# Revision 1: dependency mechanisms and evaluation stability

Decision date: 25 October 2026. Starting public commit: `07673edcbd7dea2f732d66a867fcb90213c9f500`.

The author requested that both directions proposed in the first scientific review be pursued. Direction A studies how source coverage and dependency definitions affect the evaluation population. Direction B measures model stability and prepares an eligible external comparison. They share one protocol: a dependency definition cannot be selected because it produces a convenient score or training size.

## Research questions

1. How does the source population used to construct dependencies affect the component structure and admissible training sets of a fixed evaluation population?
2. Which dependence assumptions and source constructs account for large components, and how stable are the findings across thresholds and lexical representations?
3. On a fixed historical development test, how much score variation is attributable to training-subset selection and to estimator randomness, separately?
4. Which source, dependency and annotation conditions are satisfied by a proposed external cohort, and which remain unverified?

The main scientific contribution sought is an empirical explanation and reproducible assessment of population-dependent evaluation constraints. Neither a large connected component nor a convenient alternative representation establishes semantic identity, statistical independence or a new detector.

## Work specified before new scores

| Work | Design | Claim boundary |
| --- | --- | --- |
| Graph mechanism | Thirteen thresholds from 0.70 to 1.00; project, lexical and joint relations; nested 10–100% source populations; properly contracted project graph | Conditional on the stated relations; articulation results must not reflect arbitrary star encodings |
| Alternative representations | String-aware full source versus explicit library/interface declaration masking, with and without identifier/number collapsing; Jaccard and containment | Structural lexical extraction, not a Solidity semantic proof; uninformative representations and extraction failures remain explicit |
| Training selection | Same original 1,082-file test, 21 reentrancy proxy positives; 20 paired training draws; four historical methods and four historical training regimes | Conditional development stability only; the test still represents one historical component |
| Estimator randomness | Estimator seed fixed in the main panel; a separate tree-model seed panel on the fixed joint pool | Distinguish estimator randomness from changing training membership |
| Random ranking reference | Exact finite-sample expected AP, small-case enumeration checks and a fixed Monte Carlo reference | Descriptive reference; no file-exchangeability p-value or new-family inference |
| External preparation | Preserve the 1,998-file diagnostic cohort, full-graph training exclusions, a probability sample and two independent blank review forms | No external scores or fabricated human judgments; source-reported annotations are not adjudicated truth |

Each executable module saves its final detailed configuration and source snapshot before computation. These module configurations control their actual executions; this document is the overarching decision, not a substitute for them. Historical results and the two rejected outside-giant campaigns remain immutable. The new sampling diagnostic does not reopen those rejected campaigns.

## Response principles

Substantive review points are accepted: mechanism analysis, repeated training draws, an exact random-ranking reference, self-contained method settings, source-verified literature, useful figures, clear claims and disclosure of the book relationship. Fixed quotas of words, references or figures, a guaranteed editorial decision, and an unmeasured assertion that a score difference is noise are not scientific acceptance criteria. Annotation lineage and annotation correctness are separate research objects. Human review is essential for claims about correctness, not for documenting source provenance.

Contract/function-level semantic analysis, true deployment-family verification and independent expert judgments must be reported as incomplete unless actually performed. Masking explicit library/interface declarations does not remove every reused library implementation. A review form is not a completed review. A prospective protocol does not retroactively turn inspected historical data into an untouched holdout.

## Publication scope

Publish new code, configurations, aggregate results, derived predictions, path/hash metadata and figures to the existing article branch. Keep the colleague's full review, book text, third-party Solidity and private annotation keys out of the public package. No correspondence, journal submission, DOI minting or claim of human adjudication follows from this revision task.
