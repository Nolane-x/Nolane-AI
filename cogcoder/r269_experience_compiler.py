from __future__ import annotations

import hashlib
import json
from typing import Mapping

from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary, evaluate_expr
from .r269_causal_basis_adapter import (
    PortableExperience,
    _authority_digest,
    _portable_payload,
    _rewrite_fields,
    _sha,
    _used_fields,
)
from .r269_meta_learning_kernel import PublicTaskSignature
from .r269_transfer_runtime import MetaLearningReceipt

_ACCEPTED_R268_PARENT = 'fda7f502185266fedb00886d5786c6d28cc0e0eb'
_ACCEPTED_REASONS = frozenset(('accepted_transfer', 'accepted_scratch', 'accepted_scratch_after_transfer'))


def _canonical_number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError('finite numeric value required')
    if isinstance(value, float):
        if not (float('-inf') < value < float('inf')):
            raise ValueError('finite numeric value required')
        if value.is_integer():
            return int(value)
    return value


def _binary_ops(expr: Expr) -> frozenset[str]:
    if isinstance(expr, (Field, Const)):
        return frozenset()
    if isinstance(expr, Unary):
        return _binary_ops(expr.arg)
    if isinstance(expr, Binary):
        return frozenset((expr.op,)) | _binary_ops(expr.left) | _binary_ops(expr.right)
    if isinstance(expr, IfElse):
        return _binary_ops(expr.condition) | _binary_ops(expr.when_true) | _binary_ops(expr.when_false)
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


def _observation_digest(row) -> str:
    payload = {
        'context_key': row.context_key,
        'phase': row.phase,
        'oracle_call_index': int(row.oracle_call_index),
        'status': row.status,
        'observed': row.observed,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    ).hexdigest()


def _claim_scope(signature: PublicTaskSignature) -> tuple[str, ...]:
    rows = [
        'r269_verified_meta_episode',
        'terminal_verified',
        'zero_false_accepts',
        'evidence_digest_verified',
        f'numeric_domain={signature.numeric_domain}',
    ]
    if signature.numeric_domain == 'finite_integer':
        rows.append('finite_integer_values=' + ','.join(map(str, signature.finite_integer_values)))
    return tuple(rows)


def _verify_receipt(receipt: MetaLearningReceipt, signature: PublicTaskSignature) -> Expr:
    if not isinstance(receipt, MetaLearningReceipt):
        raise TypeError('receipt must be MetaLearningReceipt')
    if not isinstance(signature, PublicTaskSignature):
        raise TypeError('signature must be PublicTaskSignature')
    if not receipt.passed or receipt.reason not in _ACCEPTED_REASONS:
        raise ValueError('source episode must be verifier-accepted')
    expected_reason = {
        'transfer': 'accepted_transfer',
        'scratch': 'accepted_scratch',
        'scratch_after_transfer': 'accepted_scratch_after_transfer',
    }.get(receipt.mode)
    if expected_reason != receipt.reason:
        raise ValueError('source episode mode/reason authority is inconsistent')
    if receipt.selected_expression is None:
        raise ValueError('source episode must carry selected executable evidence')
    if receipt.mode == 'transfer' and not receipt.selected_prior_digest:
        raise ValueError('accepted transfer episode must identify its evidence-surviving prior')
    if receipt.false_accepts != 0 or receipt.trainable_parameter_count != 0:
        raise ValueError('source episode must preserve zero false accepts and zero added parameters')
    if receipt.reused_observations != receipt.avoided_duplicate_calls:
        raise ValueError('source episode reuse accounting is inconsistent')

    expression = receipt.selected_expression
    if _used_fields(expression) != frozenset(signature.role_names):
        raise ValueError('selected expression must depend on exactly the public structural roles')
    if not _binary_ops(expression).issubset(frozenset(signature.allowed_binary_ops)):
        raise ValueError('selected expression exceeds declared operator vocabulary')

    ledger = tuple(receipt.ledger)
    if not ledger:
        raise ValueError('source episode must carry verifier evidence')
    if tuple(row.oracle_call_index for row in ledger) != tuple(range(1, len(ledger) + 1)):
        raise ValueError('source episode oracle-call ledger must be contiguous and exact')
    if len({row.context_key for row in ledger}) != len(ledger):
        raise ValueError('source episode evidence contexts must be semantically unique')

    diagnostic_rows = tuple(row for row in ledger if row.phase == 'diagnostic')
    terminal_rows = tuple(row for row in ledger if row.phase == 'terminal')
    if len(diagnostic_rows) != receipt.physical_diagnostic_calls:
        raise ValueError('diagnostic evidence accounting does not match receipt')
    if not terminal_rows or len(terminal_rows) != receipt.physical_terminal_calls:
        raise ValueError('exact terminal verification evidence is required')
    if len(ledger) != receipt.physical_diagnostic_calls + receipt.physical_terminal_calls:
        raise ValueError('physical oracle-call accounting does not match evidence ledger')
    if {row.context_key for row in diagnostic_rows} & {row.context_key for row in terminal_rows}:
        raise ValueError('terminal evidence must be semantically disjoint from diagnostic evidence')

    legal_domain = frozenset(signature.finite_integer_values)
    for row in ledger:
        if row.phase not in ('diagnostic', 'terminal'):
            raise ValueError('Phase A compiler accepts diagnostic and terminal evidence only')
        if row.status != 'ok' or row.observed is None:
            raise ValueError('accepted source episode cannot contain failed evidence')
        if row.observation_digest != _observation_digest(row):
            raise ValueError('source observation digest does not match evidence content')
        values = tuple(_canonical_number(value) for value in row.context_values)
        if len(values) != len(signature.role_names):
            raise ValueError('source evidence arity does not match structural signature')
        if signature.numeric_domain == 'finite_integer':
            if any(not isinstance(value, int) or value not in legal_domain for value in values):
                raise ValueError('source evidence lies outside declared complete finite domain')
        expected_context_key = json.dumps(values, separators=(',', ':'), allow_nan=False)
        if row.context_key != expected_context_key:
            raise ValueError('source context digest key does not match evidence values')
        context: Mapping[str, object] = dict(zip(signature.role_names, values, strict=True))
        try:
            predicted = _canonical_number(evaluate_expr(expression, context))
            observed = _canonical_number(row.observed)
        except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
            raise ValueError('selected expression cannot replay verifier evidence') from exc
        if predicted != observed:
            raise ValueError('selected expression contradicts verifier evidence')
    return expression


