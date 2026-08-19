from __future__ import annotations

import pytest

from cogcoder.r256_operator_invention import OperatorExample
from cogcoder.r268_adaptive_causal_basis import build_public_target_collision_certificate


def _collision_examples() -> tuple[OperatorExample, ...]:
    return (
        OperatorExample('a', {'__p0': 7.0, '__f1': -2.0}, 11.0),
        OperatorExample('b', {'__p0': 7.0, '__f1': -2.0}, 13.0),
        OperatorExample('c', {'__p0': 9.0, '__f1': -2.0}, 17.0),
    )


def test_full_basis_cannot_mint_a_necessity_certificate() -> None:
    with pytest.raises(ValueError, match='proper subset'):
        build_public_target_collision_certificate(
            basis_semantic_profile_ids=('basis-a', 'basis-b'),
            subset_semantic_profile_ids=('basis-a', 'basis-b'),
            exposed_fields=('__p0', '__f1'),
            examples=_collision_examples(),
        )


def test_foreign_profile_ids_cannot_mint_a_necessity_certificate() -> None:
    with pytest.raises(ValueError, match='subset'):
        build_public_target_collision_certificate(
            basis_semantic_profile_ids=('basis-a', 'basis-b'),
            subset_semantic_profile_ids=('basis-a', 'foreign-profile'),
            exposed_fields=('__p0', '__f1'),
            examples=_collision_examples(),
        )


def test_duplicate_profile_ids_cannot_weaken_subset_cardinality() -> None:
    with pytest.raises(ValueError, match='distinct'):
        build_public_target_collision_certificate(
            basis_semantic_profile_ids=('basis-a', 'basis-b'),
            subset_semantic_profile_ids=('basis-a', 'basis-a'),
            exposed_fields=('__p0', '__f1'),
            examples=_collision_examples(),
        )
