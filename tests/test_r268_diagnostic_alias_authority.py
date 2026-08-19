from __future__ import annotations

from cogcoder.r256_operator_dsl import Binary, Field
import cogcoder.r268_cross_task_causal_transfer as transfer
import cogcoder.r268_cross_task_transfer_baseline as scratch


def _candidate(role: str) -> transfer.TransferCandidate:
    expression = Field(role)
    return transfer.TransferCandidate(
        expression=expression,
        candidate_id=f'alias.{role}',
        repair_distance=0,
        role_permutation_distance=0,
    )


def _diagnostic_collision_candidates() -> tuple[transfer.TransferCandidate, ...]:
    return (_candidate('__p0'), _candidate('__p1'))


def _diagnostics() -> tuple[dict[str, int], ...]:
    # The two hypotheses are genuinely different but collide on every allowed
    # selection row. A diagnostic-only semantic dedupe must not silently choose
    # one of them merely because this finite diagnostic surface aliases them.
    return (
        {'__p0': 1, '__p1': 1, '__p2': 0},
        {'__p0': 2, '__p1': 2, '__p2': 1},
        {'__p0': -3, '__p1': -3, '__p2': 4},
    )


def _terminals() -> tuple[dict[str, int], ...]:
    return ({'__p0': 7, '__p1': 11, '__p2': 5},)


def _target_oracle(context):
    return context['__p0']


def _portable() -> transfer.PortableCausalProgram:
    expression = Binary(
        'add',
        Binary('add', Field('__p0'), Field('__p1')),
        Field('__p2'),
    )
    return transfer.export_expression_prior(expression)


def test_transfer_diagnostic_collision_does_not_create_false_uniqueness(monkeypatch):
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: _diagnostic_collision_candidates(),
    )

    receipt = transfer.adapt_portable_program(
        _portable(),
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=_target_oracle,
        max_selection_queries=3,
        max_candidates=2,
    )

    assert receipt.passed is False
    assert receipt.reason == 'no_discriminating_diagnostic'
    assert receipt.selection_queries == 0
    assert receipt.terminal_queries == 0
    assert receipt.false_accepts == 0


def test_scratch_diagnostic_collision_does_not_create_false_uniqueness(monkeypatch):
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: _diagnostic_collision_candidates(),
    )

    receipt = scratch.solve_from_scratch(
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=_target_oracle,
        max_selection_queries=3,
        max_candidates=2,
        max_depth=0,
    )

    assert receipt.passed is False
    assert receipt.reason == 'no_discriminating_diagnostic'
    assert receipt.selection_queries == 0
    assert receipt.terminal_queries == 0
    assert receipt.false_accepts == 0
