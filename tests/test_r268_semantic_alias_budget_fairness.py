from __future__ import annotations

from cogcoder.r268_adaptive_causal_basis import discover_adaptive_causal_basis


FIELDS = ('a', 'b')
DISCOVERY = (
    {'a': -2.0, 'b': -2.0},
    {'a': -2.0, 'b': -1.0},
    {'a': -1.0, 'b': -2.0},
    {'a': 1.0, 'b': 3.0},
    {'a': 4.0, 'b': -2.0},
    {'a': 5.0, 'b': 7.0},
)
VALIDATION = (
    {'a': 2.0, 'b': 5.0},
    {'a': -3.0, 'b': 6.0},
    {'a': 8.0, 'b': -4.0},
)


def _oracle(row) -> float:
    return abs(float(row['a'])) + abs(float(row['b']))


def _run(anchors: tuple[float, ...]):
    return discover_adaptive_causal_basis(
        _oracle,
        FIELDS,
        anchors,
        DISCOVERY,
        VALIDATION,
        intervention_arity=1,
        max_basis_size=2,
        composition_constants=(0.0, 2.0),
        composition_max_depth=5,
        composition_max_candidates_per_basis=60,
        max_composition_candidates_total=60,
        composition_beam_width=128,
    )


def test_behavior_identical_authority_aliases_do_not_dilute_proposal_budget() -> None:
    control = _run((-1.0,))
    aliased = _run((-1.0, 1.0))

    assert control.passed is True
    assert control.selected_basis_size == 2
    assert control.globally_minimal is True

    # Authority actions stay distinct: the fix must not erase aliases from the
    # proof universe merely to make proposal search cheaper.
    assert aliased.legal_interventions == 4
    assert aliased.semantic_profiles == 4

    # Proposal allocation, however, must be invariant to behavior-identical
    # aliases on the discovery evidence.
    assert aliased.passed is control.passed
    assert aliased.selected_basis_size == control.selected_basis_size
    assert aliased.globally_minimal is control.globally_minimal
    assert aliased.reason == control.reason
