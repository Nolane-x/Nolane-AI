import pytest

from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringPhase
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def _patch(*, patch_id: str = "patch-effect-journal-0001") -> CodingPatchCandidate:
    return CodingPatchCandidate(
        patch_id=patch_id,
        producer_agent_id="coding.backend.01",
        task_id="task-effect-journal-0001",
        work_id=f"coding-work-{patch_id}",
        base_plan_version=8,
        base_architecture_version=12,
        touched_files=("src/effect_journal.py",),
        touched_symbols=("effect_journal.execute",),
        patch_artifact_id=f"artifact:{patch_id}",
        compile_evidence_refs=("legacy:compile",),
        test_evidence_refs=("legacy:test",),
        static_evidence_refs=("legacy:static",),
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
        source_revision="git:source-effect-journal",
        rollback_artifact_ref="artifact:rollback-effect-journal",
        claim_refs=(claim.claim_id,),
        operation_ref="engineering:effect-journal:attempt-0001",
    )
    attestation = plane.record_evidence(
        patch=patch,
        source_revision="git:source-effect-journal",
        environment_digest="env:ubuntu24-py313",
        verifier_agent_id="verification.testing.01",
        verifier_region="verification-testing",
        kind=EngineeringEvidenceKind.COMPILE,
        passed=True,
        evidence_refs=("run:compile:effect-journal",),
    )
    plane.verify_preconditions(work.transaction_id, attestation_ids=(attestation.attestation_id,))
    mutation = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert mutation.authorized
    return patch, claims, plane, work, mutation


def _application_intent():
    patch, claims, plane, work, mutation = _precondition_plane()
    intent = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref="executor:idempotency:effect-journal-apply",
    )
    return patch, claims, plane, work, mutation, intent


def _committed_application():
    patch, claims, plane, work, mutation, intent = _application_intent()
    commit = plane.commit_application(
        intent.intent_id,
        executor_receipt_ref="executor:receipt:effect-journal-apply",
    )
    return patch, claims, plane, work, mutation, intent, commit


def test_application_acknowledgement_survives_restart_before_local_apply_and_finalizes_without_reexecution():
    _, claims, plane, work, _, intent = _application_intent()

    acknowledgement = plane.acknowledge_application(
        intent.intent_id,
        executor_namespace="executor.integration.test",
        executor_receipt_ref="executor:receipt:effect-journal-apply",
        observed_state_digest="state:after-effect-journal-apply",
    )

    assert acknowledgement.authority == "observation_only"
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.PRECONDITIONS_VERIFIED
    assert plane.effects.application_commit_for_transaction(work.transaction_id) is None

    snapshot = plane.to_state()
    restored = SoftwareEngineeringControlPlane.from_state(claims=claims, state=snapshot)
    restored_ack = restored.effect_journal.application_acknowledgement(acknowledgement.acknowledgement_id)
    assert restored_ack.digest == acknowledgement.digest
    assert restored.transactions.get(work.transaction_id).phase is EngineeringPhase.PRECONDITIONS_VERIFIED

    commit = restored.finalize_application(restored_ack.acknowledgement_id)

    assert commit.transaction_id == work.transaction_id
    assert commit.application_ref == intent.application_ref
    assert commit.executor_receipt_ref == acknowledgement.executor_receipt_ref
    assert restored.transactions.get(work.transaction_id).phase is EngineeringPhase.APPLIED

    retry = restored.finalize_application(restored_ack.acknowledgement_id)
    assert retry is commit


def test_application_acknowledgement_keys_cannot_be_rebound():
    _, _, plane, _, _, intent = _application_intent()

    acknowledgement = plane.acknowledge_application(
        intent.intent_id,
        executor_namespace="executor.integration.test",
        executor_receipt_ref="executor:receipt:effect-journal-apply",
        observed_state_digest="state:after-effect-journal-apply",
    )

    assert acknowledgement.authority == "observation_only"
    with pytest.raises(ValueError, match="acknowledgement|receipt|rebound"):
        plane.acknowledge_application(
            intent.intent_id,
            executor_namespace="executor.integration.test",
            executor_receipt_ref="executor:receipt:effect-journal-apply",
            observed_state_digest="state:different-after-effect",
        )

    with pytest.raises(ValueError, match="acknowledgement|receipt|rebound"):
        plane.acknowledge_application(
            intent.intent_id,
            executor_namespace="executor.integration.other",
            executor_receipt_ref="executor:receipt:effect-journal-apply",
            observed_state_digest="state:after-effect-journal-apply",
        )


def test_rollback_acknowledgement_survives_restart_before_terminal_transition_and_requires_independent_verification():
    _, claims, plane, work, _, _, _ = _committed_application()
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref="executor:idempotency:effect-journal-rollback",
        reason="post-apply regression",
        target_state_digest="state:before-effect-journal-patch",
    )
    verification = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id="verification.testing.01",
        verifier_region="verification-testing",
        restored_state_digest="state:before-effect-journal-patch",
        evidence_refs=("rollback:effect-journal-proof",),
        passed=True,
    )

    acknowledgement = plane.acknowledge_rollback(
        rollback.intent_id,
        executor_namespace="executor.integration.test",
        executor_receipt_ref="executor:receipt:effect-journal-rollback",
        observed_state_digest="state:before-effect-journal-patch",
    )

    assert acknowledgement.authority == "observation_only"
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.APPLIED

    restored = SoftwareEngineeringControlPlane.from_state(claims=claims, state=plane.to_state())
    restored_ack = restored.effect_journal.rollback_acknowledgement(acknowledgement.acknowledgement_id)
    completion = restored.finalize_rollback(
        restored_ack.acknowledgement_id,
        verification_receipt_id=verification.receipt_id,
    )

    assert completion.authority == "recovery_scope_only"
    assert completion.rollback_operation_ref == rollback.rollback_operation_ref
    assert restored.transactions.get(work.transaction_id).phase is EngineeringPhase.ROLLED_BACK

    retry = restored.finalize_rollback(
        restored_ack.acknowledgement_id,
        verification_receipt_id=verification.receipt_id,
    )
    assert retry is completion


def test_rollback_acknowledgement_target_mismatch_fails_closed():
    _, _, plane, work, _, _, _ = _committed_application()
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref="executor:idempotency:effect-journal-rollback",
        reason="post-apply regression",
        target_state_digest="state:before-effect-journal-patch",
    )

    with pytest.raises(ValueError, match="target|state|acknowledgement"):
        plane.acknowledge_rollback(
            rollback.intent_id,
            executor_namespace="executor.integration.test",
            executor_receipt_ref="executor:receipt:effect-journal-rollback",
            observed_state_digest="state:not-the-declared-rollback-target",
        )
