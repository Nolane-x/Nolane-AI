import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringPhase
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def _patch(*, patch_id: str = 'patch-attempt-0001') -> CodingPatchCandidate:
    return CodingPatchCandidate(
        patch_id=patch_id,
        producer_agent_id='coding.backend.01',
        task_id='task-attempt-0001',
        work_id='coding-work-attempt-0001',
        base_plan_version=5,
        base_architecture_version=8,
        touched_files=('src/service.py',),
        touched_symbols=('Service.execute',),
        patch_artifact_id='artifact:patch-attempt-1',
        compile_evidence_refs=('compile:legacy',),
        test_evidence_refs=('test:legacy',),
        static_evidence_refs=('static:legacy',),
        status=CodingPatchStatus.VERIFIED,
    )


def _plane_and_claim():
    patch = _patch()
    claims = CodeClaimLedger()
    claim = claims.claim(
        agent_id=patch.producer_agent_id,
        task_id=patch.task_id,
        file_paths=patch.touched_files,
        symbol_ids=patch.touched_symbols,
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    return patch, claims, claim, SoftwareEngineeringControlPlane(claims=claims)


def _begin(plane, patch, claim_id, *, operation_ref: str, rollback_artifact_ref: str = 'artifact:rollback-a'):
    return plane.begin_patch(
        patch=patch,
        source_revision='git:source-a',
        rollback_artifact_ref=rollback_artifact_ref,
        claim_refs=(claim_id,),
        dependency_refs=('component:database',),
        impacted_component_refs=('service:api',),
        operation_ref=operation_ref,
    )


def test_same_operation_retry_reuses_exact_work_and_transaction_without_counter_growth():
    patch, _, claim, plane = _plane_and_claim()

    first = _begin(plane, patch, claim.claim_id, operation_ref='eng-op:attempt-a')
    second = _begin(plane, patch, claim.claim_id, operation_ref='eng-op:attempt-a')

    assert second == first
    assert second.operation_ref == 'eng-op:attempt-a'
    assert plane.transactions.get(first.transaction_id).operation_ref == 'eng-op:attempt-a'
    assert len(plane.works()) == 1
    assert len(plane.transactions.transactions()) == 1
    assert plane.transactions.to_state()['counter'] == 1


def test_operation_ref_cannot_be_rebound_to_changed_initiation_inputs():
    patch, _, claim, plane = _plane_and_claim()
    _begin(plane, patch, claim.claim_id, operation_ref='eng-op:attempt-a')

    with pytest.raises(ValueError, match='operation'):
        _begin(
            plane,
            patch,
            claim.claim_id,
            operation_ref='eng-op:attempt-a',
            rollback_artifact_ref='artifact:rollback-forged',
        )

    assert len(plane.works()) == 1
    assert len(plane.transactions.transactions()) == 1
    assert plane.transactions.to_state()['counter'] == 1


def test_distinct_operation_refs_allow_independent_attempts_for_same_patch():
    patch, _, claim, plane = _plane_and_claim()

    first = _begin(plane, patch, claim.claim_id, operation_ref='eng-op:attempt-a')
    second = _begin(plane, patch, claim.claim_id, operation_ref='eng-op:attempt-b')

    assert first.operation_ref != second.operation_ref
    assert first.work_id != second.work_id
    assert first.transaction_id != second.transaction_id
    assert len(plane.works()) == 2
    assert len(plane.transactions.transactions()) == 2
    assert plane.transactions.to_state()['counter'] == 2


def test_retry_after_transaction_advance_returns_original_attempt_without_phase_rewrite():
    patch, _, claim, plane = _plane_and_claim()
    first = _begin(plane, patch, claim.claim_id, operation_ref='eng-op:attempt-a')
    evidence = plane.record_evidence(
        patch=patch,
        source_revision='git:source-a',
        environment_digest='env:attempt',
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        kind=EngineeringEvidenceKind.COMPILE,
        passed=True,
        evidence_refs=('run:compile-attempt',),
    )
    plane.verify_preconditions(first.transaction_id, attestation_ids=(evidence.attestation_id,))

    retried = _begin(plane, patch, claim.claim_id, operation_ref='eng-op:attempt-a')

    assert retried == first
    assert plane.transactions.get(first.transaction_id).phase is EngineeringPhase.PRECONDITIONS_VERIFIED
    assert plane.transactions.to_state()['counter'] == 1


def test_snapshot_restore_preserves_operation_retry_idempotency():
    patch, claims, claim, plane = _plane_and_claim()
    first = _begin(plane, patch, claim.claim_id, operation_ref='eng-op:attempt-a')

    restored = SoftwareEngineeringControlPlane.from_state(claims=claims, state=plane.to_state())
    retried = _begin(restored, patch, claim.claim_id, operation_ref='eng-op:attempt-a')

    assert retried == first
    assert len(restored.works()) == 1
    assert len(restored.transactions.transactions()) == 1
    assert restored.transactions.to_state()['counter'] == 1


def test_restore_rejects_cross_ledger_operation_ref_forgery_with_recomputed_outer_digest():
    patch, claims, claim, plane = _plane_and_claim()
    _begin(plane, patch, claim.claim_id, operation_ref='eng-op:attempt-a')
    state = plane.to_state()
    state['transactions']['transactions'][0]['operation_ref'] = 'eng-op:forged'
    state['digest'] = canonical_digest({key: value for key, value in state.items() if key != 'digest'})

    with pytest.raises(ValueError, match='operation'):
        SoftwareEngineeringControlPlane.from_state(claims=claims, state=state)
