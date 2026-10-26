# Fixed finite-population AP interval diagnostic

This design is frozen before evaluating any scenario. It uses only explicitly fictional binary populations and fixed artificial rankings; no project labels, predictions, review forms, private keys or source files are read. `performance_v1` is immutable. This is a numerical diagnostic, not a calibration theorem or a sample-size analysis for the actual 1,998-file/180-case proposal.

## Scenarios fixed in advance

The main factorial has 54 scenarios: N=20; three designs; three score arrangements; six positive patterns. Designs are SRSWOR n=4; independent stratified SRSWOR with N_A=16,n_A=2 and N_B=4,n_B=2; and a complete census. Stratum B contains zero-based units1,6,11,16. Scores are descending unique ranks, descending blocks of five tied units, or all tied. Positive indices are {0}, {9}, {19}, {16}, {1,18}, or all even indices. These cover rare positives at high/middle/low ranks, an oversampled stratum, two positives and a 50% positive control without selecting cases after results.

Two additional N=20 no-positive scenarios use unique scores with SRS n=4 and census. Three additional N=50, n=4 SRS scenarios use unique scores and a single positive at index0,24 or49 (2% prevalence). Total: **59 scenarios and795,934 equally probable sample states**, enumerated exactly within each declared sampling design. No scenario will be removed for poor coverage.

## Estimands and computation

True finite-population AP is computed independently from complete population tied-score groups and checked against the unchanged v1 weighted-AP routine with unit weights. No-positive population AP is undefined. Every SRSWOR sample is enumerated; only exactly equivalent configurations of outcomes, tied-score ranks, stratum positions and design counts are grouped. This does not sample or approximate the sampling distribution.

For each configuration, enumerate the finite multinomial Rao–Wu weight support with exact integer multiplicities: at most20 distinct weight vectors and64 equally likely ordered resampling sequences. Census weights remain fixed. The unchanged production AP function evaluates every support vector. Exact-bootstrap percentile endpoints use the discrete inverse CDF at.025/.975, with probability masses kept explicitly; they are reported separately from finite Monte Carlo endpoints.

Also evaluate the actual v1 weight generator with B=2,000 and seeds2026102601,2026102602,2026102603. Each replicate weight must be an exact member of the enumerated support, so its production AP value can be looked up without recomputing millions of identical metrics. Monte Carlo endpoints use exactly the v1 `numpy.quantile` convention. The complete `ap_interval` production wrapper is additionally checked on the first positive-containing configuration in each (N,design,score arrangement) combination, using the first fixed seed and all2,000 replicates. No-positive cases are checked through the production guard. The oracle selection rule is fixed before observing coverage.

No interval method, seed, score arrangement or outcome pattern is tuned after results. The three seeds describe Monte Carlo endpoint sensitivity, not extra independent populations. Results are conditional on each fixed algorithm seed; exact sample enumeration has no sampling Monte Carlo error. Computation is bounded through support lookup and resumable per scenario and configuration; source and design hashes are checked on resume.

## Prespecified outputs

For every scenario and each of the four methods (exact bootstrap distribution; three finite-MC seeds), report:

- Probability of issuing an interval, undefined/no-sample-positive frequency, and invalid-replicate fraction; undefined intervals are never replaced by zero AP.
- **Unconditional probability of issuing an interval that covers true AP**, counting undefined/no-interval samples as not covered, alongside coverage conditional on an issued interval. Neither is silently substituted for the other.
- Mean interval width and zero-width frequency conditional on issuance; conditional point bias and RMSE; lower/upper miss frequencies.
- The entire grouped exact sampling distribution and the support/configuration records required to reproduce it.

Coverage uses a fixed1e-12 numerical comparison tolerance; zero width means width<=1e-12. When true population AP is undefined, coverage, bias and width comparisons to a true AP are not assigned numeric values. All output probability denominators remain explicit.

The report will state failures and successes under these artificial finite populations. It will not claim universal95% calibration, quantify the actual external experiment's coverage, infer new-project performance, or change the external execution gate. Passing a linear-total variance identity or observing no invalid positive-sample replicates is not treated as evidence of AP coverage.
