from __future__ import annotations

# Post-fix independent replay against production R2.66 base 0edec9cddc47542eb7cf902f82f771e026bbb352.

from collections.abc import Mapping

from cogcoder.r266_learned_contextual_composition import discover_contextual_composition_structure


def _band_select(context: Mapping[str, object]) -> float:
    x = float(context['x'])
    lo = float(context['lo'])
    hi = float(context['hi'])
    if x < lo:
        return float(context['left'])
    if x > hi:
        return float(context['right'])
    return float(context['middle'])


def _rows() -> tuple[dict[str, float], ...]:
    configs = (
        (-3.0, 2.0, -7.0, 4.0, -5.0),
        (-1.0, 4.0, 6.0, -3.0, 9.0),
        (-5.0, 1.0, -8.0, 5.0, 2.0),
        (0.0, 6.0, 3.0, -6.0, -4.0),
        (-4.0, 3.0, 8.0, 2.0, -9.0),
        (-2.0, 5.0, -6.0, -1.0, 7.0),
    )
    rows: list[dict[str, float]] = []
    for lo, hi, left, middle, right in configs:
        for x in (lo - 3.0, lo, (lo + hi) / 2.0, hi, hi + 3.0):
            rows.append({
                'x': x,
                'lo': lo,
                'hi': hi,
                'left': left,
                'middle': middle,
                'right': right,
            })
    return tuple(rows)


def test_nonfinite_intervention_oracle_result_fails_closed_globally() -> None:
    rows = _rows()
    calls = 0
    intervention_failures = 0

    def oracle(context: Mapping[str, object]) -> float:
        nonlocal calls, intervention_failures
        calls += 1
        # No original row has middle==0.0. This condition is reached only when
        # the authorized 0-anchor intervention overwrites the middle field.
        if float(context['middle']) == 0.0:
            intervention_failures += 1
            return float('nan')
        return _band_select(context)

    result = discover_contextual_composition_structure(
        oracle,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        (0.0,),
        rows[:18],
        rows[18:24],
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12_000,
        max_composition_candidates_total=120_000,
    )

    assert intervention_failures > 0
    assert result.oracle_calls == calls
    assert result.passed is False
    assert result.selected is None
    assert result.reason.startswith('oracle_error:')
    assert result.false_accepts == 0
