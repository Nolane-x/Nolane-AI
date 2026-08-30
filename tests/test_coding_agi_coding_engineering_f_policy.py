from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence
from nolane.external_core.coding_claims import ClaimMode, CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.software_engineering import (
    EngineeringEvidenceKind,
    EngineeringEvidenceLedger,
    EngineeringPhase,
    PatchTransactionLedger,
    SoftwareEngineeringClosureEngine,
)
from nolane.external_core.software_engineering_policy import (
    EngineeringChangeManifestLedger,
    EngineeringRiskClass,
    EngineeringVerificationPolicy,
    GovernedEngineeringGate,
)
from nolane.external_core.software_engineering_validity import EngineeringClaimBindingLedger


def _patch(*, touched_files=('src/service.py',), touched_symbols=('Service.execute',)):
    return CodingPatchCandidate(
        patch_id='patch-00000001',
        producer_agent_id='coding.backend.01',
        task_id='task-00000001',
        work_id='coding-work-00000001',
        base_plan_version=4,
        base_architecture_version=7,
        touched_files=touched_files,
        touched_symbols=touched_symbols,
        patch_artifact_id='artifact:patch-1',
        compile_evidence_refs=('legacy:compile',),
        test_evidence_refs=('legacy:test',),
        static_evidence_refs=('legacy:static',),
        status=CodingPatchStatus.VERIFIED,
    )


