from __future__ import annotations

import pytest

import cogcoder._r268_runtime as runtime
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r268_adaptive_causal_basis import synthesize_adaptive_causal_basis


FIELDS = ('a', 'b')


def _contexts(rows):
    return tuple(dict(zip(FIELDS, row, strict=True)) for row in rows)


def _need() -> OperatorInventionNeed:
    return OperatorInventionNeed(
        'R2.68 learning/validation query-disjointness challenger',
        FIELDS,
        'out',
        constants=(0.0, 2.0),
        max_depth=5,
        max_candidates=120_000,
    )


def _solve(discovery_rows, validation_rows, *, oracle=None):
    if oracle is None:
        def oracle(row):
            return float(row['a']) + float(row['b'])

    return synthesize_adaptive_causal_basis(
        oracle,
        FIELDS,
        _need(),
        _contexts(discovery_rows),
        _contexts(validation_rows),
        terminal_contexts=_contexts(((101, 103), (-109, 113), (127, -131))),
        intervention_anchor_values=(0.0,),
        intervention_arity=1,
        max_basis_size=2,
        composition_constants=(0.0, 2.0),
        composition_max_depth=5,
        composition_max_candidates_per_basis=30_000,
        max_composition_candidates_total=160_000,
        composition_beam_width=192,
        probe_constants=(0.0, 2.0),
        probe_max_depth=5,
        probe_max_candidates=50_000,
        probe_beam_width=192,
    )


def test_rejects_validation_base_row_reused_from_discovery() -> None:
    discovery = ((1, 2), (2, 3), (-2, 5), (4, -3), (5, 7), (-1, -2))
    validation = ((1, 2), (7, 8), (9, -4))
    with pytest.raises(ValueError, match='discovery|validation|overlap|disjoint'):
        _solve(discovery, validation)


def test_rejects_validation_base_row_already_seen_as_discovery_intervention() -> None:
    # Setting a=0 on discovery row (1, 2) queries oracle at (0, 2).
    # Reusing (0, 2) as a validation target is therefore not disjoint evidence.
    discovery = ((1, 2), (2, 3), (-2, 5), (4, -3), (5, 7), (-1, -2))
    validation = ((0, 2), (7, 8), (9, -4))
    with pytest.raises(ValueError, match='discovery|validation|overlap|disjoint'):
        _solve(discovery, validation)


def test_rejects_validation_intervention_query_already_seen_in_discovery() -> None:
    # Discovery directly queries (0, 2). Validation row (1, 2) is distinct,
    # but its a=0 intervention queries that same already-observed input.
    discovery = ((0, 2), (2, 3), (-2, 5), (4, -3), (5, 7), (-1, -2))
    validation = ((1, 2), (7, 8), (9, -4))
    with pytest.raises(ValueError, match='discovery|validation|overlap|disjoint'):
        _solve(discovery, validation)


def test_overlap_rejection_happens_before_any_oracle_execution() -> None:
    calls = 0

    def counted_oracle(row):
        nonlocal calls
        calls += 1
        return float(row['a']) + float(row['b'])

    discovery = ((1, 2), (2, 3), (-2, 5), (4, -3), (5, 7), (-1, -2))
    validation = ((0, 2), (7, 8), (9, -4))
    with pytest.raises(ValueError, match='discovery|validation|overlap|disjoint'):
        _solve(discovery, validation, oracle=counted_oracle)
    assert calls == 0


def test_private_runtime_cannot_bypass_cross_phase_query_isolation() -> None:
    calls = 0

    def counted_oracle(row):
        nonlocal calls
        calls += 1
        return float(row['a']) + float(row['b'])

    discovery = _contexts(((1, 2), (2, 3), (-2, 5), (4, -3), (5, 7), (-1, -2)))
    validation = _contexts(((0, 2), (7, 8), (9, -4)))
    with pytest.raises(ValueError, match='discovery|validation|overlap|disjoint'):
        runtime.discover_adaptive_causal_basis(
            counted_oracle,
            FIELDS,
            (0.0,),
            discovery,
            validation,
            intervention_arity=1,
            max_basis_size=2,
        )
    assert calls == 0
