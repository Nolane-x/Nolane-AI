from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Sequence

from .r256_operator_invention import OperatorExample


def _finite_json_value(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('values must be finite')
    try:
        json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError('values must be finite JSON-compatible values') from exc
    return value


def _equivalent(actual: object, expected: object) -> bool:
    if isinstance(actual, (int, float)) and not isinstance(actual, bool) and isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
        except (TypeError, ValueError, OverflowError):
            return False
    return actual == expected


def _semantic_key(values: Sequence[object]) -> str:
    return json.dumps(tuple(_finite_json_value(value) for value in values), sort_keys=True, separators=(',', ':'), allow_nan=False)


def _canonical_evidence_payload(examples: Sequence[OperatorExample], exposed_fields: Sequence[str]) -> list[dict[str, object]]:
    fields = tuple(map(str, exposed_fields))
    rows: list[dict[str, object]] = []
    for index, example in enumerate(tuple(examples)):
        if any(field not in example.context for field in fields):
            missing = [field for field in fields if field not in example.context]
            raise KeyError(f'missing exposed fields: {missing}')
        rows.append({
            'index': index,
            'values': [_finite_json_value(example.context[field]) for field in fields],
            'target': _finite_json_value(example.expected),
        })
    return rows


def _canonical_evidence_digest(examples: Sequence[OperatorExample], exposed_fields: Sequence[str]) -> str:
    raw = json.dumps(
        {'exposed_fields': list(map(str, exposed_fields)), 'rows': _canonical_evidence_payload(examples, exposed_fields)},
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


@dataclass(frozen=True, slots=True)
class NecessityCertificate:
    basis_semantic_profile_ids: tuple[str, ...]
    subset_semantic_profile_ids: tuple[str, ...]
    subset_cardinality: int
    exposed_fields: tuple[str, ...]
    evidence_digest: str
    proof_kind: str
    witness_digest: str
    witness_rows: tuple[int, int]


def build_public_target_collision_certificate(
    *,
    basis_semantic_profile_ids: Sequence[str],
    subset_semantic_profile_ids: Sequence[str],
    exposed_fields: Sequence[str],
    examples: Sequence[OperatorExample],
) -> NecessityCertificate | None:
    basis_ids = tuple(map(str, basis_semantic_profile_ids))
    subset_ids = tuple(map(str, subset_semantic_profile_ids))
    fields = tuple(map(str, exposed_fields))
    rows = tuple(examples)
    if not basis_ids or not subset_ids:
        raise ValueError('basis and subset semantic profile ids must be non-empty')
    if len(subset_ids) > len(basis_ids):
        raise ValueError('subset cannot exceed basis cardinality')
    if not fields:
        raise ValueError('exposed_fields must be non-empty')
    evidence_digest = _canonical_evidence_digest(rows, fields)
    seen: dict[str, tuple[int, object]] = {}
    for index, example in enumerate(rows):
        values = tuple(example.context[field] for field in fields)
        key = _semantic_key(values)
        target = _finite_json_value(example.expected)
        previous = seen.get(key)
        if previous is not None and not _equivalent(previous[1], target):
            left_index = previous[0]
            witness_raw = json.dumps(
                {
                    'proof_kind': 'public_target_collision',
                    'evidence_digest': evidence_digest,
                    'exposed_fields': list(fields),
                    'witness_rows': [left_index, index],
                    'values': [_finite_json_value(rows[left_index].context[field]) for field in fields],
                    'targets': [_finite_json_value(rows[left_index].expected), target],
                },
                sort_keys=True,
                separators=(',', ':'),
                allow_nan=False,
            )
            return NecessityCertificate(
                basis_semantic_profile_ids=basis_ids,
                subset_semantic_profile_ids=subset_ids,
                subset_cardinality=len(subset_ids),
                exposed_fields=fields,
                evidence_digest=evidence_digest,
                proof_kind='public_target_collision',
                witness_digest=hashlib.sha256(witness_raw.encode('utf-8')).hexdigest(),
                witness_rows=(left_index, index),
            )
        seen[key] = (index, target)
    return None


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
    basis_ids = tuple(map(str, basis_semantic_profile_ids))
    subset_ids = tuple(map(str, subset_semantic_profile_ids))
    fields = tuple(map(str, exposed_fields))
    if certificate.proof_kind != 'public_target_collision':
        return False
    if certificate.basis_semantic_profile_ids != basis_ids:
        return False
    if certificate.subset_semantic_profile_ids != subset_ids:
        return False
    if certificate.subset_cardinality != len(subset_ids):
        return False
    if certificate.exposed_fields != fields:
        return False
    try:
        if certificate.evidence_digest != _canonical_evidence_digest(examples, fields):
            return False
        left_index, right_index = certificate.witness_rows
        rows = tuple(examples)
        if left_index < 0 or right_index < 0 or left_index >= len(rows) or right_index >= len(rows) or left_index == right_index:
            return False
        left = rows[left_index]
        right = rows[right_index]
        left_values = tuple(_finite_json_value(left.context[field]) for field in fields)
        right_values = tuple(_finite_json_value(right.context[field]) for field in fields)
        if _semantic_key(left_values) != _semantic_key(right_values):
            return False
        if _equivalent(_finite_json_value(left.expected), _finite_json_value(right.expected)):
            return False
        recomputed = build_public_target_collision_certificate(
            basis_semantic_profile_ids=basis_ids,
            subset_semantic_profile_ids=subset_ids,
            exposed_fields=fields,
            examples=rows,
        )
        return recomputed is not None and recomputed.witness_digest == certificate.witness_digest and recomputed.witness_rows == certificate.witness_rows
    except (KeyError, TypeError, ValueError):
        return False


__all__ = [
    'NecessityCertificate',
    'build_public_target_collision_certificate',
    'verify_necessity_certificate',
]
