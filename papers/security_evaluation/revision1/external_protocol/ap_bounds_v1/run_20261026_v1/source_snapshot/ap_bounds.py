"""Exact AP identification bounds for a complete finite score queue.

Known binary labels are held fixed; None/'unknown' may independently be 0 or 1.
Unsampled files must therefore appear explicitly with unknown labels. These are
logical completion bounds, not survey estimates or confidence intervals. No
Slither, corpus, annotation, score file, network or third-party library is used.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
from fractions import Fraction
import math
from numbers import Integral, Real
from typing import Iterable


@dataclass(frozen=True)
class FixedPositiveBounds:
    total_positives: int
    lower_ap: Fraction
    upper_ap: Fraction


@dataclass(frozen=True)
class APCompletionBounds:
    n: int
    known_positives: int
    unknown_count: int
    tie_groups: int
    undefined_possible: bool
    defined_completions_exist: bool
    lower_ap: Fraction | None
    upper_ap: Fraction | None
    identified_ap: Fraction | None
    census_ap: Fraction | None
    lower_completion: tuple[int, ...] | None
    upper_completion: tuple[int, ...] | None
    by_total_positives: tuple[FixedPositiveBounds, ...]
    transitions: int
    common_denominator_bits: int


@dataclass(frozen=True)
class _Group:
    size: int
    known_positives: int
    unknown_indices: tuple[int, ...]


def _inputs(scores: Iterable[Real], labels: Iterable[int | str | None]):
    score_values, label_values = list(scores), list(labels)
    if not score_values or len(score_values) != len(label_values):
        raise ValueError("A nonempty complete score queue and one label per file are required")
    checked_scores, checked_labels = [], []
    for value in score_values:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("Scores must be finite real numbers, not bools")
        value = int(value) if isinstance(value, Integral) else float(value)
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Missing/infinite scores are not supported; do not drop failed files")
        checked_scores.append(value)
    for label in label_values:
        if label is None or (isinstance(label, str) and label == "unknown"):
            checked_labels.append(None)
        elif isinstance(label, Integral) and not isinstance(label, bool) and label in (0, 1):
            checked_labels.append(int(label))
        else:
            raise ValueError("Labels must be integer 0/1, None, or 'unknown'")
    return checked_scores, checked_labels


def sharp_ap_completion_bounds(
    scores: Iterable[Real], labels: Iterable[int | str | None], *, include_witnesses: bool = True
) -> APCompletionBounds:
    """Optimize sklearn-style grouped-threshold AP over every label completion.

    Exact score equality defines ties; larger scores rank first. For P>0, AP is
    sum_g p_g * cumulative_p_g / (P * cumulative_n_g). P=0 is undefined here,
    regardless of a library convention. Returned Fraction endpoints are exact.
    Sorting costs O(N log N); DP has O(N*m) integer transitions, where m is the
    number of unknown labels (O(N) when m=0). Working values use O(m) memory;
    optional witness back-pointers use O(G*m), with G score groups. Integer bit
    complexity additionally depends on lcm(cumulative_n_g), recorded in output.
    """
    score_values, fixed_labels = _inputs(scores, labels)
    order = sorted(range(len(score_values)), key=score_values.__getitem__, reverse=True)
    groups = []
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and score_values[order[end]] == score_values[order[start]]:
            end += 1
        indices = order[start:end]
        groups.append(_Group(end - start, sum(fixed_labels[i] == 1 for i in indices),
                             tuple(i for i in indices if fixed_labels[i] is None)))
        start = end
    prefix_n = 0
    denominator = 1
    for group in groups:
        prefix_n += group.size
        denominator = math.lcm(denominator, prefix_n)

    # State t counts unknown positives in processed groups. All 0..M are feasible.
    lows, highs = [0], [0]
    low_trace, high_trace = [], []
    prefix_n = known_prefix = processed_unknown = transitions = 0
    for group in groups:
        prefix_n += group.size
        known_prefix += group.known_positives
        unknown = len(group.unknown_indices)
        scale = denominator // prefix_n
        length = processed_unknown + unknown + 1
        next_lows, next_highs = [None] * length, [None] * length
        low_choice = array("i", [-1]) * length if include_witnesses and unknown else None
        high_choice = array("i", [-1]) * length if include_witnesses and unknown else None
        for previous_t in range(processed_unknown + 1):
            for selected in range(unknown + 1):
                t = previous_t + selected
                contribution = (group.known_positives + selected) * (known_prefix + t) * scale
                low = lows[previous_t] + contribution
                high = highs[previous_t] + contribution
                if next_lows[t] is None or low < next_lows[t]:
                    next_lows[t] = low
                    if low_choice is not None:
                        low_choice[t] = selected
                if next_highs[t] is None or high > next_highs[t]:
                    next_highs[t] = high
                    if high_choice is not None:
                        high_choice[t] = selected
                transitions += 1
        lows, highs = next_lows, next_highs
        processed_unknown += unknown
        if include_witnesses:
            low_trace.append(low_choice)
            high_trace.append(high_choice)

    fixed_totals = []
    best_low_t = best_high_t = None
    for t in range(processed_unknown + 1):
        positives = known_prefix + t
        if positives == 0:
            continue
        fixed_totals.append(FixedPositiveBounds(
            positives, Fraction(lows[t], denominator * positives),
            Fraction(highs[t], denominator * positives)))
        if best_low_t is None or lows[t] * (known_prefix + best_low_t) < lows[best_low_t] * positives:
            best_low_t = t
        if best_high_t is None or highs[t] * (known_prefix + best_high_t) > highs[best_high_t] * positives:
            best_high_t = t

    def witness(t: int | None, trace) -> tuple[int, ...] | None:
        if t is None or not include_witnesses:
            return None
        completion = [0 if label is None else label for label in fixed_labels]
        for group, choices in zip(reversed(groups), reversed(trace)):
            selected = choices[t] if choices is not None else 0
            if selected < 0:
                raise RuntimeError("Unreachable witness state")
            for i in group.unknown_indices[:selected]:
                completion[i] = 1
            t -= selected
        if t != 0:
            raise RuntimeError("Witness did not return to initial state")
        return tuple(completion)

    lower = None if best_low_t is None else Fraction(lows[best_low_t], denominator * (known_prefix + best_low_t))
    upper = None if best_high_t is None else Fraction(highs[best_high_t], denominator * (known_prefix + best_high_t))
    identified = lower if lower is not None and lower == upper and known_prefix > 0 else None
    return APCompletionBounds(
        n=len(score_values), known_positives=known_prefix, unknown_count=processed_unknown,
        tie_groups=len(groups), undefined_possible=known_prefix == 0,
        defined_completions_exist=bool(fixed_totals), lower_ap=lower, upper_ap=upper,
        identified_ap=identified, census_ap=lower if processed_unknown == 0 else None,
        lower_completion=witness(best_low_t, low_trace), upper_completion=witness(best_high_t, high_trace),
        by_total_positives=tuple(fixed_totals), transitions=transitions,
        common_denominator_bits=denominator.bit_length())


def rational_record(value: Fraction | None):
    """Exact numerator/denominator, plus a clearly labelled display approximation."""
    if value is None:
        return None
    return {"numerator": str(value.numerator), "denominator": str(value.denominator),
            "decimal_approximation": float(value)}


def result_record(result: APCompletionBounds) -> dict:
    return {
        "kind": "sharp_finite_population_completion_bounds_not_confidence_interval",
        "n": result.n, "known_positives": result.known_positives,
        "unknown_count": result.unknown_count, "tie_groups": result.tie_groups,
        "undefined_possible": result.undefined_possible,
        "defined_completions_exist": result.defined_completions_exist,
        "lower_ap": rational_record(result.lower_ap), "upper_ap": rational_record(result.upper_ap),
        "identified_ap": rational_record(result.identified_ap), "census_ap": rational_record(result.census_ap),
        "lower_completion": result.lower_completion, "upper_completion": result.upper_completion,
        "by_total_positives": [{"total_positives": b.total_positives,
                                "lower_ap": rational_record(b.lower_ap), "upper_ap": rational_record(b.upper_ap)}
                               for b in result.by_total_positives],
        "transitions": result.transitions, "common_denominator_bits": result.common_denominator_bits,
    }
