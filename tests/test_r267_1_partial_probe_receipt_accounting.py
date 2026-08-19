from __future__ import annotations

from collections.abc import Mapping

import cogcoder.r267_three_probe_causal_composition as r267
from cogcoder.r256_operator_invention import OperatorInventionNeed


FIELDS = ('a', 'b', 'c')
ROWS = (
    (1.0, 2.0, 0.0), (2.0, 3.0, 0.0),
    (1.0, 0.0, 2.0), (2.0, 0.0, 3.0),
    (0.0, 1.0, 2.0), (0.0, 2.0, 3.0),
    (1.0, 2.0, 3.0), (4.0, 2.0, 3.0),
    (2.0, 1.0, 3.0), (2.0, 4.0, 3.0),
    (2.0, 3.0, 1.0), (2.0, 3.0, 4.0),
    (-2.0, 5.0, 3.0), (4.0, -3.0, 2.0),
    (5.0, 2.0, -4.0), (-3.0, -2.0, 6.0),
    (7.0, -1.0, -5.0), (-4.0, 6.0, -2.0),
    (3.0, 5.0, -2.0), (-5.0, 4.0, 7.0),
    (6.0, -3.0, -4.0), (-7.0, -2.0, 5.0),
    (8.0, 3.0, -6.0), (-6.0, 9.0, 2.0),
)


def _contexts() -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(FIELDS, row, strict=True)) for row in ROWS)


def _oracle(row: Mapping[str, object]) -> float:
    a = float(row['a'])
    b = float(row['b'])
    c = float(row['c'])
    return a * b + b * c + c * a


def test_probe_synthesis_midstream_failure_reports_only_observed_validation_cases(monkeypatch) -> None:
    """Receipt case counts must describe observations actually attempted, not planned work."""
    rows = _contexts()
    discovery, validation, terminal = rows[:12], rows[12:18], rows[18:24]
    need = OperatorInventionNeed(
        'R2.67.1 partial probe receipt accounting',
        FIELDS,
        'out',
        constants=(0.0,),
        max_depth=4,
        max_candidates=50_000,
    )

    original = r267._synthesize_r267_expression
    probe_calls = 0

    def fail_second_probe(field_names, constants, examples, *, max_depth, max_candidates, beam_width):
        nonlocal probe_calls
        names = tuple(map(str, field_names))
        if not any(name.startswith('__p') for name in names):
            probe_calls += 1
            if probe_calls == 2:
                return r267._ExpressionSearchReceipt(
                    False,
                    None,
                    1,
                    0,
                    0,
                    'synthetic_probe_synthesis_failure',
                )
        return original(
            field_names,
            constants,
            examples,
            max_depth=max_depth,
            max_candidates=max_candidates,
            beam_width=beam_width,
        )

    monkeypatch.setattr(r267, '_synthesize_r267_expression', fail_second_probe)
    receipt = r267.synthesize_three_probe_causal_program(
        _oracle,
        FIELDS,
        need,
        discovery,
        validation,
        terminal_contexts=terminal,
        intervention_anchor_values=(0.0,),
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=20_000,
        max_composition_candidates_total=20_000,
        ablation_max_candidates=12_000,
        composition_beam_width=128,
        probe_constants=(0.0,),
        probe_max_depth=2,
        probe_max_candidates=20_000,
        probe_beam_width=128,
    )

    assert receipt.passed is False
    assert receipt.reason == 'probe_synthesis_failed'
    assert len(receipt.probe_expressions) == 1
    assert receipt.probe_validation_exact == len(validation)
    assert receipt.probe_validation_cases == len(validation)
    assert receipt.probe_validation_exact <= receipt.probe_validation_cases
