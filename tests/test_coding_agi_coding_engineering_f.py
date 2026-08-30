from dataclasses import dataclass

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering import (
    EngineeringDecision,
    EngineeringEvidenceKind,
    EngineeringEvidenceLedger,
    EngineeringPhase,
    PatchTransactionLedger,
    SoftwareEngineeringClosureEngine,
)


@dataclass(frozen=True)
class _Verification:
    verifier_agent_id: str


@dataclass(frozen=True)
class _Patch:
    patch_id: str = 'patch-00000001'
    producer_agent_id: str = 'coding.backend.01'
    status: str = 'verified'

    def to_state(self):
        return {
            'patch_id': self.patch_id,
            'producer_agent_id': self.producer_agent_id,
            'status': self.status,
        }


@dataclass(frozen=True)
class _CodingReady:
    patch_id: str
    receipt_id: str = 'coding-ready-00000001'
    ready: bool = True
    digest: str = 'coding-ready-digest'
    verification: _Verification = _Verification('verification.testing.01')


@dataclass(frozen=True)
class _DebugResolution:
    patch_id: str
    coding_readiness_receipt_id: str
    resolution_id: str = 'debug-resolution-00000001'
    digest: str = 'debug-resolution-digest'


@dataclass(frozen=True)
class _UIReady:
    patch_id: str
    coding_readiness_receipt_id: str
    receipt_id: str = 'ui-ready-00000001'
    ready: bool = True
    digest: str = 'ui-ready-digest'


def _prepared_transaction(evidence, *, source_revision='repo-a', rollback='artifact:rollback'):
    patch = _Patch()
    patch_digest = canonical_digest(patch.to_state())
    attestations = []
    for kind in (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    ):
        attestations.append(
            evidence.record(
                subject_ref=patch.patch_id,
                subject_digest=patch_digest,
                producer_agent_id=patch.producer_agent_id,
                verifier_agent_id='verification.testing.01',
                verifier_region='verification-testing',
                kind=kind,
                passed=True,
                evidence_refs=(f'evidence:{kind.value}',),
                source_revision=source_revision,
                environment_digest='env:linux-py313',
                dependencies=(f'artifact:{kind.value}',),
            )
        )
    txs = PatchTransactionLedger(evidence)
    tx = txs.begin(
        patch_ref=patch.patch_id,
        patch_digest=patch_digest,
        source_revision=source_revision,
        rollback_artifact_ref=rollback,
    )
    tx = txs.bind_claims(tx.transaction_id, claim_refs=('claim-00000001',))
    tx = txs.verify_preconditions(tx.transaction_id, attestation_ids=(attestations[0].attestation_id,))
    tx = txs.mark_applied(tx.transaction_id, application_ref='workspace:apply-1')
    tx = txs.observe_outcome(tx.transaction_id, evidence_refs=('runtime:outcome-1',))
    tx = txs.verify_postconditions(
        tx.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    return patch, txs, tx, tuple(attestations)


def test_engineering_evidence_is_content_addressed_independent_and_non_rebindable():
    ledger = EngineeringEvidenceLedger()
    patch = _Patch()
    patch_digest = canonical_digest(patch.to_state())
    row = ledger.record(
        subject_ref=patch.patch_id,
        subject_digest=patch_digest,
        producer_agent_id=patch.producer_agent_id,
        verifier_agent_id='verification.testing.01',
        verifier_region='verification-testing',
        kind=EngineeringEvidenceKind.TEST,
        passed=True,
        evidence_refs=('run:123',),
        source_revision='repo-a',
        environment_digest='env-a',
    )
    assert row.attestation_id.startswith('eng-evidence-')
    assert ledger.get(row.attestation_id) is row

    with pytest.raises(PermissionError, match='self-verification'):
        ledger.record(
            subject_ref=patch.patch_id,
            subject_digest=patch_digest,
            producer_agent_id=patch.producer_agent_id,
            verifier_agent_id=patch.producer_agent_id,
            verifier_region='coding-backend',
            kind=EngineeringEvidenceKind.TEST,
            passed=True,
            evidence_refs=('run:self',),
            source_revision='repo-a',
            environment_digest='env-a',
        )


def test_patch_transaction_enforces_world_style_action_lifecycle_and_rollback_boundary():
    evidence = EngineeringEvidenceLedger()
    patch, txs, tx, _ = _prepared_transaction(evidence)
    assert tx.phase is EngineeringPhase.POSTCONDITIONS_VERIFIED

    rolled_back = txs.rollback(tx.transaction_id, rollback_ref='workspace:rollback-1', reason='late regression')
    assert rolled_back.phase is EngineeringPhase.ROLLED_BACK
    with pytest.raises(ValueError, match='phase'):
        txs.mark_candidate_ready(tx.transaction_id, closure_receipt_id='closure-impossible')


def test_closure_blocks_stale_source_even_when_old_verification_was_green():
    evidence = EngineeringEvidenceLedger()
    patch, txs, tx, attestations = _prepared_transaction(evidence, source_revision='repo-a')
    engine = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=txs)
    receipt = engine.assess(
        patch=patch,
        coding_readiness=_CodingReady(patch.patch_id),
        transaction_id=tx.transaction_id,
        current_source_revision='repo-b',
        required_attestation_kinds=(
            EngineeringEvidenceKind.COMPILE,
            EngineeringEvidenceKind.TEST,
            EngineeringEvidenceKind.STATIC,
        ),
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert not receipt.ready
    assert receipt.decision is EngineeringDecision.BLOCKED
    assert 'stale_source_revision' in receipt.reasons


def test_provenance_revocation_cascades_and_invalidates_ready_candidate():
    evidence = EngineeringEvidenceLedger()
    patch, txs, tx, attestations = _prepared_transaction(evidence)
    revoked = evidence.revoke('artifact:test', reason='test artifact corrupted')
    assert attestations[1].attestation_id in revoked

    engine = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=txs)
    receipt = engine.assess(
        patch=patch,
        coding_readiness=_CodingReady(patch.patch_id),
        transaction_id=tx.transaction_id,
        current_source_revision='repo-a',
        required_attestation_kinds=(
            EngineeringEvidenceKind.COMPILE,
            EngineeringEvidenceKind.TEST,
            EngineeringEvidenceKind.STATIC,
        ),
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert not receipt.ready
    assert 'revoked_or_invalid_evidence' in receipt.reasons


def test_cross_surface_closure_requires_debug_and_ui_receipts_when_declared():
    evidence = EngineeringEvidenceLedger()
    patch, txs, tx, attestations = _prepared_transaction(evidence)
    coding = _CodingReady(patch.patch_id)
    engine = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=txs)

    blocked = engine.assess(
        patch=patch,
        coding_readiness=coding,
        transaction_id=tx.transaction_id,
        current_source_revision='repo-a',
        required_attestation_kinds=(EngineeringEvidenceKind.TEST,),
        attestation_ids=tuple(row.attestation_id for row in attestations),
        require_debug=True,
        require_ui=True,
    )
    assert {'missing_debug_resolution', 'missing_ui_readiness'} <= set(blocked.reasons)

    ready = engine.assess(
        patch=patch,
        coding_readiness=coding,
        transaction_id=tx.transaction_id,
        current_source_revision='repo-a',
        required_attestation_kinds=(EngineeringEvidenceKind.TEST,),
        attestation_ids=tuple(row.attestation_id for row in attestations),
        require_debug=True,
        debug_resolution=_DebugResolution(patch.patch_id, coding.receipt_id),
        require_ui=True,
        ui_readiness=_UIReady(patch.patch_id, coding.receipt_id),
    )
    assert ready.ready
    assert ready.decision is EngineeringDecision.CANDIDATE_READY
    assert ready.authority == 'candidate_only'
    assert txs.get(tx.transaction_id).phase is EngineeringPhase.CANDIDATE_READY


