from __future__ import annotations

from cogcoder.r256_operator_dsl import Binary, Field
import cogcoder.r268_cross_task_causal_transfer as transfer
import cogcoder.r268_cross_task_transfer_baseline as scratch


def _candidate(role: str) -> transfer.TransferCandidate:
    return transfer.TransferCandidate(
        expression=Field(role),
        candidate_id=f'exception.{role}',
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


def _diagnostics() -> tuple[dict[str, int], ...]:
    return (
        {'__p0': 2, '__p1': 9, '__p2': 1},
        {'__p0': 5, '__p1': -3, '__p2': 4},
    )


def _terminals() -> tuple[dict[str, int], ...]:
    return ({'__p0': 7, '__p1': 4, '__p2': 3},)


def test_transfer_contains_selection_keyerror(monkeypatch):
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: (_candidate('__p0'),),
    )

    def oracle(_context):
        raise KeyError('external oracle lookup failed')

    receipt = transfer.adapt_portable_program(
        _portable(),
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=2,
        max_candidates=1,
    )

    assert receipt.passed is False
    assert receipt.reason == 'invalid_oracle_output'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 0
    assert receipt.terminal_exact == 0
    assert receipt.false_accepts == 0


def test_scratch_contains_selection_keyerror(monkeypatch):
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: (_candidate('__p0'),),
    )

    def oracle(_context):
        raise KeyError('external oracle lookup failed')

    receipt = scratch.solve_from_scratch(
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=2,
        max_candidates=1,
        max_depth=0,
    )

    assert receipt.passed is False
    assert receipt.reason == 'invalid_oracle_output'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 0
    assert receipt.terminal_exact == 0
    assert receipt.false_accepts == 0


def test_transfer_contains_terminal_runtimeerror(monkeypatch):
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: (_candidate('__p0'),),
    )

    def oracle(context):
        if context['__p0'] == 7:
            raise RuntimeError('external oracle backend failed')
        return context['__p0']

    receipt = transfer.adapt_portable_program(
        _portable(),
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=2,
        max_candidates=1,
    )

    assert receipt.passed is False
    assert receipt.reason == 'invalid_terminal_oracle_output'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 1
    assert receipt.terminal_exact == 0
    assert receipt.false_accepts == 0


def test_scratch_contains_terminal_runtimeerror(monkeypatch):
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: (_candidate('__p0'),),
    )

    def oracle(context):
        if context['__p0'] == 7:
            raise RuntimeError('external oracle backend failed')
        return context['__p0']

    receipt = scratch.solve_from_scratch(
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=2,
        max_candidates=1,
        max_depth=0,
    )

    assert receipt.passed is False
    assert receipt.reason == 'invalid_terminal_oracle_output'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 1
    assert receipt.terminal_exact == 0
    assert receipt.false_accepts == 0
