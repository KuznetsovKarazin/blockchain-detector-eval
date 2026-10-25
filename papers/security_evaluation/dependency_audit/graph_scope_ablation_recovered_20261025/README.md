# Isolating graph scope from the grouping implementation

The two selected development tests fail the stronger joint-disjoint condition
already when uncapped upstream files are added. Adding the external candidate
corpus is not required for that failure. At threshold 0.8, replacing the saved
historical grouping with exhaustive grouping on the same 7,080 files leaves
the historical DAppSCAN partition and both selected tests' training pools
unchanged.

| Graph | Construction population | Historical DAppSCAN components | Largest historical DAppSCAN component | Seed 2 joint training files | Seed 4 joint training files |
| --- | ---: | ---: | ---: | ---: | ---: |
| A observed historical | 7,080 | 227 | 5,408 | 5,422 | 5,418 |
| B exhaustive historical | 7,080 | 227 | 5,408 | 5,422 | 5,418 |
| C exhaustive uncapped references | 21,950 | 198 | 5,879 | 13 | 10 |
| D exhaustive references and candidates | 24,131 | 197 | 5,879 | 13 | 10 |

The historical DAppSCAN projection always contains the same 6,587 files, and
both test sets keep their original 1,062 files. Thus the larger construction
population changes their dependency connections, not their inclusion in the
reported test. The largest projected component grows from 82.10% to 89.25% of
the historical DAppSCAN files when moving from B to C.

Under C and D, seed 2 retains zero reentrancy proxy positives and one unchecked
proxy positive; seed 4 retains one and zero respectively. Neither supports
both declared two-class training tasks. The selected historical joint-training
memberships consequently remain blocked for an unqualified full-source
joint-disjoint claim. These counts are proxy-label feasibility findings, not
model performance or a power analysis.

Both legacy and string-aware normalization give the table above. The A-to-B
comparison bundles the observed historical implementation/representation and
provenance differences; it does not isolate a general causal effect of LSH or
CRC32. No projected DAppSCAN partition change occurs here at 0.8. B-to-C adds
uncapped upstream nodes and their incident relations under the same exhaustive
lexical rule. C-to-D adds candidate nodes and their identity/clone relations;
it merges one further projected component but does not alter these two tests'
remaining training counts. No claim is made about another threshold or all
95 candidate designs from this two-test ablation.

## Exact reconstruction

The script induces the previously exported complete lexical edge list at
Jaccard 0.8. Similarity is a file-pair property of the frozen normalized token
sets, so those edges can be reused without rescoring source code or models.
Project, identical-raw-source and candidate-identifier star links are rebuilt
from the nodes retained in each construction population. Merely deleting
old star anchors would lose valid relations; that operation is not used.
This ablation fixes the `base` grouping policy and does not add the optional
address-expanded policy.

`config_before_compute.json` and a source snapshot were saved before graph
reconstruction. `historical_projection.csv` provides all assignments on the
historical 7,080 files. The concentration, transition, fixed-test feasibility,
and selected-membership retention tables can be inspected separately. Every D
projection is checked against the saved complete graph. B-to-C and C-to-D are
checked to be coarsenings on the fixed historical population. The run completed
in 14.34 seconds and performed no model fitting or external scoring.
