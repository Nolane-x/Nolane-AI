from __future__ import annotations

from dataclasses import replace

import pytest

from cogcoder.r256_operator_invention import OperatorExample


def _module():
    try:
        import cogcoder.r268_adaptive_causal_basis as r268
    except ImportError as exc:
        pytest.fail(f'R2.68 module missing: {exc}')
    return r268


def _collision_examples() -> tuple[OperatorExample, ...]:
    return (
        OperatorExample('a', {'__p0': 7.0, '__f1': -2.0}, 11.0),
        OperatorExample('b', {'__p0': 7.0, '__f1': -2.0}, 13.0),
        OperatorExample('c', {'__p0': 9.0, '__f1': -2.0}, 17.0),
    )


def test_public_collision_certificate_recomputes_and_verifies() -> None:
    r268 = _module(); examples = _collision_examples()
    cert = r268.build_public_target_collision_certificate(basis_semantic_profile_ids=('basis-a', 'basis-b'), subset_semantic_profile_ids=('basis-a',), exposed_fields=('__p0', '__f1'), examples=examples)
    assert cert is not None and cert.proof_kind == 'public_target_collision' and cert.subset_cardinality == 1 and cert.witness_rows == (0, 1)
    assert r268.verify_necessity_certificate(cert, examples, basis_semantic_profile_ids=('basis-a', 'basis-b'), subset_semantic_profile_ids=('basis-a',), exposed_fields=('__p0', '__f1')) is True


def test_certificate_cannot_be_reused_across_subset_exposure() -> None:
    r268 = _module(); examples = _collision_examples()
    cert = r268.build_public_target_collision_certificate(basis_semantic_profile_ids=('basis-a', 'basis-b'), subset_semantic_profile_ids=('basis-a',), exposed_fields=('__p0', '__f1'), examples=examples)
    assert cert is not None
    forged = replace(cert, exposed_fields=('__p0',))
    assert r268.verify_necessity_certificate(forged, examples, basis_semantic_profile_ids=('basis-a', 'basis-b'), subset_semantic_profile_ids=('basis-a',), exposed_fields=('__p0',)) is False
    assert r268.verify_necessity_certificate(cert, examples, basis_semantic_profile_ids=('basis-a', 'basis-b'), subset_semantic_profile_ids=('different-profile',), exposed_fields=('__p0', '__f1')) is False


def test_no_collision_never_mints_necessity_certificate() -> None:
    r268 = _module()
    examples = (OperatorExample('a', {'__p0': 1.0}, 2.0), OperatorExample('b', {'__p0': 2.0}, 4.0), OperatorExample('c', {'__p0': 3.0}, 6.0))
    cert = r268.build_public_target_collision_certificate(basis_semantic_profile_ids=('basis-a', 'basis-b'), subset_semantic_profile_ids=('basis-a',), exposed_fields=('__p0',), examples=examples)
    assert cert is None


def test_no_collision_lower_order_search_miss_stays_minimality_inconclusive(monkeypatch) -> None:
    import cogcoder._r268_runtime as runtime
    from cogcoder._r268_search import ExpressionSearchReceipt
    from cogcoder.r256_operator_invention import OperatorInventionNeed
    original=runtime.synthesize_variable_expression
    def forced(field_names, required_probe_fields, constants, examples, **kwargs):
        if len(tuple(required_probe_fields))==1: return ExpressionSearchReceipt(False,None,1,1,1,'synthetic_search_miss')
        return original(field_names,required_probe_fields,constants,examples,**kwargs)
    monkeypatch.setattr(runtime,'synthesize_variable_expression',forced)
    fields=('a','b')
    def oracle(row): return float(row['a'])+float(row['b'])
    def ctx(rows): return tuple(dict(zip(fields,row,strict=True)) for row in rows)
    need=OperatorInventionNeed('no collision search miss',fields,'out',constants=(0.0,2.0),max_depth=5,max_candidates=100_000)
    receipt=runtime.synthesize_adaptive_causal_basis(oracle,fields,need,ctx(((1,10),(2,20),(3,30),(4,40))),ctx(((5,50),(6,60))),terminal_contexts=ctx(((101,103),(-109,113))),intervention_anchor_values=(0.0,),intervention_arity=1,max_basis_size=2,composition_constants=(0.0,2.0),composition_max_depth=5,composition_max_candidates_per_basis=20_000,max_composition_candidates_total=80_000,composition_beam_width=128,probe_constants=(0.0,2.0),probe_max_depth=5,probe_max_candidates=30_000,probe_beam_width=128)
    assert receipt.passed is True and receipt.selected_basis_size==2 and receipt.globally_minimal is False
    assert receipt.reason=='sufficient_but_minimality_inconclusive' and receipt.structure.unresolved_lower_order


def test_collision_certificate_rejects_nonmember_subset_identity() -> None:
    r268=_module(); examples=_collision_examples()
    with pytest.raises(ValueError, match='subset semantic profile ids must belong to basis'):
        r268.build_public_target_collision_certificate(basis_semantic_profile_ids=('basis-a','basis-b'), subset_semantic_profile_ids=('outside-basis',), exposed_fields=('__p0','__f1'), examples=examples)


def test_collision_certificate_normalizes_numeric_aliases() -> None:
    r268=_module()
    examples=(OperatorExample('int-float',{'__p0':1,'__f1':2.0},11.0), OperatorExample('float-int',{'__p0':1.0,'__f1':2},13.0))
    cert=r268.build_public_target_collision_certificate(basis_semantic_profile_ids=('basis-a','basis-b'),subset_semantic_profile_ids=('basis-a',),exposed_fields=('__p0','__f1'),examples=examples)
    assert cert is not None


def test_certificate_evidence_digest_is_numeric_semantic_invariant() -> None:
    r268=_module()
    a=(OperatorExample('x',{'__p0':1,'__f1':2.0},11), OperatorExample('y',{'__p0':1.0,'__f1':2},13.0))
    b=(OperatorExample('x',{'__p0':1.0,'__f1':2},11.0), OperatorExample('y',{'__p0':1,'__f1':2.0},13))
    ca=r268.build_public_target_collision_certificate(basis_semantic_profile_ids=('a','b'),subset_semantic_profile_ids=('a',),exposed_fields=('__p0','__f1'),examples=a)
    cb=r268.build_public_target_collision_certificate(basis_semantic_profile_ids=('a','b'),subset_semantic_profile_ids=('a',),exposed_fields=('__p0','__f1'),examples=b)
    assert ca is not None and cb is not None
    assert ca.evidence_digest==cb.evidence_digest and ca.witness_digest==cb.witness_digest
