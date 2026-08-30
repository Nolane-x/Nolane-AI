from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringPhase
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def _patch():
    return CodingPatchCandidate(
        patch_id='patch-00000001',
        producer_agent_id='coding.backend.01',
        task_id='task-00000001',
        work_id='coding-work-00000001',
        base_plan_version=5,
        base_architecture_version=8,
        touched_files=('src/service.py',),
        touched_symbols=('Service.execute',),
        patch_artifact_id='artifact:patch-1',
        compile_evidence_refs=('compile:legacy',),
        test_evidence_refs=('test:legacy',),
        static_evidence_refs=('static:legacy',),
        status=CodingPatchStatus.VERIFIED,
    )


def _coding_ready(patch_id):
    verification = PatchVerificationEvidence(
        evidence_id='verify:canonical',
        verifier_agent_id='verification.testing.01',
        passed=True,
    )
    payload = {
        'receipt_id': 'coding-ready-00000001',
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


def _ready_plane():
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
        dependency_refs=('component:database',),
        impacted_component_refs=('service:api',),
    )
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.CLAIMS_BOUND

    attestations = []
    for kind in (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    ):
        attestations.append(plane.record_evidence(
            patch=patch,
            source_revision='git:source-a',
            environment_digest='env:ubuntu24-py313',
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}',),
            dependencies=(f'artifact:{kind.value}',),
        ))

    plane.verify_preconditions(
        work.transaction_id,
        attestation_ids=(attestations[0].attestation_id,),
    )
    mutation = plane.assess_mutation_authority(work.work_id, patch=patch)
    assert mutation.authorized
    plane.mark_applied(
        work.transaction_id,
        application_ref='workspace:apply-a',
        mutation_authority_receipt_id=mutation.receipt_id,
    )
    plane.observe_outcome(work.transaction_id, evidence_refs=('runtime:outcome-a',))
    plane.verify_postconditions(
        work.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    gate = plane.assess_candidate(
        work_id=work.work_id,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        current_source_revision='git:source-a',
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert gate.ready
    validity = plane.revalidate(
        gate.receipt_id,
        patch=patch,
        current_source_revision='git:source-a',
    )
    assert validity.current
    return patch, claims, claim, plane, work, gate, validity


def test_control_plane_is_single_entry_point_for_f_governed_lifecycle():
    patch, _, _, plane, work, gate, validity = _ready_plane()
    assert work.patch_ref == patch.patch_id
    assert work.authority == 'candidate_only'
    assert gate.authority == 'candidate_only'
    assert validity.authority == 'candidate_only'
    assert len(plane.mutation_authority.receipts()) == 1
    assert plane.mutation_authority.receipts()[0].authority == 'mutation_scope_only'
    assert plane.transactions.get(work.transaction_id).phase is EngineeringPhase.CANDIDATE_READY
    state = plane.to_state()
    assert plane.digest == state['digest']
    assert plane.digest == canonical_digest({key: value for key, value in state.items() if key != 'digest'})


def test_control_plane_snapshot_roundtrip_preserves_every_f_closure_layer():
    patch, claims, _, plane, work, gate, validity = _ready_plane()
    mutation = plane.mutation_authority.receipts()[0]
    restored = SoftwareEngineeringControlPlane.from_state(
        claims=claims,
        state=plane.to_state(),
    )
    assert restored.digest == plane.digest
    assert restored.work(work.work_id).digest == work.digest
    assert restored.mutation_authority.get(mutation.receipt_id).digest == mutation.digest
    assert restored.gate.get(gate.receipt_id).digest == gate.digest
    assert restored.validity.get(validity.receipt_id).digest == validity.digest
    assert restored.revalidate(
        gate.receipt_id,
        patch=patch,
        current_source_revision='git:source-a',
    ).current


def test_control_plane_restore_rejects_cross_layer_manifest_forgery():
    _, claims, _, plane, _, _, _ = _ready_plane()
    state = plane.to_state()
    work_state = state['works'][0]
    work_state['manifest_digest'] = 'forged-manifest-digest'
    work_payload = {
        key: value
        for key, value in work_state.items()
        if key not in {'work_id', 'digest'}
    }
    forged_work_digest = canonical_digest(work_payload)
    work_state['digest'] = forged_work_digest
    work_state['work_id'] = f'eng-work-{forged_work_digest[:20]}'
    state['digest'] = canonical_digest({key: value for key, value in state.items() if key != 'digest'})

    try:
        SoftwareEngineeringControlPlane.from_state(claims=claims, state=state)
    except ValueError as exc:
        assert 'manifest' in str(exc)
    else:
        raise AssertionError('forged work/manifest lineage must be rejected')


def test_control_plane_restore_rejects_gate_closure_forgery_even_with_recomputed_outer_digest():
    _, claims, _, plane, _, gate, _ = _ready_plane()
    state = plane.to_state()
    state['gate']['receipts'][0]['closure_receipt_id'] = 'eng-closure-forged'
    gate_payload = {
        key: value
        for key, value in state['gate']['receipts'][0].items()
        if key not in {'receipt_id', 'digest'}
    }
    forged_gate_digest = canonical_digest(gate_payload)
    state['gate']['receipts'][0]['digest'] = forged_gate_digest
    state['gate']['receipts'][0]['receipt_id'] = f'eng-gate-{forged_gate_digest[:20]}'
    state['digest'] = canonical_digest({key: value for key, value in state.items() if key != 'digest'})

    try:
        SoftwareEngineeringControlPlane.from_state(claims=claims, state=state)
    except (ValueError, KeyError) as exc:
        assert 'closure' in str(exc)
    else:
        raise AssertionError('forged gate/closure lineage must be rejected')


def test_candidate_revalidation_survives_normal_claim_release_after_apply():
    patch, claims, claim, plane, _, gate, first = _ready_plane()
    historical_gate_digest = gate.digest
    claims.release(claim.claim_id, actor_agent_id=claim.agent_id)
    second = plane.revalidate(
        gate.receipt_id,
        patch=patch,
        current_source_revision='git:source-a',
    )
    assert first.current
    assert second.current
    assert second.reasons == ()
    assert plane.gate.get(gate.receipt_id).digest == historical_gate_digest
