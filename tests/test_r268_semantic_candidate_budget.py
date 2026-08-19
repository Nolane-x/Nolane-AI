from __future__ import annotations

from cogcoder.r256_operator_dsl import Binary, Field
import cogcoder.r268_cross_task_causal_transfer as transfer
import cogcoder.r268_cross_task_transfer_baseline as scratch


def _portable() -> transfer.PortableCausalProgram:
    expression = Binary(
        'add',
        Binary('add', Field('__p0'), Field('__p1')),
        Field('__p2'),
    )
    return transfer.export_expression_prior(expression)


def _candidate(expression, candidate_id: str) -> transfer.TransferCandidate:
    return transfer.TransferCandidate(
        expression=expression,
        candidate_id=candidate_id,
        repair_distance=0,
        role_permutation_distance=0,
    )


def _transfer_rows() -> tuple[transfer.TransferCandidate, ...]:
    # The first two rows are already proof-equivalent under numeric add
    # commutativity. They must consume one semantic hypothesis slot, not two.
    return (
        _candidate(Binary('add', Field('__p0'), Field('__p1')), 'budget.alias.a'),
        _candidate(Binary('add', Field('__p1'), Field('__p0')), 'budget.alias.b'),
        _candidate(Field('__p2'), 'budget.correct'),
    )


def _transfer_diagnostics() -> tuple[dict[str, int], ...]:
    return (
        {'__p0': 1, '__p1': 2, '__p2': 9},
        {'__p0': 2, '__p1': 4, '__p2': 7},
    )


def _transfer_terminals() -> tuple[dict[str, int], ...]:
    return ({'__p0': 3, '__p1': 5, '__p2': 11},)


def _p2_oracle(context):
    return context['__p2']


def test_transfer_candidate_budget_counts_proof_distinct_hypotheses(monkeypatch):
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: _transfer_rows(),
    )

    receipt = transfer.adapt_portable_program(
        _portable(),
        diagnostic_contexts=_transfer_diagnostics(),
        terminal_contexts=_transfer_terminals(),
        oracle=_p2_oracle,
        max_selection_queries=2,
        max_candidates=2,
    )

    assert receipt.passed is True
    assert receipt.reason == 'verified_transfer'
    assert receipt.selected_candidate_id == 'budget.correct'
    assert receipt.candidates_generated == 2
    assert receipt.selection_queries >= 1
    assert receipt.terminal_queries == 1
    assert receipt.false_accepts == 0


def _scratch_diagnostics() -> tuple[dict[str, int], ...]:
    return (
        {'__p0': 1, '__p1': 3, '__p2': 7},
        {'__p0': 4, '__p1': 6, '__p2': 9},
    )


def _scratch_terminals() -> tuple[dict[str, int], ...]:
    return ({'__p0': 2, '__p1': 5, '__p2': 8},)


def _double_p1_oracle(context):
    return context['__p1'] + context['__p1']


def test_scratch_candidate_budget_counts_proof_distinct_hypotheses():
    # Raw depth-1 enumeration reaches p1+p1 only after it has emitted both
    # p0+p1 and the proof-equivalent p1+p0 representation. With a semantic
    # hypothesis budget of seven, the duplicate representation must not starve
    # p1+p1 from the bounded search frontier.
    receipt = scratch.solve_from_scratch(
        diagnostic_contexts=_scratch_diagnostics(),
        terminal_contexts=_scratch_terminals(),
        oracle=_double_p1_oracle,
        max_selection_queries=2,
        max_candidates=7,
        max_depth=1,
    )

    assert receipt.passed is True
    assert receipt.reason == 'verified_scratch'
    assert receipt.candidates_generated == 7
    assert receipt.selection_queries >= 1
    assert receipt.terminal_queries == 1
    assert receipt.false_accepts == 0
