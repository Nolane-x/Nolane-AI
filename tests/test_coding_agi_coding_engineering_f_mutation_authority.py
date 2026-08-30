import pytest

from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringPhase
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane
from nolane.external_core.software_engineering_validity import EngineeringMutationAuthorityDecision


def _patch():
    return CodingPatchCandidate(
        patch_id='patch-00000001',
        producer_agent_id='coding.backend.01',
        task_id='task-00000001',
        work_id='coding-work-00000001',
        base_plan_version=1,
        base_architecture_version=1,
        touched_files=('src/runtime.py',),
        touched_symbols=('Runtime.apply',),
        patch_artifact_id='artifact:patch',
        compile_evidence_refs=('compile',),
        test_evidence_refs=('test',),
        static_evidence_refs=('static',),
        status=CodingPatchStatus.VERIFIED,
    )


def _precondition_ready_plane():
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
        source_revision='git:a',
        rollback_artifact_ref='rollback:a',
        claim_refs=(claim.claim_id,),
    )
    compile_attestation = plane.record_evidence(
        patch=patch,
        source_revision='git:a',
        environment_digest='env:a',
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
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.PRECONDITIONS_VERIFIED
    return patch, claims, claim, plane, work


def test_mutation_authority_is_explicit_and_green_only_before_application():
    patch, _, _, plane, work = _precondition_ready_plane()
    receipt = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert receipt.authorized
    assert receipt.decision is EngineeringMutationAuthorityDecision.AUTHORIZED
    assert receipt.reasons == ()
    assert receipt.authority == 'mutation_scope_only'

    plane.mark_applied(
        work.transaction_id,
        application_ref='workspace:apply-a',
        mutation_authority_receipt_id=receipt.receipt_id,
    )
    after = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert not after.authorized
    assert after.decision is EngineeringMutationAuthorityDecision.BLOCKED
    assert 'transaction_not_precondition_verified' in after.reasons


def test_apply_boundary_cannot_bypass_explicit_mutation_authority_receipt():
    _, _, _, plane, work = _precondition_ready_plane()
    with pytest.raises(PermissionError, match='mutation authority receipt'):
        plane.mark_applied(work.transaction_id, application_ref='workspace:bypass')
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.PRECONDITIONS_VERIFIED


def test_releasing_claim_before_apply_revokes_mutation_authority_and_blocks_application():
    patch, claims, claim, plane, work = _precondition_ready_plane()
    first = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert first.authorized
    claims.release(claim.claim_id, actor_agent_id=claim.agent_id)

    second = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert not second.authorized
    assert any(reason.startswith('claim_state_changed:') for reason in second.reasons)
    assert any(reason.startswith('claim_not_active:') for reason in second.reasons)
    assert 'bound_claim_scope_does_not_cover_patch' in second.reasons

    with pytest.raises(PermissionError, match='mutation authority'):
        plane.mark_applied(
            work.transaction_id,
            application_ref='workspace:should-not-apply',
            mutation_authority_receipt_id=first.receipt_id,
        )
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.PRECONDITIONS_VERIFIED


def test_mutation_authority_receipts_are_historical_and_content_addressed():
    patch, claims, claim, plane, work = _precondition_ready_plane()
    allowed = plane.assess_mutation_authority(work.work_id, patch=patch)
    allowed_digest = allowed.digest
    claims.release(claim.claim_id, actor_agent_id=claim.agent_id)
    blocked = plane.assess_mutation_authority(work.work_id, patch=patch)

    assert allowed.digest == allowed_digest
    assert plane.mutation_authority.get(allowed.receipt_id).authorized
    assert not plane.mutation_authority.get(blocked.receipt_id).authorized
    assert allowed.receipt_id != blocked.receipt_id


def test_revoked_precondition_evidence_revokes_mutation_authority_before_apply():
    patch, _, _, plane, work = _precondition_ready_plane()
    allowed = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert allowed.authorized
    tx = plane.transactions.get(work.transaction_id)
    precondition_id = tx.precondition_attestation_ids[0]
    plane.evidence.revoke(precondition_id, reason='precondition artifact invalidated')

    receipt = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert not receipt.authorized
    assert f'precondition_evidence_invalid:{precondition_id}' in receipt.reasons

    with pytest.raises(PermissionError, match='mutation authority'):
        plane.mark_applied(
            work.transaction_id,
            application_ref='workspace:stale-precondition',
            mutation_authority_receipt_id=allowed.receipt_id,
        )
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.PRECONDITIONS_VERIFIED
