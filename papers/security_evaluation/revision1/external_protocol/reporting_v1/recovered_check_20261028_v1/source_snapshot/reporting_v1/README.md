# External B reporting adapter — inactive amendment

This implements the numerical reporting choices in the [draft inference amendment](../INFERENCE_AMENDMENT_DRAFT_20261026.md). It **does not adopt that amendment**, validate the original AP percentile intervals, authenticate experts, change a release gate or establish external detector performance. Existing performance, AP-bound, orchestration and protocol files are unchanged.

`report_class` is a pure in-memory API. No source, label or score file is read and no tool/model is invoked. There is no actual-input CLI. `production_admission` returns a closed result before touching any supplied path. A future production integration still needs a new prospectively approved protocol/release binding covering this adapter, exact AP-bound implementation, original case-to-file mapping, score/status adapters and complete sealed review/score evidence. Supplying a name, hash or `approved=True` does not activate it.

## Fixed identities and outputs

Each class has 13 primary score vectors: raw and normalized LR seed 0, RF seeds 0–4, LightGBM seeds 0–4, and Slither. The learned job IDs are `METHOD:CLASS:SEED`; the static ID is `slither:CLASS:0`, matching immutable orchestration. Exactly 12 contrasts are displayed, each alternative minus raw LR. Repeated tree seeds are descriptive model fits on the same population, not independent population replications.

Required score columns are `job_id,method,class,seed,variant,path,execution_status,status,score`. Every vector retains every file, including failures with missing scores. Unknown canonical failure statuses, invented failure scores, missing/duplicate job-file rows, wrong seeds and extra primary vectors are rejected. Canonical statuses use the frozen performance-v2 vocabulary. Raw reasons remain visible; this numerical check does not replace the worker's bound status mapping or verify the truth of a log.

An optional vector `slither_broad:CLASS:0`, variant `broad_secondary`, is reported separately. Primary and broad static vectors must share per-file execution statuses, binary successful union scores and, when provided, trace hashes. Reentrancy broad must include the primary union; unchecked must equal it. These enforce the existing draft definitions without asserting semantic sign-off. The broad vector does not enter the 13-vector common-success intersection.

Inputs include the independently retained `case_manifest` linking `case_id,path,class,source_id,label_status`. Sample identities must equal this manifest, reference forms must retain the original cases and class labels, and any supplied form paths must agree. Strata, original weights, initial judgments, adjudication and unknowns undergo the unchanged review/performance validators. This checks consistency relative to supplied identities; genuine source authenticity needs the future sealed production binding.

Domains and queues are constructed from score identities/statuses before joining expert outcomes. The full-frame queue ranks successes with budget `floor(f*N_full)` and leaves unavailable slots unfilled. The secondary common-success domain is the intersection across all 13 primary vectors, computed once per class. Its original sample strata and weights are retained, including zero contributions outside the domain. Empty common domains have undefined rankings.

## Primary statistics

- Coverage records exact finite-frame successes and every canonical/raw failure status, along with planned, filled and unfilled budget slots.
- Reference-positive totals and expected queue yields report unclipped HT estimates, stratified without-replacement variance estimates and standard errors. No default Wald, percentile or other primary confidence interval is attached. Zero sample variance is explicitly not certainty.
- Unknown sampled outcomes in the target domain suppress its primary point/SE. Separate completed-variable endpoint estimates retain their own variance/SE. For signed paired yield differences, unknown contributions use `min(q_A-q_B,0)` and `max(q_A-q_B,0)`; mechanically setting every unknown to 0 or 1 would be wrong. Hard logical population bounds separately include **all** unassessed and unresolved files. Estimated endpoints are not hard bounds.
- Exact rational AP completion endpoints, attaining completions and `undefined_possible` are reported using the unchanged AP-bound implementation. Missing scores suppress full-frame AP bounds. All-negative references have undefined AP. Paired AP envelopes are conservative and generally nonsharp; component endpoints may use incompatible label completions. Undefined possibility propagates and no confidence-based superiority claim is produced.
- Annotation audit retains the existing supported whole-stratum binary hypergeometric/unknown envelopes and descriptive reviewer agreement. These are not transferred to queue weights, AP or arbitrary common-success subdomains.

`fixed_queue_ht` exposes the signed linear calculation for independent finite-design checks. Input arrays must retain sample alignment and binary/unknown outcomes. Mathematical design variance concerns a fixed finite population and fixed queue; it does not account for reference mistakes, new families or training variation.

## Explicit exploratory path

`include_exploratory=False` is the default; it does not invoke resampling or the complete v2 comparison engine. When explicitly requested, all vectors/domains share the frozen Rao–Wu design matrix. Displayed percentile ranges and AP/recall ratios are labelled **exploratory and design approximate, with coverage unvalidated**; invalid replicates are retained and suppress the range. Only the 12 prespecified reference contrasts appear in the report.

The complete, unchanged v2 output—including its 78 unordered pairs and legacy interval fields—is retained separately under `engine_audit`, labelled as unfiltered audit material, not primary results. It must not be relabelled calibrated uncertainty. Default prospective settings remain 2,000 replicates, seed 20261026, alpha 0.05 and budgets 0.05/0.10/0.20; smaller fixtures or changed settings require an explicit synthetic profile.

All trusted numerical dependencies are loaded from their exact source bytes and recorded by digest. The wrapper rebinds the unchanged v2→v1→review dependency objects to those exact loads; it does not edit the frozen modules. These source checks are provenance, not authentication of people or study permission.

## Verification

`test_reporting.py` uses only fictional records, including signed unknowns, finite-design variance enumeration, unassessed labels, failed scores, shared domains, joint identity corruption and undefined AP contrasts. `run_synthetic.py` creates a new design/configuration and public source snapshot before computing any durable fictional report. Existing output directories are never overwritten. No real human assessment or external model result is created.
