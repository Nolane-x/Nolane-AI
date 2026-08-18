import copy

import pytest

from cogcoder.r258_intervention_discovery import InterventionSpec, enumerate_interventions


def test_intervention_ids_are_positional_and_field_rename_invariant():
    original = enumerate_interventions(('x', 'a', 'b'), (0.0, 1.0), arity=2)
    renamed = enumerate_interventions(('q7', 'q2', 'q9'), (0.0, 1.0), arity=2)

    assert len(original) == 6
    assert [row.intervention_id for row in original] == [row.intervention_id for row in renamed]
    assert [row.bind(('x', 'a', 'b')) for row in original] != [row.bind(('q7', 'q2', 'q9')) for row in renamed]


def test_interventions_use_distinct_positions_and_distinct_anchor_values():
    rows = enumerate_interventions(('a', 'b', 'c', 'd'), (-1.0, 0.0, 1.0), arity=2)
    assert rows
    for row in rows:
        positions = [position for position, _value in row.bindings]
        values = [value for _position, value in row.bindings]
        assert len(positions) == len(set(positions)) == 2
        assert len(values) == len(set(values)) == 2


def test_apply_is_pure_copy_and_bind_resolves_positions_only_at_execution():
    spec = InterventionSpec(((1, 0.0), (3, 1.0)))
    context = {'u': 5.0, 'v': 6.0, 'w': 7.0, 'z': 8.0}
    before = copy.deepcopy(context)

    applied = spec.apply(context, ('u', 'v', 'w', 'z'))

    assert context == before
    assert applied == {'u': 5.0, 'v': 0.0, 'w': 7.0, 'z': 1.0}
    assert spec.bind(('u', 'v', 'w', 'z')) == (('v', 0.0), ('z', 1.0))


def test_invalid_intervention_rejects_duplicate_positions_and_nonfinite_values():
    with pytest.raises(ValueError, match='distinct'):
        InterventionSpec(((0, 0.0), (0, 1.0)))
    with pytest.raises(ValueError, match='finite'):
        InterventionSpec(((0, float('nan')), (1, 1.0)))

from benchmarks.kfigg.r257_verified_vocabulary_growth import build_promoted_vocabulary
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r258_intervention_discovery import discover_causal_intervention


def _linearstep_from_context(context):
    x = float(context['p0'])
    a = float(context['p1'])
    b = float(context['p2'])
    fa = float(context['p3'])
    fb = float(context['p4'])
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return fa + t * (fb - fa)


def _probe_contexts():
    rows = []
    for i, (x, a, b, fa, fb) in enumerate((
        (-4.0, 0.0, 8.0, 2.0, 10.0),
        (0.0, 0.0, 8.0, -3.0, 5.0),
        (2.0, 0.0, 8.0, 7.0, 15.0),
        (4.0, 0.0, 8.0, -8.0, 4.0),
        (6.0, 0.0, 8.0, 9.0, 17.0),
        (8.0, 0.0, 8.0, -1.0, 3.0),
        (12.0, 0.0, 8.0, 11.0, 19.0),
        (-6.0, -4.0, 4.0, -2.0, 6.0),
        (0.0, -4.0, 4.0, 3.0, 11.0),
        (6.0, -4.0, 4.0, -5.0, 7.0),
    )):
        rows.append({'p0': x, 'p1': a, 'p2': b, 'p3': fa, 'p4': fb, '_id': i})
    return tuple(rows)


def _probe_validation_contexts():
    return (
        {'p0': -6.0, 'p1': -4.0, 'p2': 4.0, 'p3': 3.0, 'p4': 9.0},
        {'p0': -2.0, 'p1': -4.0, 'p2': 4.0, 'p3': -7.0, 'p4': 13.0},
        {'p0': 2.0, 'p1': -4.0, 'p2': 4.0, 'p3': 5.0, 'p4': 21.0},
        {'p0': 8.0, 'p1': -4.0, 'p2': 4.0, 'p3': 2.0, 'p4': 12.0},
    )


