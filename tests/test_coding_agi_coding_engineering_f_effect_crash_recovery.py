import pytest

from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringPhase
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def _patch():
    return CodingPatchCandidate(
        patch_id='patch-crash-recovery-0001',
        producer_agent_id='coding.backend.01',
        task_id='task-crash-recovery-0001',
        work_id='coding-work-crash-recovery-0001',
        base_plan_version=7,
        base_architecture_version=11,
        touched_files=('src/crash_recovery.py',),
        touched_symbols=('crash_recovery.execute',),
        patch_artifact_id='artifact:patch-crash-recovery',
        compile_evidence_refs=('legacy:compile',),
        test_evidence_refs=('legacy:test',),
        static_evidence_refs=('legacy:static',),
        status=CodingPatchStatus.VERIFIED,
    )


def _precondition_plane():
    patch = _patch()
    claims = CodeClaimLedger()
    claim = claims.claim(
        agent_id=patch.producer_agent_id,
        task_id=patch.task_id,
        file_paths=patch.touched_files,
        symbol_ids=patch.touched_symbols,
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    plane = SoftwareEngineeringControlPlane(claims=claims)
    work = plane.begin_patch(
        patch=patch,
        source_revision='git:source-crash-recovery',
        rollback_artifact_ref='artifact:rollback-crash-recovery',
        claim_refs=(claim.claim_id,),
    )
    attestation = plane.record_evidence(
        patch=patch,
        source_revision='git:source-crash-recovery',
        environment_digest='env:ubuntu24-py313',
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        kind=EngineeringEvidenceKind.COMPILE,
        passed=True,
        evidence_refs=('run:compile:crash-recovery',),
    )
    plane.verify_preconditions(work.transaction_id, attestation_ids=(attestation.attestation_id,))
    mutation = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert mutation.authorized
    return patch, claims, plane, work, mutation


def _committed_application():
    patch, claims, plane, work, mutation = _precondition_plane()
    intent = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref='executor:idempotency:apply-crash-recovery',
    )
    commit = plane.commit_application(
        intent.intent_id,
        executor_receipt_ref='executor:receipt:apply-crash-recovery',
    )
    return patch, claims, plane, work, mutation, intent, commit


def test_application_retry_reconstructs_commit_after_crash_between_tx_and_receipt():
    patch, claims, plane, work, mutation = _precondition_plane()
    intent = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref='executor:idempotency:apply-crash-recovery',
    )

    # Simulate the narrow crash window: the external effect is known to have
    # committed and transaction state was advanced, but its durable effect
    # receipt was not recorded before process loss.
    plane.transactions.mark_applied(
        work.transaction_id,
        application_ref=intent.application_ref,
    )
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.APPLIED
    assert plane.effects.application_commit_for_transaction(work.transaction_id) is None

    recovered = plane.commit_application(
        intent.intent_id,
        executor_receipt_ref='executor:receipt:apply-crash-recovery',
    )

    assert recovered.transaction_id == work.transaction_id
    assert recovered.application_ref == intent.application_ref
    assert recovered.executor_receipt_ref == 'executor:receipt:apply-crash-recovery'
    assert plane.effects.application_commit_for_transaction(work.transaction_id) is recovered
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.APPLIED

    retry = plane.commit_application(
        intent.intent_id,
        executor_receipt_ref='executor:receipt:apply-crash-recovery',
    )
    assert retry is recovered

    # Reconciled history must become a normal, durable snapshot.
    restored = SoftwareEngineeringControlPlane.from_state(claims=claims, state=plane.to_state())
    assert restored.effects.application_commit(recovered.commit_id).digest == recovered.digest


def test_application_retry_fails_closed_when_applied_transaction_ref_does_not_match_intent():
    patch, _, plane, work, mutation = _precondition_plane()
    intent = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref='executor:idempotency:apply-crash-recovery',
    )
    plane.transactions.mark_applied(
        work.transaction_id,
        application_ref='executor:idempotency:different-application',
    )

    with pytest.raises(ValueError, match='application ref'):
        plane.commit_application(
            intent.intent_id,
            executor_receipt_ref='executor:receipt:apply-crash-recovery',
        )


def test_rollback_retry_reconstructs_completion_after_crash_between_tx_and_receipt():
    _, claims, plane, work, _, _, _ = _committed_application()
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref='executor:idempotency:rollback-crash-recovery',
        reason='post-apply regression',
        target_state_digest='state:before-crash-recovery-patch',
    )
    proof = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        restored_state_digest='state:before-crash-recovery-patch',
        evidence_refs=('rollback:crash-recovery-proof',),
        passed=True,
    )

    # Simulate the matching crash window after rollback state mutation but
    # before the completion receipt was durably recorded.
    plane.transactions.rollback(
        work.transaction_id,
        rollback_ref=rollback.rollback_operation_ref,
        reason=rollback.reason,
    )
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.ROLLED_BACK

    recovered = plane.complete_rollback(
        rollback.intent_id,
        verification_receipt_id=proof.receipt_id,
    )

    assert recovered.transaction_id == work.transaction_id
    assert recovered.rollback_operation_ref == rollback.rollback_operation_ref
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.ROLLED_BACK

    retry = plane.complete_rollback(
        rollback.intent_id,
        verification_receipt_id=proof.receipt_id,
    )
    assert retry is recovered

    restored = SoftwareEngineeringControlPlane.from_state(claims=claims, state=plane.to_state())
    assert restored.effects.rollback_completion(recovered.completion_id).digest == recovered.digest


def test_rollback_retry_fails_closed_when_rolled_back_transaction_lineage_differs():
    _, _, plane, work, _, _, _ = _committed_application()
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref='executor:idempotency:rollback-crash-recovery',
        reason='post-apply regression',
        target_state_digest='state:before-crash-recovery-patch',
    )
    proof = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        restored_state_digest='state:before-crash-recovery-patch',
        evidence_refs=('rollback:crash-recovery-proof',),
        passed=True,
    )
    plane.transactions.rollback(
        work.transaction_id,
        rollback_ref='executor:idempotency:different-rollback',
        reason=rollback.reason,
    )

    with pytest.raises(ValueError, match='rollback operation ref'):
        plane.complete_rollback(
            rollback.intent_id,
            verification_receipt_id=proof.receipt_id,
        )
