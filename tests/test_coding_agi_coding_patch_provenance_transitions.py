from __future__ import annotations

import copy

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchCandidate, CodingPatchLedger, CodingPatchStatus
from nolane.external_core.software_engineering import EngineeringEvidenceKind, EngineeringEvidenceLedger


ARTIFACT_ID = "artifact-patch-001"
ARTIFACT_DIGEST = "sha256:patch-001"
SOURCE_REVISION = "source-rev-001"
OPERATION_REF = "patch-op-001"


def _evidence_ledger() -> EngineeringEvidenceLedger:
    return EngineeringEvidenceLedger()


def _patch_ledger(evidence: EngineeringEvidenceLedger | None = None) -> CodingPatchLedger:
    return CodingPatchLedger(CodeClaimLedger(), engineering_evidence=evidence)


def _register_patch(ledger: CodingPatchLedger, **overrides):
    values = {
        "producer_agent_id": "coding.agent",
        "task_id": "task-patch-provenance",
        "work_id": "work-patch-provenance",
        "base_plan_version": 1,
        "base_architecture_version": 1,
        "touched_files": ("nolane/example.py",),
        "patch_artifact_id": ARTIFACT_ID,
        "patch_artifact_digest": ARTIFACT_DIGEST,
        "base_source_revision": SOURCE_REVISION,
        "operation_ref": OPERATION_REF,
        "compile_evidence_refs": ("compile-green",),
        "test_evidence_refs": ("test-green",),
    }
    values.update(overrides)
    return ledger.register_patch(**values)


def _record_verification_evidence(
    evidence: EngineeringEvidenceLedger,
    *,
    kind: EngineeringEvidenceKind,
    artifact_id: str = ARTIFACT_ID,
    artifact_digest: str = ARTIFACT_DIGEST,
    source_revision: str = SOURCE_REVISION,
):
    return evidence.record(
        subject_ref=artifact_id,
        subject_digest=artifact_digest,
        producer_agent_id="coding.agent",
        verifier_agent_id=f"verifier.{kind.value}",
        verifier_region="verification-testing",
        kind=kind,
        passed=True,
        evidence_refs=(f"observed:{kind.value}",),
        source_revision=source_revision,
        environment_digest="env:hosted-ci",
    )


def _verify(ledger: CodingPatchLedger, evidence: EngineeringEvidenceLedger, patch_id: str):
    compile_attestation = _record_verification_evidence(evidence, kind=EngineeringEvidenceKind.COMPILE)
    test_attestation = _record_verification_evidence(evidence, kind=EngineeringEvidenceKind.TEST)
    verified = ledger.verify_patch(
        patch_id,
        evidence_attestation_ids=(compile_attestation.attestation_id, test_attestation.attestation_id),
    )
    return verified, compile_attestation, test_attestation


def test_direct_verified_status_cannot_launder_unproven_patch() -> None:
    ledger = _patch_ledger()
    patch = _register_patch(ledger)

    with pytest.raises(PermissionError, match="verified"):
        ledger.set_status(patch.patch_id, CodingPatchStatus.VERIFIED)


def test_provenance_registration_is_content_bound_and_operation_idempotent() -> None:
    ledger = _patch_ledger()
    first = _register_patch(ledger)
    replay = _register_patch(ledger)

    assert replay == first
    assert first.patch_artifact_digest == ARTIFACT_DIGEST
    assert first.base_source_revision == SOURCE_REVISION
    assert first.operation_ref == OPERATION_REF
    provenance = ledger.get_provenance(first.provenance_id)
    assert provenance.patch_artifact_id == ARTIFACT_ID
    assert provenance.patch_artifact_digest == ARTIFACT_DIGEST
    assert provenance.base_source_revision == SOURCE_REVISION
    assert provenance.operation_ref == OPERATION_REF
    assert provenance.digest

    with pytest.raises(ValueError, match="operation ref"):
        _register_patch(ledger, patch_artifact_digest="sha256:different")


