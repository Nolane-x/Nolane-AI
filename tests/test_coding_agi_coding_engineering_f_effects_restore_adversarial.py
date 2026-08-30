import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def _patch():
    return CodingPatchCandidate(
        patch_id='patch-restore-adversarial',
        producer_agent_id='coding.backend.01',
        task_id='task-restore-adversarial',
        work_id='coding-work-restore-adversarial',
        base_plan_version=8,
        base_architecture_version=12,
        touched_files=('src/restore_adversarial.py',),
        touched_symbols=('RestoreAdversarial.execute',),
        patch_artifact_id='artifact:restore-adversarial',
        compile_evidence_refs=('legacy:compile',),
        test_evidence_refs=('legacy:test',),
        static_evidence_refs=('legacy:static',),
        status=CodingPatchStatus.VERIFIED,
    )


def _rolled_back_plane():
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
        source_revision='git:source-a',
        rollback_artifact_ref='artifact:rollback-a',
        claim_refs=(claim.claim_id,),
    )
    pre = plane.record_evidence(
        patch=patch,
        source_revision='git:source-a',
        environment_digest='env:a',
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        kind=EngineeringEvidenceKind.COMPILE,
        passed=True,
        evidence_refs=('run:compile',),
    )
    plane.verify_preconditions(work.transaction_id, attestation_ids=(pre.attestation_id,))
    mutation = plane.assess_mutation_authority(work.work_id, patch=patch)
    app = plane.prepare_application(
        work_id=work.work_id,
        patch=patch,
        mutation_authority_receipt_id=mutation.receipt_id,
        application_ref='executor:apply:restore-adversarial',
    )
    plane.commit_application(app.intent_id, executor_receipt_ref='executor:receipt:apply')
    rollback = plane.prepare_rollback(
        transaction_id=work.transaction_id,
        rollback_operation_ref='executor:rollback:restore-adversarial',
        reason='regression',
        target_state_digest='state:before',
    )
    proof = plane.verify_rollback(
        rollback.intent_id,
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        restored_state_digest='state:before',
        evidence_refs=('rollback:proof',),
        passed=True,
    )
    plane.complete_rollback(rollback.intent_id, verification_receipt_id=proof.receipt_id)
    return patch, claims, plane


def test_restore_rejects_recomputed_self_verified_rollback_proof():
    patch, claims, plane = _rolled_back_plane()
    state = plane.to_state()
    proof = state['effects']['rollback_verifications'][0]
    proof['verifier_agent_id'] = patch.producer_agent_id
    payload = {key: value for key, value in proof.items() if key not in {'receipt_id', 'digest'}}
    digest = canonical_digest(payload)
    old_receipt_id = proof['receipt_id']
    proof['digest'] = digest
    proof['receipt_id'] = f'eng-rollback-verification-{digest[:20]}'

    completion = state['effects']['rollback_completions'][0]
    completion['verification_receipt_id'] = proof['receipt_id']
    completion['verification_receipt_digest'] = proof['digest']
    completion_payload = {
        key: value
        for key, value in completion.items()
        if key not in {'completion_id', 'digest'}
    }
    completion_digest = canonical_digest(completion_payload)
    completion['digest'] = completion_digest
    completion['completion_id'] = f'eng-rollback-completion-{completion_digest[:20]}'

    state['digest'] = canonical_digest({key: value for key, value in state.items() if key != 'digest'})
    assert proof['receipt_id'] != old_receipt_id

    with pytest.raises(PermissionError, match='self-verification'):
        SoftwareEngineeringControlPlane.from_state(claims=claims, state=state)


def test_restore_rejects_recomputed_passed_proof_from_wrong_verifier_region():
    _, claims, plane = _rolled_back_plane()
    state = plane.to_state()
    proof = state['effects']['rollback_verifications'][0]
    proof['verifier_region'] = 'coding-backend'
    payload = {key: value for key, value in proof.items() if key not in {'receipt_id', 'digest'}}
    digest = canonical_digest(payload)
    proof['digest'] = digest
    proof['receipt_id'] = f'eng-rollback-verification-{digest[:20]}'

    completion = state['effects']['rollback_completions'][0]
    completion['verification_receipt_id'] = proof['receipt_id']
    completion['verification_receipt_digest'] = proof['digest']
    completion_payload = {
        key: value
        for key, value in completion.items()
        if key not in {'completion_id', 'digest'}
    }
    completion_digest = canonical_digest(completion_payload)
    completion['digest'] = completion_digest
    completion['completion_id'] = f'eng-rollback-completion-{completion_digest[:20]}'
    state['digest'] = canonical_digest({key: value for key, value in state.items() if key != 'digest'})

    with pytest.raises(PermissionError, match='verification-testing'):
        SoftwareEngineeringControlPlane.from_state(claims=claims, state=state)
