import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringPhase
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane
from nolane.external_core.software_engineering_effect_dispatch import EngineeringDispatchOrigin
from nolane.external_core.software_engineering_recovery_frontier import EngineeringRecoveryAction


def _patch():
    return CodingPatchCandidate(
        patch_id="patch-dispatch-frontier-0001",
        producer_agent_id="coding.backend.01",
        task_id="task-dispatch-frontier-0001",
        work_id="coding-work-dispatch-frontier-0001",
        base_plan_version=9,
        base_architecture_version=13,
        touched_files=("src/dispatch_frontier.py",),
        touched_symbols=("dispatch_frontier.execute",),
        patch_artifact_id="artifact:patch-dispatch-frontier",
        compile_evidence_refs=("legacy:compile",),
        test_evidence_refs=("legacy:test",),
        static_evidence_refs=("legacy:static",),
        status=CodingPatchStatus.VERIFIED,
    )


def _application_intent():
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
        source_revision="git:source-dispatch-frontier",
        rollback_artifact_ref="artifact:rollback-dispatch-frontier",
        claim_refs=(claim.claim_id,),
        operation_ref="engineering:dispatch-frontier:attempt-0001",
    )
    attestation = plane.record_evidence(
        patch=patch,
        source_revision="git:source-dispatch-frontier",
        environment_digest="env:ubuntu24-py313",
        verifier_agent_id="verification.testing.01",
        verifier_region="verification-testing",
        kind=EngineeringEvidenceKind.COMPILE,
        passed=True,
        evidence_refs=("run:compile:dispatch-frontier",),
    )
    plane.verify_preconditions(work.transaction_id, attestation_ids=(attestation.attestation_id,))
    mutation = plane.assess_mutation_authority(work.work_id, patch=patch)
    intent = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref="executor:idempotency:dispatch-frontier-apply",
    )
    return patch, claims, plane, work, mutation, intent


def _committed_application():
    patch, claims, plane, work, mutation, intent = _application_intent()
    dispatch = plane.begin_application_dispatch(
        intent.intent_id,
        executor_namespace="executor.integration.test",
    )
    acknowledgement = plane.acknowledge_application(
        intent.intent_id,
        executor_namespace="executor.integration.test",
        executor_receipt_ref="executor:receipt:dispatch-frontier-apply",
        observed_state_digest="state:after-dispatch-frontier-apply",
    )
    commit = plane.finalize_application(acknowledgement.acknowledgement_id)
    return patch, claims, plane, work, mutation, intent, dispatch, acknowledgement, commit


def _recompute_nested_and_outer(state: dict, key: str) -> None:
    nested = state[key]
    nested_payload = {name: value for name, value in nested.items() if name != "digest"}
    nested["digest"] = canonical_digest(nested_payload)
    outer_payload = {name: value for name, value in state.items() if name != "digest"}
    state["digest"] = canonical_digest(outer_payload)


def test_application_frontier_moves_from_safe_dispatch_to_uncertain_to_local_finalize_to_finalized():
    _, claims, plane, work, _, intent = _application_intent()

    before = plane.application_recovery_frontier(intent.intent_id)
    assert before.action is EngineeringRecoveryAction.READY_TO_DISPATCH

    dispatch = plane.begin_application_dispatch(
        intent.intent_id,
        executor_namespace="executor.integration.test",
    )
    assert dispatch.origin is EngineeringDispatchOrigin.PRE_DISPATCH
    assert dispatch.authority == "coordination_only"

    uncertain = plane.application_recovery_frontier(intent.intent_id)
    assert uncertain.action is EngineeringRecoveryAction.EXTERNAL_STATUS_REQUIRED
    assert uncertain.dispatch_id == dispatch.dispatch_id

    snapshot = plane.to_state()
    restored = SoftwareEngineeringControlPlane.from_state(claims=claims, state=snapshot)
    assert restored.application_recovery_frontier(intent.intent_id).action is EngineeringRecoveryAction.EXTERNAL_STATUS_REQUIRED
    with pytest.raises(PermissionError, match="status|dispatch|uncertain"):
        restored.begin_application_dispatch(
            intent.intent_id,
            executor_namespace="executor.integration.test",
        )

    acknowledgement = restored.acknowledge_application(
        intent.intent_id,
        executor_namespace="executor.integration.test",
        executor_receipt_ref="executor:receipt:dispatch-frontier-apply",
        observed_state_digest="state:after-dispatch-frontier-apply",
    )
    assert restored.application_recovery_frontier(intent.intent_id).action is EngineeringRecoveryAction.LOCAL_FINALIZATION_READY

    restored.finalize_application(acknowledgement.acknowledgement_id)
    assert restored.transactions.get(work.transaction_id).phase is EngineeringPhase.APPLIED
    assert restored.application_recovery_frontier(intent.intent_id).action is EngineeringRecoveryAction.FINALIZED


def test_application_dispatch_namespace_is_immutable_and_ack_must_match_it():
    _, _, plane, _, _, intent = _application_intent()
    plane.begin_application_dispatch(intent.intent_id, executor_namespace="executor.integration.test")

    with pytest.raises(PermissionError, match="status|dispatch|uncertain"):
        plane.begin_application_dispatch(intent.intent_id, executor_namespace="executor.integration.other")

    with pytest.raises(ValueError, match="executor|namespace|dispatch"):
        plane.acknowledge_application(
            intent.intent_id,
            executor_namespace="executor.integration.other",
            executor_receipt_ref="executor:receipt:dispatch-frontier-apply",
            observed_state_digest="state:after-dispatch-frontier-apply",
        )


