from __future__ import annotations

import pytest

from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r268_adaptive_causal_basis import (
    build_public_target_collision_certificate,
    synthesize_adaptive_causal_basis,
)


def _collision_examples() -> tuple[OperatorExample, ...]:
    return (
        OperatorExample('a', {'__p0': 7.0, '__f1': -2.0}, 11.0),
        OperatorExample('b', {'__p0': 7.0, '__f1': -2.0}, 13.0),
        OperatorExample('c', {'__p0': 9.0, '__f1': -2.0}, 17.0),
    )


def test_full_basis_cannot_mint_necessity_certificate() -> None:
    with pytest.raises(ValueError, match='proper subset'):
        build_public_target_collision_certificate(
            basis_semantic_profile_ids=('basis-a', 'basis-b'),
            subset_semantic_profile_ids=('basis-a', 'basis-b'),
            exposed_fields=('__p0', '__f1'),
            examples=_collision_examples(),
        )


def test_runtime_necessity_certificates_bind_to_selected_basis_proper_subsets() -> None:
    fields = ('a', 'b')

    def oracle(row):
        return float(row['a']) + float(row['b'])

    discovery = tuple(dict(zip(fields, values, strict=True)) for values in ((-2,-2),(-2,-1),(-1,-2),(1,3),(4,-2),(5,7)))
    validation = tuple(dict(zip(fields, values, strict=True)) for values in ((2,5),(-3,6),(8,-4)))
    terminal = tuple(dict(zip(fields, values, strict=True)) for values in ((101,103),(-109,113),(127,-131)))
    need = OperatorInventionNeed('R2.68 selected-basis certificate binding',fields,'out',constants=(0.0,2.0),max_depth=5,max_candidates=120_000)
    receipt = synthesize_adaptive_causal_basis(
        oracle,fields,need,discovery,validation,terminal_contexts=terminal,
        intervention_anchor_values=(0.0,),intervention_arity=1,max_basis_size=2,
        composition_constants=(0.0,2.0),composition_max_depth=5,
        composition_max_candidates_per_basis=30_000,max_composition_candidates_total=160_000,
        composition_beam_width=192,probe_constants=(0.0,2.0),probe_max_depth=5,
        probe_max_candidates=50_000,probe_beam_width=192,
    )
    assert receipt.passed is True
    assert receipt.selected_basis_size == 2
    assert receipt.globally_minimal is True
    selected = receipt.structure.selected
    assert selected is not None
    selected_ids = selected.semantic_profile_ids
    assert len(receipt.structure.necessity_certificates) == 2
    for certificate in receipt.structure.necessity_certificates:
        assert certificate.basis_semantic_profile_ids == selected_ids
        assert 0 < certificate.subset_cardinality < selected.basis_size
        assert set(certificate.subset_semantic_profile_ids) < set(selected_ids)
