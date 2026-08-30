from dataclasses import replace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def _patch():
    return CodingPatchCandidate(
        patch_id='patch-receipt-integrity-1',
        producer_agent_id='coding.backend.01',
        task_id='task-receipt-integrity-1',
        work_id='coding-work-receipt-integrity-1',
        base_plan_version=1,
        base_architecture_version=1,
        touched_files=('src/integrity.py',),
        touched_symbols=('Integrity.apply',),
        patch_artifact_id='artifact:integrity-patch',
        compile_evidence_refs=('legacy:compile',),
        test_evidence_refs=('legacy:test',),
        static_evidence_refs=('legacy:static',),
        status=CodingPatchStatus.VERIFIED,
    )


def _receipt(patch_id, *, passed=True, false_accepts=0, regressions=0, digest_override=None):
    verification = PatchVerificationEvidence(
        evidence_id='verification:integrity',
        verifier_agent_id='verification.testing.01',
        passed=passed,
        false_accepts=false_accepts,
        regressions=regressions,
    )
    payload = {
        'receipt_id': 'coding-ready-integrity',
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
        digest=digest_override or canonical_digest(payload),
    )


def _postcondition_plane():
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
        source_revision='git:integrity',
        rollback_artifact_ref='artifact:rollback-integrity',
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
            source_revision='git:integrity',
            environment_digest='env:ubuntu24-py313',
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}:integrity',),
        ))
    plane.verify_preconditions(
        work.transaction_id,
        attestation_ids=(attestations[0].attestation_id,),
    )
    authority = plane.assess_mutation_authority(work.work_id, patch=patch)
    plane.mark_applied(
        work.transaction_id,
        application_ref='workspace:integrity',
        mutation_authority_receipt_id=authority.receipt_id,
    )
    plane.observe_outcome(work.transaction_id, evidence_refs=('runtime:integrity',))
    plane.verify_postconditions(
        work.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    return patch, plane, work, tuple(row.attestation_id for row in attestations)


def test_unified_f_boundary_rejects_coding_receipt_with_forged_digest():
    patch, plane, work, attestations = _postcondition_plane()
    forged = _receipt(patch.patch_id, digest_override='forged-digest')
    with pytest.raises(ValueError, match='coding readiness.*integrity'):
        plane.assess_candidate(
            work_id=work.work_id,
            patch=patch,
            coding_readiness=forged,
            current_source_revision='git:integrity',
            attestation_ids=attestations,
        )


def test_unified_f_boundary_rejects_semantically_impossible_ready_coding_receipt():
    patch, plane, work, attestations = _postcondition_plane()
    impossible = _receipt(patch.patch_id, passed=False, regressions=1)
    # Digest is valid for this object, so this specifically tests semantic
    # consistency rather than transport corruption.
    assert CodingReadinessReceipt.from_state(impossible.to_state()) == impossible
    with pytest.raises(ValueError, match='coding readiness.*semantics'):
        plane.assess_candidate(
            work_id=work.work_id,
            patch=patch,
            coding_readiness=impossible,
            current_source_revision='git:integrity',
            attestation_ids=attestations,
        )
