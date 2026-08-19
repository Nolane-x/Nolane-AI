from __future__ import annotations

from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary
from .r269_causal_basis_adapter import (
    PortableExperience,
    _portable_payload,
    _rewrite_fields,
    _sha,
    _used_fields,
)
from .r269_meta_learning_kernel import PublicTaskSignature
from .r269_transfer_runtime import MetaLearningReceipt

_ACCEPTED_R268_PARENT = 'fda7f502185266fedb00886d5786c6d28cc0e0eb'
_ACCEPTED_REASONS = frozenset(('accepted_transfer', 'accepted_scratch', 'accepted_scratch_after_transfer'))


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


def _semantic_signature_payload(signature: PublicTaskSignature) -> dict[str, object]:
    return {
        'role_count': len(signature.role_names),
        'numeric_domain': signature.numeric_domain,
        'allowed_binary_ops': sorted(signature.allowed_binary_ops),
        'query_space_digest': signature.query_space_digest,
        'budget_contract': signature.budget_contract,
        'finite_integer_values': list(signature.finite_integer_values),
    }


def _domain_claim_scope(signature: PublicTaskSignature) -> tuple[str, ...]:
    rows = [f'numeric_domain={signature.numeric_domain}']
    if signature.numeric_domain == 'finite_integer':
        rows.append('finite_integer_values=' + ','.join(map(str, signature.finite_integer_values)))
    return tuple(rows)


def _canonical_receipt_payload(
    receipt: MetaLearningReceipt,
    *,
    canonical_expression: Expr,
) -> dict[str, object]:
    return {
        'schema_version': 1,
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
        'observation_digests': [row.observation_digest for row in receipt.ledger],
        'trainable_parameter_count': 0,
    }


def _validate_receipt_authority(receipt: MetaLearningReceipt, signature: PublicTaskSignature) -> Expr:
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
        raise ValueError('source episode must carry the selected executable expression')
    if receipt.mode == 'transfer' and not receipt.selected_prior_digest:
        raise ValueError('accepted transfer episode must identify its evidence-surviving prior')
    if receipt.false_accepts != 0 or receipt.trainable_parameter_count != 0:
        raise ValueError('source episode must preserve zero-false-accept and zero-parameter authority')
    if receipt.reused_observations != receipt.avoided_duplicate_calls:
        raise ValueError('source episode reuse accounting is internally inconsistent')

    expression = receipt.selected_expression
    if _used_fields(expression) != frozenset(signature.role_names):
        raise ValueError('selected expression must depend on exactly the public structural roles')
    if not _binary_ops(expression).issubset(frozenset(signature.allowed_binary_ops)):
        raise ValueError('selected expression exceeds the declared operator vocabulary')

    ledger = tuple(receipt.ledger)
    if not ledger:
        raise ValueError('source episode must carry verifier evidence')
    if any(row.status != 'ok' or row.observed is None for row in ledger):
        raise ValueError('accepted source episode cannot contain failed oracle evidence')
    if tuple(row.oracle_call_index for row in ledger) != tuple(range(1, len(ledger) + 1)):
        raise ValueError('source episode oracle-call ledger must be contiguous and exact')
    if len({row.context_key for row in ledger}) != len(ledger):
        raise ValueError('source episode ledger contexts must be semantically unique')

    diagnostic_rows = tuple(row for row in ledger if row.phase == 'diagnostic')
    terminal_rows = tuple(row for row in ledger if row.phase == 'terminal')
    other_rows = tuple(row for row in ledger if row.phase not in ('diagnostic', 'terminal'))
    if other_rows:
        raise ValueError('Phase A episode compiler accepts diagnostic and terminal evidence only')
    if len(diagnostic_rows) != receipt.physical_diagnostic_calls:
        raise ValueError('diagnostic evidence accounting does not match the receipt')
    if not terminal_rows or len(terminal_rows) != receipt.physical_terminal_calls:
        raise ValueError('exact terminal verification evidence is required')
    if {row.context_key for row in diagnostic_rows} & {row.context_key for row in terminal_rows}:
        raise ValueError('terminal evidence must be semantically disjoint from diagnostic evidence')
    if len(ledger) != receipt.physical_diagnostic_calls + receipt.physical_terminal_calls:
        raise ValueError('physical oracle-call accounting does not match the evidence ledger')
    return expression


def compile_meta_learning_experience(
    receipt: MetaLearningReceipt,
    *,
    signature: PublicTaskSignature,
    accepted_parent_sha: str,
) -> PortableExperience:
    expression = _validate_receipt_authority(receipt, signature)
    accepted_parent_sha = str(accepted_parent_sha).strip()
    if accepted_parent_sha != _ACCEPTED_R268_PARENT:
        raise ValueError('accepted_parent_sha must be the accepted R2.68 parent')

    canonical_roles = tuple(f'__r{i}' for i in range(len(signature.role_names)))
    canonical_expression = _rewrite_fields(
        expression,
        dict(zip(signature.role_names, canonical_roles, strict=True)),
    )
    receipt_payload = _canonical_receipt_payload(
        receipt,
        canonical_expression=canonical_expression,
    )
    source_receipt_digest = f'r269.receipt.{_sha(receipt_payload)}'
    claim_scope = (
        'r269_verified_meta_episode',
        'terminal_verified',
        'zero_false_accepts',
        *_domain_claim_scope(signature),
    )
    authority_payload = {
        'schema_version': 1,
        'accepted_parent_sha': accepted_parent_sha,
        'source_receipt_digest': source_receipt_digest,
        'public_structural_signature': _semantic_signature_payload(signature),
        'claim_scope': list(claim_scope),
    }
    source_authority_digest = f'r269.authority.{_sha(authority_payload)}'
    allowed_adaptation_ops = tuple(signature.allowed_binary_ops)
    payload = _portable_payload(
        adapter_type='verified_meta_episode_v1',
        expression=canonical_expression,
        roles=canonical_roles,
        source_receipt_digest=source_receipt_digest,
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
        source_authority_digest=source_authority_digest,
        accepted_parent_sha=accepted_parent_sha,
        claim_scope=claim_scope,
        allowed_adaptation_ops=allowed_adaptation_ops,
        portable_digest=_sha(payload),
        trainable_parameter_count=0,
    )


__all__ = ['compile_meta_learning_experience']
