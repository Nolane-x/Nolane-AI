from dataclasses import replace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import (
    EngineeringEvidenceKind,
    EngineeringEvidenceLedger,
    EngineeringPhase,
    PatchTransactionLedger,
    SoftwareEngineeringClosureEngine,
)
from nolane.external_core.software_engineering_validity import (
    EngineeringClaimBindingLedger,
    EngineeringValidityDecision,
    EngineeringValidityEngine,
)


def _patch(status=CodingPatchStatus.VERIFIED):
    return CodingPatchCandidate(
        patch_id='patch-00000001',
        producer_agent_id='coding.backend.01',
        task_id='task-00000001',
        work_id='coding-work-00000001',
        base_plan_version=4,
        base_architecture_version=7,
        touched_files=('src/service.py',),
        touched_symbols=('Service.execute',),
        patch_artifact_id='artifact:patch-1',
        compile_evidence_refs=('legacy:compile',),
        test_evidence_refs=('legacy:test',),
        static_evidence_refs=('legacy:static',),
        status=status,
    )


def _coding_ready(patch_id):
    verification = PatchVerificationEvidence(
        evidence_id='verify:patch-1',
        verifier_agent_id='verification.testing.01',
        passed=True,
    )
    payload = {
        'receipt_id': 'coding-ready-00000001',
        'patch_id': patch_id,
        'ready': True,
        'reasons': [],
        'verification': verification.to_state(),
    }
    return CodingReadinessReceipt(
        receipt_id=payload['receipt_id'],
        patch_id=patch_id,
        ready=True,
        reasons=(),
        verification=verification,
        digest=canonical_digest(payload),
    )