def test_application_dispatch_start_rechecks_live_mutation_authority():
    patch, claims, plane, work, _, intent = _application_intent()
    binding = plane.claim_bindings.get(work.claim_binding_id)
    claims.release(binding.claim_snapshots[0].claim_id, actor_agent_id=patch.producer_agent_id)

    with pytest.raises(PermissionError, match="authority|claim|dispatch"):
        plane.begin_application_dispatch(
            intent.intent_id,
            executor_namespace="executor.integration.test",
        )
    assert plane.application_recovery_frontier(intent.intent_id).action is EngineeringRecoveryAction.BLOCKED


def test_rollback_frontier_requires_external_status_then_independent_verification_before_finalize():
    _, claims, plane, work, _, _, _, _, _ = _committed_application()
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref="executor:idempotency:dispatch-frontier-rollback",
        reason="post-apply regression",
        target_state_digest="state:before-dispatch-frontier-patch",
    )
    assert plane.rollback_recovery_frontier(rollback.intent_id).action is EngineeringRecoveryAction.READY_TO_DISPATCH

    plane.begin_rollback_dispatch(
        rollback.intent_id,
        executor_namespace="executor.integration.test",
    )
    assert plane.rollback_recovery_frontier(rollback.intent_id).action is EngineeringRecoveryAction.EXTERNAL_STATUS_REQUIRED

    acknowledgement = plane.acknowledge_rollback(
        rollback.intent_id,
        executor_namespace="executor.integration.test",
        executor_receipt_ref="executor:receipt:dispatch-frontier-rollback",
        observed_state_digest="state:before-dispatch-frontier-patch",
    )
    assert plane.rollback_recovery_frontier(rollback.intent_id).action is EngineeringRecoveryAction.VERIFICATION_REQUIRED

    verification = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id="verification.testing.01",
        verifier_region="verification-testing",
        restored_state_digest="state:before-dispatch-frontier-patch",
        evidence_refs=("rollback:dispatch-frontier-proof",),
        passed=True,
    )
    assert plane.rollback_recovery_frontier(rollback.intent_id).action is EngineeringRecoveryAction.LOCAL_FINALIZATION_READY

    plane.finalize_rollback(
        acknowledgement.acknowledgement_id,
        verification_receipt_id=verification.receipt_id,
    )
    assert plane.rollback_recovery_frontier(rollback.intent_id).action is EngineeringRecoveryAction.FINALIZED

    restored = SoftwareEngineeringControlPlane.from_state(claims=claims, state=plane.to_state())
    assert restored.rollback_recovery_frontier(rollback.intent_id).action is EngineeringRecoveryAction.FINALIZED


def test_restore_rejects_acknowledgement_without_dispatch_lineage_even_after_digest_recompute():
    _, claims, plane, _, _, intent = _application_intent()
    plane.begin_application_dispatch(intent.intent_id, executor_namespace="executor.integration.test")
    plane.acknowledge_application(
        intent.intent_id,
        executor_namespace="executor.integration.test",
        executor_receipt_ref="executor:receipt:dispatch-frontier-apply",
        observed_state_digest="state:after-dispatch-frontier-apply",
    )
    state = plane.to_state()
    state["effect_dispatch"]["records"] = []
    _recompute_nested_and_outer(state, "effect_dispatch")

    with pytest.raises(ValueError, match="dispatch|acknowledgement|lineage"):
        SoftwareEngineeringControlPlane.from_state(claims=claims, state=state)


def test_legacy_acknowledgement_path_backfills_dispatch_history_without_claiming_predispatch_durability():
    _, _, plane, _, _, intent = _application_intent()

    acknowledgement = plane.acknowledge_application(
        intent.intent_id,
        executor_namespace="executor.integration.legacy",
        executor_receipt_ref="executor:receipt:legacy",
        observed_state_digest="state:legacy-observed",
    )
    dispatch = plane.effect_dispatch.application_dispatch_for_intent(intent.intent_id)

    assert dispatch is not None
    assert dispatch.origin is EngineeringDispatchOrigin.OBSERVED_WITH_ACK
    assert dispatch.executor_namespace == acknowledgement.executor_namespace
    assert plane.application_recovery_frontier(intent.intent_id).action is EngineeringRecoveryAction.LOCAL_FINALIZATION_READY


def test_compatibility_commit_and_rollback_completion_are_dispatch_backed():
    patch, _, plane, work, mutation, intent = _application_intent()
    commit = plane.commit_application(
        intent.intent_id,
        executor_receipt_ref="executor:receipt:compat-dispatch-frontier-apply",
    )
    app_dispatch = plane.effect_dispatch.application_dispatch_for_transaction(work.transaction_id)
    assert app_dispatch is not None
    assert app_dispatch.origin is EngineeringDispatchOrigin.OBSERVED_WITH_ACK
    assert commit.transaction_id == work.transaction_id

    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref="executor:idempotency:compat-dispatch-frontier-rollback",
        reason="post-apply regression",
        target_state_digest="state:before-dispatch-frontier-patch",
    )
    verification = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id="verification.testing.01",
        verifier_region="verification-testing",
        restored_state_digest="state:before-dispatch-frontier-patch",
        evidence_refs=("rollback:compat-dispatch-frontier-proof",),
        passed=True,
    )
    plane.complete_rollback(rollback.intent_id, verification_receipt_id=verification.receipt_id)
    rollback_dispatch = plane.effect_dispatch.rollback_dispatch_for_transaction(work.transaction_id)
    assert rollback_dispatch is not None
    assert rollback_dispatch.origin is EngineeringDispatchOrigin.OBSERVED_WITH_ACK

    # Keep patch/authority objects live in this compatibility test so a future
    # implementation cannot satisfy it by bypassing the original lineage.
    assert patch.patch_id == intent.patch_ref
    assert mutation.transaction_id == work.transaction_id
