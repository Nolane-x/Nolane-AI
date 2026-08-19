from __future__ import annotations

import hashlib
import json
from typing import Sequence

from .r256_operator_invention import OperatorExample
from ._r268_search import equivalent, finite_json_value, semantic_key
from ._r268_types import NecessityCertificate


def canonical_evidence_payload(
    examples: Sequence[OperatorExample],
    exposed_fields: Sequence[str],
) -> list[dict[str, object]]:
    fields = tuple(map(str, exposed_fields))
    rows: list[dict[str, object]] = []
    for index, example in enumerate(tuple(examples)):
        missing = [field for field in fields if field not in example.context]
        if missing:
            raise KeyError(f'missing exposed fields: {missing}')
        rows.append(
            {
                'index': index,
                'values_semantic': semantic_key(
                    tuple(finite_json_value(example.context[field]) for field in fields)
                ),
                'target_semantic': semantic_key((finite_json_value(example.expected),)),
            }
        )
    return rows


def canonical_evidence_digest(
    examples: Sequence[OperatorExample],
    exposed_fields: Sequence[str],
) -> str:
    raw = json.dumps(
        {
            'exposed_fields': list(map(str, exposed_fields)),
            'rows': canonical_evidence_payload(examples, exposed_fields),
        },
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def public_target_collision_witness(
    examples: Sequence[OperatorExample],
    exposed_fields: Sequence[str],
) -> tuple[int, int] | None:
    """Return a public information-theoretic collision witness, without authority metadata."""
    fields = tuple(map(str, exposed_fields))
    if not fields:
        raise ValueError('exposed_fields must be non-empty')
    rows = tuple(examples)
    seen: dict[str, tuple[int, object]] = {}
    for index, example in enumerate(rows):
        values = tuple(finite_json_value(example.context[field]) for field in fields)
        key = semantic_key(values)
        target = finite_json_value(example.expected)
        previous = seen.get(key)
        if previous is not None and not equivalent(previous[1], target):
            return previous[0], index
        seen[key] = (index, target)
    return None


def has_public_target_collision(
    examples: Sequence[OperatorExample],
    exposed_fields: Sequence[str],
) -> bool:
    return public_target_collision_witness(examples, exposed_fields) is not None


def _validated_authority_ids(
    basis_semantic_profile_ids: Sequence[str],
    subset_semantic_profile_ids: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    basis_ids = tuple(map(str, basis_semantic_profile_ids))
    subset_ids = tuple(map(str, subset_semantic_profile_ids))
    if not basis_ids or not subset_ids:
        raise ValueError('basis and subset semantic profile ids must be non-empty')
    if len(set(basis_ids)) != len(basis_ids) or len(set(subset_ids)) != len(subset_ids):
        raise ValueError('semantic profile ids must be distinct')
    if not set(subset_ids) < set(basis_ids):
        raise ValueError('subset semantic profile ids must form a proper subset of basis')
    return basis_ids, subset_ids


def build_public_target_collision_certificate(
    *,
    basis_semantic_profile_ids: Sequence[str],
    subset_semantic_profile_ids: Sequence[str],
    exposed_fields: Sequence[str],
    examples: Sequence[OperatorExample],
) -> NecessityCertificate | None:
    basis_ids, subset_ids = _validated_authority_ids(
        basis_semantic_profile_ids,
        subset_semantic_profile_ids,
    )
    fields = tuple(map(str, exposed_fields))
    rows = tuple(examples)
    if not fields:
        raise ValueError('exposed_fields must be non-empty')
    evidence_digest = canonical_evidence_digest(rows, fields)
    witness = public_target_collision_witness(rows, fields)
    if witness is None:
        return None
    left, right = witness
    witness_raw = json.dumps(
        {
            'proof_kind': 'public_target_collision',
            'evidence_digest': evidence_digest,
            'exposed_fields': list(fields),
            'witness_rows': [left, right],
            'values_semantic': semantic_key(
                tuple(finite_json_value(rows[left].context[field]) for field in fields)
            ),
            'targets_semantic': semantic_key(
                (
                    finite_json_value(rows[left].expected),
                    finite_json_value(rows[right].expected),
                )
            ),
        },
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    )
    return NecessityCertificate(
        basis_ids,
        subset_ids,
        len(subset_ids),
        fields,
        evidence_digest,
        'public_target_collision',
        hashlib.sha256(witness_raw.encode()).hexdigest(),
        (left, right),
    )


def verify_necessity_certificate(
    certificate: NecessityCertificate,
    examples: Sequence[OperatorExample],
    *,
    basis_semantic_profile_ids: Sequence[str],
    subset_semantic_profile_ids: Sequence[str],
    exposed_fields: Sequence[str],
) -> bool:
    if not isinstance(certificate, NecessityCertificate):
        return False
    try:
        basis_ids, subset_ids = _validated_authority_ids(
            basis_semantic_profile_ids,
            subset_semantic_profile_ids,
        )
    except ValueError:
        return False
    fields = tuple(map(str, exposed_fields))
    if (
        certificate.proof_kind != 'public_target_collision'
        or certificate.basis_semantic_profile_ids != basis_ids
        or certificate.subset_semantic_profile_ids != subset_ids
        or certificate.subset_cardinality != len(subset_ids)
        or certificate.exposed_fields != fields
    ):
        return False
    try:
        if certificate.evidence_digest != canonical_evidence_digest(examples, fields):
            return False
        rows = tuple(examples)
        left, right = certificate.witness_rows
        if left < 0 or right < 0 or left >= len(rows) or right >= len(rows) or left == right:
            return False
        if semantic_key(
            tuple(finite_json_value(rows[left].context[field]) for field in fields)
        ) != semantic_key(
            tuple(finite_json_value(rows[right].context[field]) for field in fields)
        ):
            return False
        if equivalent(
            finite_json_value(rows[left].expected),
            finite_json_value(rows[right].expected),
        ):
            return False
        recomputed = build_public_target_collision_certificate(
            basis_semantic_profile_ids=basis_ids,
            subset_semantic_profile_ids=subset_ids,
            exposed_fields=fields,
            examples=rows,
        )
        return (
            recomputed is not None
            and recomputed.witness_digest == certificate.witness_digest
            and recomputed.witness_rows == certificate.witness_rows
        )
    except (KeyError, TypeError, ValueError):
        return False
