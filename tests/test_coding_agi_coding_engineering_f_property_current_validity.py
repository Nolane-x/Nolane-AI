from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

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
from nolane.external_core.software_engineering_current_property_validity import (
    EngineeringCurrentPropertyBoundReceipt,
    SoftwareEngineeringCurrentPropertyValidity,
)
from nolane.external_core.software_engineering_property_evidence import (
    EngineeringClaimClass,
    EngineeringProofMethod,
    EngineeringPropertyEvidenceLedger,
    EngineeringWitnessRole,
)
from nolane.external_core.software_engineering_property_gate import (
    EngineeringPropertyRequirement,
    SoftwareEngineeringPropertyGate,
)
from nolane.external_core.software_engineering_validity import (
    EngineeringClaimBindingLedger,
    EngineeringValidityEngine,
)


SOURCE_REVISION = "git:f-v11-source-a"


def _patch(status: CodingPatchStatus = CodingPatchStatus.VERIFIED) -> CodingPatchCandidate:
    return CodingPatchCandidate(
        patch_id="patch-f-v11-00000001",
        producer_agent_id="coding.backend.01",
        task_id="task-f-v11-00000001",
        work_id="coding-work-f-v11-00000001",
        base_plan_version=4,
        base_architecture_version=7,
        touched_files=("src/service.py",),
        touched_symbols=("Service.execute",),
        patch_artifact_id="artifact:f-v11-patch-1",
        compile_evidence_refs=("legacy:compile",),
        test_evidence_refs=("legacy:test",),
        static_evidence_refs=("legacy:static",),
        status=status,
    )


def _coding_ready(patch_id: str) -> CodingReadinessReceipt:
    verification = PatchVerificationEvidence(
        evidence_id="verify:f-v11-patch-1",
        verifier_agent_id="verification.testing.legacy",
        passed=True,
    )
    payload = {
        "receipt_id": "coding-ready-f-v11-00000001",
        "patch_id": patch_id,
        "ready": True,
        "reasons": [],
        "verification": verification.to_state(),
    }
    return CodingReadinessReceipt(
        receipt_id=payload["receipt_id"],
        patch_id=patch_id,
        ready=True,
        reasons=(),
        verification=verification,
        digest=canonical_digest(payload),
    )


