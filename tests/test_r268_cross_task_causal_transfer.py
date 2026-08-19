from __future__ import annotations

import json

import pytest

from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r268_cross_task_causal_transfer import (
    adapt_portable_program,
    export_expression_prior,
    generate_transfer_candidates,
)


def _source_expression():
    return Binary('add', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))


def _ordered_source_expression():
    return Binary('sub', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))


def _diagnostics():
    return (
        {'__p0': 1, '__p1': 2, '__p2': 3},
        {'__p0': 2, '__p1': 4, '__p2': 1},
        {'__p0': -1, '__p1': 3, '__p2': 2},
        {'__p0': 5, '__p1': -2, '__p2': 4},
        {'__p0': 3, '__p1': 3, '__p2': 1},
        {'__p0': 6, '__p1': 2, '__p2': -3},
        {'__p0': -4, '__p1': 5, '__p2': 2},
    )


def _terminals():
    return (
        {'__p0': 7, '__p1': 2, '__p2': 5},
        {'__p0': 4, '__p1': 6, '__p2': -1},
    )


def test_expression_prior_serialization_is_identity_free_and_zero_parameter():
    portable = export_expression_prior(_source_expression())
    data = portable.to_data()

    assert data['probe_roles'] == ['__p0', '__p1', '__p2']
    assert data['expression'] == _source_expression().to_data()
    assert data['trainable_parameter_count'] == 0
    assert portable.trainable_parameter_count == 0

    serialized = json.dumps(data, sort_keys=True)
    for forbidden in (
        'source_a',
        'source_b',
        'intervention-',
        'semantic-profile',
        'target_task',
    ):
        assert forbidden not in serialized


def test_expression_prior_requires_exactly_three_abstract_probe_roles():
    with pytest.raises(ValueError, match='exactly three abstract probe roles'):
        export_expression_prior(Binary('add', Field('__p0'), Field('__p1')))


def test_expression_prior_rejects_non_abstract_field_dependency():
    expression = Binary(
        'add',
        Binary('add', Field('__p0'), Field('__p1')),
        Field('source_secret'),
    )
    with pytest.raises(ValueError, match='exactly three abstract probe roles'):
        export_expression_prior(expression)


def test_transfer_candidate_generation_is_content_addressed_and_contains_one_repair():
    portable = export_expression_prior(_ordered_source_expression())
    candidates = generate_transfer_candidates(portable)

    assert candidates == tuple(sorted(candidates, key=lambda row: (row.repair_distance, row.candidate_id)))
    assert len({row.candidate_id for row in candidates}) == len(candidates)
    assert any(row.repair_distance == 0 for row in candidates)
    assert any(
        row.expression.to_data()
        == Binary('sub', Binary('mul', Field('__p0'), Field('__p1')), Field('__p2')).to_data()
        and row.repair_distance == 1
        for row in candidates
    )


def test_active_transfer_resolves_probe_role_permutation_without_host_binding():
    portable = export_expression_prior(_ordered_source_expression())
    calls: list[tuple[int, int, int]] = []

    def oracle(context):
        calls.append((context['__p0'], context['__p1'], context['__p2']))
        return context['__p2'] + context['__p0'] - context['__p1']

    receipt = adapt_portable_program(
        portable,
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
    )

    assert receipt.passed is True
    assert receipt.false_accepts == 0
    assert 1 <= receipt.selection_queries <= 3
    assert receipt.terminal_queries == len(_terminals())
    assert receipt.terminal_exact == len(_terminals())
    assert receipt.trainable_parameter_count == 0
    assert len(calls) == receipt.selection_queries + receipt.terminal_queries
    assert tuple(calls[: receipt.selection_queries]) == tuple(row.context_values for row in receipt.query_trace)


def test_active_transfer_adapts_exactly_one_binary_operator():
    portable = export_expression_prior(_ordered_source_expression())

    def oracle(context):
        return context['__p0'] * context['__p1'] - context['__p2']

    receipt = adapt_portable_program(
        portable,
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
    )

    expected = Binary('sub', Binary('mul', Field('__p0'), Field('__p1')), Field('__p2'))
    assert receipt.passed is True
    assert receipt.selected_expression is not None
    assert receipt.selected_expression.to_data() == expected.to_data()
    assert receipt.repaired_expression_selected is True
    assert receipt.source_expression_selected is False
    assert receipt.false_accepts == 0


def test_selection_and_terminal_contexts_must_be_disjoint_before_oracle_use():
    portable = export_expression_prior(_ordered_source_expression())
    calls = 0

    def oracle(context):
        nonlocal calls
        calls += 1
        return context['__p0'] + context['__p1'] - context['__p2']

    overlap = _diagnostics()[0]
    with pytest.raises(ValueError, match='selection and terminal contexts must be disjoint'):
        adapt_portable_program(
            portable,
            diagnostic_contexts=_diagnostics(),
            terminal_contexts=(overlap,),
            oracle=oracle,
            max_selection_queries=3,
            max_candidates=96,
        )
    assert calls == 0