def test_verified_transition_requires_canonical_compile_and_test_evidence_bound_to_provenance() -> None:
    evidence = _evidence_ledger()
    ledger = _patch_ledger(evidence)
    patch = _register_patch(ledger)
    compile_attestation = _record_verification_evidence(evidence, kind=EngineeringEvidenceKind.COMPILE)

    with pytest.raises(PermissionError, match="compile.*test|test.*compile"):
        ledger.verify_patch(patch.patch_id, evidence_attestation_ids=(compile_attestation.attestation_id,))

    test_attestation = _record_verification_evidence(evidence, kind=EngineeringEvidenceKind.TEST)
    verified = ledger.verify_patch(
        patch.patch_id,
        evidence_attestation_ids=(compile_attestation.attestation_id, test_attestation.attestation_id),
    )
    receipt = ledger.latest_transition(patch.patch_id)

    assert verified.status is CodingPatchStatus.VERIFIED
    assert receipt.to_status is CodingPatchStatus.VERIFIED
    assert receipt.authority == "patch_transition_only"
    assert receipt.provenance_id == patch.provenance_id
    assert set(receipt.evidence_attestation_ids) == {
        compile_attestation.attestation_id,
        test_attestation.attestation_id,
    }
    assert ledger.is_currently_verified(
        patch.patch_id,
        current_artifact_digest=ARTIFACT_DIGEST,
        current_source_revision=SOURCE_REVISION,
    ) is True


def test_wrong_artifact_or_source_evidence_cannot_verify_patch() -> None:
    evidence = _evidence_ledger()
    ledger = _patch_ledger(evidence)
    patch = _register_patch(ledger)
    compile_attestation = _record_verification_evidence(evidence, kind=EngineeringEvidenceKind.COMPILE)
    wrong_test = _record_verification_evidence(
        evidence,
        kind=EngineeringEvidenceKind.TEST,
        artifact_digest="sha256:other-artifact",
    )

    with pytest.raises(PermissionError, match="provenance"):
        ledger.verify_patch(
            patch.patch_id,
            evidence_attestation_ids=(compile_attestation.attestation_id, wrong_test.attestation_id),
        )


def test_current_verification_reopens_on_source_or_artifact_drift() -> None:
    evidence = _evidence_ledger()
    ledger = _patch_ledger(evidence)
    patch = _register_patch(ledger)
    _verify(ledger, evidence, patch.patch_id)

    assert ledger.is_currently_verified(
        patch.patch_id,
        current_artifact_digest="sha256:changed",
        current_source_revision=SOURCE_REVISION,
    ) is False
    assert ledger.is_currently_verified(
        patch.patch_id,
        current_artifact_digest=ARTIFACT_DIGEST,
        current_source_revision="source-rev-002",
    ) is False


def test_evidence_revocation_reopens_current_verification_without_rewriting_history() -> None:
    evidence = _evidence_ledger()
    ledger = _patch_ledger(evidence)
    patch = _register_patch(ledger)
    historical, _, test_attestation = _verify(ledger, evidence, patch.patch_id)
    historical_receipt = ledger.latest_transition(patch.patch_id)

    evidence.revoke(test_attestation.attestation_id, reason="test result invalidated")

    assert ledger.get_patch(patch.patch_id) == historical
    assert ledger.latest_transition(patch.patch_id) == historical_receipt
    assert ledger.get_patch(patch.patch_id).status is CodingPatchStatus.VERIFIED
    assert ledger.is_currently_verified(
        patch.patch_id,
        current_artifact_digest=ARTIFACT_DIGEST,
        current_source_revision=SOURCE_REVISION,
    ) is False


def test_snapshot_rejects_verified_status_without_verified_transition_receipt() -> None:
    ledger = _patch_ledger()
    _register_patch(ledger)
    state = ledger.to_state()
    state["patches"][0]["status"] = CodingPatchStatus.VERIFIED.value

    with pytest.raises(ValueError, match="transition"):
        CodingPatchLedger.from_state(claims=CodeClaimLedger(), state=state)