def _canonical_receipt_payload(
    receipt: MetaLearningReceipt,
    *,
    canonical_expression: Expr,
) -> dict[str, object]:
    return {
        'schema_version': 2,
        'passed': True,
        'mode': receipt.mode,
        'reason': receipt.reason,
        'selected_expression': canonical_expression.to_data(),
        'physical_diagnostic_calls': int(receipt.physical_diagnostic_calls),
        'physical_terminal_calls': int(receipt.physical_terminal_calls),
        'transfer_candidates_considered': int(receipt.transfer_candidates_considered),
        'scratch_candidates_considered': int(receipt.scratch_candidates_considered),
        'reused_observations': int(receipt.reused_observations),
        'avoided_duplicate_calls': int(receipt.avoided_duplicate_calls),
        'transfer_contradictions': int(receipt.transfer_contradictions),
        'quarantine_action': bool(receipt.quarantine_action),
        'false_accepts': 0,
        'observations': [
            {
                'context_values': list(row.context_values),
                'phase': row.phase,
                'oracle_call_index': int(row.oracle_call_index),
                'status': row.status,
                'observed': row.observed,
                'observation_digest': row.observation_digest,
            }
            for row in receipt.ledger
        ],
        'trainable_parameter_count': 0,
    }


def compile_meta_learning_experience(
    receipt: MetaLearningReceipt,
    *,
    signature: PublicTaskSignature,
    accepted_parent_sha: str,
) -> PortableExperience:
    expression = _verify_receipt(receipt, signature)
    accepted_parent_sha = str(accepted_parent_sha).strip()
    if accepted_parent_sha != _ACCEPTED_R268_PARENT:
        raise ValueError('accepted_parent_sha must be the accepted R2.68 parent')

    canonical_roles = tuple(f'__r{i}' for i in range(len(signature.role_names)))
    canonical_expression = _rewrite_fields(
        expression,
        dict(zip(signature.role_names, canonical_roles, strict=True)),
    )
    receipt_payload = _canonical_receipt_payload(receipt, canonical_expression=canonical_expression)
    source_receipt_digest = 'r269.receipt.' + _sha(receipt_payload)
    claim_scope = _claim_scope(signature)
    verifier_payload = {
        'schema_version': 2,
        'source_receipt_digest': source_receipt_digest,
        'structural_class_digest': signature.structural_class_digest,
        'selected_prior_digest': receipt.selected_prior_digest,
        'terminal_verified': True,
        'evidence_digest_verified': True,
        'claim_scope': list(claim_scope),
    }
    source_verifier_evidence_digest = 'r269.meta-verifier-evidence.' + _sha(verifier_payload)
    source_authority_digest = _authority_digest(
        source_receipt_digest=source_receipt_digest,
        source_verifier_evidence_digest=source_verifier_evidence_digest,
        accepted_parent_sha=accepted_parent_sha,
        claim_scope=claim_scope,
    )
    allowed_adaptation_ops = tuple(signature.allowed_binary_ops)
    payload = _portable_payload(
        adapter_type='verified_meta_episode_v1',
        expression=canonical_expression,
        roles=canonical_roles,
        source_receipt_digest=source_receipt_digest,
        source_verifier_evidence_digest=source_verifier_evidence_digest,
        source_authority_digest=source_authority_digest,
        accepted_parent_sha=accepted_parent_sha,
        claim_scope=claim_scope,
        allowed_adaptation_ops=allowed_adaptation_ops,
        trainable_parameter_count=0,
    )
    return PortableExperience(
        adapter_type='verified_meta_episode_v1',
        canonical_expression=canonical_expression,
        canonical_roles=canonical_roles,
        role_count=len(canonical_roles),
        source_receipt_digest=source_receipt_digest,
        source_verifier_evidence_digest=source_verifier_evidence_digest,
        source_authority_digest=source_authority_digest,
        accepted_parent_sha=accepted_parent_sha,
        claim_scope=claim_scope,
        allowed_adaptation_ops=allowed_adaptation_ops,
        portable_digest=_sha(payload),
        trainable_parameter_count=0,
    )


__all__ = ['compile_meta_learning_experience']
