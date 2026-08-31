import pytest

from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def _application_intent():
    patch = CodingPatchCandidate(
        patch_id="patch-dispatch-atomicity-0001",
        producer_agent_id="coding.backend.01",
        task_id="task-dispatch-atomicity-0001",
        work_id="coding-work-dispatch-atomicity-0001",
        base_plan_version=9,
        base_architecture_version=14,
        touched_files=("src/dispatch_atomicity.py",),
        touched_symbols=("dispatch_atomicity.execute",),
        patch_artifact_id="artifact:patch-dispatch-atomicity",
        compile_evidence_refs=("legacy:compile",),
        test_evidence_refs=("legacy:test",),
        static_evidence_refs=("legacy:static",),
        status=CodingPatchStatus.VERIFIED,
    )
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
        source_revision="git:dispatch-atomicity",
        rollback_artifact_ref="artifact:rollback-dispatch-atomicity",
        claim_refs=(claim.claim_id,),
        operation_ref="engineering:dispatch-atomicity:attempt-0001",
    )
    evidence = plane.record_evidence(
        patch=patch,
        source_revision="git:dispatch-atomicity",
        environment_digest="env:dispatch-atomicity",
        verifier_agent_id="verification.testing.01",
        verifier_region="verification-testing",
        kind=EngineeringEvidenceKind.COMPILE,
        passed=True,
        evidence_refs=("run:dispatch-atomicity-compile",),
    )
    plane.verify_preconditions(work.transaction_id, attestation_ids=(evidence.attestation_id,))
    mutation = plane.assess_mutation_authority(work.work_id, patch=patch)
    intent = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref="executor:idempotency:dispatch-atomicity-apply",
    )
    return patch, claims, claim, plane, work, intent


def _applied_plane():
    patch, claims, claim, plane, work, intent = _application_intent()
    plane.commit_application(
        intent.intent_id,
        executor_receipt_ref="executor:receipt:dispatch-atomicity-apply",
    )
    return patch, claims, claim, plane, work


def test_denied_compatibility_application_leaves_no_dispatch_history():
    patch, claims, claim, plane, _, intent = _application_intent()
    claims.release(claim.claim_id, actor_agent_id=patch.producer_agent_id)

    with pytest.raises(PermissionError, match="authority|claim|application"):
        plane.commit_application(
            intent.intent_id,
            executor_receipt_ref="executor:receipt:denied-apply",
        )

    assert plane.effect_dispatch.application_dispatch_for_intent(intent.intent_id) is None
    assert plane.effect_journal.application_acknowledgements() == ()


def test_invalid_application_acknowledgement_leaves_no_dispatch_history():
    _, _, _, plane, _, intent = _application_intent()

    with pytest.raises(ValueError, match="receipt|explicit"):
        plane.acknowledge_application(
            intent.intent_id,
            executor_namespace="executor.integration.test",
            executor_receipt_ref="",
            observed_state_digest="state:observed",
        )

    assert plane.effect_dispatch.application_dispatch_for_intent(intent.intent_id) is None
    assert plane.effect_journal.application_acknowledgements() == ()


def test_failed_rollback_verification_completion_leaves_no_dispatch_history():
    _, _, _, plane, work = _applied_plane()
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref="executor:idempotency:dispatch-atomicity-rollback",
        reason="regression",
        target_state_digest="state:before-dispatch-atomicity",
    )
    failed = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id="verification.testing.01",
        verifier_region="verification-testing",
        restored_state_digest="state:before-dispatch-atomicity",
        evidence_refs=("rollback:failed-proof",),
        passed=False,
    )

    with pytest.raises(PermissionError, match="verification|verified"):
        plane.complete_rollback(
            rollback.intent_id,
            verification_receipt_id=failed.receipt_id,
        )

    assert plane.effect_dispatch.rollback_dispatch_for_intent(rollback.intent_id) is None
    assert plane.effect_journal.rollback_acknowledgements() == ()


def test_invalid_rollback_acknowledgement_leaves_no_dispatch_history():
    _, _, _, plane, work = _applied_plane()
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref="executor:idempotency:dispatch-atomicity-rollback",
        reason="regression",
        target_state_digest="state:before-dispatch-atomicity",
    )

    with pytest.raises(ValueError, match="target|state|observed"):
        plane.acknowledge_rollback(
            rollback.intent_id,
            executor_namespace="executor.integration.test",
            executor_receipt_ref="executor:receipt:rollback",
            observed_state_digest="state:wrong-target",
        )

    assert plane.effect_dispatch.rollback_dispatch_for_intent(rollback.intent_id) is None
    assert plane.effect_journal.rollback_acknowledgements() == ()
