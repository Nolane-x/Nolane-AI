from __future__ import annotations

from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r268_adaptive_causal_basis import (
    BasisCollisionCertificate,
    build_basis_collision_certificate,
    synthesize_adaptive_causal_basis,
    verify_basis_collision_certificate,
)


def _collision_examples() -> tuple[OperatorExample, ...]:
    return (
        OperatorExample('a', {'__p0': 7.0, '__f1': -2.0}, 11.0),
        OperatorExample('b', {'__p0': 7.0, '__f1': -2.0}, 13.0),
        OperatorExample('c', {'__p0': 9.0, '__f1': -2.0}, 17.0),
    )


def test_basis_collision_certificate_is_replayable_and_not_subset_authority() -> None:
    examples=_collision_examples()
    cert=build_basis_collision_certificate(
        semantic_profile_ids=('profile-a',),
        exposed_fields=('__p0','__f1'),
        examples=examples,
    )
    assert isinstance(cert,BasisCollisionCertificate)
    assert cert is not None
    assert cert.basis_cardinality==1
    assert cert.semantic_profile_ids==('profile-a',)
    assert cert.proof_kind=='public_basis_target_collision'
    assert verify_basis_collision_certificate(
        cert,examples,
        semantic_profile_ids=('profile-a',),
        exposed_fields=('__p0','__f1'),
    ) is True


def test_global_minimality_receipt_carries_one_certificate_per_lower_basis() -> None:
    fields=('a','b')
    def ctx(rows): return tuple(dict(zip(fields,row,strict=True)) for row in rows)
    def oracle(row): return float(row['a'])+float(row['b'])
    need=OperatorInventionNeed('R2.68 replayable global ledger',fields,'out',constants=(0.0,2.0),max_depth=5,max_candidates=120_000)
    receipt=synthesize_adaptive_causal_basis(
        oracle,fields,need,
        ctx(((-2,-2),(-2,-1),(-1,-2),(1,3),(4,-2),(5,7))),
        ctx(((2,5),(-3,6),(8,-4))),
        terminal_contexts=ctx(((101,103),(-109,113),(127,-131))),
        intervention_anchor_values=(0.0,),intervention_arity=1,max_basis_size=2,
        composition_constants=(0.0,2.0),composition_max_depth=5,
        composition_max_candidates_per_basis=30_000,max_composition_candidates_total=160_000,
        composition_beam_width=192,probe_constants=(0.0,2.0),probe_max_depth=5,
        probe_max_candidates=50_000,probe_beam_width=192,
    )
    assert receipt.passed is True
    assert receipt.globally_minimal is True
    assert receipt.structure.lower_basis_count==2
    assert receipt.structure.lower_basis_certified==2
    assert len(receipt.structure.lower_basis_certificates)==2
    assert {cert.basis_cardinality for cert in receipt.structure.lower_basis_certificates}=={1}
    assert len({cert.witness_digest for cert in receipt.structure.lower_basis_certificates})==2
