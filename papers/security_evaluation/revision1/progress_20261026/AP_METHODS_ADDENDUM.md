# Proposed methods and diagnostic-results addendum

Prepared 26 October 2026 for a future manuscript revision or supplement. The
following text describes completed synthetic methodological work. It does not
modify Revision 2 or report performance on the actual external cohort.

## Methods: partial-label AP and exact completion bounds

We distinguished uncertainty from probability sampling from uncertainty caused
by unobserved reference labels. To examine the proposed survey-weighted AP
procedure, we specified 59 artificial finite populations and sampling designs
before calculation. The principal factorial used 20 items, simple random
sampling of four items without replacement, unequal stratified sampling, or a
census; rankings were distinct, tied in groups of five, or completely tied.
Positive patterns ranged from one positive to a half-positive control. Additional
cases considered no positives and populations of 50 items. We enumerated all
sampling states and the finite support of the rescaled bootstrap, retaining
undefined AP separately. We reported interval issuance, coverage conditional
on issuance, and the probability of issuing a covering interval as distinct
quantities.

Following this diagnostic, we implemented a separate logical analysis that
requires a finite score for every item in a declared population and reference
labels in `{positive, negative, unknown}`. Unsampled and unresolved cases remain
unknown; known labels are held fixed. For descending score groups, let group
\(g\) contain \(a_g\) known positives and \(u_g\) unknowns, and let \(N_g\)
and \(A_g\) denote cumulative item and known-positive counts. Assigning
\(z_g\in\{0,\ldots,u_g\}\) unknown positives gives group positive count
\(p_g=a_g+z_g\), cumulative positives \(T_g\), and total positives \(P\).
For \(P>0\), grouped-threshold average precision is

\[
\operatorname{AP}=\frac{1}{P}\sum_g\frac{p_gT_g}{N_g}.
\]

An exact dynamic program retains the minimum and maximum numerator after each
group for every cumulative unknown-positive count \(t\):

\[
F_g^{\min/\max}(t)=\min/\max_z\left[
F_{g-1}^{\min/\max}(t-z)+\frac{(a_g+z)(A_g+t)}{N_g}\right].
\]

This state is sufficient because later contributions depend on earlier label
choices only through their cumulative positive count. At each terminal state,
division by its fixed \(P=A_G+t>0\), followed by optimization across states,
gives sharp endpoints: both are attained by saved feasible label completions.
The implementation scales all terms by \(\operatorname{lcm}(N_1,\ldots,N_G)\)
and uses exact integer arithmetic and rational endpoints. The dynamic program
requires \(O(Nm)\) transitions for \(m>0\) unknown labels, in addition to
sorting. All-negative completions are recorded as an undefined possibility,
not assigned AP zero. A point value is returned only when the available
constraints identify a single defined AP, including a positive complete census.
These are completion bounds, not confidence intervals or survey-weighted point
estimates; no claim of methodological priority is made.

## Synthetic diagnostic results

The interval diagnostic enumerated 795,934 sampling states. Among 39
positive-population noncensus scenarios, conditional coverage of nominal 95%
percentile intervals ranged from 22.22% to 100%; 16 scenarios were below 95%.
These counts describe the specified grid, not the frequency of failure in
arbitrary applications. All 18 positive census controls returned exact point
intervals; the two no-positive guards retained undefined AP.

For one positive in the highest tied group of five among 20 items, true AP was
0.2. Sampling four items issued an interval with probability 20%, but coverage
conditional on issuance was only \(514/969=53.04\%\). In 455 of the 969 samples
containing the positive, it was the sole sampled member of that top group;
every positive-weight bootstrap replicate then had AP one and produced the
incorrect interval \([1,1]\). In a separate unequal-strata example with two
positives, conditional coverage was 22.22%. Valid replicate weights therefore
did not establish calibration, and additional bootstrap draws cannot repair
the first counterexample.

For completion bounds, every ordered tie pattern and partial-label assignment
through six items was checked against an independent exact threshold formula:
27,993 partial configurations and 149,796 binary completions. Every fixed-total
and global endpoint and its attaining completion agreed. A further 2,667
complete-label comparisons agreed with sklearn to within \(1.12\times10^{-16}\).
An independent software review checked the proof and additional exhaustive
completions of 96 seeded toy cases. Three wholly artificial 1,998-item queues
also completed successfully; this size test used no actual external scores or
labels. The algorithm handles score ties directly: simply putting unknown
positives earliest or latest is not generally optimal for grouped-threshold AP.

## Limitations and prospective use

The bootstrap diagnostic does not estimate coverage for the planned
1,998-file, 180-case external design, establish a universal minimum sample size,
or invalidate every bootstrap method. The completion bounds answer a different
question: which AP values remain compatible with fixed known labels and the
complete score queue? They may be wide, and they supply no 95% probability
statement. Exact arithmetic does not account for reviewer error, model-training
variation, semantic dependence or unseen families. Missing model scores must
not be replaced with safe ranks; any restriction to successfully scored items
requires a separately declared estimand. Individual bounds yield only a
conservative, generally nonsharp envelope for a difference between methods.
Neither study provides external detector performance or completed expert review.

## Evidence for editorial integration

- [Frozen interval diagnostic and results](../external_protocol/performance_validation_v1/REPORT.md), including its independent verification and full prespecified grid.
- [Completion-bound definition and proof](../external_protocol/ap_bounds_v1/README.md).
- [Exact implementation validation](../external_protocol/ap_bounds_v1/RESULTS.md) and [v2 dated receipt](../external_protocol/ap_bounds_v1/run_20261026_v2/results.json).
- [Independent completion-bound review](../recovery_20261026/engineering_independent_stage2_ap_bounds_20261026_v1/result.json).

## Краткий статус для автора

Завершена проверка статистического метода на искусственных данных. Она выявила,
что предложенные 95%-е bootstrap-интервалы AP могут существенно недопокрывать
истинное значение даже при правильных весах. Поэтому их нельзя выдавать за
подтверждённую основную оценку неопределённости внешнего эксперимента.

Реализована и независимо проверена другая величина: точные достижимые границы AP
при неизвестных метках и полной очереди оценок. Это не доверительный интервал
и не замена экспертной разметки. Реальные внешние показатели моделей и экспертные
ответы этими вычислениями не получены; текущие Word и Revision 2 не изменены.
