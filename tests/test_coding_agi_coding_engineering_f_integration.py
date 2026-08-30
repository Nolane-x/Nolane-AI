from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingReadinessReceipt, PatchVerificationEvidence
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchStatus
from nolane.external_core.debugging import DebugResolutionReceipt
from nolane.external_core.software_engineering import (
    EngineeringDecision,
    EngineeringEvidenceKind,
    EngineeringEvidenceLedger,
    EngineeringPhase,
    PatchTransactionLedger,
    SoftwareEngineeringClosureEngine,
)
from nolane.external_core.ui_ux import UIReadinessReceipt


def _coding_receipt(patch_id: str) -> CodingReadinessReceipt:
    verification = PatchVerificationEvidence(
        evidence_id='verification-evidence-1',
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


def _debug_receipt(patch_id: str, coding_receipt_id: str) -> DebugResolutionReceipt:
    payload = {
        'resolution_id': 'debug-resolution-00000001',
        'case_id': 'debug-case-00000001',
        'handoff_id': 'debug-handoff-00000001',
        'hypothesis_id': 'debug-hypothesis-00000001',
        'patch_id': patch_id,
        'coding_readiness_receipt_id': coding_receipt_id,
        'resolver_agent_id': 'debug.root-cause.01',
    }
    return DebugResolutionReceipt(**payload, digest=canonical_digest(payload))


def _ui_receipt(patch_id: str, coding_receipt_id: str) -> UIReadinessReceipt:
    payload = {
        'receipt_id': 'ui-ready-00000001',
        'patch_id': patch_id,
        'coding_readiness_receipt_id': coding_receipt_id,
        'ready': True,
        'reasons': [],
        'observation_ids': ['ui-observation-1', 'ui-observation-2'],
        'quality_evidence_ids': ['ui-quality-visual', 'ui-quality-accessibility'],
    }
    return UIReadinessReceipt(
        receipt_id=payload['receipt_id'],
        patch_id=patch_id,
        coding_readiness_receipt_id=coding_receipt_id,
        ready=True,
        reasons=(),
        observation_ids=tuple(payload['observation_ids']),
        quality_evidence_ids=tuple(payload['quality_evidence_ids']),
        digest=canonical_digest(payload),
    )


def test_governed_closure_composes_real_canonical_f_receipts_without_shadow_authority():
    patch = CodingPatchCandidate(
        patch_id='patch-00000001',
        producer_agent_id='coding.backend.01',
        task_id='task-00000001',
        work_id='coding-work-00000001',
        base_plan_version=4,
        base_architecture_version=7,
        touched_files=('nolane/service.py',),
        touched_symbols=('Service.execute',),
        patch_artifact_id='artifact:patch-1',
        compile_evidence_refs=('legacy:compile',),
        test_evidence_refs=('legacy:test',),
        static_evidence_refs=('legacy:static',),
        status=CodingPatchStatus.VERIFIED,
    )
    patch_digest = canonical_digest(patch.to_state())
    evidence = EngineeringEvidenceLedger()
    attestations = []
    for kind in (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    ):
        attestations.append(evidence.record(
            subject_ref=patch.patch_id,
            subject_digest=patch_digest,
            producer_agent_id=patch.producer_agent_id,
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}:canonical',),
            source_revision='git:8063cb7',
            environment_digest='env:ubuntu24-py313',
            dependencies=(f'artifact:{kind.value}:canonical',),
        ))

    transactions = PatchTransactionLedger(evidence)
    tx = transactions.begin(
        patch_ref=patch.patch_id,
        patch_digest=patch_digest,
        source_revision='git:8063cb7',
        rollback_artifact_ref='artifact:rollback-bundle-1',
    )
    tx = transactions.bind_claims(tx.transaction_id, claim_refs=('claim-00000001',))
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
    assert tx.phase is EngineeringPhase.POSTCONDITIONS_VERIFIED

    coding = _coding_receipt(patch.patch_id)
    debug = _debug_receipt(patch.patch_id, coding.receipt_id)
    ui = _ui_receipt(patch.patch_id, coding.receipt_id)
    closure = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=transactions)
    receipt = closure.assess(
        patch=patch,
        coding_readiness=coding,
        transaction_id=tx.transaction_id,
        current_source_revision='git:8063cb7',
        required_attestation_kinds=(
            EngineeringEvidenceKind.COMPILE,
            EngineeringEvidenceKind.TEST,
            EngineeringEvidenceKind.STATIC,
        ),
        attestation_ids=tuple(row.attestation_id for row in attestations),
        require_debug=True,
        debug_resolution=debug,
        require_ui=True,
        ui_readiness=ui,
    )

    assert receipt.ready
    assert receipt.decision is EngineeringDecision.CANDIDATE_READY
    assert receipt.authority == 'candidate_only'
    assert transactions.get(tx.transaction_id).closure_receipt_id == receipt.receipt_id
    assert transactions.get(tx.transaction_id).phase is EngineeringPhase.CANDIDATE_READY
