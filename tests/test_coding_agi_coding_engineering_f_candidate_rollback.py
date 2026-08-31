from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringPhase
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane
from nolane.external_core.software_engineering_validity import EngineeringValidityDecision


def _patch():
    return CodingPatchCandidate(
        patch_id='patch-candidate-rollback',
        producer_agent_id='coding.backend.01',
        task_id='task-candidate-rollback',
        work_id='coding-work-candidate-rollback',
        base_plan_version=9,
        base_architecture_version=13,
        touched_files=('src/candidate_rollback.py',),
        touched_symbols=('CandidateRollback.execute',),
        patch_artifact_id='artifact:candidate-rollback',
        compile_evidence_refs=('legacy:compile',),
        test_evidence_refs=('legacy:test',),
        static_evidence_refs=('legacy:static',),
        status=CodingPatchStatus.VERIFIED,
    )


def _coding_ready(patch_id: str) -> CodingReadinessReceipt:
    verification = PatchVerificationEvidence(
        evidence_id='verification:candidate-rollback',
        verifier_agent_id='verification.testing.01',
        passed=True,
    )
    payload = {
        'receipt_id': 'coding-ready-candidate-rollback',
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


def _candidate_ready_plane():
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
        source_revision='git:candidate-source',
        rollback_artifact_ref='artifact:candidate-rollback-bundle',
        claim_refs=(claim.claim_id,),
    )
    attestations = []
    for kind in (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    ):
        attestations.append(plane.record_evidence(
            patch=patch,
            source_revision='git:candidate-source',
            environment_digest='env:ubuntu24-py313',
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}:candidate-rollback',),
        ))
    plane.verify_preconditions(
        work.transaction_id,
        attestation_ids=(attestations[0].attestation_id,),
    )
    mutation = plane.assess_mutation_authority(work.work_id, patch=patch)
    app = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref='executor:apply:candidate-rollback',
    )
    plane.commit_application(app.intent_id, executor_receipt_ref='executor:receipt:candidate-rollback')
    plane.observe_outcome(work.transaction_id, evidence_refs=('runtime:candidate-rollback',))
    plane.verify_postconditions(
        work.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    gate = plane.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:candidate-source',
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert gate.ready
    assert gate.closure_receipt_id is not None
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.CANDIDATE_READY
    return patch, claims, plane, work, gate


def test_candidate_ready_effect_can_be_verified_rolled_back_without_rewriting_closure_history():
    patch, _, plane, work, gate = _candidate_ready_plane()
    historical = plane.closure.get(gate.closure_receipt_id)
    assert historical.ready

    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref='executor:rollback:candidate-ready',
        reason='late integration regression',
        target_state_digest='state:before-candidate-patch',
    )
    proof = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        restored_state_digest='state:before-candidate-patch',
        evidence_refs=('rollback:e2e', 'rollback:restored-state'),
        passed=True,
    )
    plane.complete_rollback(rollback.intent_id, verification_receipt_id=proof.receipt_id)

    tx = plane.transactions.get(work.transaction_id)
    assert tx.phase is EngineeringPhase.ROLLED_BACK
    assert tx.closure_receipt_id == historical.receipt_id
    assert plane.closure.get(historical.receipt_id).digest == historical.digest

    current = plane.revalidate(
        gate.receipt_id,
        patch=patch,
        current_source_revision='git:candidate-source',
    )
    assert not current.current
    assert current.decision is EngineeringValidityDecision.STALE
    assert 'candidate_transaction_state_changed' in current.reasons


def test_candidate_ready_verified_rollback_roundtrips_as_terminal_recovery_history():
    patch, claims, plane, work, gate = _candidate_ready_plane()
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref='executor:rollback:candidate-ready-roundtrip',
        reason='late regression',
        target_state_digest='state:before-candidate-patch',
    )
    proof = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        restored_state_digest='state:before-candidate-patch',
        evidence_refs=('rollback:roundtrip-proof',),
        passed=True,
    )
    completion = plane.complete_rollback(rollback.intent_id, verification_receipt_id=proof.receipt_id)

    restored = SoftwareEngineeringControlPlane.from_state(claims=claims, state=plane.to_state())
    assert restored.transactions.get(work.transaction_id).phase is EngineeringPhase.ROLLED_BACK
    assert restored.effects.rollback_completion(completion.completion_id).digest == completion.digest
    current = restored.revalidate(
        gate.receipt_id,
        patch=patch,
        current_source_revision='git:candidate-source',
    )
    assert current.decision is EngineeringValidityDecision.STALE
