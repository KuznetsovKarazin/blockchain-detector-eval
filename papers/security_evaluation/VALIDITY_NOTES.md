# Validity checks for the first development cycle

## What has been checked

An additional automated review independently checked the fixed-test memberships and recomputed the reported AP and workload values from saved predictions and locally reconstructed labels. This is an implementation review, not independent human vulnerability adjudication.

The four regimes use the same 1,082 test file IDs and 1,179 training files, including 31 reentrancy proxy positives. Exact test objects are excluded from every training set. Project-disjoint, clone-disjoint and joint-disjoint constraints are verified separately. The training/test shared project and clone counts are 270/110 for unrestricted, 0/30 for project-disjoint, 255/0 for clone-disjoint, and 0/0 for joint-disjoint. Thus the experiment compares different training populations with the intended restrictions.

The test contains 21 reentrancy proxy positives but only three unchecked-call proxy positives. It is a software and feasibility pilot. It does not support a strong two-class generalization claim. Selecting a different test after seeing these results must be reported as development, not retrospectively represented as a previously untouched test.

## What the dependency graph means

The pilot reproduces the historical partition on 7,080 rows: 6,587 sampled DAppSCAN files, 350 SolidiFI files and 143 SmartBugs files. The full transitive union is retained before selecting a test subset. Joint-disjointness holds relative to that frozen observed graph. It is not a proof of semantic independence or a statement about all upstream source files.

The historical `exact_hash` function hashes normalized tokens rather than original bytes. Its comment removal is not string-literal aware: comment-like text inside string literals may be removed. Identifier and numeric normalization intentionally loses distinctions. The clone search retrieves candidates using LSH and verifies Jaccard similarity in a CRC32 shingle representation. LSH can miss edges, and CRC32 collisions are a separate limitation. Even the existing exhaustive pair checker uses CRC32 and therefore does not independently rule out such collisions.

The external audit records byte SHA-256 separately, scans full upstream sources, and uses exhaustive comparisons of normalized shingle sets represented by 128-bit digests. This removes LSH candidate omission for that representation; it does not make lexical similarity semantic equivalence. Project, deployed-address and library-family provenance still need adjudication.

## What can be concluded now

For this one test and matched draw, AP differs between training regimes even after holding test files, training size and proxy-positive counts constant. Joint-disjoint AP is above project-disjoint and clone-disjoint AP, so a claim of monotonic degradation is not supported. Training composition remains different, and a pure causal leakage effect is not identified.

The test belongs to one joint component. No confidence interval, bootstrap inference or hypothesis test is reported. Random seeds measure computational or sampling variability; they cannot create independent test families. DAppSCAN zeros remain absence of a published finding, not confirmed safety.

## Workload rounding amendment

The pilot configuration used ceiling rounding for review budgets and was saved before scoring. A parallel general metric implementation used floor rounding. The mismatch was noticed after the original pilot had begun. The original configuration and results are preserved. A separately labelled post-hoc analysis applies floor rounding to the same saved predictions; it does not refit models. Floor rounding remains the proposed main-study rule and is recorded in `protocol.json`.
