# Independent reporting tests: source recovery and new verification

28 October 2026. **34 synthetic tests passed**, with zero failures, errors or
skips. Pytest reported 19.15 seconds; the complete subprocess took 19.82 seconds.
No actual reference, source-label key, target source, external score, fitted model
or tool execution was used. This is a new verification after environment loss.

The independent test source was reconstructed from the preserved tool-history
patch and amendments. Its SHA256 is
`0df301bf6ad537d5d5b84c611781c07d1487295a3df3ebb550439b46888c4316`, exactly the
hash recorded on 26 October. The recovered code is retained at the new path
[`test_reporting_independent.py`](test_reporting_independent.py).

The original 26 October test path, plan, result and captured stdout remain
absent. Reproducing the assertions does **not** restore the old run's output,
timing or receipt bytes. No missing old receipt has been recreated or labelled
as recovered. The [recovery inventory](reporting_independent_reproduction_20261028_v1/RECOVERY_INVENTORY.json)
records this distinction and the observed absence of those old artifacts.

The reporting core is byte-identical to the previously reviewed source,
SHA256 `eb2502b2604955e6cbe1cd54819481c0a9911d5c3738d3b0525426b04e7aa504`.
All four numerical dependencies and four policy/protocol files were also checked
against their previously recorded hashes. Before tests, the new runner preserved
the [execution plan and runtime](reporting_independent_reproduction_20261028_v1/plan_before_tests.json)
and complete source snapshots. Every captured source hash remained unchanged.
The [new result](reporting_independent_reproduction_20261028_v1/result.json) and
[JUnit record](reporting_independent_reproduction_20261028_v1/pytest.xml) document
the 28 October execution.

The runtime is Python 3.12.14, NumPy 2.3.5, pandas 2.2.3, SciPy 1.17.0 and
scikit-learn 1.8.0. Pytest is now 9.2.0; the original recorded run used 8.4.2.
This environment difference is explicit rather than treated as original-run
recovery.

The tests retain the earlier independent finite-design and scalar-AP oracles:
all 18 stratified sample states for signed HT totals/variance, unknown endpoint
estimates versus hard bounds, original weights and finite-population correction
in the common domain, unclipped totals, tie-averaged yield, completion AP over all
unassessed labels, missing-score and undefined-state propagation, 13 seed-specific
jobs and 12 reference contrasts, static-union consistency, identity rejection,
and closed production admission. This successful rerun does not activate the
inference amendment, establish nominal AP confidence coverage, authenticate
human reviewers, or permit actual external evaluation.
