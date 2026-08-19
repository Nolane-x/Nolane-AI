from __future__ import annotations

from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r268_cross_task_causal_transfer import (
    adapt_portable_program,
    export_expression_prior,
    generate_scratch_candidates,
    solve_from_scratch,
)


def _source():
    return Binary('sub', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))


def _target():
    return Binary('sub', Binary('mul', Field('__p0'), Field('__p1')), Field('__p2'))


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
        {'__p0': -3, '__p1': -2, '__p2': 4},
    )


def test_negative_transfer_outside_one_repair_neighborhood_abstains():
    portable = export_expression_prior(_source())

    def oracle(context):
        return (context['__p0'] - context['__p1']) * context['__p2']

    receipt = adapt_portable_program(
        portable,
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
    )

    assert receipt.passed is False
    assert receipt.false_accepts == 0
    assert receipt.selected_expression is None


def test_matched_tight_scratch_omits_target_but_roomy_scratch_contains_it():
    target = _target().to_data()
    tight = generate_scratch_candidates(max_depth=2, max_candidates=96)
    roomy = generate_scratch_candidates(max_depth=2, max_candidates=600)

    assert all(row.expression.to_data() != target for row in tight)
    assert any(row.expression.to_data() == target for row in roomy)


def test_transfer_solves_tight_budget_where_scratch_fails_and_roomy_scratch_solves():
    portable = export_expression_prior(_source())

    def oracle(context):
        return context['__p0'] * context['__p1'] - context['__p2']

    transfer = adapt_portable_program(
        portable,
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
    )
    tight = solve_from_scratch(
        diagnostic_contexts=_diagnostics(), terminal_contexts=_terminals(), oracle=oracle,
        max_selection_queries=3, max_candidates=96, max_depth=2,
    )
    roomy = solve_from_scratch(
        diagnostic_contexts=_diagnostics(), terminal_contexts=_terminals(), oracle=oracle,
        max_selection_queries=len(_diagnostics()), max_candidates=600, max_depth=2,
    )

    assert transfer.passed is True
    assert tight.passed is False
    assert tight.false_accepts == 0
    assert roomy.passed is True
    assert roomy.selected_expression is not None
    assert roomy.selected_expression.to_data() == _target().to_data()
    assert roomy.false_accepts == 0
    assert roomy.trainable_parameter_count == 0
