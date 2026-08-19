from __future__ import annotations

import itertools
from collections.abc import Mapping

from cogcoder.r256_operator_dsl import Binary, Field, evaluate_expr
from cogcoder.r267_three_probe_causal_composition import discover_three_probe_structure


FIELDS = ('a', 'b', 'c')
ROWS = (
    # Pair-ablation collisions: when the pair-specific free field is zero,
    # both selected probe observations collapse while the hidden product varies.
    (1.0, 2.0, 0.0), (2.0, 3.0, 0.0),
    (1.0, 0.0, 2.0), (2.0, 0.0, 3.0),
    (0.0, 1.0, 2.0), (0.0, 2.0, 3.0),
    # Singleton collisions: same visible free fields, different hidden field.
    (1.0, 2.0, 3.0), (4.0, 2.0, 3.0),
    (2.0, 1.0, 3.0), (2.0, 4.0, 3.0),
    (2.0, 3.0, 1.0), (2.0, 3.0, 4.0),
    # Additional asymmetric rows for validation/general position.
    (-2.0, 5.0, 3.0), (4.0, -3.0, 2.0),
    (5.0, 2.0, -4.0), (-3.0, -2.0, 6.0),
    (7.0, -1.0, -5.0), (-4.0, 6.0, -2.0),
)


def _contexts() -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(FIELDS, row, strict=True)) for row in ROWS)


def _oracle(row: Mapping[str, object]) -> float:
    a = float(row['a'])
    b = float(row['b'])
    c = float(row['c'])
    return a * b + b * c + c * a


def _probe(field: str, row: Mapping[str, object]) -> float:
    changed = dict(row)
    changed[field] = 0.0
    return _oracle(changed)


def _semantic_key(values: tuple[object, ...]) -> tuple[object, ...]:
    return tuple(float(value) if isinstance(value, (int, float)) else value for value in values)


def test_cyclic_bilinear_family_has_information_theoretic_three_probe_witness() -> None:
    rows = _contexts()

    # All three zero-intervention probes are sufficient by a fixed trusted-DSL
    # expression: bc + ca + ab == target.
    full = Binary(
        'add',
        Binary('add', Field('__p0'), Field('__p1')),
        Field('__p2'),
    )
    for row in rows:
        env = {
            '__p0': _probe('a', row),
            '__p1': _probe('b', row),
            '__p2': _probe('c', row),
        }
        assert float(evaluate_expr(full, env)) == float(_oracle(row))

    # Every genuine two-intervention ablation gets the original field left free
    # by those two interventions.  Even with that field, the dataset contains a
    # public collision: identical lower-order evidence but different targets.
    # Therefore no deterministic expression language can solve that pair.
    for left, right in itertools.combinations(FIELDS, 2):
        free = ({*FIELDS} - {left, right}).pop()
        buckets: dict[tuple[object, ...], set[float]] = {}
        for row in rows:
            key = _semantic_key((_probe(left, row), _probe(right, row), row[free]))
            buckets.setdefault(key, set()).add(float(_oracle(row)))
        assert any(len(targets) > 1 for targets in buckets.values()), (left, right, free)

    # The same is true for every singleton: the other two original fields are
    # visible, but the hidden intervened field remains information-bearing.
    for intervention in FIELDS:
        free = tuple(field for field in FIELDS if field != intervention)
        buckets: dict[tuple[object, ...], set[float]] = {}
        for row in rows:
            key = _semantic_key((_probe(intervention, row), *(row[field] for field in free)))
            buckets.setdefault(key, set()).add(float(_oracle(row)))
        assert any(len(targets) > 1 for targets in buckets.values()), intervention


def test_current_r267_engine_can_discover_cyclic_family_without_host_selected_triplet() -> None:
    rows = _contexts()
    receipt = discover_three_probe_structure(
        _oracle,
        FIELDS,
        (0.0,),
        rows[:12],
        rows[12:18],
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=20_000,
        max_composition_candidates_total=20_000,
        ablation_max_candidates=12_000,
        composition_beam_width=128,
    )

    assert receipt.passed is True
    assert receipt.selected is not None
    selected_positions = {
        spec.bindings[0][0]
        for spec in receipt.selected.interventions
    }
    assert selected_positions == {0, 1, 2}
    assert set(receipt.selected.used_fields) >= {'__p0', '__p1', '__p2'}
    assert receipt.selected.singleton_ablation_passed == (False, False, False)
    assert receipt.selected.pair_ablation_passed == (False, False, False)
    assert receipt.false_accepts == 0
