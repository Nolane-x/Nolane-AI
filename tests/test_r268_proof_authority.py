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
