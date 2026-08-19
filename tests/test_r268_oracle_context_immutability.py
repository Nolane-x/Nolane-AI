from __future__ import annotations

from copy import deepcopy

from cogcoder.r256_operator_dsl import Binary, Field
import cogcoder.r268_cross_task_causal_transfer as transfer
import cogcoder.r268_cross_task_transfer_baseline as scratch


def _candidate(role: str) -> transfer.TransferCandidate:
    return transfer.TransferCandidate(
        expression=Field(role),
        candidate_id=f'mutation.{role}',
        repair_distance=0,
        role_permutation_distance=0,
    )


def _portable() -> transfer.PortableCausalProgram:
    expression = Binary(
        'add',
        Binary('add', Field('__p0'), Field('__p1')),
        Field('__p2'),
    )
    return transfer.export_expression_prior(expression)


def _contexts():
    diagnostics = [
        {'__p0': 2, '__p1': 9, '__p2': 1},
        {'__p0': 5, '__p1': -3, '__p2': 4},
    ]
    terminals = [
        {'__p0': 7, '__p1': 4, '__p2': 3},
    ]
    return diagnostics, terminals


def test_transfer_fails_closed_if_selection_oracle_mutates_context(monkeypatch):
    diagnostics, terminals = _contexts()
    before_diagnostics = deepcopy(diagnostics)
    before_terminals = deepcopy(terminals)
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: (_candidate('__p1'),),
    )

    def mutating_oracle(context):
        if context['__p0'] == 2:
            context['__p1'] = context['__p0']
        return context['__p0']

    receipt = transfer.adapt_portable_program(
        _portable(),
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=mutating_oracle,
        max_selection_queries=2,
        max_candidates=1,
    )

    assert receipt.passed is False
    assert receipt.reason == 'oracle_context_mutation'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 0
    assert diagnostics == before_diagnostics
    assert terminals == before_terminals


def test_scratch_fails_closed_if_selection_oracle_mutates_context(monkeypatch):
    diagnostics, terminals = _contexts()
    before_diagnostics = deepcopy(diagnostics)
    before_terminals = deepcopy(terminals)
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: (_candidate('__p1'),),
    )

    def mutating_oracle(context):
        if context['__p0'] == 2:
            context['__p1'] = context['__p0']
        return context['__p0']

    receipt = scratch.solve_from_scratch(
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=mutating_oracle,
        max_selection_queries=2,
        max_candidates=1,
        max_depth=0,
    )

    assert receipt.passed is False
    assert receipt.reason == 'oracle_context_mutation'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 0
    assert diagnostics == before_diagnostics
    assert terminals == before_terminals


def test_transfer_fails_closed_if_terminal_oracle_mutates_context(monkeypatch):
    diagnostics, terminals = _contexts()
    before_diagnostics = deepcopy(diagnostics)
    before_terminals = deepcopy(terminals)
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: (_candidate('__p0'),),
    )

    def mutating_oracle(context):
        if context['__p0'] == 7:
            context['__p1'] = 999
        return context['__p0']

    receipt = transfer.adapt_portable_program(
        _portable(),
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=mutating_oracle,
        max_selection_queries=2,
        max_candidates=1,
    )

    assert receipt.passed is False
    assert receipt.reason == 'terminal_oracle_context_mutation'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 1
    assert receipt.terminal_exact == 0
    assert diagnostics == before_diagnostics
    assert terminals == before_terminals


def test_scratch_fails_closed_if_terminal_oracle_mutates_context(monkeypatch):
    diagnostics, terminals = _contexts()
    before_diagnostics = deepcopy(diagnostics)
    before_terminals = deepcopy(terminals)
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: (_candidate('__p0'),),
    )

    def mutating_oracle(context):
        if context['__p0'] == 7:
            context['__p1'] = 999
        return context['__p0']

    receipt = scratch.solve_from_scratch(
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=mutating_oracle,
        max_selection_queries=2,
        max_candidates=1,
        max_depth=0,
    )

    assert receipt.passed is False
    assert receipt.reason == 'terminal_oracle_context_mutation'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 1
    assert receipt.terminal_exact == 0
    assert diagnostics == before_diagnostics
    assert terminals == before_terminals
