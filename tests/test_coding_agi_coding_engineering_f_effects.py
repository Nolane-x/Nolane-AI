import copy

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringPhase
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane
from nolane.external_core.software_engineering_effects import (
    EngineeringEffectDecision,
    EngineeringRollbackDecision,
)


def _patch(patch_id='patch-00000001', task_id='task-00000001'):
    return CodingPatchCandidate(
        patch_id=patch_id,
        producer_agent_id='coding.backend.01',
        task_id=task_id,
        work_id=f'coding-work-{patch_id}',
        base_plan_version=7,
        base_architecture_version=11,
        touched_files=(f'src/{patch_id}.py',),
        touched_symbols=(f'{patch_id}.execute',),
        patch_artifact_id=f'artifact:{patch_id}',
        compile_evidence_refs=('legacy:compile',),
        test_evidence_refs=('legacy:test',),
        static_evidence_refs=('legacy:static',),
        status=CodingPatchStatus.VERIFIED,
    )


def _precondition_plane(*, patch=None):
    patch = patch or _patch()
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
        source_revision='git:source-a',
        rollback_artifact_ref='artifact:rollback-a',
        claim_refs=(claim.claim_id,),
    )
    compile_attestation = plane.record_evidence(
        patch=patch,
        source_revision='git:source-a',
        environment_digest='env:ubuntu24-py313',
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        kind=EngineeringEvidenceKind.COMPILE,
        passed=True,
        evidence_refs=('run:compile',),
    )
    plane.verify_preconditions(
        work.transaction_id,
        attestation_ids=(compile_attestation.attestation_id,),
    )
    mutation = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert mutation.authorized
    return patch, claims, plane, work, mutation


def test_application_requires_prepared_intent_and_commit_is_idempotent():
    patch, _, plane, work, mutation = _precondition_plane()
    intent = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref='executor:idempotency:apply-1',
    )
    assert intent.authorized
    assert intent.decision is EngineeringEffectDecision.PREPARED
    assert intent.idempotency_key == intent.intent_id

    commit = plane.commit_application(
        intent.intent_id,
        executor_receipt_ref='executor:receipt:apply-1',
    )
    assert commit.decision is EngineeringEffectDecision.COMMITTED
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.APPLIED

    retry = plane.commit_application(
        intent.intent_id,
        executor_receipt_ref='executor:receipt:apply-1',
    )
    assert retry is commit
    with pytest.raises(ValueError, match='executor receipt'):
        plane.commit_application(
            intent.intent_id,
            executor_receipt_ref='executor:receipt:conflict',
        )


def test_application_ref_cannot_be_rebound_to_another_transaction():
    patch_a, claims, plane, work_a, mutation_a = _precondition_plane()
    intent = plane.prepare_application(
        work_id=work_a.work_id,
        patch=patch_a,
        mutation_authority_receipt_id=mutation_a.receipt_id,
        application_ref='executor:idempotency:shared',
    )
    assert intent.authorized

    patch_b = _patch('patch-00000002', 'task-00000002')
    claim_b = claims.claim(
        agent_id=patch_b.producer_agent_id,
        task_id=patch_b.task_id,
        file_paths=patch_b.touched_files,
        symbol_ids=patch_b.touched_symbols,
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    work_b = plane.begin_patch(
        patch=patch_b,
        source_revision='git:source-a',
        rollback_artifact_ref='artifact:rollback-b',
        claim_refs=(claim_b.claim_id,),
    )
    pre_b = plane.record_evidence(
        patch=patch_b,
        source_revision='git:source-a',
        environment_digest='env:ubuntu24-py313',
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        kind=EngineeringEvidenceKind.COMPILE,
        passed=True,
        evidence_refs=('run:compile:b',),
    )
    plane.verify_preconditions(work_b.transaction_id, attestation_ids=(pre_b.attestation_id,))
    mutation_b = plane.assess_mutation_authority(work_b.work_id, patch=patch_b)

    with pytest.raises(ValueError, match='application ref'):
        plane.prepare_application(
            work_id=work_b.work_id,
            patch=patch_b,
            mutation_authority_receipt_id=mutation_b.receipt_id,
            application_ref='executor:idempotency:shared',
        )


def test_snapshot_restore_rejects_applied_transaction_without_application_commit():
    patch, claims, plane, work, mutation = _precondition_plane()
    intent = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref='executor:idempotency:apply-1',
    )
    plane.commit_application(intent.intent_id, executor_receipt_ref='executor:receipt:apply-1')
    state = plane.to_state()
    state['effects']['application_commits'] = []
    state['digest'] = canonical_digest({k: v for k, v in state.items() if k != 'digest'})

    with pytest.raises(ValueError, match='application commit'):
        SoftwareEngineeringControlPlane.from_state(claims=claims, state=state)


