# Expanded dependency graph invalidates both selected development designs

The two frozen outside-component tests were rechecked without changing their
file identities, reading predictions or fitting models. Their original training
exclusions used the historical capped 7,080-object graph. This sensitivity uses
the expanded 24,131-object graph, including uncapped upstream files and external
candidate files as potential dependency bridges. Both graph normalizations,
base/address-expanded policies and thresholds 0.7, 0.8 and 0.9 were evaluated.
Source hashes join every historical object to the expanded graph.

At threshold 0.8 the result is decisive under the declared transitive dependency
rule. For `outside_p90_seed2`, only 13 of the other 5,525 DAppSCAN files are
eligible for joint-disjoint training, with zero reentrancy and one unchecked
proxy-positive file. For `outside_p90_seed4`, only 10 remain, with one reentrancy
and zero unchecked proxy-positive files. The original historical-graph joint
training sets contain 5,409/5,422 and 5,408/5,418 files connected to their test
through the expanded graph. Counts are identical for both normalizations and
for base versus address-expanded policies. The failure is not caused by scanner
error quarantine, whose count is zero.

| Threshold | Test | Eligible joint train | Reentrancy proxy positives | Unchecked proxy positives | Test components | Largest test component share |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0.7 | seed 2 | 11 | 0 | 1 | 153 | 63.47% |
| 0.7 | seed 4 | 9 | 1 | 0 | 154 | 63.28% |
| 0.8 | seed 2 | 13 | 0 | 1 | 185 | 40.30% |
| 0.8 | seed 4 | 10 | 1 | 0 | 187 | 40.02% |
| 0.9 | seed 2 | 310 | 4 | 1 | 201 | 30.04% |
| 0.9 | seed 4 | 308 | 5 | 0 | 202 | 30.23% |

All 95 existing deterministic test proposals were also rechecked, keeping T
unchanged. None passes the original operational count and component-dispersion
screens under any of the twelve graph variants. Some proposals still contain
both classes and could technically be fitted; that is different from passing
the declared screens. The screens themselves are feasibility criteria, not a
statistical power analysis.

These findings invalidate the interpretation of the frozen historical-graph
joint regime as source-wide family separation. They establish infeasibility for
these particular test proposals under this conservative transitive dependency
definition. They do not prove that every possible study, graph definition or
future corpus is infeasible. Shared libraries and project transitivity can merge
large parts of a corpus; semantic relevance of these links remains a limitation.
The expanded graph is itself an observed lexical/project dependency model, not
proof of exhaustive semantic independence.

`CAMPAIGN_GATE.json` blocks comparative training and external scoring. An exact
copy is placed beside each frozen bundle, without changing its original manifest
or memberships. The earlier historical-only train_allowed flag is a provenance
record and is superseded by the later gate. No campaign models were fitted.
Any further comparison needs a newly justified scope and newly frozen valid
manifests; deleting the gate or weakening grouping silently is not acceptable.

## Evidence

`all95_joint_sensitivity.csv` contains 1,140 design/graph rows. The graph variants
are sensitivity conditions, not independent experiments. `selected_training_overlap.csv`
checks both classes, all five sampling seeds and all four historical regimes
for both selected tests. `selected_test_expanded_memberships.csv` makes the
new component assignments inspectable. `config_before_check.json`, graph input
hashes, code snapshots and gate output hashes preserve provenance.

This is a fresh post-recovery metadata analysis. It uses regenerated, independently
verified dependency graph artifacts; it is not the lost pre-recovery output.
The two test sets share 961 files, or 90.49% of either test, and are not independent
replications. All vulnerability counts and feasibility rules here use DAppSCAN
published-finding proxies, not independently adjudicated vulnerability labels.

## Reproduction

```bash
python papers/security_evaluation/design_feasibility/check_expanded_graph.py --audit papers/security_evaluation/design_feasibility/audit_recovered_20261025_v2 --graphs papers/security_evaluation/dependency_audit/legacy_recovered_20261025 papers/security_evaluation/dependency_audit/string_aware_recovered_20261025 --bundles papers/security_evaluation/design_feasibility/selected_outside_p90_seed2_recovered_v2 papers/security_evaluation/design_feasibility/selected_outside_p90_seed4_recovered_v2 --out papers/security_evaluation/design_feasibility/expanded_sensitivity_reproduction
```
