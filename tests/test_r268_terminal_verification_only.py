from __future__ import annotations

# Hosted RED authority: run 32254278088 reproduced both terminal-selection leaks
# before the production guard was materialized. Source fix: b3d454e7b05b47bbc80108809f393765561ae0d5.

from cogcoder.r256_operator_dsl import Binary, Field
import cogcoder.r268_cross_task_causal_transfer as transfer
import cogcoder.r268_cross_task_transfer_baseline as scratch


def _candidate(role: str, suffix: str) -> transfer.TransferCandidate:
    expression = Field(role)
    return transfer.TransferCandidate(
        expression=expression,
        candidate_id=f'test.{suffix}',
        repair_distance=0,
        role_permutation_distance=0,
    )


def _ambiguous_after_one_query_candidates() -> tuple[transfer.TransferCandidate, ...]:
    return (
        _candidate('__p0', 'p0'),
        _candidate('__p1', 'p1'),
        _candidate('__p2', 'p2'),
    )


def _diagnostics() -> tuple[dict[str, int], ...]:
    # Both rows split the three hypotheses 2-vs-1. The first row wins the
    # deterministic tie-break and leaves __p0/__p1 ambiguous under a one-query
    # selection budget. The second row proves those survivors are genuinely
    # distinct, so diagnostic deduplication must retain both.
    return (
        {'__p0': 0, '__p1': 0, '__p2': 1},
        {'__p0': 1, '__p1': 2, '__p2': 1},
    )


def _terminals() -> tuple[dict[str, int], ...]:
    return ({'__p0': 3, '__p1': 4, '__p2': 5},)


def _target_oracle(context):
    return context['__p0']


def _portable() -> transfer.PortableCausalProgram:
    expression = Binary(
        'add',
        Binary('add', Field('__p0'), Field('__p1')),
        Field('__p2'),
    )
    return transfer.export_expression_prior(expression)


def test_transfer_terminal_rows_verify_but_do_not_select(monkeypatch):
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: _ambiguous_after_one_query_candidates(),
    )

    receipt = transfer.adapt_portable_program(
        _portable(),
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=_target_oracle,
        max_selection_queries=1,
        max_candidates=3,
    )

    assert receipt.passed is False
    assert receipt.reason == 'ambiguous_after_selection'
    assert receipt.candidates_live_after_selection == 2
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 0
    assert receipt.terminal_exact == 0


def test_scratch_terminal_rows_verify_but_do_not_select(monkeypatch):
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: _ambiguous_after_one_query_candidates(),
    )

    receipt = scratch.solve_from_scratch(
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=_target_oracle,
        max_selection_queries=1,
        max_candidates=3,
        max_depth=0,
    )

    assert receipt.passed is False
    assert receipt.reason == 'ambiguous_after_selection'
    assert receipt.candidates_live_after_selection == 2
    assert receipt.selection_queries == 1
    assert receipt.terminal_queries == 0
    assert receipt.terminal_exact == 0
