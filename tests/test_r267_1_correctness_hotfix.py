from __future__ import annotations

import itertools
import json
from collections.abc import Mapping

from cogcoder.r256_operator_dsl import Binary, Field, evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import (
    discover_three_probe_structure,
    synthesize_three_probe_causal_program,
)


FIELDS = ('a', 'b', 'c', 'd', 'e', 'f')
CONFIGS = (
    (-7, -13, 4, -3, -10, -13), (7, 5, -12, 10, -6, 9),
    (-13, 8, 8, -12, 6, -9), (12, 7, 4, 2, -13, -3),
    (-3, -11, 7, 11, 10, -3), (-10, 5, 4, 9, -6, 6),
    (8, -3, 5, 2, -10, 3), (-11, -7, -3, -13, -7, -13),
    (11, 5, -5, -2, 8, 2), (5, -5, 9, 7, -6, -3),
    (12, -5, 11, -4, -2, 10), (-7, 9, 9, -9, -8, -7),
    (11, -10, -5, 11, -9, 4), (13, -8, 2, -6, -5, -12),
    (-5, 8, 11, 8, -9, 13), (10, -10, -9, 6, 12, -2),
    (6, -9, 4, 2, 9, -7), (8, -11, -13, -4, -11, -4),
    (-4, 9, -12, 13, -12, -5), (-10, -13, 10, 11, -10, -7),
    (4, 9, 2, -2, 4, 13), (13, 9, 6, -6, 4, 12),
    (13, -5, -6, 3, -11, 9), (-6, 11, 13, -9, -3, -10),
)
PARTNER = {'a': 'b', 'b': 'a', 'c': 'd', 'd': 'c', 'e': 'f', 'f': 'e'}


def _rows() -> tuple[dict[str, float], ...]:
    return tuple(
        {field: float(value) for field, value in zip(FIELDS, values, strict=True)}
        for values in CONFIGS
    )


def _oracle(row: Mapping[str, object]) -> float:
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def _need() -> OperatorInventionNeed:
    return OperatorInventionNeed(
        'R2.67.1 correctness hotfix RED',
        FIELDS,
        'out',
        constants=(0.0, 2.0),
        max_depth=4,
        max_candidates=50_000,
    )


def _synthesize():
    rows = _rows()
    return synthesize_three_probe_causal_program(
        _oracle,
        FIELDS,
        _need(),
        rows[:12],
        rows[12:18],
        terminal_contexts=rows[18:24],
        intervention_anchor_values=(0.0,),
        intervention_arity=1,
        composition_constants=(0.0, 2.0),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=35_000,
        max_composition_candidates_total=70_000,
        ablation_max_candidates=20_000,
        composition_beam_width=192,
        probe_constants=(0.0,),
        probe_max_depth=2,
        probe_max_candidates=30_000,
        probe_beam_width=160,
    )


def test_probe_validation_receipt_uses_probe_observation_case_units() -> None:
    receipt = _synthesize()
    assert receipt.passed is True
    assert len(receipt.probe_expressions) == 3
    expected_cases = 6 * 3
    assert receipt.probe_validation_cases == expected_cases
    assert receipt.probe_validation_exact == expected_cases
    assert receipt.probe_validation_exact <= receipt.probe_validation_cases


def test_triplet_cannot_be_authorized_when_genuine_pair_specific_evidence_solves_target() -> None:
    rows = _rows()
    discovery = rows[:12]
    validation = rows[12:18]
    structure = discover_three_probe_structure(
        _oracle,
        FIELDS,
        (0.0,),
        discovery,
        validation,
        intervention_arity=1,
        composition_constants=(0.0, 2.0),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=35_000,
        max_composition_candidates_total=70_000,
        ablation_max_candidates=20_000,
        composition_beam_width=192,
    )
    assert structure.passed is True
    assert structure.selected is not None
    selected = structure.selected
    contexts = discovery + validation

    pair_specific_solutions = 0
    for left_index, right_index in itertools.combinations(range(3), 2):
        pair_profiles = (selected.profiles[left_index], selected.profiles[right_index])
        fixed_positions = {
            position
            for profile in pair_profiles
            for position, _value in profile.intervention.bindings
        }
        free_fields = tuple(
            FIELDS[position]
            for position in range(len(FIELDS))
            if position not in fixed_positions
        )
        omitted_index = ({0, 1, 2} - {left_index, right_index}).pop()
        omitted_position = selected.profiles[omitted_index].intervention.bindings[0][0]
        omitted_field = FIELDS[omitted_position]
        partner_field = PARTNER[omitted_field]
        assert omitted_field in free_fields
        assert partner_field in free_fields

        expression = Binary(
            'sub',
            Binary('add', Field('__p0'), Field('__p1')),
            Binary('mul', Field(omitted_field), Field(partner_field)),
        )
        left_outputs = pair_profiles[0].discovery_outputs + pair_profiles[0].validation_outputs
        right_outputs = pair_profiles[1].discovery_outputs + pair_profiles[1].validation_outputs
        exact = 0
        for index, context in enumerate(contexts):
            environment = {field: context[field] for field in free_fields}
            environment['__p0'] = left_outputs[index]
            environment['__p1'] = right_outputs[index]
            exact += int(float(evaluate_expr(expression, environment)) == float(_oracle(context)))
        pair_specific_solutions += int(exact == len(contexts))

    assert pair_specific_solutions == 3
    assert structure.passed is False
