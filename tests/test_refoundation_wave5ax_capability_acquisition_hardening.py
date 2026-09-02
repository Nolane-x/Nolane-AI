from __future__ import annotations

import importlib
from typing import get_type_hints

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane, PromotionAssuranceReceipt
from nolane.external_core.cognitive_catalog import OperatorFamilyDescriptor, SubOperatorDescriptor
from nolane.external_core.cognitive_library import CognitiveLibrary


def _family() -> OperatorFamilyDescriptor:
    return OperatorFamilyDescriptor(
        "wave5ax_hardening",
        "Capability used to harden Assurance provenance.",
        (
            SubOperatorDescriptor(
                "wave5ax_hardening.probe",
                "experimental",
                "Exercise promotion-store provenance.",
                frozenset({"wave5ax", "hardening"}),
            ),
        ),
    )


def _receipt(candidate_id: str, evidence_ids: tuple[str, ...], baseline: str) -> PromotionAssuranceReceipt:
    payload = {
        "receipt_id": "assurance-promotion-spoofed-store",
        "subject_id": candidate_id,
        "evidence_ids": list(evidence_ids),
        "predecessor_version": baseline,
        "verifier_ids": ["verification.chief"],
        "authorized": True,
        "reasons": [],
    }
    return PromotionAssuranceReceipt(
        receipt_id=payload["receipt_id"],
        subject_id=candidate_id,
        evidence_ids=evidence_ids,
        predecessor_version=baseline,
        verifier_ids=("verification.chief",),
        authorized=True,
        reasons=(),
        digest=canonical_digest(payload),
    )


def _assurance_plane(*receipts: PromotionAssuranceReceipt) -> AssuranceControlPlane:
    plane = object.__new__(AssuranceControlPlane)
    plane._promotion_receipts = {row.receipt_id: row for row in receipts}
    return plane


class _SpoofedReceiptStore:
    def __init__(self, receipt: PromotionAssuranceReceipt) -> None:
        self.receipt = receipt

    def promotion_receipt(self, receipt_id: str) -> PromotionAssuranceReceipt:
        assert receipt_id == self.receipt.receipt_id
        return self.receipt


def test_wave5ax_promotion_rejects_non_native_assurance_store_even_with_byte_exact_receipt() -> None:
    native = importlib.import_module("nolane.external_core.capability_acquisition")
    library = CognitiveLibrary()
    governor = native.CapabilityAcquisitionGovernor(library)
    candidate = native.CapabilityCandidate.for_operator_family(_family())
    governor.admit(candidate)
    governor.begin_probation(candidate.candidate_id)
    evidence_ids = ("independent:hardening", "challenge:hardening")
    governor.record_probation(
        candidate.candidate_id,
        evidence_ids=evidence_ids,
        independent_passed=True,
        challenge_passed=True,
        reliability=0.99,
    )
    receipt = _receipt(candidate.candidate_id, evidence_ids, library.digest)

    with pytest.raises(TypeError, match="AssuranceControlPlane"):
        governor.promote(
            candidate.candidate_id,
            assurance=_SpoofedReceiptStore(receipt),
            receipt=receipt,
        )

    assert governor.retrievable_ids() == ()
    with pytest.raises(KeyError):
        library.family("wave5ax_hardening")


def test_wave5ax_promote_public_contract_names_native_assurance_authority() -> None:
    native = importlib.import_module("nolane.external_core.capability_acquisition")
    hints = get_type_hints(native.CapabilityAcquisitionGovernor.promote)
    assert hints["assurance"] is AssuranceControlPlane


def test_wave5ax_restore_rejects_library_authority_for_non_promoted_state() -> None:
    native = importlib.import_module("nolane.external_core.capability_acquisition")
    library = CognitiveLibrary()
    governor = native.CapabilityAcquisitionGovernor(library)
    candidate = native.CapabilityCandidate.for_operator_family(_family())
    governor.admit(candidate)
    state = governor.to_state()

    # A distinct governor can legitimately promote the same content into the
    # shared library, but that must not retroactively promote this saved record.
    promoting_governor = native.CapabilityAcquisitionGovernor(library)
    promoting_governor.admit(candidate)
    promoting_governor.begin_probation(candidate.candidate_id)
    evidence_ids = ("independent:foreign-governor", "challenge:foreign-governor")
    promoting_governor.record_probation(
        candidate.candidate_id,
        evidence_ids=evidence_ids,
        independent_passed=True,
        challenge_passed=True,
        reliability=0.99,
    )
    receipt = _receipt(candidate.candidate_id, evidence_ids, library.digest)
    promoting_governor.promote(
        candidate.candidate_id,
        assurance=_assurance_plane(receipt),
        receipt=receipt,
    )

    with pytest.raises(ValueError, match="non-promoted.*library|library.*non-promoted"):
        native.CapabilityAcquisitionGovernor.from_state(state, library=library)


def test_wave5ax_restore_rebinds_promoted_authority_to_persisted_native_assurance() -> None:
    native = importlib.import_module("nolane.external_core.capability_acquisition")
    library = CognitiveLibrary()
    governor = native.CapabilityAcquisitionGovernor(library)
    candidate = native.CapabilityCandidate.for_operator_family(_family())
    governor.admit(candidate)
    governor.begin_probation(candidate.candidate_id)
    evidence_ids = ("independent:restore", "challenge:restore")
    governor.record_probation(
        candidate.candidate_id,
        evidence_ids=evidence_ids,
        independent_passed=True,
        challenge_passed=True,
        reliability=0.99,
    )
    baseline = library.digest
    receipt = _receipt(candidate.candidate_id, evidence_ids, baseline)
    assurance = _assurance_plane(receipt)
    governor.promote(candidate.candidate_id, assurance=assurance, receipt=receipt)
    state = governor.to_state()
    restored_library = CognitiveLibrary.from_state(
        library.to_state(),
        assurance=assurance,
    )

    with pytest.raises(ValueError, match="persisted assurance"):
        native.CapabilityAcquisitionGovernor.from_state(
            state,
            library=restored_library,
            assurance=_assurance_plane(),
        )

    wrong_subject = _receipt("capability:wrong-subject", evidence_ids, baseline)
    with pytest.raises(ValueError, match="subject"):
        native.CapabilityAcquisitionGovernor.from_state(
            state,
            library=restored_library,
            assurance=_assurance_plane(wrong_subject),
        )

    restored = native.CapabilityAcquisitionGovernor.from_state(
        state,
        library=restored_library,
        assurance=assurance,
    )
    assert restored.retrievable_ids() == (candidate.candidate_id,)
    assert restored.retrieve(candidate.candidate_id) == _family()


def test_wave5ax_candidate_can_be_quarantined_before_probation_fail_closed() -> None:
    native = importlib.import_module("nolane.external_core.capability_acquisition")
    library = CognitiveLibrary()
    governor = native.CapabilityAcquisitionGovernor(library)
    candidate = native.CapabilityCandidate.for_operator_family(_family())
    governor.admit(candidate)
    baseline = library.digest

    quarantined = governor.quarantine(candidate.candidate_id, reason="admission policy rejected")

    assert quarantined.state is native.CapabilityState.QUARANTINED
    assert quarantined.baseline_digest == baseline
    assert quarantined.assurance_receipt_id is None
    assert governor.retrievable_ids() == ()
    with pytest.raises(PermissionError):
        governor.retrieve(candidate.candidate_id)
    with pytest.raises(ValueError, match="quarantined"):
        governor.begin_probation(candidate.candidate_id)
    with pytest.raises(KeyError):
        library.family("wave5ax_hardening")
