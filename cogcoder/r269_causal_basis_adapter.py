from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Mapping

from ._r268_types import AdaptiveCausalBasisReceipt
from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary

_ACCEPTED_R268_PARENT = 'fda7f502185266fedb00886d5786c6d28cc0e0eb'
_ALLOWED_ADAPTATION_OPS = ('add', 'sub', 'mul', 'div', 'min', 'max')
_ALLOWED_ADAPTER_TYPES = frozenset(('causal_basis_v1', 'verified_meta_episode_v1'))
_CANONICAL_ROLE_RE = re.compile(r'^__r([0-9]+)$')


def _sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _used_fields(expr: Expr) -> frozenset[str]:
    if isinstance(expr, Field):
        return frozenset((expr.name,))
    if isinstance(expr, Const):
        return frozenset()
    if isinstance(expr, Unary):
        return _used_fields(expr.arg)
    if isinstance(expr, Binary):
        return _used_fields(expr.left) | _used_fields(expr.right)
    if isinstance(expr, IfElse):
        return _used_fields(expr.condition) | _used_fields(expr.when_true) | _used_fields(expr.when_false)
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


def _rewrite_fields(expr: Expr, mapping: Mapping[str, str]) -> Expr:
    if isinstance(expr, Field):
        return Field(mapping.get(expr.name, expr.name))
    if isinstance(expr, Const):
        return expr
    if isinstance(expr, Unary):
        return Unary(expr.op, _rewrite_fields(expr.arg, mapping))
    if isinstance(expr, Binary):
        return Binary(expr.op, _rewrite_fields(expr.left, mapping), _rewrite_fields(expr.right, mapping))
    if isinstance(expr, IfElse):
        return IfElse(
            _rewrite_fields(expr.condition, mapping),
            _rewrite_fields(expr.when_true, mapping),
            _rewrite_fields(expr.when_false, mapping),
        )
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError('mapping required')
    return value


def _expr_from_data(data: Mapping[str, object]) -> Expr:
    if set(data) == {'field'}:
        return Field(str(data['field']))
    if set(data) == {'const'}:
        return Const(data['const'])
    op = data.get('op')
    if op == 'if':
        return IfElse(
            _expr_from_data(_mapping(data.get('condition'))),
            _expr_from_data(_mapping(data.get('then'))),
            _expr_from_data(_mapping(data.get('else'))),
        )
    if 'arg' in data:
        return Unary(str(op), _expr_from_data(_mapping(data['arg'])))
    if 'left' in data and 'right' in data:
        return Binary(str(op), _expr_from_data(_mapping(data['left'])), _expr_from_data(_mapping(data['right'])))
    raise ValueError('invalid expression data')


def _portable_payload(*, adapter_type: str, expression: Expr, roles: tuple[str, ...], source_receipt_digest: str, source_authority_digest: str, accepted_parent_sha: str, claim_scope: tuple[str, ...], allowed_adaptation_ops: tuple[str, ...], trainable_parameter_count: int) -> dict[str, object]:
    return {
        'schema_version': 1,
        'adapter_type': adapter_type,
        'canonical_expression': expression.to_data(),
        'canonical_roles': list(roles),
        'role_count': len(roles),
        'source_receipt_digest': source_receipt_digest,
        'source_authority_digest': source_authority_digest,
        'accepted_parent_sha': accepted_parent_sha,
        'claim_scope': list(claim_scope),
        'allowed_adaptation_ops': list(allowed_adaptation_ops),
        'trainable_parameter_count': trainable_parameter_count,
    }


@dataclass(frozen=True, slots=True)
class VerifiedExperienceEnvelope:
    source_receipt_digest: str
    source_authority_digest: str
    accepted_parent_sha: str
    claim_scope: tuple[str, ...]
    source_basis_size: int
    trainable_parameter_count: int = 0

    def __post_init__(self) -> None:
        if not self.source_receipt_digest or not self.source_authority_digest:
            raise ValueError('verifier-backed source digests are required')
        if self.accepted_parent_sha != _ACCEPTED_R268_PARENT:
            raise ValueError('accepted_parent_sha must be the accepted R2.68 parent')
        if self.source_basis_size not in (2, 3, 4):
            raise ValueError('source_basis_size must be 2, 3, or 4')
        if self.trainable_parameter_count != 0:
            raise ValueError('trainable_parameter_count must remain zero')
        if not self.claim_scope:
            raise ValueError('claim_scope must be non-empty')