def _downstream_examples():
    cases = (
        (-4.0, 0.0, 8.0, 2.0, 10.0), (0.0, 0.0, 8.0, 2.0, 10.0),
        (2.0, 0.0, 8.0, 2.0, 10.0), (4.0, 0.0, 8.0, 2.0, 10.0),
        (6.0, 0.0, 8.0, 2.0, 10.0), (8.0, 0.0, 8.0, 2.0, 10.0),
        (12.0, 0.0, 8.0, 2.0, 10.0), (0.0, -4.0, 4.0, -2.0, 6.0),
    )
    return tuple(
        OperatorExample(
            f'full:{i}',
            {'p0': x, 'p1': a, 'p2': b, 'p3': fa, 'p4': fb},
            _linearstep_from_context({'p0': x, 'p1': a, 'p2': b, 'p3': fa, 'p4': fb}),
        )
        for i, (x, a, b, fa, fb) in enumerate(cases)
    )


def test_discovery_selects_a_verified_causal_endpoint_intervention_without_semantic_labels():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    need = OperatorInventionNeed(
        'opaque-full-task', ('p0', 'p1', 'p2', 'p3', 'p4'), 'out',
        constants=(0, 1), max_depth=3, max_candidates=1000,
    )

    receipt = discover_causal_intervention(
        _linearstep_from_context,
        ('p0', 'p1', 'p2', 'p3', 'p4'),
        (0.0, 1.0),
        _probe_contexts(),
        _probe_validation_contexts(),
        vocabulary,
        need,
        _downstream_examples(),
        probe_max_depth=2,
        probe_max_candidates=5000,
    )

    assert receipt.passed
    assert receipt.selected is not None
    assert {position for position, _value in receipt.selected.intervention.bindings} == {3, 4}
    assert receipt.no_seed_passed is False
    assert receipt.selected.seeded_downstream_passed is True
    assert receipt.selected.probe_validation_exact == receipt.selected.probe_validation_cases == 4
    assert receipt.selected.base_probe_passed is False
    assert receipt.selected.vocabulary_probe_passed is True
    assert receipt.oracle_calls > 0
    assert receipt.synthesis_candidates_considered > receipt.no_seed_candidates_considered
    assert receipt.trainable_parameter_count == 0


def test_constant_probe_candidates_are_rejected_before_downstream_credit():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    need = OperatorInventionNeed('tiny', ('a', 'b'), 'out', constants=(0, 1), max_depth=1, max_candidates=20)
    downstream = (
        OperatorExample('d0', {'a': 0.0, 'b': 0.0}, 0.0),
        OperatorExample('d1', {'a': 1.0, 'b': 1.0}, 1.0),
    )

    def oracle(ctx):
        return float(ctx['a'])

    receipt = discover_causal_intervention(
        oracle,
        ('a', 'b'),
        (0.0, 1.0),
        ({'a': 2.0, 'b': 3.0}, {'a': 4.0, 'b': 5.0}, {'a': 6.0, 'b': 7.0}),
        ({'a': 8.0, 'b': 9.0},),
        vocabulary,
        need,
        downstream,
        intervention_arity=1,
        probe_max_depth=1,
        probe_max_candidates=20,
    )

    assert any(row.reason == 'constant_probe_output' for row in receipt.candidates)
    assert all(not row.seeded_downstream_passed for row in receipt.candidates if row.reason == 'constant_probe_output')

from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r258_intervention_discovery import PositionalSchema


def test_positional_schema_canonicalizes_field_names_and_externalizes_expressions():
    a = PositionalSchema(('human_x', 'human_a', 'human_b'))
    b = PositionalSchema(('q9', 'q4', 'q1'))

    assert a.canonical_fields == b.canonical_fields == ('__f0', '__f1', '__f2')
    assert a.to_canonical_context({'human_x': 3, 'human_a': 1, 'human_b': 9}) == {
        '__f0': 3, '__f1': 1, '__f2': 9,
    }
    expr = Binary('sub', Field('__f2'), Field('__f0'))
    assert a.externalize_expr(expr).to_data() == {
        'op': 'sub',
        'left': {'field': 'human_b'},
        'right': {'field': 'human_x'},
    }
    external = Binary('add', Field('human_a'), Field('human_x'))
    assert a.canonicalize_expr(external).to_data() == {
        'op': 'add',
        'left': {'field': '__f1'},
        'right': {'field': '__f0'},
    }
