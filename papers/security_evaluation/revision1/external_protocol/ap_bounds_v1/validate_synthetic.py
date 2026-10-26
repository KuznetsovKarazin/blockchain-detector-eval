"""Frozen, exhaustive synthetic validation; no empirical scores or labels."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import platform
import random
import time

from ap_bounds import sharp_ap_completion_bounds, result_record, rational_record


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def reference_ap(scores, labels):
    """Independent exact threshold definition; no DP, common LCM or tie reducer."""
    positives = sum(labels)
    if positives == 0:
        return None
    result = Fraction(0)
    for threshold in sorted(set(scores), reverse=True):
        at_threshold = sum(y for s, y in zip(scores, labels) if s == threshold)
        through_threshold = sum(y for s, y in zip(scores, labels) if s >= threshold)
        through_count = sum(s >= threshold for s in scores)
        result += Fraction(at_threshold, positives) * Fraction(through_threshold, through_count)
    return result


def score_patterns(n):
    """Every ordered tie composition of n positions, represented by integers."""
    for cuts in itertools.product((0, 1), repeat=n - 1):
        scores = [n]
        for cut in cuts:
            scores.append(scores[-1] - cut)
        yield scores


def exhaustive(max_n):
    partial_cases = completions = positive_completions = 0
    by_n = []
    for n in range(1, max_n + 1):
        n_cases = n_completions = 0
        for scores in score_patterns(n):
            for labels in itertools.product((0, 1, None), repeat=n):
                result = sharp_ap_completion_bounds(scores, labels)
                unknown = [i for i, y in enumerate(labels) if y is None]
                expected = {}
                undefined = False
                for bits in itertools.product((0, 1), repeat=len(unknown)):
                    complete = list(labels)
                    for i, bit in zip(unknown, bits):
                        complete[i] = bit
                    p = sum(complete)
                    ap = reference_ap(scores, complete)
                    completions += 1
                    n_completions += 1
                    if ap is None:
                        undefined = True
                        continue
                    positive_completions += 1
                    if p not in expected:
                        expected[p] = [ap, ap]
                    else:
                        expected[p][0] = min(expected[p][0], ap)
                        expected[p][1] = max(expected[p][1], ap)
                actual = {b.total_positives: [b.lower_ap, b.upper_ap] for b in result.by_total_positives}
                check(actual == expected, f"Fixed-P mismatch: {scores}, {labels}")
                check(result.undefined_possible == undefined, "Undefined flag mismatch")
                check(result.defined_completions_exist == bool(expected), "Defined-completion flag mismatch")
                lower = min((b[0] for b in expected.values()), default=None)
                upper = max((b[1] for b in expected.values()), default=None)
                check(result.lower_ap == lower and result.upper_ap == upper, "Global bound mismatch")
                for witness, endpoint in [(result.lower_completion, lower), (result.upper_completion, upper)]:
                    if endpoint is None:
                        check(witness is None, "Undefined case has witness")
                    else:
                        check(all(y is None or y == witness[i] for i, y in enumerate(labels)), "Witness changed known label")
                        check(reference_ap(scores, witness) == endpoint, "Endpoint not attained")
                if not unknown:
                    check(result.census_ap == reference_ap(scores, labels), "Census AP mismatch")
                check(result.identified_ap == (lower if lower == upper and not undefined else None), "Identified AP mismatch")
                partial_cases += 1
                n_cases += 1
        by_n.append({"n": n, "ordered_tie_patterns": 2 ** (n - 1), "partial_cases": n_cases,
                     "all_binary_completions_checked": n_completions})
    return {"status": "pass", "max_n": max_n, "partial_cases": partial_cases,
            "binary_completions": completions, "positive_binary_completions": positive_completions,
            "by_n": by_n}


def sklearn_agreement(max_n):
    import sklearn
    from sklearn.metrics import average_precision_score
    compared = 0
    largest_error = 0.0
    for n in range(1, max_n + 1):
        for scores in score_patterns(n):
            for labels in itertools.product((0, 1), repeat=n):
                if not any(labels):
                    continue  # P=0 intentionally has no AP in this API.
                exact = reference_ap(scores, labels)
                observed = average_precision_score(labels, scores)
                error = abs(observed - float(exact))
                check(error <= 1e-14, "sklearn disagrees with exact threshold definition")
                largest_error = max(largest_error, error)
                compared += 1
    return {"status": "pass", "sklearn_version": sklearn.__version__, "compared": compared,
            "maximum_float_absolute_error": largest_error, "comparison_tolerance": 1e-14,
            "tolerance_role": "cross-library floating display comparison only; DP endpoints remain exact Fractions"}


def permutation_checks(seed=9137, cases=100):
    rng = random.Random(seed)
    for _ in range(cases):
        n = rng.randrange(1, 13)
        scores = [rng.randrange(4) for _ in range(n)]
        labels = [rng.choice([0, 1, None]) for _ in range(n)]
        permutation = list(range(n))
        rng.shuffle(permutation)
        original = sharp_ap_completion_bounds(scores, labels)
        permuted = sharp_ap_completion_bounds([scores[i] for i in permutation], [labels[i] for i in permutation])
        check(original.by_total_positives == permuted.by_total_positives, "Permutation changed fixed-P bounds")
        check(original.lower_ap == permuted.lower_ap and original.upper_ap == permuted.upper_ap, "Permutation changed bounds")
        check(original.undefined_possible == permuted.undefined_possible, "Permutation changed undefined state")
        if permuted.lower_completion is not None:
            check(reference_ap([scores[i] for i in permutation], permuted.lower_completion) == permuted.lower_ap,
                  "Permuted witness incorrect")
    return {"status": "pass", "seed": seed, "cases": cases}


def edge_checks():
    cases = 0
    invalid = [([], []), ([1], []), ([float("nan")], [1]), ([float("inf")], [1]),
               ([1], [-1]), ([1], [0.5]), ([True], [1]), ([1], [True]), (["1"], [1]),
               ([Fraction(2**60 + 1, 2**60), Fraction(1)], [1, 0])]
    for scores, labels in invalid:
        try:
            sharp_ap_completion_bounds(scores, labels)
        except ValueError:
            cases += 1
        else:
            raise AssertionError("Invalid input accepted")
    a = sharp_ap_completion_bounds([1], [0])
    check(a.undefined_possible and not a.defined_completions_exist and a.lower_ap is None and a.census_ap is None,
          "All-negative census must be undefined")
    b = sharp_ap_completion_bounds([1], [None])
    check(b.undefined_possible and b.lower_ap == b.upper_ap == 1 and b.identified_ap is None,
          "Unknown singleton must retain undefined possibility")
    c = sharp_ap_completion_bounds([2**60 + 1, 2**60], [0, 1])
    check(c.census_ap == Fraction(1, 2) and c.tie_groups == 2, "Large integers collapsed into float tie")
    d = sharp_ap_completion_bounds([2, 1], [1, "unknown"], include_witnesses=False)
    check(d.identified_ap == 1 and d.census_ap is None and d.lower_completion is None,
          "Identified-but-not-census behavior wrong")
    return {"status": "pass", "invalid_inputs_rejected": cases, "additional_edge_cases": 4}


def counterexamples():
    # Fixed k=1: neither earliest-max nor latest-min survives tied-score AP.
    scores = [2, 2, 1, 1, 1]
    partial = [None, 0, 1, 1, None]
    result = sharp_ap_completion_bounds(scores, partial)
    earliest = reference_ap(scores, [1, 0, 1, 1, 0])
    latest = reference_ap(scores, [0, 0, 1, 1, 1])
    check(earliest == Fraction(17, 30) < latest == Fraction(3, 5), "Counterexample calculation wrong")
    fixed = {b.total_positives: b for b in result.by_total_positives}[3]
    check(fixed.lower_ap == earliest and fixed.upper_ap == latest, "DP missed counterexample")
    second = sharp_ap_completion_bounds([1, 1, 1, 0, 0, 0], [None] * 6)
    fixed_three = {b.total_positives: b for b in second.by_total_positives}[3]
    check(fixed_three.lower_ap == Fraction(4, 9) and fixed_three.upper_ap == 1, "Six-file counterexample wrong")
    return {"status": "pass", "five_file_scores": scores, "five_file_partial_labels": partial,
            "earliest_assignment_ap": rational_record(earliest), "latest_assignment_ap": rational_record(latest),
            "five_file_exact_bounds": result_record(result),
            "six_file_fixed_three_min": rational_record(fixed_three.lower_ap),
            "six_file_latest_three_ap": rational_record(Fraction(1, 2))}


def large_synthetic(n):
    cases = []
    for name, scores in [("unique_scores_all_unknown", list(range(n, 0, -1))),
                         ("two_tie_groups_all_unknown", [1] * (n // 2) + [0] * (n - n // 2)),
                         ("one_tie_group_all_unknown", [1] * n)]:
        before = time.perf_counter()
        result = sharp_ap_completion_bounds(scores, [None] * n)
        elapsed = time.perf_counter() - before
        check(result.lower_ap == Fraction(1, n) and result.upper_ap == 1 and result.undefined_possible,
              "Large all-unknown endpoints incorrect")
        check(reference_ap(scores, result.lower_completion) == result.lower_ap, "Large lower witness wrong")
        check(reference_ap(scores, result.upper_completion) == result.upper_ap, "Large upper witness wrong")
        cases.append({"name": name, "n": n, "tie_groups": result.tie_groups,
                      "transitions": result.transitions, "common_denominator_bits": result.common_denominator_bits,
                      "elapsed_seconds": elapsed, "lower_ap": rational_record(result.lower_ap),
                      "upper_ap": rational_record(result.upper_ap), "undefined_possible": True,
                      "lower_witness_positives": sum(result.lower_completion),
                      "upper_witness_positives": sum(result.upper_completion)})
    return {"status": "pass", "cases": cases, "scope": "synthetic computational feasibility, not empirical performance"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(output):
    if output.exists():
        raise FileExistsError("Use a new frozen run directory")
    output.mkdir(parents=True)
    source = Path(__file__).parent
    snapshot = output / "source_snapshot"
    snapshot.mkdir()
    paths = [source / "ap_bounds.py", Path(__file__)]
    manifest = {}
    for path in paths:
        (snapshot / path.name).write_bytes(path.read_bytes())
        manifest[path.name] = sha(path)
    config = {"schema": "ap_completion_bounds_synthetic_validation_v1", "prepared_date": "2026-10-26",
              "prepared_utc": datetime.now(timezone.utc).isoformat(), "sources": manifest,
              "max_exhaustive_n": 6, "max_sklearn_n": 6, "permutation_seed": 9137,
              "permutation_cases": 100, "large_synthetic_n": 1998,
              "arithmetic": "exact_integer_LCM_dynamic_programming_and_Fraction_endpoints",
              "human_labels_used": 0, "empirical_scores_used": 0, "confidence_interval_claim": False}
    (output / "config_before_run.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    print("Prepared new synthetic-only frozen run", output)


def run(output):
    if (output / "results.json").exists():
        raise FileExistsError("Results already exist; do not overwrite")
    config_path = output / "config_before_run.json"
    config = json.loads(config_path.read_text())
    for name, expected in config["sources"].items():
        check(sha(Path(__file__).parent / name) == expected, "Current source changed after freeze")
        check(sha(output / "source_snapshot" / name) == expected, "Source snapshot mismatch")
    before = time.perf_counter()
    results = {"schema": "ap_completion_bounds_validation_results_v1", "started_utc": datetime.now(timezone.utc).isoformat(),
               "config_sha256": sha(config_path), "python_version": platform.python_version(),
               "edge_checks": edge_checks(), "counterexamples": counterexamples()}
    results["exhaustive"] = exhaustive(config["max_exhaustive_n"])
    print("Exhaustive checks passed", results["exhaustive"]["partial_cases"], flush=True)
    results["sklearn_agreement"] = sklearn_agreement(config["max_sklearn_n"])
    results["permutations"] = permutation_checks(config["permutation_seed"], config["permutation_cases"])
    results["large_synthetic"] = large_synthetic(config["large_synthetic_n"])
    results.update(status="pass", elapsed_seconds=time.perf_counter() - before,
                   completed_utc=datetime.now(timezone.utc).isoformat(), human_labels_used=0, empirical_scores_used=0,
                   scope="exact finite-population logical completion bounds, not confidence coverage")
    (output / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print("PASS", output / "results.json", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "run"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    (prepare if args.action == "prepare" else run)(args.output)
