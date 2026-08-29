from __future__ import annotations

import importlib

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import PromotionAssuranceReceipt
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
