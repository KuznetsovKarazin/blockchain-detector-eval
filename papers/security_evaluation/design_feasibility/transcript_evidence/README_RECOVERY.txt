TRANSCRIPT RECOVERY AFTER WORKSPACE LOSS

This package was reconstructed from this agent's visible tool-call transcript on 25 October 2026. It is NOT a recovered copy of the original run directory, original manifests, or source inventories. No experiment or metadata audit was rerun during recovery.

At loss inspection, /workspace/scratch/b7b7c7c8fdb5/security-eval/.git, papers/security_evaluation/design_feasibility/, tests/test_security_design.py, and papers/security_evaluation/code/fixed_t_development.py were absent. A later file scan found only the conversation config file under the workspace. The cause is unknown.

The previous-cycle fixed-T development pilot had been committed by parent to GitHub commit 25a191df4a7fdcd0e0aede3c09e33fc0be6a6b29 (observed HEAD before this new cycle). Recover that cycle from Git rather than treating this package as its authoritative artifact.

The new cycle enumerated 95 label-blind deterministic test proposals, with five seeds each. No model scores were read or models trained. Screens were saved before enumeration: minimum20 test proxy positives per class,20 training positives per class,500 training files,10 test components,inverse-Simpson component concentration>=5,largest test component share<=0.5,positive class components>=5 and positive concentration>=3. These are operational checks, not power calculations. Candidate membership was label blind; selecting passed candidates uses label counts and must be disclosed as development after the observed pilot.

The preserved stdout says only outside_p90_seed2 and outside_p90_seed4 passed. No selected campaign bundle was exported and no training was enabled. Original design_manifest had train_allowed=false. The original95-row design_summary.csv,760-row class_pool_feasibility.csv, exact candidate_tests.csv, input hashes and manifest are NOT available in this transcript recovery package. Do not claim they have been recovered.

Source audit used the historical original7080-object C2 observed dependency graph, then restricted training/test to6587 DAppSCAN objects. Expanded uncapped/external graph evidence is separate and may invalidate historical feasibility. It must not be silently substituted.

Tests: tool output reported6 passed in0.60s immediately before audit, then6 passed in0.48s after exporter-only improvements. Test source covered label-blind/order-invariant selection, concentration dominance, whole-component identical pools, full-transitive exclusion, whole-component sampling, and95 fixed candidate definitions. No tests were rerun after loss.

Interpretation: fullpopulation T creates small joint training pools; giant-only T has one dependency component; whole outsidegiant T makes restrictions identical. Outside90% is only a complementary changed-population development comparison: it excludes the82.1%giant and joint exclusion changes training by only~1.9%. A broad main-study claim remains unsupported by this feasibility screen.
