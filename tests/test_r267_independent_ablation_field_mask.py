from __future__ import annotations

import itertools
from collections.abc import Mapping

from benchmarks.kfigg.r267_three_probe_causal_composition import CONFIGS, ROLES
from cogcoder.r256_operator_dsl import Binary, Field, evaluate_expr
from cogcoder.r267_three_probe_causal_composition import discover_three_probe_structure


_PARTNER = {
    'a': 'b', 'b': 'a',
    'c': 'd', 'd': 'c',
    'e': 'f', 'f': 'e',
}


def _rows() -> tuple[dict[str, float], ...]:
    return tuple(
        {field: float(value) for field, value in zip(ROLES, values, strict=True)}
        for values in CONFIGS[:18]
    )


def _oracle(row: Mapping[str, object]) -> float:
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def test_three_probe_authority_rejects_triplet_when_pair_specific_free_fields_suffice() -> None:
    rows = _rows()
    discovery = rows[:12]
    validation = rows[12:18]
    structure = discover_three_probe_structure(
        _oracle,
        ROLES,
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

    # A proper two-intervention ablation should regain every original field that
    # is not overwritten by those two interventions.  For the authored
    # tri-bilinear family, each selected pair can then exactly reconstruct the
    # target: p0 + p1 - (the untouched third bilinear term).
    pair_specific_exact = []
    for left_index, right_index in itertools.combinations(range(3), 2):
        pair_profiles = (selected.profiles[left_index], selected.profiles[right_index])
        fixed_positions = {
            position
            for profile in pair_profiles
            for position, _value in profile.intervention.bindings
        }
        free_fields = tuple(
            ROLES[position]
            for position in range(len(ROLES))
            if position not in fixed_positions
        )

        omitted_index = ({0, 1, 2} - {left_index, right_index}).pop()
        omitted_profile = selected.profiles[omitted_index]
        omitted_position = omitted_profile.intervention.bindings[0][0]
        omitted_field = ROLES[omitted_position]
        partner_field = _PARTNER[omitted_field]
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
        pair_specific_exact.append(exact == len(contexts))

    assert pair_specific_exact == [True, True, True]

    # If every pair-specific lower-order program exists inside the trusted DSL,
    # the current triplet cannot be evidence that all three interventions are
    # causally necessary.  The production receipt must therefore abstain.
    assert structure.passed is False
