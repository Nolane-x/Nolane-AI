from __future__ import annotations

from cogcoder.r256_operator_dsl import Binary, Field
import cogcoder.r268_cross_task_causal_transfer as transfer
import cogcoder.r268_cross_task_transfer_baseline as scratch


_LARGE = 1000000000000000.25
_DELTA = 50000.0


def _candidate() -> transfer.TransferCandidate:
    return transfer.TransferCandidate(
        expression=Field('__p0'),
        candidate_id='exact-numeric.p0',
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


def test_transfer_selection_rejects_large_relative_tolerance_mismatch(monkeypatch):
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: (_candidate(),),
    )
    diagnostics = ({'__p0': _LARGE, '__p1': 2.5, '__p2': 1.25},)
    terminals = ({'__p0': 3.25, '__p1': 4.5, '__p2': 2.75},)

    def oracle(context):
        if context['__p0'] == _LARGE:
            return context['__p0'] + _DELTA
        return context['__p0']

    receipt = transfer.adapt_portable_program(
        _portable(),
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=oracle,
        max_selection_queries=1,
        max_candidates=1,
    )

    assert receipt.passed is False
    assert receipt.reason == 'target_outside_transfer_neighborhood'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 0
    assert receipt.false_accepts == 0


def test_scratch_selection_rejects_large_relative_tolerance_mismatch(monkeypatch):
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: (_candidate(),),
    )
    diagnostics = ({'__p0': _LARGE, '__p1': 2.5, '__p2': 1.25},)
    terminals = ({'__p0': 3.25, '__p1': 4.5, '__p2': 2.75},)

    def oracle(context):
        if context['__p0'] == _LARGE:
            return context['__p0'] + _DELTA
        return context['__p0']

    receipt = scratch.solve_from_scratch(
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=oracle,
        max_selection_queries=1,
        max_candidates=1,
        max_depth=0,
    )

    assert receipt.passed is False
    assert receipt.reason == 'target_outside_scratch_space'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 0
    assert receipt.false_accepts == 0


def test_transfer_terminal_rejects_large_relative_tolerance_mismatch(monkeypatch):
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: (_candidate(),),
    )
    diagnostics = ({'__p0': 3.25, '__p1': 4.5, '__p2': 2.75},)
    terminals = ({'__p0': _LARGE, '__p1': 2.5, '__p2': 1.25},)

    def oracle(context):
        if context['__p0'] == _LARGE:
            return context['__p0'] + _DELTA
        return context['__p0']

    receipt = transfer.adapt_portable_program(
        _portable(),
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=oracle,
        max_selection_queries=1,
        max_candidates=1,
    )

    assert receipt.passed is False
    assert receipt.reason == 'terminal_mismatch'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 1
    assert receipt.terminal_exact == 0
    assert receipt.false_accepts == 0


def test_scratch_terminal_rejects_large_relative_tolerance_mismatch(monkeypatch):
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: (_candidate(),),
    )
    diagnostics = ({'__p0': 3.25, '__p1': 4.5, '__p2': 2.75},)
    terminals = ({'__p0': _LARGE, '__p1': 2.5, '__p2': 1.25},)

    def oracle(context):
        if context['__p0'] == _LARGE:
            return context['__p0'] + _DELTA
        return context['__p0']

    receipt = scratch.solve_from_scratch(
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=oracle,
        max_selection_queries=1,
        max_candidates=1,
        max_depth=0,
    )

    assert receipt.passed is False
    assert receipt.reason == 'terminal_mismatch'
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 1
    assert receipt.terminal_exact == 0
    assert receipt.false_accepts == 0
