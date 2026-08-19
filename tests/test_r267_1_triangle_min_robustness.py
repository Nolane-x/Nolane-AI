from __future__ import annotations

import itertools
from collections.abc import Mapping

from cogcoder.r256_operator_dsl import Binary, Field, evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import (
    discover_three_probe_structure,
    synthesize_three_probe_causal_program,
)


FIELDS = ('a', 'b', 'c')
ROWS = (
    # Pair-specific positive-domain collisions. The genuinely free field is 1
    # in each pair, retained probe observations are identical, but the target
    # differs because the omitted min term still carries information.
    (2.0, 3.0, 1.0), (4.0, 5.0, 1.0),
    (2.0, 1.0, 3.0), (4.0, 1.0, 5.0),
    (1.0, 2.0, 3.0), (1.0, 4.0, 5.0),
    # Singleton collisions with the two legitimate free fields held fixed.
    (1.0, 3.0, 5.0), (2.0, 3.0, 5.0),
    (3.0, 1.0, 5.0), (3.0, 2.0, 5.0),
    (3.0, 5.0, 1.0), (3.0, 5.0, 2.0),
    # Independent validation contexts.
    (2.0, 5.0, 4.0), (6.0, 3.0, 2.0),
    (4.0, 7.0, 5.0), (8.0, 2.0, 6.0),
    (5.0, 9.0, 3.0), (7.0, 6.0, 10.0),
    # Independent terminal contexts.
    (11.0, 4.0, 8.0), (3.0, 12.0, 7.0),
    (9.0, 5.0, 13.0), (14.0, 6.0, 2.0),
    (10.0, 15.0, 4.0), (16.0, 7.0, 11.0),
)


def _contexts() -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(FIELDS, row, strict=True)) for row in ROWS)


def _oracle(row: Mapping[str, object]) -> float:
    a = float(row['a'])
    b = float(row['b'])
    c = float(row['c'])
    return min(a, b) + min(b, c) + min(c, a)


def _probe(field: str, row: Mapping[str, object]) -> float:
    changed = dict(row)
    changed[field] = 0.0
    return _oracle(changed)


def _semantic_key(values: tuple[object, ...]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def test_triangle_min_has_nonzero_information_theoretic_lower_order_collisions() -> None:
    rows = _contexts()[:12]
    assert all(float(row[field]) > 0.0 for row in rows for field in FIELDS)

    full = Binary('add', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))
    for row in rows:
        env = {
            '__p0': _probe('a', row),
            '__p1': _probe('b', row),
            '__p2': _probe('c', row),
        }
        assert float(evaluate_expr(full, env)) == float(_oracle(row))

    for left, right in itertools.combinations(FIELDS, 2):
        free = ({*FIELDS} - {left, right}).pop()
        buckets: dict[tuple[float, ...], set[float]] = {}
        for row in rows:
            key = _semantic_key((_probe(left, row), _probe(right, row), row[free]))
            buckets.setdefault(key, set()).add(float(_oracle(row)))
        assert any(len(targets) > 1 for targets in buckets.values()), (left, right, free)

    for intervention in FIELDS:
        free = tuple(field for field in FIELDS if field != intervention)
        buckets: dict[tuple[float, ...], set[float]] = {}
        for row in rows:
            key = _semantic_key((_probe(intervention, row), *(row[field] for field in free)))
            buckets.setdefault(key, set()).add(float(_oracle(row)))
        assert any(len(targets) > 1 for targets in buckets.values()), intervention


def test_corrected_r267_1_discovers_and_terminally_verifies_triangle_min() -> None:
    rows = _contexts()
    discovery, validation, terminal = rows[:12], rows[12:18], rows[18:24]
    need = OperatorInventionNeed(
        'R2.67.1 positive triangle-min robustness',
        FIELDS,
        'out',
        constants=(0.0,),
        max_depth=4,
        max_candidates=50_000,
    )
    structure = discover_three_probe_structure(
        _oracle,
        FIELDS,
        (0.0,),
        discovery,
        validation,
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=20_000,
        max_composition_candidates_total=20_000,
        ablation_max_candidates=12_000,
        composition_beam_width=128,
    )
    assert structure.passed is True, structure.reason
    assert structure.selected is not None
    assert {spec.bindings[0][0] for spec in structure.selected.interventions} == {0, 1, 2}
    assert structure.selected.singleton_ablation_passed == (False, False, False)
    assert structure.selected.pair_ablation_passed == (False, False, False)
    assert structure.false_accepts == 0

    receipt = synthesize_three_probe_causal_program(
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
    assert receipt.passed is True, receipt.reason
    assert receipt.expression is not None
    assert len(receipt.probe_expressions) == 3
    assert receipt.probe_validation_cases == len(validation) * 3
    assert receipt.probe_validation_exact == receipt.probe_validation_cases
    assert receipt.terminal_probe_validation_cases == len(terminal) * 3
    assert receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases
    assert receipt.final_validation_cases == len(terminal)
    assert receipt.final_validation_exact == len(terminal)
    assert receipt.trainable_parameter_count == 0
