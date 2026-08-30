from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def _patch():
    return CodingPatchCandidate(
        patch_id='patch-claim-release-1',
        producer_agent_id='coding.backend.01',
        task_id='task-claim-release-1',
        work_id='coding-work-claim-release-1',
        base_plan_version=1,
        base_architecture_version=1,
        touched_files=('src/release_safe.py',),
        touched_symbols=('ReleaseSafe.apply',),
        patch_artifact_id='artifact:release-safe-patch',
        compile_evidence_refs=('legacy:compile',),
        test_evidence_refs=('legacy:test',),
        static_evidence_refs=('legacy:static',),
        status=CodingPatchStatus.VERIFIED,
    )


def _coding_ready(patch_id):
    verification = PatchVerificationEvidence(
        evidence_id='verify:release-safe',
        verifier_agent_id='verification.testing.01',
        passed=True,
    )
    payload = {
        'receipt_id': 'coding-ready-release-safe',
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


def test_normal_claim_release_after_apply_does_not_block_candidate_closure():
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
        source_revision='git:release-safe',
        rollback_artifact_ref='artifact:rollback-release-safe',
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
            source_revision='git:release-safe',
            environment_digest='env:ubuntu24-py313',
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}:release-safe',),
        ))

    plane.verify_preconditions(
        work.transaction_id,
        attestation_ids=(attestations[0].attestation_id,),
    )
    authority = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert authority.authorized
    plane.mark_applied(
        work.transaction_id,
        application_ref='workspace:release-safe',
        mutation_authority_receipt_id=authority.receipt_id,
    )

    # Releasing a mutation lease after successful application is normal lifecycle,
    # not evidence that the applied patch became technically invalid.
    claims.release(claim.claim_id, actor_agent_id=claim.agent_id)

    plane.observe_outcome(
        work.transaction_id,
        evidence_refs=('runtime:release-safe-outcome',),
    )
    plane.verify_postconditions(
        work.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    gate = plane.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:release-safe',
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )

    assert gate.ready
    assert gate.reasons == ()
    assert gate.authority == 'candidate_only'
    current = plane.revalidate(
        gate.receipt_id,
        patch=patch,
        current_source_revision='git:release-safe',
    )
    assert current.current
