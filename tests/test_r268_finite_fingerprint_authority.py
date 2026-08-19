from __future__ import annotations

from cogcoder.r256_operator_dsl import Binary, Const, Field
import cogcoder.r268_cross_task_causal_transfer as transfer
import cogcoder.r268_cross_task_transfer_baseline as scratch


def _portable() -> transfer.PortableCausalProgram:
    expression = Binary(
        'add',
        Binary('add', Field('__p0'), Field('__p1')),
        Field('__p2'),
    )
    return transfer.export_expression_prior(expression)


def _vanishing_factor():
    # Exactly zero for every p1 value that the current bounded semantic closure
    # can reconstruct from the diagnostics below, but non-zero at p1 == 8.
    expression = Binary('sub', Field('__p1'), Const(0))
    for value in range(1, 8):
        expression = Binary(
            'mul',
            expression,
            Binary('sub', Field('__p1'), Const(value)),
        )
    return expression


def _finite_collision_candidates() -> tuple[transfer.TransferCandidate, ...]:
    plain = Field('__p0')
    hidden_difference = Binary('add', Field('__p0'), _vanishing_factor())
    return (
        transfer.TransferCandidate(
            expression=plain,
            candidate_id='finite-fingerprint.a',
            repair_distance=0,
            role_permutation_distance=0,
        ),
        transfer.TransferCandidate(
            expression=hidden_difference,
            candidate_id='finite-fingerprint.b',
            repair_distance=0,
            role_permutation_distance=0,
        ),
    )


def _diagnostics() -> tuple[dict[str, int], ...]:
    # There are exactly eight public marginal values for p0 and p1. The current
    # semantic-closure heuristic therefore uses all of them; candidate B still
    # vanishes on every original row and every Cartesian recombination.
    return tuple(
        {'__p0': index + 1, '__p1': index, '__p2': 0}
        for index in range(8)
    )


def _terminals() -> tuple[dict[str, int], ...]:
    # p1 == 8 is outside the diagnostic marginal bank, so candidate B differs
    # from candidate A here by 8! while A matches the target oracle.
    return ({'__p0': 10, '__p1': 8, '__p2': 1},)


def _target_oracle(context):
    return context['__p0']


def test_transfer_finite_fingerprint_collision_cannot_authorize_uniqueness(monkeypatch):
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: _finite_collision_candidates(),
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


def test_scratch_finite_fingerprint_collision_cannot_authorize_uniqueness(monkeypatch):
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: _finite_collision_candidates(),
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
