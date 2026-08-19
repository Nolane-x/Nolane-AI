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
    (101.0, 103.0, 107.0), (-109.0, 113.0, 127.0),
    (131.0, -137.0, 139.0), (149.0, 151.0, -157.0),
    (-163.0, -167.0, 173.0), (179.0, -181.0, -191.0),
)


def _contexts() -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(FIELDS, row, strict=True)) for row in ROWS)


def _oracle(row: Mapping[str, object]) -> float:
    a = float(row['a'])
    b = float(row['b'])
    c = float(row['c'])
    return a * b + b * c + c * a


def _need(label: str) -> OperatorInventionNeed:
    return OperatorInventionNeed(label, FIELDS, 'out', constants=(0.0,), max_depth=4, max_candidates=50_000)


def _run(oracle, *, need: OperatorInventionNeed):
    rows = _contexts()
    return r267.synthesize_three_probe_causal_program(
        oracle, FIELDS, need, rows[:12], rows[12:18], terminal_contexts=rows[18:24],
        intervention_anchor_values=(0.0,), intervention_arity=1,
        composition_constants=(0.0,), composition_max_depth=3,
        composition_max_candidates_per_triplet=20_000, max_composition_candidates_total=20_000,
        ablation_max_candidates=12_000, composition_beam_width=128,
        probe_constants=(0.0,), probe_max_depth=2, probe_max_candidates=20_000, probe_beam_width=128,
    )


def test_probe_synthesis_midstream_failure_reports_only_observed_validation_cases(monkeypatch) -> None:
    original = r267._synthesize_r267_expression
    probe_calls = 0

    def fail_second_probe(field_names, constants, examples, *, max_depth, max_candidates, beam_width):
        nonlocal probe_calls
        names = tuple(map(str, field_names))
        if not any(name.startswith('__p') for name in names):
            probe_calls += 1
            if probe_calls == 2:
                return r267._ExpressionSearchReceipt(False, None, 1, 0, 0, 'synthetic_probe_synthesis_failure')
        return original(field_names, constants, examples, max_depth=max_depth, max_candidates=max_candidates, beam_width=beam_width)

    monkeypatch.setattr(r267, '_synthesize_r267_expression', fail_second_probe)
    receipt = _run(_oracle, need=_need('R2.67.1 partial probe receipt accounting'))
    assert receipt.passed is False
    assert receipt.reason == 'probe_synthesis_failed'
    assert len(receipt.probe_expressions) == 1
    assert receipt.probe_validation_exact == 6
    assert receipt.probe_validation_cases == 6
    assert receipt.probe_validation_exact <= receipt.probe_validation_cases
    assert receipt.terminal_probe_validation_cases == 0
    assert receipt.final_validation_cases == 0


def test_terminal_probe_error_reports_only_attempted_terminal_cases() -> None:
    first_terminal = _contexts()[18]

    def terminal_failing_oracle(row: Mapping[str, object]) -> float:
        values = {field: float(row[field]) for field in FIELDS}
        nonzero_matches = sum(values[field] == float(first_terminal[field]) for field in FIELDS if values[field] != 0.0)
        zero_fields = sum(values[field] == 0.0 for field in FIELDS)
        if zero_fields == 1 and nonzero_matches == 2:
            raise ValueError('synthetic terminal intervention oracle failure')
        return _oracle(row)

    receipt = _run(terminal_failing_oracle, need=_need('R2.67.1 terminal partial receipt accounting'))
    assert receipt.passed is False
    assert receipt.reason == 'independent_terminal_verification_error'
    assert receipt.probe_validation_cases == 18
    assert receipt.probe_validation_exact == 18
    assert receipt.terminal_probe_validation_cases == 1
    assert receipt.terminal_probe_validation_exact == 0
    assert receipt.final_validation_cases == 0
    assert receipt.final_validation_exact == 0
