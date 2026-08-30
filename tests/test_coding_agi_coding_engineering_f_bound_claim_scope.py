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
    EngineeringVerificationPolicy,
    GovernedEngineeringGate,
)
from nolane.external_core.software_engineering_validity import EngineeringClaimBindingLedger


def _patch():
    return CodingPatchCandidate(
        patch_id='patch-00000001',
        producer_agent_id='coding.backend.01',
        task_id='task-00000001',
        work_id='coding-work-00000001',
        base_plan_version=1,
        base_architecture_version=1,
        touched_files=('src/a.py', 'src/b.py'),
        touched_symbols=('A.run', 'B.run'),
        patch_artifact_id='artifact:patch',
        compile_evidence_refs=('compile',),
        test_evidence_refs=('test',),
        static_evidence_refs=('static',),
        status=CodingPatchStatus.VERIFIED,
    )


def _ready(patch_id):
    verification = PatchVerificationEvidence('verify:1', 'verification.testing.01', True)
    payload = {
        'receipt_id': 'coding-ready-1',
        'patch_id': patch_id,
        'ready': True,
        'reasons': [],
        'verification': verification.to_state(),
    }
    return CodingReadinessReceipt(
        receipt_id='coding-ready-1',
        patch_id=patch_id,
        ready=True,
        reasons=(),
        verification=verification,
        digest=canonical_digest(payload),
    )


def _engineering_evidence(patch, evidence):
    patch_digest = canonical_digest(patch.to_state())
    rows = []
    for kind in (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    ):
        rows.append(evidence.record(
            subject_ref=patch.patch_id,
            subject_digest=patch_digest,
            producer_agent_id=patch.producer_agent_id,
            verifier_agent_id='verification.testing.01',
            verifier_region='verification-testing',
            kind=kind,
            passed=True,
            evidence_refs=(f'run:{kind.value}',),
            source_revision='git:a',
            environment_digest='env:a',
        ))
    return tuple(rows)


def test_gate_uses_only_transaction_bound_claims_not_other_active_claims():
    patch = _patch()
    claims = CodeClaimLedger()
    bound = claims.claim(
        agent_id=patch.producer_agent_id,
        task_id=patch.task_id,
        file_paths=('src/a.py',),
        symbol_ids=('A.run',),
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    claims.claim(
        agent_id=patch.producer_agent_id,
        task_id=patch.task_id,
        file_paths=('src/b.py',),
        symbol_ids=('B.run',),
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    assert claims.covers(
        agent_id=patch.producer_agent_id,
        task_id=patch.task_id,
        file_paths=patch.touched_files,
        symbol_ids=patch.touched_symbols,
    )

    evidence = EngineeringEvidenceLedger()
    attestations = _engineering_evidence(patch, evidence)
    transactions = PatchTransactionLedger(evidence)
    tx = transactions.begin(
        patch_ref=patch.patch_id,
        patch_digest=canonical_digest(patch.to_state()),
        source_revision='git:a',
        rollback_artifact_ref='rollback:a',
    )
    tx = transactions.bind_claims(tx.transaction_id, claim_refs=(bound.claim_id,))
    bindings = EngineeringClaimBindingLedger(transactions=transactions, claims=claims)
    binding = bindings.bind(tx.transaction_id)
    assert not bindings.covers_patch(binding.binding_id, patch)

    tx = transactions.verify_preconditions(tx.transaction_id, attestation_ids=(attestations[0].attestation_id,))
    tx = transactions.mark_applied(tx.transaction_id, application_ref='apply:a')
    tx = transactions.observe_outcome(tx.transaction_id, evidence_refs=('outcome:a',))
    tx = transactions.verify_postconditions(
        tx.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    closure = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=transactions)
    manifest = EngineeringChangeManifestLedger().register(patch=patch, source_revision='git:a')
    gate = GovernedEngineeringGate(
        evidence=evidence,
        transactions=transactions,
        closure=closure,
        claims=claims,
        claim_bindings=bindings,
        policy=EngineeringVerificationPolicy(),
    )
    receipt = gate.assess(
        manifest=manifest,
        patch=patch,
        coding_readiness=_ready(patch.patch_id),
        transaction_id=tx.transaction_id,
        current_source_revision='git:a',
        attestation_ids=tuple(row.attestation_id for row in attestations),
    )
    assert not receipt.ready
    assert 'bound_claim_scope_does_not_cover_patch' in receipt.reasons
    assert closure.receipts() == ()
    assert transactions.get(tx.transaction_id).phase is EngineeringPhase.POSTCONDITIONS_VERIFIED


def test_bound_claim_owner_and_task_must_match_patch_lineage():
    patch = _patch()
    claims = CodeClaimLedger()
    wrong = claims.claim(
        agent_id='coding.other.01',
        task_id='task-other',
        file_paths=patch.touched_files,
        symbol_ids=patch.touched_symbols,
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    evidence = EngineeringEvidenceLedger()
    transactions = PatchTransactionLedger(evidence)
    tx = transactions.begin(
        patch_ref=patch.patch_id,
        patch_digest=canonical_digest(patch.to_state()),
        source_revision='git:a',
        rollback_artifact_ref='rollback:a',
    )
    tx = transactions.bind_claims(tx.transaction_id, claim_refs=(wrong.claim_id,))
    bindings = EngineeringClaimBindingLedger(transactions=transactions, claims=claims)
    binding = bindings.bind(tx.transaction_id)
    assert not bindings.covers_patch(binding.binding_id, patch)
