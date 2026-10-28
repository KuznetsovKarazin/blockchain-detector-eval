"""Read-only arithmetic/source audit of the stage-3 scientific claims.

Reads saved aggregate/per-file compiler metadata, synthetic results and prose.
No corpus bodies, private review keys, compiler execution or model fitting.
This does not replace the earlier full independent computation checks.
"""
from pathlib import Path
from collections import Counter
from fractions import Fraction
from math import comb, isclose
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / 'papers/security_evaluation/revision1'
HERE = Path(__file__).resolve().parent
EXPECTED_DRAFT = '89a6acafb4a0ea941d20f77ba45110ca49f693086046adc07715fe22b9ff068a'
checked = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checked.append(name)


def main():
    draft = ROOT / 'papers/security_evaluation/manuscript/DRAFT_REVISION3.md'
    text = draft.read_text()
    check('reviewed_manuscript_hash', sha(draft) == EXPECTED_DRAFT)
    check('bootstrap_original_design_distinguished_from_resampling',
          'rescaled bootstrap for stratified sampling without replacement' in text)
    check('references_18_and_19_present', '[18] Emine Yilmaz' in text and
          '[19] Household Finance and Consumption Network (2023)' in text)

    compiler_path = BASE / 'external_protocol/compiler_preflight_v1/plan_20261026_v2/execution_results/per_file_status.json'
    compiler = json.loads(compiler_path.read_text())
    check('compiler_rows_unique', len({r['job_id'] for r in compiler}) == len(compiler) == 2689)
    cohorts = {}
    for cohort, expected in [('external', (1998, 1968, 1807, 0, 10)),
                             ('train', (691, 336, 330, 101, 10))]:
        rows = [r for r in compiler if r['cohort'] == cohort]
        ok = [r for r in rows if r['success']]
        actual = (len(rows), sum(bool(r['attempts']) for r in rows), len(ok),
                  sum(r['attempts'][-1]['nonempty_bytecode_contracts'] == 0 for r in ok),
                  sum(r['attempts'][-1]['unlinked_bytecode_contracts'] > 0 for r in ok))
        check(cohort + '_compiler_counts', actual == expected)
        cohorts[cohort] = dict(zip(['fixed_files', 'attempted_files', 'successful_files',
                                   'successful_no_nonempty_root_bytecode', 'successful_unlinked'], actual))
        cohorts[cohort]['statuses'] = dict(Counter(r['status'] for r in rows))
        cohorts[cohort]['success_percent_fixed'] = round(100 * actual[2] / actual[0], 2)
        cohorts[cohort]['success_percent_attempted'] = round(100 * actual[2] / actual[1], 2)
    statuses = Counter(r['status'] for r in compiler)
    check('compiler_success_total', statuses['compiler_success'] == 2137)
    check('compiler_final_errors', statuses['compiler_error'] == 167)
    check('compiler_unavailable_total', sum(not r['attempts'] for r in compiler) == 385)
    imports = {'missing_import', 'import_outside_snapshot', 'import_syntax_unresolved',
               'remote_or_absolute_import_forbidden'}
    check('training_import_context_failures',
          sum(r['status'] in imports for r in compiler if r['cohort'] == 'train') == 346)
    check('compiler_percentages',
          [cohorts['external']['success_percent_fixed'], cohorts['external']['success_percent_attempted'],
           cohorts['train']['success_percent_fixed'], cohorts['train']['success_percent_attempted'],
           round(100 * 2137 / 2689, 2)] == [90.44, 91.82, 47.76, 98.21, 79.47])

    summary_path = BASE / 'external_protocol/performance_validation_v1/run_20261026_v1/summary.csv'
    with summary_path.open() as f:
        all_rows = list(csv.DictReader(f))
    rows = [r for r in all_rows if r['method'] == 'exact_support']
    check('coverage_scenario_method_counts', len(all_rows) == 236 and len(rows) == 59)
    check('exact_sample_states', sum(int(r['exact_sample_states']) for r in rows) == 795934)
    noncensus = [r for r in rows if int(r['K']) > 0 and r['design'] != 'census']
    census = [r for r in rows if int(r['K']) > 0 and r['design'] == 'census']
    zero = [r for r in rows if int(r['K']) == 0]
    coverages = [float(r['coverage_conditional_on_issued']) for r in noncensus]
    check('coverage_positive_noncensus', len(noncensus) == 39)
    check('coverage_noncensus_below_nominal', sum(c < .95 for c in coverages) == 16)
    check('coverage_range', isclose(min(coverages), 2 / 9) and max(coverages) == 1)
    check('coverage_census', len(census) == 18 and all(float(r['coverage_conditional_on_issued']) == 1 for r in census))
    check('coverage_no_positive_guards', len(zero) == 2 and all(float(r['interval_issuance_probability']) == 0 for r in zero))
    check('positive_sample_replicates_all_valid', all(float(r['invalid_replicate_fraction_positive_samples']) == 0 for r in noncensus))
    witness = next(r for r in rows if r['scenario'] == 'N20_srs4_blocks5_one_top')
    positive_samples, forced_misses = comb(19, 3), comb(15, 3)
    conditional = Fraction(positive_samples - forced_misses, positive_samples)
    joint = Fraction(positive_samples - forced_misses, comb(20, 4))
    check('analytic_counterexample_combinatorics',
          positive_samples == 969 and forced_misses == 455 and conditional == Fraction(514, 969))
    check('analytic_counterexample_matches_summary',
          float(witness['true_population_ap']) == .2 and
          float(witness['interval_issuance_probability']) == .2 and
          isclose(float(witness['coverage_conditional_on_issued']), float(conditional)) and
          isclose(float(witness['unconditional_issued_and_covering_probability']), float(joint)))

    bounds_path = BASE / 'external_protocol/ap_bounds_v1/run_20261026_v2/results.json'
    bounds = json.loads(bounds_path.read_text())
    expected_cases = sum(2 ** (n - 1) * 3 ** n for n in range(1, 7))
    expected_completions = sum(2 ** (n - 1) * 4 ** n for n in range(1, 7))
    check('DP_partial_case_combinatorics', expected_cases == 27993 == bounds['exhaustive']['partial_cases'])
    check('DP_binary_completion_combinatorics', expected_completions == 149796 == bounds['exhaustive']['binary_completions'])
    api = BASE / 'external_protocol/ap_bounds_v1/ap_bounds.py'
    api_snapshot = BASE / 'external_protocol/ap_bounds_v1/run_20261026_v2/source_snapshot/ap_bounds.py'
    check('AP_bounds_API_unchanged', sha(api) == sha(api_snapshot) == '71147a09cec0f755a735224f127ef379d7b4e78c17094d3ee48c3635df54ef2c')
    performance = BASE / 'external_protocol/performance_v1/performance.py'
    check('performance_v1_unchanged', sha(performance) == 'b5bdd17f6e90b0456b03ca64a5d528e53927437a9d72cfef0d9d962316e46d9b')
    results_md = BASE / 'external_protocol/ap_bounds_v1/RESULTS.md'
    check('editorial_correction_exact_document', sha(results_md) == '3169f6a62d890c92594fefe73c90e0b5f1e5bb2f53f931a869ab591137eb7fbe')
    sources = json.loads((HERE / 'PRIMARY_SOURCES.json').read_text())
    check('short_primary_source_quotations', all(len(s['short_exact_support'].split()) <= 25 for s in sources['sources']))
    relevant = [draft, compiler_path, summary_path, bounds_path, api, api_snapshot,
                performance, results_md, HERE / 'PRIMARY_SOURCES.json', Path(__file__).resolve()]
    receipt = {
        'status': 'PASS', 'review_date': '2026-10-26', 'checks_passed': len(checked),
        'checks': checked, 'manuscript_sha256': EXPECTED_DRAFT,
        'scope': 'Independent metadata arithmetic, source identity, mathematical reading and primary literature review; not a rerun of underlying experiments.',
        'new_fits': 0, 'new_compiler_runs': 0, 'private_review_keys_read': False,
        'corpus_source_bodies_read': False, 'human_adjudications': 0,
        'compiler_cohorts': cohorts,
        'counterexample': {'conditional_coverage': str(conditional), 'issued_and_covering': str(joint),
                           'forced_miss_given_positive_sample': str(Fraction(forced_misses, positive_samples))},
        'editorial_correction': {'path': str(results_md.relative_to(ROOT)),
            'old_sha256': '1d465674d7458a0fc9d2bd45594c7724d86abdf6cb9e788b60ed6b77ee891b89',
            'new_sha256': sha(results_md), 'authorized_by': 'parent /root explicit message',
            'reason': 'Estimator and logical completion envelope can target the same finite-population AP.'},
        'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in relevant},
        'manual_scope_assessment': 'No material scientific blocker in R3 additions. No priority claim, AP coverage guarantee, actual external accuracy, semantic identity or universal split-impossibility claim inferred.'
    }
    out = HERE / 'CHECKS.json'
    if out.exists():
        raise FileExistsError('Preserve existing receipt; review changed draft in a separately named file.')
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'status': receipt['status'], 'checks_passed': len(checked),
                      'manuscript_sha256': EXPECTED_DRAFT, 'receipt_sha256': sha(out)}))


if __name__ == '__main__':
    main()