@dataclass(frozen=True, slots=True)
class PortableExperience:
    adapter_type: str
    canonical_expression: Expr
    canonical_roles: tuple[str, ...]
    role_count: int
    source_receipt_digest: str
    source_authority_digest: str
    accepted_parent_sha: str
    claim_scope: tuple[str, ...]
    allowed_adaptation_ops: tuple[str, ...]
    portable_digest: str
    trainable_parameter_count: int = 0

    def __post_init__(self) -> None:
        if self.adapter_type not in _ALLOWED_ADAPTER_TYPES:
            raise ValueError('unsupported adapter_type')
        if not isinstance(self.canonical_expression, Expr):
            raise TypeError('canonical_expression must be Expr')
        if self.trainable_parameter_count != 0:
            raise ValueError('trainable_parameter_count must remain zero')
        roles = tuple(self.canonical_roles)
        expected = tuple(f'__r{i}' for i in range(len(roles)))
        if roles != expected or self.role_count != len(roles) or not roles:
            raise ValueError('canonical_roles must be contiguous __rN roles')
        if _used_fields(self.canonical_expression) != frozenset(roles):
            raise ValueError('canonical_expression must depend on exactly canonical_roles')
        if self.accepted_parent_sha != _ACCEPTED_R268_PARENT:
            raise ValueError('portable experience must bind accepted R2.68 parent')
        if not self.source_receipt_digest or not self.source_authority_digest:
            raise ValueError('source authority digests must be non-empty')
        if not self.claim_scope:
            raise ValueError('claim_scope must be non-empty')
        if not self.allowed_adaptation_ops or any(op not in _ALLOWED_ADAPTATION_OPS for op in self.allowed_adaptation_ops):
            raise ValueError('unsupported adaptation op')
        payload = _portable_payload(
            adapter_type=self.adapter_type,
            expression=self.canonical_expression,
            roles=roles,
            source_receipt_digest=self.source_receipt_digest,
            source_authority_digest=self.source_authority_digest,
            accepted_parent_sha=self.accepted_parent_sha,
            claim_scope=tuple(self.claim_scope),
            allowed_adaptation_ops=tuple(self.allowed_adaptation_ops),
            trainable_parameter_count=0,
        )
        if self.portable_digest != _sha(payload):
            raise ValueError('portable_digest must exactly match portable content')

    def to_data(self) -> dict[str, object]:
        payload = _portable_payload(
            adapter_type=self.adapter_type,
            expression=self.canonical_expression,
            roles=tuple(self.canonical_roles),
            source_receipt_digest=self.source_receipt_digest,
            source_authority_digest=self.source_authority_digest,
            accepted_parent_sha=self.accepted_parent_sha,
            claim_scope=tuple(self.claim_scope),
            allowed_adaptation_ops=tuple(self.allowed_adaptation_ops),
            trainable_parameter_count=0,
        )
        payload['portable_digest'] = self.portable_digest
        return payload


def _source_receipt_digest(receipt: AdaptiveCausalBasisReceipt) -> str:
    expression = receipt.expression
    payload = {
        'passed': bool(receipt.passed),
        'reason': str(receipt.reason),
        'selected_basis_size': int(receipt.selected_basis_size),
        'globally_minimal': bool(receipt.globally_minimal),
        'proof_ledger_complete': bool(receipt.structure.proof_ledger_complete),
        'lower_basis_universe_digest': str(receipt.structure.lower_basis_universe_digest),
        'necessity_witnesses': [row.witness_digest for row in receipt.structure.necessity_certificates],
        'lower_basis_witnesses': [row.witness_digest for row in receipt.structure.lower_basis_certificates],
        'expression': None if expression is None else expression.to_data(),
        'final_validation_cases': int(receipt.final_validation_cases),
        'final_validation_exact': int(receipt.final_validation_exact),
        'oracle_calls_total': int(receipt.oracle_calls_total),
    }
    return f'r268.receipt.{_sha(payload)}'


