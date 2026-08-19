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
    r268 = _module()
    examples = _collision_examples()
    cert = r268.build_public_target_collision_certificate(
        basis_semantic_profile_ids=('basis-a', 'basis-b'),
        subset_semantic_profile_ids=('basis-a',),
        exposed_fields=('__p0', '__f1'),
        examples=examples,
    )
    assert cert is not None
    assert cert.proof_kind == 'public_target_collision'
    assert cert.subset_cardinality == 1
    assert cert.witness_rows == (0, 1)
    assert r268.verify_necessity_certificate(
        cert,
        examples,
        basis_semantic_profile_ids=('basis-a', 'basis-b'),
        subset_semantic_profile_ids=('basis-a',),
        exposed_fields=('__p0', '__f1'),
    ) is True


def test_certificate_cannot_be_reused_across_subset_exposure() -> None:
    r268 = _module()
    examples = _collision_examples()
    cert = r268.build_public_target_collision_certificate(
        basis_semantic_profile_ids=('basis-a', 'basis-b'),
        subset_semantic_profile_ids=('basis-a',),
        exposed_fields=('__p0', '__f1'),
        examples=examples,
    )
    assert cert is not None
    forged = replace(cert, exposed_fields=('__p0',))
    assert r268.verify_necessity_certificate(
        forged,
        examples,
        basis_semantic_profile_ids=('basis-a', 'basis-b'),
        subset_semantic_profile_ids=('basis-a',),
        exposed_fields=('__p0',),
    ) is False
    assert r268.verify_necessity_certificate(
        cert,
        examples,
        basis_semantic_profile_ids=('basis-a', 'basis-b'),
        subset_semantic_profile_ids=('different-profile',),
        exposed_fields=('__p0', '__f1'),
    ) is False


def test_no_collision_never_mints_necessity_certificate() -> None:
    r268 = _module()
    examples = (
        OperatorExample('a', {'__p0': 1.0}, 2.0),
        OperatorExample('b', {'__p0': 2.0}, 4.0),
        OperatorExample('c', {'__p0': 3.0}, 6.0),
    )
    cert = r268.build_public_target_collision_certificate(
        basis_semantic_profile_ids=('basis-a', 'basis-b'),
        subset_semantic_profile_ids=('basis-a',),
        exposed_fields=('__p0',),
        examples=examples,
    )
    assert cert is None


def test_no_collision_lower_order_search_miss_stays_minimality_inconclusive(monkeypatch) -> None:
    import cogcoder._r268_runtime as runtime
    from cogcoder._r268_search import ExpressionSearchReceipt
    from cogcoder.r256_operator_invention import OperatorInventionNeed
    original=runtime.synthesize_variable_expression
    def forced(field_names, required_probe_fields, constants, examples, **kwargs):
        if len(tuple(required_probe_fields))==1:
            return ExpressionSearchReceipt(False,None,1,1,1,'synthetic_search_miss')
        return original(field_names,required_probe_fields,constants,examples,**kwargs)
    monkeypatch.setattr(runtime,'synthesize_variable_expression',forced)
    fields=('a','b')
    def oracle(row): return float(row['a'])+float(row['b'])
    def ctx(rows): return tuple(dict(zip(fields,row,strict=True)) for row in rows)
    need=OperatorInventionNeed('no collision search miss',fields,'out',constants=(0.0,2.0),max_depth=5,max_candidates=100_000)
    receipt=runtime.synthesize_adaptive_causal_basis(
        oracle,fields,need,ctx(((1,10),(2,20),(3,30),(4,40))),ctx(((5,50),(6,60))),
        terminal_contexts=ctx(((101,103),(-109,113))),intervention_anchor_values=(0.0,),intervention_arity=1,max_basis_size=2,
        composition_constants=(0.0,2.0),composition_max_depth=5,composition_max_candidates_per_basis=20_000,max_composition_candidates_total=80_000,
        composition_beam_width=128,probe_constants=(0.0,2.0),probe_max_depth=5,probe_max_candidates=30_000,probe_beam_width=128)
    assert receipt.passed is True
    assert receipt.selected_basis_size==2
    assert receipt.globally_minimal is False
    assert receipt.reason=='sufficient_but_minimality_inconclusive'
    assert receipt.structure.unresolved_lower_order
