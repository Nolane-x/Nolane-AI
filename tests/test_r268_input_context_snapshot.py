from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest

from cogcoder.r256_operator_dsl import Binary, Field
import cogcoder.r268_cross_task_causal_transfer as transfer
import cogcoder.r268_cross_task_transfer_baseline as scratch


class SwitchingContext(Mapping[str, int]):
    """Expose one semantic row for the first role-read pass, another afterward."""

    def __init__(self, first: dict[str, int], later: dict[str, int]) -> None:
        self._first = dict(first)
        self._later = dict(later)
        self.role_reads = 0

    def __getitem__(self, key: str) -> int:
        values = self._first if self.role_reads < 3 else self._later
        self.role_reads += 1
        return values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._first)

    def __len__(self) -> int:
        return len(self._first)


def _candidate() -> transfer.TransferCandidate:
    return transfer.TransferCandidate(
        expression=Field('__p0'),
        candidate_id='snapshot.p0',
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


def _rows():
    diagnostic_declared = {'__p0': 2, '__p1': 9, '__p2': 1}
    terminal_declared = {'__p0': 7, '__p1': 4, '__p2': 3}
    later_shared = {'__p0': 5, '__p1': 5, '__p2': 5}
    diagnostic = SwitchingContext(diagnostic_declared, later_shared)
    terminal = SwitchingContext(terminal_declared, later_shared)
    return diagnostic, terminal, diagnostic_declared, terminal_declared


def _recording_oracle(seen: list[tuple[int, int, int]]):
    def oracle(context):
        row = (context['__p0'], context['__p1'], context['__p2'])
        seen.append(row)
        return context['__p0']

    return oracle


def test_transfer_snapshots_contexts_before_disjointness_and_oracle_use(monkeypatch):
    diagnostic, terminal, declared_diagnostic, declared_terminal = _rows()
    seen: list[tuple[int, int, int]] = []
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: (_candidate(),),
    )

    receipt = transfer.adapt_portable_program(
        _portable(),
        diagnostic_contexts=(diagnostic,),
        terminal_contexts=(terminal,),
        oracle=_recording_oracle(seen),
        max_selection_queries=1,
        max_candidates=1,
    )

    assert receipt.passed is True
    assert seen == [
        (declared_diagnostic['__p0'], declared_diagnostic['__p1'], declared_diagnostic['__p2']),
        (declared_terminal['__p0'], declared_terminal['__p1'], declared_terminal['__p2']),
    ]
    assert diagnostic.role_reads == 3
    assert terminal.role_reads == 3
    assert receipt.query_trace[0].context_values == (2, 9, 1)


def test_scratch_snapshots_contexts_before_disjointness_and_oracle_use(monkeypatch):
    diagnostic, terminal, declared_diagnostic, declared_terminal = _rows()
    seen: list[tuple[int, int, int]] = []
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: (_candidate(),),
    )

    receipt = scratch.solve_from_scratch(
        diagnostic_contexts=(diagnostic,),
        terminal_contexts=(terminal,),
        oracle=_recording_oracle(seen),
        max_selection_queries=1,
        max_candidates=1,
        max_depth=0,
    )

    assert receipt.passed is True
    assert seen == [
        (declared_diagnostic['__p0'], declared_diagnostic['__p1'], declared_diagnostic['__p2']),
        (declared_terminal['__p0'], declared_terminal['__p1'], declared_terminal['__p2']),
    ]
    assert diagnostic.role_reads == 3
    assert terminal.role_reads == 3
    assert receipt.query_trace[0].context_values == (2, 9, 1)


def test_transfer_reused_mapping_cannot_masquerade_as_two_contexts(monkeypatch):
    shared = SwitchingContext(
        {'__p0': 2, '__p1': 9, '__p2': 1},
        {'__p0': 7, '__p1': 4, '__p2': 3},
    )
    monkeypatch.setattr(
        transfer,
        'generate_transfer_candidates',
        lambda _portable_program: (_candidate(),),
    )

    with pytest.raises(ValueError, match='selection and terminal contexts must be disjoint'):
        transfer.adapt_portable_program(
            _portable(),
            diagnostic_contexts=(shared,),
            terminal_contexts=(shared,),
            oracle=lambda context: context['__p0'],
            max_selection_queries=1,
            max_candidates=1,
        )

    assert shared.role_reads == 3


def test_scratch_reused_mapping_cannot_masquerade_as_two_contexts(monkeypatch):
    shared = SwitchingContext(
        {'__p0': 2, '__p1': 9, '__p2': 1},
        {'__p0': 7, '__p1': 4, '__p2': 3},
    )
    monkeypatch.setattr(
        scratch,
        'generate_scratch_candidates',
        lambda *, max_depth, max_candidates: (_candidate(),),
    )

    with pytest.raises(ValueError, match='selection and terminal contexts must be disjoint'):
        scratch.solve_from_scratch(
            diagnostic_contexts=(shared,),
            terminal_contexts=(shared,),
            oracle=lambda context: context['__p0'],
            max_selection_queries=1,
            max_candidates=1,
            max_depth=0,
        )

    assert shared.role_reads == 3