def test_rollback_requires_independent_verified_restored_state_before_terminal_phase():
    patch, _, plane, work, mutation = _precondition_plane()
    intent = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref='executor:idempotency:apply-1',
    )
    plane.commit_application(intent.intent_id, executor_receipt_ref='executor:receipt:apply-1')

    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref='executor:idempotency:rollback-1',
        reason='post-apply regression',
        target_state_digest='state:before-patch',
    )
    assert rollback.decision is EngineeringRollbackDecision.PREPARED
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.APPLIED

    with pytest.raises(PermissionError, match='verification'):
        plane.complete_rollback(rollback.intent_id, verification_receipt_id='missing')

    with pytest.raises(PermissionError, match='self-verification'):
        plane.verify_rollback(
            rollback.intent_id,
            verifier_agent_id=patch.producer_agent_id,
            verifier_region='verification-testing',
            restored_state_digest='state:before-patch',
            evidence_refs=('rollback:test-run',),
            passed=True,
        )

    verification = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        restored_state_digest='state:before-patch',
        evidence_refs=('rollback:test-run', 'rollback:diff-empty'),
        passed=True,
    )
    assert verification.decision is EngineeringRollbackDecision.VERIFIED

    completed = plane.complete_rollback(
        rollback.intent_id,
        verification_receipt_id=verification.receipt_id,
    )
    assert completed.decision is EngineeringRollbackDecision.COMPLETED
    tx = plane.transactions.get(work.transaction_id)
    assert tx.phase is EngineeringPhase.ROLLED_BACK
    assert tx.rollback_ref == rollback.rollback_operation_ref


def test_failed_or_wrong_target_rollback_proof_cannot_complete():
    patch, _, plane, work, mutation = _precondition_plane()
    app = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref='executor:idempotency:apply-1',
    )
    plane.commit_application(app.intent_id, executor_receipt_ref='executor:receipt:apply-1')
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref='executor:idempotency:rollback-1',
        reason='regression',
        target_state_digest='state:before-patch',
    )

    with pytest.raises(ValueError, match='target state'):
        plane.verify_rollback(
            rollback.intent_id,
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            restored_state_digest='state:wrong',
            evidence_refs=('rollback:wrong',),
            passed=True,
        )

    failed = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        restored_state_digest='state:before-patch',
        evidence_refs=('rollback:failed',),
        passed=False,
    )
    assert failed.decision is EngineeringRollbackDecision.BLOCKED
    with pytest.raises(PermissionError, match='not verified'):
        plane.complete_rollback(rollback.intent_id, verification_receipt_id=failed.receipt_id)


def test_effect_history_roundtrips_without_reactivating_completed_capabilities():
    patch, claims, plane, work, mutation = _precondition_plane()
    app = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref='executor:idempotency:apply-1',
    )
    commit = plane.commit_application(app.intent_id, executor_receipt_ref='executor:receipt:apply-1')
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref='executor:idempotency:rollback-1',
        reason='regression',
        target_state_digest='state:before-patch',
    )
    proof = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        restored_state_digest='state:before-patch',
        evidence_refs=('rollback:proof',),
        passed=True,
    )
    completion = plane.complete_rollback(rollback.intent_id, verification_receipt_id=proof.receipt_id)

    restored = SoftwareEngineeringControlPlane.from_state(claims=claims, state=plane.to_state())
    assert restored.effects.application_commit(commit.commit_id).digest == commit.digest
    assert restored.effects.rollback_completion(completion.completion_id).digest == completion.digest
    assert restored.transactions.get(work.transaction_id).phase is EngineeringPhase.ROLLED_BACK
    with pytest.raises(ValueError, match='phase'):
        restored.prepare_application(
            work_id=work.work_id,
            patch=patch,
            mutation_authority_receipt_id=mutation.receipt_id,
            application_ref='executor:idempotency:apply-1',
        )