def _systems():
    patch = _patch()
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
    legacy_attestations = []
    for kind in (
        EngineeringEvidenceKind.COMPILE,
        EngineeringEvidenceKind.TEST,
        EngineeringEvidenceKind.STATIC,
    ):
        legacy_attestations.append(
            evidence.record(
                subject_ref=patch.patch_id,
                subject_digest=patch_digest,
                producer_agent_id=patch.producer_agent_id,
                verifier_agent_id=f"verification.testing.legacy.{kind.value}",
                verifier_region="verification-testing",
                kind=kind,
                passed=True,
                evidence_refs=(f"run:legacy:{kind.value}:1",),
                source_revision=SOURCE_REVISION,
                environment_digest=f"env:legacy:{kind.value}",
                dependencies=(f"artifact:legacy:{kind.value}:1",),
            )
        )

    transactions = PatchTransactionLedger(evidence)
    tx = transactions.begin(
        patch_ref=patch.patch_id,
        patch_digest=patch_digest,
        source_revision=SOURCE_REVISION,
        rollback_artifact_ref="artifact:f-v11-rollback-1",
    )
    tx = transactions.bind_claims(tx.transaction_id, claim_refs=(claim.claim_id,))
    claim_bindings = EngineeringClaimBindingLedger(transactions=transactions, claims=claims)
    claim_bindings.bind(tx.transaction_id)
    tx = transactions.verify_preconditions(
        tx.transaction_id,
        attestation_ids=(legacy_attestations[0].attestation_id,),
    )
    tx = transactions.mark_applied(tx.transaction_id, application_ref="workspace:f-v11-apply-1")
    tx = transactions.observe_outcome(tx.transaction_id, evidence_refs=("runtime:f-v11-outcome-1",))
    tx = transactions.verify_postconditions(
        tx.transaction_id,
        attestation_ids=tuple(row.attestation_id for row in legacy_attestations),
    )
    closure = SoftwareEngineeringClosureEngine(evidence=evidence, transactions=transactions)
    historical = closure.assess(
        patch=patch,
        coding_readiness=_coding_ready(patch.patch_id),
        transaction_id=tx.transaction_id,
        current_source_revision=SOURCE_REVISION,
        required_attestation_kinds=(
            EngineeringEvidenceKind.COMPILE,
            EngineeringEvidenceKind.TEST,
            EngineeringEvidenceKind.STATIC,
        ),
        attestation_ids=tuple(row.attestation_id for row in legacy_attestations),
    )
    assert historical.ready is True
    assert transactions.get(tx.transaction_id).phase is EngineeringPhase.CANDIDATE_READY

    validity = EngineeringValidityEngine(
        evidence=evidence,
        transactions=transactions,
        closure=closure,
        claims=claims,
        claim_bindings=claim_bindings,
    )
    property_evidence = EngineeringPropertyEvidenceLedger(evidence=evidence)
    property_gate = SoftwareEngineeringPropertyGate(property_evidence=property_evidence)
    requirement = EngineeringPropertyRequirement(
        claim_id="claim:functional:session-refresh",
        claim_class=EngineeringClaimClass.FUNCTIONAL_BEHAVIOR,
        property_ref="behavior:session-refresh-preserves-auth",
    )
    manifest = property_gate.register_manifest(
        patch_ref=patch.patch_id,
        patch_digest=patch_digest,
        source_revision=SOURCE_REVISION,
        source_authority_ref="goal-design:engineering-contract:f-v11",
        requirements=(requirement,),
    )
    obligation = property_evidence.register_obligation(
        claim_id=requirement.claim_id,
        claim_class=requirement.claim_class,
        property_ref=requirement.property_ref,
        subject_ref=patch.patch_id,
        subject_digest=patch_digest,
        source_revision=SOURCE_REVISION,
    )
    oracle_ref = f"oracle:{requirement.property_ref}"
    property_attestation = evidence.record(
        subject_ref=patch.patch_id,
        subject_digest=patch_digest,
        producer_agent_id=patch.producer_agent_id,
        verifier_agent_id="verification.testing.property.semantic",
        verifier_region="verification-testing",
        kind=EngineeringEvidenceKind.TEST,
        passed=True,
        evidence_refs=("run:property:semantic:1", oracle_ref),
        source_revision=SOURCE_REVISION,
        environment_digest="env:property:semantic",
        dependencies=("artifact:property:semantic:1",),
    )
    witness = property_evidence.record_witness(
        obligation_id=obligation.obligation_id,
        attestation_id=property_attestation.attestation_id,
        method=EngineeringProofMethod.PROPERTY_TEST,
        role=EngineeringWitnessRole.DIRECT,
        measured_property_ref=requirement.property_ref,
        oracle_ref=oracle_ref,
        source_family="family:semantic-property-verifier",
    )
    property_closure = property_evidence.assess(
        obligation.obligation_id,
        witness_ids=(witness.witness_id,),
    )
    assert property_closure.ready is True
    historical_property_gate = property_gate.assess(
        manifest.manifest_id,
        property_bindings=((obligation.obligation_id, property_closure.receipt_id),),
    )
    assert historical_property_gate.ready is True

    current = SoftwareEngineeringCurrentPropertyValidity(
        validity=validity,
        property_gate=property_gate,
    )
    return {
        "patch": patch,
        "evidence": evidence,
        "legacy_attestations": tuple(legacy_attestations),
        "historical": historical,
        "validity": validity,
        "property_evidence": property_evidence,
        "property_gate": property_gate,
        "property_attestation": property_attestation,
        "historical_property_gate": historical_property_gate,
        "current": current,
    }