def test_recomputed_verified_receipt_without_evidence_cannot_launder_status() -> None:
    ledger = _patch_ledger()
    _register_patch(ledger)
    state = ledger.to_state()
    forged = copy.deepcopy(state)
    forged["patches"][0]["status"] = CodingPatchStatus.VERIFIED.value
    transition = forged["transitions"][0]
    transition["to_status"] = CodingPatchStatus.VERIFIED.value
    transition["evidence_attestation_ids"] = []
    transition["evidence_attestation_digests"] = []
    payload = {key: value for key, value in transition.items() if key not in {"receipt_id", "digest"}}
    transition["digest"] = canonical_digest(payload)
    transition["receipt_id"] = "patch-transition-" + transition["digest"][:20]

    with pytest.raises(ValueError, match="verified.*evidence|verified.*transition"):
        CodingPatchLedger.from_state(claims=CodeClaimLedger(), state=forged)


def test_snapshot_rejects_recomputed_operation_ref_rebinding() -> None:
    ledger = _patch_ledger()
    _register_patch(ledger)
    state = ledger.to_state()
    forged = copy.deepcopy(state)
    forged["provenance"][0]["operation_ref"] = "patch-op-rebound"

    with pytest.raises(ValueError, match="provenance.*digest|digest.*provenance|operation"):
        CodingPatchLedger.from_state(claims=CodeClaimLedger(), state=forged)


def test_v002_snapshot_rejects_patch_counter_frontier_inflation() -> None:
    ledger = _patch_ledger()
    _register_patch(ledger)
    state = ledger.to_state()
    state["patch_counter"] += 100

    with pytest.raises(ValueError, match="frontier inflation"):
        CodingPatchLedger.from_state(claims=CodeClaimLedger(), state=state)


def test_legacy_candidate_positional_constructor_order_is_preserved() -> None:
    candidate = CodingPatchCandidate(
        "patch-00000001",
        "coding.agent",
        "legacy-task",
        "legacy-work",
        1,
        1,
        ("nolane/legacy.py",),
        (),
        "legacy-artifact",
        ("legacy-compile",),
        ("legacy-test",),
        ("legacy-static",),
        ("legacy-risk",),
        (),
        (),
        CodingPatchStatus.EVIDENCE_READY,
    )

    assert candidate.compile_evidence_refs == ("legacy-compile",)
    assert candidate.test_evidence_refs == ("legacy-test",)
    assert candidate.static_evidence_refs == ("legacy-static",)
    assert candidate.status is CodingPatchStatus.EVIDENCE_READY
    assert candidate.provenance_id == ""


def test_legacy_v001_snapshot_restores_without_inventing_verification_authority() -> None:
    legacy = {
        "patch_counter": 1,
        "patches": [
            {
                "patch_id": "patch-00000001",
                "producer_agent_id": "coding.agent",
                "task_id": "legacy-task",
                "work_id": "legacy-work",
                "base_plan_version": 1,
                "base_architecture_version": 1,
                "touched_files": ["nolane/legacy.py"],
                "touched_symbols": [],
                "patch_artifact_id": "legacy-artifact",
                "compile_evidence_refs": ["legacy-compile"],
                "test_evidence_refs": ["legacy-test"],
                "static_evidence_refs": [],
                "known_risks": [],
                "plan_gap_event_refs": [],
                "architecture_concern_event_refs": [],
                "status": "verified",
            }
        ],
        "tool_receipts": [],
    }

    replay = CodingPatchLedger.from_state(claims=CodeClaimLedger(), state=legacy)
    restored = replay.get_patch("patch-00000001")

    assert restored.status is CodingPatchStatus.VERIFIED
    assert restored.provenance_id == ""
    assert replay.is_currently_verified(restored.patch_id) is False
    assert replay.transitions(restored.patch_id) == ()
