# Exact finite-population AP completion bounds

Prepared 26 October 2026. This is a standalone, synthetic-only alternative for
describing what incomplete reference labels identify. It is **not a repair of
bootstrap confidence coverage**, a survey-weighted estimator, a new external
experiment, or a claim of mathematical priority. No protocol mapping, frozen
empirical result, reviewer packet or manuscript is changed.

## Defined quantity

Supply one **finite, nonmissing score for every item in a declared finite
population**, and a label in `{0, 1, unknown}` for every item. All unsampled or
unresolved labels are unknown. Known expert labels are treated as fixed, correct
constraints for this calculation; possible expert error is outside its scope.
Larger scores rank first; exact equality of accepted integer/native binary64
float values defines ties. Other real types, such as `Fraction`, are rejected
rather than silently rounded to binary64 and potentially merged into ties.

Let score groups be ordered from highest to lowest. Group `g` has `n_g` files,
`a_g` known positives and `u_g` unknowns. Write `N_g` for cumulative files,
`A_g` for cumulative known positives, and choose `z_g` unknown positives in
`0..u_g`. Then `p_g=a_g+z_g`, cumulative positives are `T_g`, and for total
`P>0` the grouped-threshold average precision is

\[
\operatorname{AP}=\frac{1}{P}\sum_g \frac{p_g T_g}{N_g}.
\]

This is the average-precision definition used by sklearn for tied scores,
not trapezoidal PR area or expected AP after randomly breaking ties. If `P=0`,
AP is **undefined in this API**. A library's zero-valued convention is not
substituted. The result separately reports whether an all-negative completion
is possible, whether any positive completion exists, and extrema over the
positive completions only.

Endpoints are sharp: each is attained by a feasible completion. The interval
between them is an envelope; not every real number inside need be attainable.
No probabilities, inclusion weights, 95% coverage, new-family inference or
method superiority follow from this envelope. Unknown labels need not be
missing at random. Failed or missing model scores are rejected, not assigned
synthetic ranks; any restricted analysis population must be declared externally.

## Why the proposed greedy rule fails with ties

For scores `[2,2,1,1,1]` and partial labels `[?,0,1,1,?]`, fix one unknown
positive. Assigning it to the earliest unknown yields
`(1/3)(1/2)+(2/3)(3/5)=17/30`; assigning it to the latest gives `3/5`.
Thus earliest does not maximize and latest does not minimize AP.

A second example has scores `[1,1,1,0,0,0]`, all labels unknown, and three
positives. Putting all three in the lower group gives `1/2`; placing one in
the upper and two in the lower gives `4/9`, which is smaller. A move changes
the recall mass assigned to each group-end precision. An exchange argument
valid for strict ranks cannot silently be transferred to grouped-threshold AP.

## Exact dynamic program and proof

After group `g`, let `t` be the cumulative number of unknowns assigned positive.
Let `F_g^min(t)` and `F_g^max(t)` be the minimum and maximum **AP numerator**
`sum p_j*T_j/N_j` over such prefixes. The initial state is `F_0(0)=0`.
For each feasible `z` in the current group,

\[
F_g^{\min/\max}(t)=\min/\max_z\left\{
F_{g-1}^{\min/\max}(t-z)
+\frac{(a_g+z)(A_g+t)}{N_g}\right\}.
\]

Proof by induction: every feasible prefix has exactly one such previous count
and current-group count. Conversely, any feasible previous completion can be
extended with any `z` between zero and `u_g`; within a tied group, the identities
of the selected unknown slots do not affect AP. The added term depends on the
previous completion only through its cumulative count. Therefore retaining the
two extreme numerators per count discards no possible optimum, and stored
choices construct completions attaining them. This establishes the recurrence.

At the last group, the denominator is `P=A_G+t`, fixed within a terminal state.
For each `P>0`, dividing its extreme numerators by `P` gives sharp fixed-total
bounds. Minimizing and maximizing across these terminal states gives the global
sharp endpoints. The terminal state `P=0` is excluded from arithmetic and recorded
as `undefined_possible`, not an AP of zero. This also proves that a fully known,
positive census returns exactly its ordinary AP.

The implementation uses `L=lcm(N_1,...,N_G)`. Each transition adds the integer
`(a_g+z)*(A_g+t)*(L/N_g)`. All comparisons are integer comparisons, and final
endpoints are Python `Fraction` values. There is **no floating-point DP** or
rounding tolerance in the mathematical bounds. JSON preserves exact numerator
and denominator strings; `decimal_approximation` is for display only.

Let `m=sum u_g`, and `M_(g-1)` be prior unknowns. The number of transitions is
`sum_g (M_(g-1)+1)*(u_g+1)`. The cross-term
`sum_g M_(g-1)*u_g=(m²-sum_g u_g²)/2`, and
`sum_g M_(g-1)<=G*m`. Thus the DP uses `O(G*m+m²+G+m)`, hence `O(N*m)`
transitions for `m>0`, plus sorting `O(N log N)`. For a census, DP work is linear
after sorting. This counts integer operations; their bit cost depends on `L`.
Working DP arrays use `O(m)` values; optional witness traces use `O(G*m)` slots.

## API and validation

`ap_bounds.sharp_ap_completion_bounds(scores, labels)` returns exact global and
fixed-total bounds, endpoint label completions in the original input order,
undefined/defined flags, and transition counts. `identified_ap` is supplied only
when the complete set of feasible outcomes identifies one defined AP;
`census_ap` requires no unknown labels. There is no arbitrary point estimate for
a partially identified AP. `include_witnesses=False` omits trace storage.

The dated configuration under `run_20261026_v2/` is saved before execution and
pins both source snapshots. Validation enumerates every ordered tie composition,
every partial binary/unknown vector, and every binary completion for `N=1..6`.
An independent rational threshold evaluator checks every fixed-positive-count
bound, global endpoint, witness, and undefined state. Separate checks compare
the formula with sklearn for all positive complete labels in that grid, validate
permutations and invalid inputs, and time three wholly synthetic 1,998-item
queues. Exact fraction equality controls correctness; the sklearn float tolerance
only checks numerical agreement with a library implementation.

Run from the repository root with a fresh directory:

```bash
python papers/security_evaluation/revision1/external_protocol/ap_bounds_v1/validate_synthetic.py prepare /tmp/ap_bounds_fresh
python papers/security_evaluation/revision1/external_protocol/ap_bounds_v1/validate_synthetic.py run /tmp/ap_bounds_fresh
```

These checks use no real source code, model score or expert response. The
independent proof/code review and dated result receipt, when present, specify
their own scope. Applying separate bounds to two methods yields the conservative
difference envelope `[L_A-U_B, U_A-L_B]`; it is generally **not sharp**, because
the endpoint completions need not agree across methods. No paired sharp-bound
solver is claimed or implemented here.

`run_20261026_v1/` preserves the initial complete synthetic run and source
snapshots. After that run, input review found that accepting arbitrary
`numbers.Real` values and converting them to float could merge distinct
high-precision scores. The explicit input-type restriction and its regression
case are a separately frozen v2 amendment; the integer DP and all previously
tested inputs retain their definitions. Neither run uses empirical data.
