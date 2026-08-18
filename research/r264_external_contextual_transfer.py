from __future__ import annotations

import hashlib
import json
import math
from typing import Callable

from cogcoder.r256_operator_dsl import evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r264_learned_contextual_composition import synthesize_contextual_composition_program


def _rows() -> tuple[dict[str, float], ...]:
    configs = (
        (-4.0, -9.0, 3.0, -6.0),
        (-3.0, 8.0, -5.0, 2.0),
        (-2.0, -7.0, 6.0, 9.0),
        (-1.0, 5.0, -8.0, -3.0),
        (0.0, -6.0, 4.0, 7.0),
        (1.0, 9.0, -2.0, -5.0),
        (2.0, -4.0, 7.0, 3.0),
        (3.0, 6.0, -9.0, 8.0),
        (4.0, -8.0, 5.0, -2.0),
        (-5.0, 7.0, -4.0, 6.0),
        (5.0, -3.0, 8.0, -7.0),
        (-6.0, 4.0, -6.0, 5.0),
        (6.0, -5.0, 9.0, -4.0),
        (-7.0, 3.0, -7.0, 4.0),
        (7.0, -2.0, 6.0, -8.0),
    )
    rows: list[dict[str, float]] = []
    for a, flow, fa, fhigh in configs:
        for delta in (-5.0, -1.0, 0.0, 1.0, 5.0):
            rows.append({'x': a + delta, 'a': a, 'flow': flow, 'fa': fa, 'fhigh': fhigh})
    rows.sort(key=lambda row: hashlib.sha256(
        json.dumps(row, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest())
    return tuple(rows)


def _equivalent(actual: object, expected: object) -> bool:
    try:
        return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
    except (TypeError, ValueError, OverflowError):
        return actual == expected


def run_external_transfer(
    step_callable: Callable[[float, float, float, float, float], object],
    *,
    source_id: str,
    source_commit: str,
) -> dict[str, object]:
    if not callable(step_callable):
        raise TypeError('step_callable must be callable')
    source_id = str(source_id).strip()
    source_commit = str(source_commit).strip()
    if not source_id or not source_commit:
        raise ValueError('source_id and source_commit must be non-empty')

    fields = ('x', 'a', 'flow', 'fa', 'fhigh')
    rows = _rows()
    discovery = rows[:18]
    validation = rows[18:27]
    challenge = rows[27:39]
    heldout = rows[39:75]

    def oracle(context):
        value = step_callable(
            float(context['x']),
            float(context['a']),
            float(context['flow']),
            float(context['fa']),
            float(context['fhigh']),
        )
        if hasattr(value, 'item'):
            value = value.item()
        value = float(value)
        if not math.isfinite(value):
            raise ValueError('external oracle output must be finite')
        return value

    need = OperatorInventionNeed(
        'R2.64 external contextual step composition',
        fields,
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25000,
    )
    receipt = synthesize_contextual_composition_program(
        oracle,
        fields,
        need,
        discovery,
        validation,
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
        probe_constants=(0.0,),
        probe_max_depth=3,
        probe_max_candidates=22000,
    )

    challenge_exact = 0
    heldout_exact = 0
    if receipt.passed and receipt.expression is not None:
        for row in challenge:
            challenge_exact += int(_equivalent(evaluate_expr(receipt.expression, row), oracle(row)))
        for row in heldout:
            heldout_exact += int(_equivalent(evaluate_expr(receipt.expression, row), oracle(row)))

    selected = receipt.structure.selected
    selected_bindings = []
    selected_positions = []
    composition_data = None
    composition_digest = None
    fixed_rows: list[list[object]] = []
    singleton = [False, False]
    if selected is not None:
        selected_bindings = [
            [[int(position), float(value)] for position, value in spec.bindings]
            for spec in selected.program.interventions
        ]
        selected_positions = sorted({
            int(position)
            for spec in selected.program.interventions
            for position, _value in spec.bindings
        })
        composition_data = selected.program.composition_expression.to_data()
        composition_digest = selected.program.composition_digest
        fixed_rows = [[op, int(exact)] for op, exact in selected.r262_fixed_op_exact]
        singleton = [bool(value) for value in selected.singleton_composition_passed]

    passed = bool(
        receipt.passed
        and challenge_exact == len(challenge)
        and heldout_exact == len(heldout)
        and selected is not None
        and selected.r262_fixed_op_passed is False
        and selected.singleton_composition_passed == (False, False)
    )
    return {
        'milestone': 'R2.64',
        'capability': 'learned-contextual-causal-composition',
        'passed': passed,
        'source_id': source_id,
        'source_commit': source_commit,
        'source_exposure': 'io_only',
        'host_selected_intervention': False,
        'anchor_source': 'downstream_need.constants',
        'derived_anchor_values': [0.0],
        'selection_cases': len(discovery) + len(validation),
        'challenge_cases': len(challenge),
        'challenge_exact': challenge_exact,
        'heldout_cases': len(heldout),
        'heldout_exact': heldout_exact,
        'selected_bindings': selected_bindings,
        'selected_position_set': selected_positions,
        'shared_positions': list(selected.program.shared_positions) if selected is not None else [],
        'learned_composition_expression': composition_data,
        'learned_composition_digest': composition_digest,
        'r262_fixed_op_passed': bool(selected.r262_fixed_op_passed) if selected is not None else False,
        'r262_fixed_op_exact': fixed_rows,
        'singleton_composition_passed': singleton,
        'composition_candidates_considered': receipt.structure.composition_candidates_considered,
        'singleton_candidates_considered': receipt.structure.singleton_candidates_considered,
        'probe_candidates_considered': list(receipt.probe_candidates_considered),
        'probe_validation_cases': receipt.probe_validation_cases,
        'probe_validation_exact': receipt.probe_validation_exact,
        'final_validation_cases': receipt.final_validation_cases,
        'final_validation_exact': receipt.final_validation_exact,
        'final_expression': receipt.expression.to_data() if receipt.expression is not None else None,
        'trainable_parameter_count': 0,
        'claim_boundary': (
            'Bounded learned contextual composition of two pure-input interventions over a finite trusted DSL, '
            'with no access to positions overwritten by either intervention; not primitive-language invention, '
            '3+ intervention scaling, stateful experimentation, blind task discovery, or AGI.'
        ),
    }


if __name__ == '__main__':
    raise SystemExit('Pass an external step callable from a hosted verification harness.')