def _candidate():
    patch = _patch()
    patch_digest = canonical_digest(patch.to_state())
    claims = CodeClaimLedger()
    claim = claims.claim(
        agent_id=patch.producer_agent_id,
        task_id=patch.task_id,
        file_paths=patch.touched_files,
        symbol_ids=patch.touched_symbols,
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    evidence = EngineeringEvidenceLedger()
    attestations = []
    for kind in (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    ):
        attestations.append(evidence.record(
            subject_ref=patch.patch_id,
            subject_digest=patch_digest,
            producer_agent_id=patch.producer_agent_id,
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}:1',),
            source_revision='git:source-a',
            environment_digest='env:ubuntu24-py313',
            dependencies=(f'artifact:{kind.value}:1',),
        ))

    transactions = PatchTransactionLedger(evidence)
    tx = transactions.begin(
        patch_ref=patch.patch_id,
        patch_digest=patch_digest,
        source_revision='git:source-a',
        rollback_artifact_ref='artifact:rollback-1',
    )
    tx = transactions.bind_claims(tx.transaction_id, claim_refs=(claim.claim_id,))
    claim_bindings = EngineeringClaimBindingLedger(transactions=transactions, claims=claims)
    binding = claim_bindings.bind(tx.transaction_id)
    tx = transactions.verify_preconditions(
        tx.transaction_id,
        attestation_ids=(attestations[0].attestation_id,),
    )
    tx = transactions.mark_applied(tx.transaction_id, application_ref='workspace:apply-1')
    tx = transactions.observe_outcome(tx.transaction_id, evidence_refs=('runtime:outcome-1',))
    tx = transactions.verify_postconditions(
        tx.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    closure = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=transactions)
    historical = closure.assess(
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        transaction_id=tx.transaction_id,
        current_source_revision='git:source-a',
        required_attestation_kinds=(
            EngineeringEvidenceKind.COMPILE,
            EngineeringEvidenceKind.TEST,
            EngineeringEvidenceKind.STATIC,
        ),
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert historical.ready
    assert transactions.get(tx.transaction_id).phase is EngineeringPhase.CANDIDATE_READY
    validity = EngineeringValidityEngine(
        evidence=evidence,
        transactions=transactions,
        closure=closure,
        claims=claims,
        claim_bindings=claim_bindings,
    )
    return patch, claims, claim, evidence, attestations, transactions, binding, closure, historical, validity


def test_live_revalidation_is_current_before_any_drift():
    patch, _, _, _, _, _, binding, _, historical, validity = _candidate()
    current = validity.revalidate(
        historical.receipt_id,
        patch=patch,
        current_source_revision='git:source-a',
    )
    assert current.current
    assert current.decision is EngineeringValidityDecision.CURRENT_VALID
    assert current.reasons == ()
    assert current.claim_binding_id == binding.binding_id
    assert current.authority == 'candidate_only'


def test_evidence_revocation_invalidates_current_view_without_rewriting_history():
    patch, _, _, evidence, _, transactions, _, _, historical, validity = _candidate()
    historical_digest = historical.digest
    evidence.revoke('artifact:test:1', reason='artifact checksum mismatch')

    current = validity.revalidate(
        historical.receipt_id,
        patch=patch,
        current_source_revision='git:source-a',
    )
    assert not current.current
    assert current.decision is EngineeringValidityDecision.STALE
    assert 'revoked_or_invalid_evidence' in current.reasons
    assert historical.ready and historical.digest == historical_digest
    assert transactions.get(historical.transaction_id).phase is EngineeringPhase.CANDIDATE_READY


def test_released_claim_invalidates_current_view_but_preserves_historical_binding():
    patch, claims, claim, _, _, _, binding, _, historical, validity = _candidate()
    original_digest = dict(binding.claim_state_digests)[claim.claim_id]
    claims.release(claim.claim_id, actor_agent_id=claim.agent_id)

    current = validity.revalidate(
        historical.receipt_id,
        patch=patch,
        current_source_revision='git:source-a',
    )
    assert not current.current
    assert any(reason.startswith('claim_state_changed:') for reason in current.reasons)
    assert any(reason.startswith('claim_not_active:') for reason in current.reasons)
    assert dict(binding.claim_state_digests)[claim.claim_id] == original_digest


def test_source_or_patch_state_drift_is_visible_without_mutating_closure_receipt():
    patch, _, _, _, _, _, _, _, historical, validity = _candidate()
    source_stale = validity.revalidate(
        historical.receipt_id,
        patch=patch,
        current_source_revision='git:source-b',
    )
    assert not source_stale.current
    assert 'stale_source_revision' in source_stale.reasons

    superseded = replace(patch, status=CodingPatchStatus.SUPERSEDED)
    patch_stale = validity.revalidate(
        historical.receipt_id,
        patch=superseded,
        current_source_revision='git:source-a',
    )
    assert not patch_stale.current
    assert 'patch_state_changed' in patch_stale.reasons
    assert historical.ready


def test_claim_binding_must_be_exclusive_active_and_created_before_apply():
    patch = _patch()
    claims = CodeClaimLedger()
    claim = claims.claim(
        agent_id=patch.producer_agent_id,
        task_id=patch.task_id,
        file_paths=patch.touched_files,
        symbol_ids=patch.touched_symbols,
        mode=ClaimMode.SHARED_READ,
    )
    evidence = EngineeringEvidenceLedger()
    transactions = PatchTransactionLedger(evidence)
    tx = transactions.begin(
        patch_ref=patch.patch_id,
        patch_digest=canonical_digest(patch.to_state()),
        source_revision='git:source-a',
        rollback_artifact_ref='artifact:rollback-1',
    )
    tx = transactions.bind_claims(tx.transaction_id, claim_refs=(claim.claim_id,))
    bindings = EngineeringClaimBindingLedger(transactions=transactions, claims=claims)
    with pytest.raises(PermissionError, match='exclusive'):
        bindings.bind(tx.transaction_id)


def test_claim_binding_snapshot_restores_history_even_after_claim_becomes_stale():
    _, claims, claim, _, _, transactions, binding, _, _, _ = _candidate()
    state = binding_state = EngineeringClaimBindingLedger(
        transactions=transactions,
        claims=claims,
    )
    # Rebuild a ledger with the actual binding to exercise the snapshot codec.
    # The source ledger is obtained from a fresh candidate because bindings are immutable.
    _, claims2, claim2, _, _, transactions2, binding2, _, _, _ = _candidate()
    ledger2 = EngineeringClaimBindingLedger(transactions=transactions2, claims=claims2)
    rebound = ledger2.bindings()
    if not rebound:
        # The candidate helper's binding ledger is independent; serialize through the binding itself.
        snapshot = {'bindings': [binding2.to_state()]}
    else:
        snapshot = ledger2.to_state()
    claims2.release(claim2.claim_id, actor_agent_id=claim2.agent_id)
    restored = EngineeringClaimBindingLedger.from_state(
        transactions=transactions2,
        claims=claims2,
        state=snapshot,
    )
    restored_binding = restored.get(binding2.binding_id)
    assert restored_binding.digest == binding2.digest
    assert any(reason.startswith('claim_') for reason in restored.current_reasons(binding2.binding_id))


def test_live_validity_receipt_is_deterministic():
    patch, _, _, _, _, _, _, _, historical, validity = _candidate()
    first = validity.revalidate(
        historical.receipt_id,
        patch=patch,
        current_source_revision='git:source-a',
    )
    second = validity.revalidate(
        historical.receipt_id,
        patch=patch,
        current_source_revision='git:source-a',
    )
    assert first.receipt_id == second.receipt_id
    assert first.digest == second.digest