def test_closure_digest_is_deterministic_under_attestation_input_order():
    evidence = EngineeringEvidenceLedger()
    patch, txs_a, tx_a, attestations = _prepared_transaction(evidence)
    coding = _CodingReady(patch.patch_id)
    engine_a = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=txs_a)
    a = engine_a.assess(
        patch=patch,
        coding_readiness=coding,
        transaction_id=tx_a.transaction_id,
        current_source_revision='repo-a',
        required_attestation_kinds=(EngineeringEvidenceKind.TEST,),
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )

    # A fresh transaction prevents the first successful assessment's terminal phase
    # from affecting the determinism check.
    patch_b, txs_b, tx_b, attestations_b = _prepared_transaction(evidence)
    engine_b = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=txs_b)
    b = engine_b.assess(
        patch=patch_b,
        coding_readiness=coding,
        transaction_id=tx_b.transaction_id,
        current_source_revision='repo-a',
        required_attestation_kinds=(EngineeringEvidenceKind.TEST,),
        attestation_ids=tuple(reversed([row.attestation_id for row in attestations_b])),
    )
    assert a.digest == b.digest


def test_revocation_history_cannot_be_rebound_to_a_new_reason():
    evidence = EngineeringEvidenceLedger()
    evidence.revoke('artifact:test', reason='first-observed corruption')
    with pytest.raises(ValueError, match='revocation'):
        evidence.revoke('artifact:test', reason='rewritten history')


def test_transaction_snapshot_rejects_candidate_ready_without_closure_receipt():
    evidence = EngineeringEvidenceLedger()
    _, txs, _, _ = _prepared_transaction(evidence)
    state = txs.to_state()
    state['transactions'][0]['phase'] = EngineeringPhase.CANDIDATE_READY.value
    state['transactions'][0]['closure_receipt_id'] = None

    with pytest.raises(ValueError, match='candidate-ready'):
        PatchTransactionLedger.from_state(evidence=evidence, state=state)


def test_closure_snapshot_rejects_forged_transaction_closure_linkage():
    evidence = EngineeringEvidenceLedger()
    patch, txs, tx, attestations = _prepared_transaction(evidence)
    engine = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=txs)
    receipt = engine.assess(
        patch=patch,
        coding_readiness=_CodingReady(patch.patch_id),
        transaction_id=tx.transaction_id,
        current_source_revision='repo-a',
        required_attestation_kinds=(EngineeringEvidenceKind.TEST,),
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert receipt.ready

    tx_state = txs.to_state()
    tx_state['transactions'][0]['closure_receipt_id'] = 'eng-closure-forged'
    restored_transactions = PatchTransactionLedger.from_state(evidence=evidence, state=tx_state)

    with pytest.raises(ValueError, match='closure.*lineage'):
        SoftwareEngineeringClosureEngine.from_state(
            evidence=evidence,
            transactions=restored_transactions,
            state=engine.to_state(),
        )
