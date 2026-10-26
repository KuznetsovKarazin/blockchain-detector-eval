# Random-ranking helper versions

`random_ranking_reference.py` is the exact helper frozen into the completed `run_20261025_v2` experiment. Its workload fractions are fixed at 0.05, 0.10 and 0.20 for N=1,082, yielding the correct budgets 54, 108 and 216. Its source, tests, snapshots and computed results remain unchanged, preserving hash-checked resume.

Code review identified a general-use floating-point boundary issue outside those experimental settings: directly flooring `0.29 * 100` can yield 28. The separately named `random_ranking_reference_v2.py` uses decimal arithmetic on the decimal spelling of each validated float fraction before flooring. Use this version for new general-purpose calculations; a new experiment should freeze this version explicitly. It was added after the completed experiment and was not its executed source.

Six regression cases pass, including decimal boundaries and a complete 10,000-draw comparison at the actual experimental N/K/seed. Every AP draw, workload count and numerical summary agrees between versions for the frozen experiment; only schema and budget-rule metadata differ. The exact AP expectation and its small-population enumeration checks are unaffected. Neither version computes inferential p-values or project-generalization intervals.