def _coding_ready(patch_id):
    verification = PatchVerificationEvidence(
        evidence_id='verify:patch-1',
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


def _prepared(*, patch=None, kinds=None, bind_claims=True):
    patch = patch or _patch()
    kinds = kinds or (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    )
    patch_digest = canonical_digest(patch.to_state())
    claims = CodeClaimLedger()
    claim = claims.claim(
        agent_id=patch.producer_agent_id,
        task_id=patch.task_id,
        file_paths=patch.touched_files,
        symbol_ids=patch.touched_symbols,
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    evidence = EngineeringEvidenceLedger()
    attestations = []
    for kind in kinds:
        attestations.append(evidence.record(
            subject_ref=patch.patch_id,
            subject_digest=patch_digest,
            producer_agent_id=patch.producer_agent_id,
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}:1',),
            source_revision='git:source-a',
            environment_digest='env:ubuntu24-py313',
            dependencies=(f'artifact:{kind.value}:1',),
        ))
    transactions = PatchTransactionLedger(evidence)
    tx = transactions.begin(
        patch_ref=patch.patch_id,
        patch_digest=patch_digest,
        source_revision='git:source-a',
        rollback_artifact_ref='artifact:rollback-1',
    )
    tx = transactions.bind_claims(tx.transaction_id, claim_refs=(claim.claim_id,))
    bindings = EngineeringClaimBindingLedger(transactions=transactions, claims=claims)
    if bind_claims:
        bindings.bind(tx.transaction_id)
    tx = transactions.verify_preconditions(
        tx.transaction_id,
        attestation_ids=(attestations[0].attestation_id,),
    )
    tx = transactions.mark_applied(tx.transaction_id, application_ref='workspace:apply-1')
    tx = transactions.observe_outcome(tx.transaction_id, evidence_refs=('runtime:outcome-1',))
    tx = transactions.verify_postconditions(
        tx.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    closure = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=transactions)
    manifests = EngineeringChangeManifestLedger()
    policy = EngineeringVerificationPolicy()
    gate = GovernedEngineeringGate(
        evidence=evidence,
        transactions=transactions,
        closure=closure,
        claims=claims,
        claim_bindings=bindings,
        policy=policy,
    )
    return patch, claims, evidence, attestations, transactions, closure, manifests, policy, gate, tx


def test_policy_base_requirements_cannot_be_weakened_by_caller():
    patch, _, _, _, _, _, manifests, policy, _, _ = _prepared()
    manifest = manifests.register(patch=patch, source_revision='git:source-a')
    required = policy.requirements(manifest)
    assert {
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    } <= set(required.attestation_kinds)
    assert required.policy_id == policy.policy_id


def test_manifest_infers_ui_surface_and_policy_requires_full_ui_quality_family():
    patch = _patch(
        touched_files=('frontend/components/LoginPanel.tsx', 'frontend/login.css'),
        touched_symbols=('LoginPanel.submit',),
    )
    patch, _, _, _, _, _, manifests, policy, _, _ = _prepared(patch=patch)
    manifest = manifests.register(patch=patch, source_revision='git:source-a')
    assert manifest.ui_sensitive
    assert manifest.risk in {EngineeringRiskClass.MODERATE, EngineeringRiskClass.HIGH, EngineeringRiskClass.CRITICAL}
    required = policy.requirements(manifest)
    assert required.require_ui
    assert {
        EngineeringEvidenceKind.VISUAL,
        EngineeringEvidenceKind.RESPONSIVE,
        EngineeringEvidenceKind.ACCESSIBILITY,
        EngineeringEvidenceKind.INTERACTION,
    } <= set(required.attestation_kinds)


def test_security_surface_forces_high_risk_security_and_review_evidence():
    patch = _patch(
        touched_files=('src/auth/token_service.py',),
        touched_symbols=('TokenService.rotate_secret',),
    )
    patch, _, _, _, _, _, manifests, policy, _, _ = _prepared(patch=patch)
    manifest = manifests.register(patch=patch, source_revision='git:source-a')
    assert manifest.security_sensitive
    assert manifest.risk in {EngineeringRiskClass.HIGH, EngineeringRiskClass.CRITICAL}
    required = policy.requirements(manifest)
    assert EngineeringEvidenceKind.SECURITY in required.attestation_kinds
    assert EngineeringEvidenceKind.REVIEW in required.attestation_kinds


def test_gate_blocks_before_closure_when_claim_state_binding_is_missing():
    patch, _, _, attestations, transactions, closure, manifests, _, gate, tx = _prepared(bind_claims=False)
    manifest = manifests.register(patch=patch, source_revision='git:source-a')
    receipt = gate.assess(
        manifest=manifest,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        transaction_id=tx.transaction_id,
        current_source_revision='git:source-a',
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert not receipt.ready
    assert 'missing_claim_state_binding' in receipt.reasons
    assert receipt.closure_receipt_id is None
    assert closure.receipts() == ()
    assert transactions.get(tx.transaction_id).phase is EngineeringPhase.POSTCONDITIONS_VERIFIED


def test_gate_blocks_security_patch_when_policy_evidence_is_missing():
    patch = _patch(touched_files=('src/auth/session.py',), touched_symbols=('Session.verify',))
    patch, _, _, attestations, transactions, closure, manifests, _, gate, tx = _prepared(patch=patch)
    manifest = manifests.register(patch=patch, source_revision='git:source-a')
    receipt = gate.assess(
        manifest=manifest,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        transaction_id=tx.transaction_id,
        current_source_revision='git:source-a',
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert not receipt.ready
    assert any('security' in reason for reason in receipt.reasons)
    assert any('review' in reason for reason in receipt.reasons)
    assert receipt.closure_receipt_id is not None
    assert not closure.get(receipt.closure_receipt_id).ready
    assert transactions.get(tx.transaction_id).phase is EngineeringPhase.POSTCONDITIONS_VERIFIED


def test_gate_transitions_to_candidate_only_when_policy_is_fully_satisfied():
    kinds = (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
        EngineeringEvidenceKind.SECURITY,
        EngineeringEvidenceKind.REVIEW,
    )
    patch = _patch(touched_files=('src/security/policy.py',), touched_symbols=('Policy.authorize',))
    patch, _, _, attestations, transactions, closure, manifests, _, gate, tx = _prepared(
        patch=patch,
        kinds=kinds,
    )
    manifest = manifests.register(patch=patch, source_revision='git:source-a')
    receipt = gate.assess(
        manifest=manifest,
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        transaction_id=tx.transaction_id,
        current_source_revision='git:source-a',
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert receipt.ready
    assert receipt.authority == 'candidate_only'
    assert receipt.required_attestation_kinds == tuple(sorted(kind.value for kind in kinds))
    assert receipt.closure_receipt_id is not None
    assert closure.get(receipt.closure_receipt_id).ready
    assert transactions.get(tx.transaction_id).phase is EngineeringPhase.CANDIDATE_READY


def test_manifest_and_policy_receipts_are_content_addressed_and_deterministic():
    patch, _, _, _, _, _, manifests, policy, _, _ = _prepared()
    first = manifests.register(
        patch=patch,
        source_revision='git:source-a',
        dependency_refs=('dep:b', 'dep:a'),
        impacted_component_refs=('component:y', 'component:x'),
    )
    second = manifests.register(
        patch=patch,
        source_revision='git:source-a',
        dependency_refs=('dep:a', 'dep:b'),
        impacted_component_refs=('component:x', 'component:y'),
    )
    assert first.manifest_id == second.manifest_id
    assert first.digest == second.digest
    assert policy.requirements(first).digest == policy.requirements(second).digest
