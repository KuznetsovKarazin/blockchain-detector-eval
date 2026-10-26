"""Independently enumerate rescaled-bootstrap linear-total moments.

This validates a proposed mathematical formula, not AP interval coverage or
the production implementation. All populations and draws here are synthetic.
"""
from functools import lru_cache
import hashlib
from itertools import combinations
import json
from math import factorial, sqrt
from pathlib import Path
import numpy as np


def compositions(total, parts):
    if parts == 1:
        yield (total,)
    else:
        for first in range(total + 1):
            for remaining in compositions(total - first, parts - 1):
                yield (first,) + remaining


@lru_cache(None)
def multinomial_support(n):
    m = n - 1
    counts = np.asarray(list(compositions(m, n)), dtype=float)
    probabilities = np.asarray([factorial(m) / np.prod([factorial(int(x)) for x in row]) / n ** m
                                for row in counts])
    assert np.isclose(probabilities.sum(), 1)
    return counts, probabilities


def run():
    cases = samples = replicates = 0
    maximum_conditional_error = maximum_design_error = 0.0
    for N in range(2, 9):
        populations = [np.r_[np.ones(K), np.zeros(N-K)] for K in range(N+1)]
        populations.append(np.arange(N, dtype=float) ** 2 - 3)
        for population in populations:
            for n in range(2, N+1):
                estimates, bootstrap_variances = [], []
                counts, probabilities = multinomial_support(n)
                f = n / N
                for chosen in combinations(range(N), n):
                    y = population[list(chosen)]
                    estimate = N * y.mean()
                    if n == N:
                        replicate_totals = np.array([estimate])
                        mean, variance = estimate, 0.0
                    else:
                        multipliers = 1-sqrt(1-f)+sqrt(1-f)*n/(n-1)*counts
                        assert np.all(multipliers > 0)
                        assert np.allclose(multipliers.sum(axis=1), n)
                        replicate_totals = (multipliers @ y) * N/n
                        mean = float(probabilities @ replicate_totals)
                        variance = float(probabilities @ ((replicate_totals-mean)**2))
                    expected_variance = N*N*(1-f)*float(np.var(y, ddof=1))/n
                    assert np.isclose(mean, estimate, rtol=1e-12, atol=1e-12)
                    assert np.isclose(variance, expected_variance, rtol=1e-12, atol=1e-10)
                    maximum_conditional_error = max(maximum_conditional_error, abs(variance-expected_variance))
                    estimates.append(estimate)
                    bootstrap_variances.append(variance)
                    samples += 1
                    replicates += len(replicate_totals)
                actual_design_variance = float(np.var(estimates))
                expected_bootstrap_variance = float(np.mean(bootstrap_variances))
                assert np.isclose(np.mean(estimates), population.sum(), rtol=1e-12, atol=1e-12)
                assert np.isclose(actual_design_variance, expected_bootstrap_variance, rtol=1e-12, atol=1e-10)
                maximum_design_error = max(maximum_design_error, abs(actual_design_variance-expected_bootstrap_variance))
                cases += 1
    return {'schema':'independent_rescaled_bootstrap_linear_variance_v1', 'status':'pass',
        'formula':'w_i*[1-sqrt(1-n/N)+sqrt(1-n/N)*n/(n-1)*M_i], M~Multinomial(n-1,1/n)',
        'linear_total_conditional_variance':'N^2*(1-n/N)*sample_variance(y,ddof=1)/n',
        'population_size_range':[2,8], 'sample_size_range':'2..N; census handled deterministically',
        'populations':'all binary positive counts plus y_i=i^2-3 for each N',
        'finite_population_design_cases':cases, 'all_srs_samples_enumerated':samples,
        'multinomial_count_configurations_evaluated':replicates,
        'maximum_absolute_conditional_variance_error':maximum_conditional_error,
        'maximum_absolute_design_variance_error':maximum_design_error,
        'all_samples_have_expected_replicate_total_equal_point_estimate':True,
        'mean_conditional_bootstrap_variance_equals_true_srs_design_variance':True,
        'production_implementation_tested':False, 'ap_interval_coverage_tested':False,
        'actual_scores_or_human_judgments_used':0,
        'limits':['No proof of nominal nonlinear AP confidence-interval coverage',
                  'Noncensus n=1 has unidentified variance and must fail closed',
                  'Positive baseline weight means no zero-positive replicate is not an adequacy test',
                  'Independent strata permit addition of these variance components; no extra cluster sampling stage is assumed'],
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == '__main__':
    destination = Path(__file__).with_name('independent_variance_enumeration.json')
    assert not destination.exists(), 'Preserve prior receipts; choose a new file for a later check'
    result = run()
    destination.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, indent=2))
