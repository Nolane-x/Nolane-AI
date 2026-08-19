from __future__ import annotations

import pytest

from cogcoder.r256_operator_invention import OperatorInventionNeed


def _module():
    try:
        import cogcoder.r268_adaptive_causal_basis as r268
    except ImportError as exc:
        pytest.fail(f'R2.68 module missing: {exc}')
    return r268


def _need(label: str, fields: tuple[str, ...]) -> OperatorInventionNeed:
    return OperatorInventionNeed(
        label,
        fields,
        'out',
        constants=(0.0, 2.0),
        max_depth=5,
        max_candidates=120_000,
    )


def _contexts(fields: tuple[str, ...], rows: tuple[tuple[float, ...], ...]) -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(fields, row, strict=True)) for row in rows)


def _solve(oracle, fields, discovery_rows, validation_rows, terminal_rows, *, max_basis_size):
    r268 = _module()
    return r268.synthesize_adaptive_causal_basis(
        oracle,
        fields,
        _need(f'R2.68 basis-{max_basis_size}', fields),
        _contexts(fields, discovery_rows),
        _contexts(fields, validation_rows),
        terminal_contexts=_contexts(fields, terminal_rows),
        intervention_anchor_values=(0.0,),
        intervention_arity=1,
        max_basis_size=max_basis_size,
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


def test_discovers_one_probe_sufficient_basis_without_false_minimality_claim() -> None:
    fields = ('a', 'b', 'c')

    def oracle(row):
        return float(row['a']) * float(row['b'])

    receipt = _solve(
        oracle,
        fields,
        ((1, 2, 3), (2, 3, 4), (-2, 5, 7), (4, -3, 9), (5, 2, 11), (-3, -2, 13)),
        ((6, 7, 15), (-5, 4, 17), (8, -2, 19)),
        ((101, 103, 107), (-109, 113, 127), (131, -137, 139)),
        max_basis_size=4,
    )
    assert receipt.passed is True
    assert receipt.selected_basis_size == 1
    assert receipt.globally_minimal is False
    assert receipt.reason == 'sufficient_but_minimality_inconclusive'
    assert receipt.false_accepts == 0
    assert receipt.final_validation_exact == receipt.final_validation_cases == 3
    assert receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases == 3


def test_certifies_two_probe_sum_basis() -> None:
    fields = ('a', 'b')

    def oracle(row):
        return float(row['a']) + float(row['b'])

    receipt = _solve(
        oracle,
        fields,
        ((-2, -2), (-2, -1), (-1, -2), (1, 3), (4, -2), (5, 7)),
        ((2, 5), (-3, 6), (8, -4)),
        ((101, 103), (-109, 113), (127, -131)),
        max_basis_size=2,
    )
    assert receipt.passed is True
    assert receipt.selected_basis_size == 2
    assert receipt.globally_minimal is True
    assert receipt.reason == 'adaptive_basis_discovered'
    assert len(receipt.structure.necessity_certificates) >= 2
    assert receipt.false_accepts == 0
    assert receipt.final_validation_exact == receipt.final_validation_cases == 3
    assert receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases == 6


def test_certifies_three_probe_triangle_basis() -> None:
    fields = ('a', 'b', 'c')

    def oracle(row):
        a, b, c = (float(row[name]) for name in fields)
        return a * b + b * c + c * a

    discovery = (
        (-2, -2, -2), (-2, -2, -1), (-2, -2, 0), (-2, -1, -2), (-2, -1, 0),
        (-2, 0, -2), (-2, 0, -1), (-1, -2, -2), (0, -2, -2), (0, -2, -1),
        (1, 2, 3), (4, -3, 2), (5, 2, -4),
    )
    receipt = _solve(
        oracle,
        fields,
        discovery,
        ((3, 5, 7), (-5, 4, 6), (8, -2, 9)),
        ((101, 103, 107), (-109, 113, 127), (131, -137, 139)),
        max_basis_size=3,
    )
    assert receipt.passed is True
    assert receipt.selected_basis_size == 3
    assert receipt.globally_minimal is True
    assert receipt.false_accepts == 0
    assert receipt.final_validation_exact == receipt.final_validation_cases == 3
    assert receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases == 9


def test_certifies_four_probe_complete_pairwise_basis() -> None:
    fields = ('a', 'b', 'c', 'd')

    def oracle(row):
        a, b, c, d = (float(row[name]) for name in fields)
        return a*b + a*c + a*d + b*c + b*d + c*d

    discovery = (
        (-2, -2, -2, -2), (-2, -2, -2, -1), (-2, -2, -2, 2),
        (-2, -2, -1, -2), (-2, -2, -1, 2), (-2, -2, 2, -2),
        (-2, -2, 2, -1), (-2, -2, 2, 2), (-2, -1, -2, -2),
        (-2, -1, -2, 2), (-2, -1, 2, 2), (-2, 2, -2, -2),
        (-2, 2, -2, -1), (-1, -2, -2, -2),
        (1, 2, 3, 4), (5, -3, 2, 7), (-4, 6, -2, 3),
    )
    receipt = _solve(
        oracle,
        fields,
        discovery,
        ((3, 5, 7, 11), (-5, 4, 6, -3), (8, -2, 9, 10)),
        ((101, 103, 107, 109), (-113, 127, 131, 137), (139, -149, 151, 157)),
        max_basis_size=4,
    )
    assert receipt.passed is True
    assert receipt.selected_basis_size == 4
    assert receipt.globally_minimal is True
    assert receipt.false_accepts == 0
    assert receipt.final_validation_exact == receipt.final_validation_cases == 3
    assert receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases == 12
    certified_sizes = {cert.subset_cardinality for cert in receipt.structure.necessity_certificates}
    assert {1, 2, 3} <= certified_sizes