def compile_r268_experience(receipt: AdaptiveCausalBasisReceipt, *, source_authority_digest: str, accepted_parent_sha: str) -> PortableExperience:
    if not isinstance(receipt, AdaptiveCausalBasisReceipt):
        raise TypeError('receipt must be AdaptiveCausalBasisReceipt')
    if not receipt.passed or receipt.false_accepts != 0:
        raise ValueError('source receipt must be passed with zero false accepts')
    if not receipt.globally_minimal or not receipt.structure.globally_minimal:
        raise ValueError('source receipt must carry global minimality authority')
    if not receipt.structure.proof_ledger_complete:
        raise ValueError('source receipt proof ledger must be complete')
    if receipt.selected_basis_size not in (2, 3, 4):
        raise ValueError('source selected basis size must be 2, 3, or 4')
    if receipt.expression is None:
        raise ValueError('source receipt must carry an executable expression')
    if receipt.final_validation_cases <= 0 or receipt.final_validation_exact != receipt.final_validation_cases:
        raise ValueError('source receipt must have exact terminal validation')
    if receipt.trainable_parameter_count != 0 or receipt.structure.trainable_parameter_count != 0:
        raise ValueError('R2.69 adapter accepts zero-parameter R2.68 receipts only')

    source_authority_digest = str(source_authority_digest).strip()
    accepted_parent_sha = str(accepted_parent_sha).strip()
    source_fields = tuple(sorted(_used_fields(receipt.expression)))
    if not source_fields:
        raise ValueError('source expression must expose at least one structural role')
    canonical_roles = tuple(f'__r{i}' for i in range(len(source_fields)))
    canonical_expression = _rewrite_fields(receipt.expression, dict(zip(source_fields, canonical_roles, strict=True)))
    envelope = VerifiedExperienceEnvelope(
        source_receipt_digest=_source_receipt_digest(receipt),
        source_authority_digest=source_authority_digest,
        accepted_parent_sha=accepted_parent_sha,
        claim_scope=('r268_verified_adaptive_basis', 'globally_minimal', 'proof_ledger_complete'),
        source_basis_size=receipt.selected_basis_size,
        trainable_parameter_count=0,
    )
    payload = _portable_payload(
        adapter_type='causal_basis_v1',
        expression=canonical_expression,
        roles=canonical_roles,
        source_receipt_digest=envelope.source_receipt_digest,
        source_authority_digest=envelope.source_authority_digest,
        accepted_parent_sha=envelope.accepted_parent_sha,
        claim_scope=envelope.claim_scope,
        allowed_adaptation_ops=_ALLOWED_ADAPTATION_OPS,
        trainable_parameter_count=0,
    )
    return PortableExperience(
        adapter_type='causal_basis_v1',
        canonical_expression=canonical_expression,
        canonical_roles=canonical_roles,
        role_count=len(canonical_roles),
        source_receipt_digest=envelope.source_receipt_digest,
        source_authority_digest=envelope.source_authority_digest,
        accepted_parent_sha=envelope.accepted_parent_sha,
        claim_scope=envelope.claim_scope,
        allowed_adaptation_ops=_ALLOWED_ADAPTATION_OPS,
        portable_digest=_sha(payload),
        trainable_parameter_count=0,
    )


def portable_experience_from_data(data: Mapping[str, object]) -> PortableExperience:
    row = _mapping(data)
    expression = _expr_from_data(_mapping(row.get('canonical_expression')))
    roles_obj = row.get('canonical_roles')
    scope_obj = row.get('claim_scope')
    ops_obj = row.get('allowed_adaptation_ops')
    if not isinstance(roles_obj, list) or not isinstance(scope_obj, list) or not isinstance(ops_obj, list):
        raise ValueError('portable list fields are invalid')
    return PortableExperience(
        adapter_type=str(row.get('adapter_type', '')),
        canonical_expression=expression,
        canonical_roles=tuple(map(str, roles_obj)),
        role_count=int(row.get('role_count', -1)),
        source_receipt_digest=str(row.get('source_receipt_digest', '')),
        source_authority_digest=str(row.get('source_authority_digest', '')),
        accepted_parent_sha=str(row.get('accepted_parent_sha', '')),
        claim_scope=tuple(map(str, scope_obj)),
        allowed_adaptation_ops=tuple(map(str, ops_obj)),
        portable_digest=str(row.get('portable_digest', '')),
        trainable_parameter_count=int(row.get('trainable_parameter_count', -1)),
    )


__all__ = ['VerifiedExperienceEnvelope', 'PortableExperience', 'compile_r268_experience', 'portable_experience_from_data']