def _assess(systems, *, patch=None, source_revision: str = SOURCE_REVISION):
    return systems["current"].assess(
        base_closure_id=systems["historical"].receipt_id,
        property_gate_receipt_id=systems["historical_property_gate"].receipt_id,
        patch=patch or systems["patch"],
        current_source_revision=source_revision,
    )


def test_current_property_bound_candidate_requires_both_live_truth_layers() -> None:
    systems = _systems()
    receipt = _assess(systems)

    assert isinstance(receipt, EngineeringCurrentPropertyBoundReceipt)
    assert receipt.current is True
    assert receipt.reasons == ()
    assert receipt.authority == "candidate_only"
    assert receipt.base_closure_id == systems["historical"].receipt_id
    assert receipt.historical_property_gate_receipt_id == systems["historical_property_gate"].receipt_id
    assert receipt.live_property_gate_receipt_id
    assert receipt.current_validity_receipt_id


def test_revoked_legacy_evidence_reopens_current_property_bound_candidate_without_rewriting_history() -> None:
    systems = _systems()
    first = _assess(systems)
    assert first.current is True
    historical_digest = systems["historical"].digest
    property_gate_digest = systems["historical_property_gate"].digest

    systems["evidence"].revoke(
        systems["legacy_attestations"][1].attestation_id,
        reason="legacy test provenance invalidated",
    )
    reopened = _assess(systems)

    assert reopened.current is False
    assert "legacy_current_validity:revoked_or_invalid_evidence" in reopened.reasons
    assert systems["historical"].ready is True
    assert systems["historical"].digest == historical_digest
    assert systems["historical_property_gate"].ready is True
    assert systems["historical_property_gate"].digest == property_gate_digest


def test_revoked_property_evidence_reopens_even_when_legacy_closure_remains_current() -> None:
    systems = _systems()
    assert _assess(systems).current is True

    systems["evidence"].revoke(
        systems["property_attestation"].attestation_id,
        reason="semantic property oracle invalidated",
    )
    reopened = _assess(systems)

    assert systems["validity"].revalidate(
        systems["historical"].receipt_id,
        patch=systems["patch"],
        current_source_revision=SOURCE_REVISION,
    ).current is True
    assert reopened.current is False
    assert "property_gate_not_current" in reopened.reasons


def test_source_and_patch_drift_block_current_property_bound_candidate() -> None:
    systems = _systems()

    stale_source = _assess(systems, source_revision="git:f-v11-source-b")
    assert stale_source.current is False
    assert "legacy_current_validity:stale_source_revision" in stale_source.reasons
    assert "current_property_source_revision_mismatch" in stale_source.reasons

    superseded = replace(systems["patch"], status=CodingPatchStatus.SUPERSEDED)
    stale_patch = _assess(systems, patch=superseded)
    assert stale_patch.current is False
    assert "legacy_current_validity:patch_state_changed" in stale_patch.reasons


def test_current_property_validity_snapshot_rejects_recomputed_truth_upgrade() -> None:
    systems = _systems()
    systems["evidence"].revoke(
        systems["legacy_attestations"][1].attestation_id,
        reason="legacy test revoked before snapshot",
    )
    blocked = _assess(systems)
    assert blocked.current is False

    state = deepcopy(systems["current"].to_state())
    row = state["receipts"][-1]
    row["current"] = True
    row["reasons"] = []
    payload = {key: value for key, value in row.items() if key not in {"receipt_id", "digest"}}
    digest = canonical_digest(payload)
    row["digest"] = digest
    row["receipt_id"] = f"eng-current-property-{digest[:20]}"

    with pytest.raises(ValueError, match="current|truth|validity|property"):
        SoftwareEngineeringCurrentPropertyValidity.from_state(
            validity=systems["validity"],
            property_gate=systems["property_gate"],
            state=state,
        )
