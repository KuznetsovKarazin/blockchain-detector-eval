# Probability-sample performance: engineering version1

This module is tested engineering for the proposed probability review design. It **does not authorize or perform external scoring**. It does not change the existing draft protocol, packet, gate, source/adjudication keys, model code, or previous experiments. `performance.py` accepts in-memory DataFrames; the only command-line runner constructs explicitly fictional inputs. No command-line argument accepts real scores, keys or source files.

## Interface and validation

`evaluate(frame, sample, allocation, first, second, adjudication, scores, target_class, ...)` evaluates one fixed method/class. Defaults require the complete 1,998-file × two-class frame (3,996 units), all180 selected file/class cases, and exactly1,998 successful finite scores for the requested class. The synthetic test helpers can explicitly override dimensions. `frame` contains `path`, `source_id`, `class`, `label_status`; `sample` additionally contains `case_id`, `N_h`, `n_h`, `inclusion_probability`, `design_weight`. Allocation strata are `source_id,class,label_status`; scores contain `path,class,score,status`.

The existing `review_estimators.analyze_review` validates complete aligned human forms, two distinct identified initial reviewers, provenance fields, and preservation of their initial judgments in adjudication. New checks additionally require the complete frame, correct population stratum counts, exact sampling weights, valid class/file joins and full successful queue scores. These checks validate recorded provenance, not human identity or correctness. Any missing/failed/nonfinite score blocks this estimator; no failure receives a safe score and no common-success subset is silently substituted.

## AP and uncertainty

AP is sklearn `average_precision_score` on the sampled class units with weights `N_h/n_h`. It is a **nonlinear plug-in estimate, not an unbiased Horvitz–Thompson estimator**. It uses the weighted empirical score/outcome distribution; it is not claimed to recover the unsampled ordering without estimation error. A complete census reduces to ordinary sklearn AP, including its exact-score tie convention.

Every selected outcome remains present. Any unknown outcome for the class suppresses AP point and interval; only the safe range[0,1] conditional on at least one population positive is reported. Unknowns are not assumed missing at random. A no-positive observed sample produces undefined AP, not zero; if this is a census, population AP is undefined. Any bootstrap replicate with no positive weighted mass or no total mass is explicitly invalid and blocks the entire interval. Invalid replicates are never dropped to manufacture an interval.

For each noncensus stratum, independently generate

\[
M_h\sim\operatorname{Multinomial}(n_h-1;1/n_h,\ldots,1/n_h),\qquad f_h=n_h/N_h,
\]
\[
w^*_{hi}=\frac{N_h}{n_h}\left[1-\sqrt{1-f_h}+\sqrt{1-f_h}\frac{n_h}{n_h-1}M_{hi}\right].
\]

This is the `m_h=n_h−1` specialization of the explicit single-stage SRSWOR formula in the **primary official [ECB/HFCN methodological report, §7.2, pp52–53](https://www.ecb.europa.eu/pub/pdf/scpsps/ecb.sps45~4bbcfb02eb.en.pdf)**. The complete source trail and verification scope are in [REFERENCES.json](REFERENCES.json). Census weights remain one; noncensus singleton strata fail closed. Strata are never merged. The implementation evaluates `1−sqrt(1−f)` as `f/(1+sqrt(1−f))` to avoid cancellation.

For a fixed sample vector z, the multinomial moments give E*(T*)=T_HT and

\[
\operatorname{Var}_*(T^*)=\sum_h N_h^2(1-f_h)s_{z,h}^2/n_h.
\]

This identity is independently checked by finite enumeration and separately tested through the production implementation. It is an identity for linear totals, **not a coverage proof for AP**. AP percentile intervals are explicitly design-approximate, conditional on this finite frame, fixed scores and adjudication process. They do not cover new projects/families, model training variability, semantic dependence definitions or reviewer error. Sparse positives, discreteness and score ties can impair nominal coverage. Because the finite-population baseline weight is positive, an observed positive can survive every replicate: absence of invalid replicates is not an adequacy test. Zero bootstrap spread likewise does not establish certainty about unsampled units. The original Rao–Wu bootstrap-t theory must not be presented as a theorem for this AP percentile implementation.

## Full-queue workload

Compute the cutoff on all1,998 scores first. At budget k=floor(q×1,998), probabilities a_i are1 above the cutoff, remaining-slots/tie-size at the boundary, and0 below it. The defaults yield99,199 and399 reviews. Decimal arithmetic avoids binary-float floor errors. Only after computing the complete queue are probabilities joined to all sampled cases of the class, retaining the zero-probability cases in variance estimation.

The target is tie-averaged recovered reference findings, T=Σ_i a_i y_i. With z_i=a_i y_i, return the **unclipped** HT point Σ_s w_i z_i and standard SRSWOR design variance above. This unbiased linear estimator can exceed the finite budget in a particular sample. Such a point is preserved and flagged; clipping it would change its statistical properties. Normal intervals/envelopes are approximate and may extend outside[0,k]; a separately labelled support intersection does not alter the point. Zero estimated variance in a noncensus sample is exposed and does not imply there are no unsampled findings.

Unknown outcomes suppress a single workload point. Lower and upper HT endpoint estimates use unknown=0/1 solely to represent unresolved outcomes and retain separate endpoint variances. These estimated endpoints are **not hard population bounds**. The module also returns logically valid finite-population bounds without survey weights:

\[
L=\sum_{i\in s,\,y_i=1}a_i,\qquad U=k-\sum_{i\in s,\,y_i=0}a_i.
\]

These include every unobserved and unresolved outcome. They can be wide, but exhaustive completion tests verify their meaning. Workload variance concerns annotation sampling for tie-averaged yield; it does not add the variance of a realized random choice within a tie.

## Tests and executable synthetic snapshot

```sh
.venv/bin/python -m pytest papers/security_evaluation/revision1/external_protocol/performance_v1/test_performance.py -q
.venv/bin/python papers/security_evaluation/revision1/external_protocol/performance_v1/run_synthetic.py --out papers/security_evaluation/revision1/external_protocol/performance_v1/synthetic_check_20261026_v1
```

The output directory must be new. Config, source snapshots and hashes are saved before synthetic estimation. The runner builds a fictional1,998-file/two-class frame and180 fictional review cases, then evaluates complete and unknown-reference scenarios. Its labels and scores never come from real contracts or people. Separate independent scripts/tests check the formulas and production API. No test success sets an external execution gate to true.

Remaining work before prospective scoring includes protocol freeze, genuine independent reviews/adjudication and all existing source/model gates. This version does not implement weighted recall ratios, paired method-difference intervals, multiple-comparison adjustment, cross-class covariance, model-training uncertainty, failed-tool/common-success analyses, or a rare-positive AP coverage study. Do not mark the whole external performance protocol complete merely because these primitives pass synthetic checks.
