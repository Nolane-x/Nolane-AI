from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane, PromotionAssuranceReceipt
from nolane.external_core.capability_acquisition import CapabilityCandidate
from nolane.external_core.cognitive_catalog import OperatorFamilyDescriptor, SubOperatorDescriptor
from nolane.external_core.cognitive_library import CognitiveLibrary
from nolane.external_core.cognitive_operators import Binary, Const
from nolane.external_core.cognitive_vocabulary import TemplateParam, make_abstraction
from nolane.metadata.component_versions import component_version


def _family() -> OperatorFamilyDescriptor:
    return OperatorFamilyDescriptor(
        "c5_authority_family",
        "Authority-gated family used by the Cognitive Library v0.0.2 contract.",
        (
            SubOperatorDescriptor(
                "c5_authority_family.probe",
                "experimental",
                "Probe an authority-gated Cognitive Library capability.",
                frozenset({"c5", "authority"}),
            ),
        ),
    )


def _abstraction():
    return make_abstraction(
        Binary("add", TemplateParam(0), Const(1)),
        parameter_count=1,
        support_task_ids=("task:c5:b", "task:c5:a"),
        raw_occurrence_cost=12,
        rewritten_cost=8,
    )


def _promotion_receipt(
    *,
    receipt_id: str,
    candidate_id: str,
    predecessor_version: str,
    evidence_ids: tuple[str, ...] = ("evidence:c5:independent", "evidence:c5:challenge"),
    authorized: bool = True,
) -> PromotionAssuranceReceipt:
    verifier_ids = ("verification.c5.alpha", "verification.c5.beta")
    reasons: tuple[str, ...] = () if authorized else ("rejected",)
    payload = {
        "receipt_id": receipt_id,
        "subject_id": candidate_id,
        "evidence_ids": list(evidence_ids),
        "predecessor_version": predecessor_version,
        "verifier_ids": list(verifier_ids),
        "authorized": authorized,
        "reasons": list(reasons),
    }
    return PromotionAssuranceReceipt(
        receipt_id=receipt_id,
        subject_id=candidate_id,
        evidence_ids=evidence_ids,
        predecessor_version=predecessor_version,
        verifier_ids=verifier_ids,
        authorized=authorized,
        reasons=reasons,
        digest=canonical_digest(payload),
    )


def _assurance_plane(*receipts: PromotionAssuranceReceipt) -> AssuranceControlPlane:
    plane = object.__new__(AssuranceControlPlane)
    plane._promotion_receipts = {row.receipt_id: row for row in receipts}
    return plane


def test_c5_revision_declares_diagnostics_descriptors_and_authority_gate() -> None:
    import nolane.external_core.cognitive_library as native

    assert str(component_version("external.cognitive_library")) == "0.0.2"
    assert native.COMPONENT_VERSION == "0.0.2"
    for name in (
        "CognitiveCapabilityDescriptor",
        "LibraryFitReport",
        "CognitiveVocabularyView",
    ):
        assert hasattr(native, name), name


def test_c5_direct_mutation_and_mutable_vocabulary_escape_hatch_fail_closed() -> None:
    library = CognitiveLibrary()
    family = _family()
    abstraction = _abstraction()
    baseline = library.digest

    with pytest.raises(TypeError, match="candidate_id|assurance|receipt|authority"):
        library.register_family(family)
    with pytest.raises(TypeError, match="candidate_id|assurance|receipt|authority"):
        library.register_abstraction(abstraction)
    assert library.digest == baseline

    view = library.vocabulary
    assert not hasattr(view, "register")
    assert not hasattr(view, "remove")
    with pytest.raises(KeyError):
        view.get(abstraction.abstraction_id)
    assert library.digest == baseline


def test_c5_installation_requires_exact_persisted_authorized_receipt_and_baseline() -> None:
    library = CognitiveLibrary()
    family = _family()
    candidate = CapabilityCandidate.for_operator_family(family)
    baseline = library.digest

    forged = _promotion_receipt(
        receipt_id="assurance-promotion-c5-forged",
        candidate_id=candidate.candidate_id,
        predecessor_version=baseline,
    )
    with pytest.raises(ValueError, match="persisted assurance"):
        library.register_family(
            family,
            candidate_id=candidate.candidate_id,
            assurance=_assurance_plane(),
            receipt=forged,
        )
    assert library.digest == baseline

    wrong_subject = _promotion_receipt(
        receipt_id="assurance-promotion-c5-wrong-subject",
        candidate_id="capability:not-the-family",
        predecessor_version=baseline,
    )
    with pytest.raises(ValueError, match="subject|candidate"):
        library.register_family(
            family,
            candidate_id=candidate.candidate_id,
            assurance=_assurance_plane(wrong_subject),
            receipt=wrong_subject,
        )
    assert library.digest == baseline

    wrong_baseline = _promotion_receipt(
        receipt_id="assurance-promotion-c5-wrong-baseline",
        candidate_id=candidate.candidate_id,
        predecessor_version="sha256:not-the-current-library",
    )
    with pytest.raises(ValueError, match="baseline|predecessor"):
        library.register_family(
            family,
            candidate_id=candidate.candidate_id,
            assurance=_assurance_plane(wrong_baseline),
            receipt=wrong_baseline,
        )
    assert library.digest == baseline

    rejected = _promotion_receipt(
        receipt_id="assurance-promotion-c5-rejected",
        candidate_id=candidate.candidate_id,
        predecessor_version=baseline,
        authorized=False,
    )
    with pytest.raises(ValueError, match="authorized"):
        library.register_family(
            family,
            candidate_id=candidate.candidate_id,
            assurance=_assurance_plane(rejected),
            receipt=rejected,
        )
    assert library.digest == baseline


def test_c5_authorized_installation_records_provenance_and_read_only_fit_diagnostics() -> None:
    library = CognitiveLibrary()
    family = _family()
    family_candidate = CapabilityCandidate.for_operator_family(family)
    family_receipt = _promotion_receipt(
        receipt_id="assurance-promotion-c5-family",
        candidate_id=family_candidate.candidate_id,
        predecessor_version=library.digest,
    )
    family_descriptor = library.register_family(
        family,
        candidate_id=family_candidate.candidate_id,
        assurance=_assurance_plane(family_receipt),
        receipt=family_receipt,
    )

    abstraction = _abstraction()
    abstraction_candidate = CapabilityCandidate.for_learned_abstraction(abstraction)
    abstraction_receipt = _promotion_receipt(
        receipt_id="assurance-promotion-c5-abstraction",
        candidate_id=abstraction_candidate.candidate_id,
        predecessor_version=library.digest,
    )
    abstraction_descriptor = library.register_abstraction(
        abstraction,
        candidate_id=abstraction_candidate.candidate_id,
        assurance=_assurance_plane(abstraction_receipt),
        receipt=abstraction_receipt,
    )

    assert family_descriptor.candidate_id == family_candidate.candidate_id
    assert family_descriptor.assurance_receipt_id == family_receipt.receipt_id
    assert family_descriptor.evidence_ids == family_receipt.evidence_ids
    assert abstraction_descriptor.candidate_id == abstraction_candidate.candidate_id
    assert abstraction_descriptor.assurance_receipt_id == abstraction_receipt.receipt_id
    assert abstraction_descriptor.evidence_ids == abstraction_receipt.evidence_ids
    assert abstraction_descriptor.support_task_ids == ("task:c5:a", "task:c5:b")

    baseline = library.digest
    report = library.diagnose_fit(
        operator_ids=("c5_authority_family.probe", "missing.operator"),
        abstraction_ids=(abstraction.abstraction_id,),
    )
    assert report.library_digest == baseline
    assert report.matched_operator_ids == ("c5_authority_family.probe",)
    assert report.missing_operator_ids == ("missing.operator",)
    assert report.matched_abstraction_ids == (abstraction.abstraction_id,)
    assert report.missing_abstraction_ids == ()
    assert report.coverage == pytest.approx(2 / 3)
    assert report.complete is False
    assert family_descriptor.descriptor_id in report.descriptor_ids
    assert abstraction_descriptor.descriptor_id in report.descriptor_ids
    assert library.digest == baseline

    restored = CognitiveLibrary.from_state(library.to_state())
    assert restored.to_state() == library.to_state()
    assert restored.digest == library.digest
    assert restored.descriptor(family_descriptor.descriptor_id) == family_descriptor
    assert restored.descriptor(abstraction_descriptor.descriptor_id) == abstraction_descriptor


def test_c5_capability_acquisition_promotion_routes_through_library_authority_gate() -> None:
    from nolane.external_core.capability_acquisition import CapabilityAcquisitionGovernor

    library = CognitiveLibrary()
    governor = CapabilityAcquisitionGovernor(library)
    abstraction = _abstraction()
    candidate = CapabilityCandidate.for_learned_abstraction(abstraction)
    governor.admit(candidate)
    governor.begin_probation(candidate.candidate_id)
    evidence_ids = ("evidence:c5:independent", "evidence:c5:challenge")
    governor.record_probation(
        candidate.candidate_id,
        evidence_ids=evidence_ids,
        independent_passed=True,
        challenge_passed=True,
        reliability=0.95,
    )
    receipt = _promotion_receipt(
        receipt_id="assurance-promotion-c5-governor",
        candidate_id=candidate.candidate_id,
        predecessor_version=library.digest,
        evidence_ids=evidence_ids,
    )
    promoted = governor.promote(
        candidate.candidate_id,
        assurance=_assurance_plane(receipt),
        receipt=receipt,
    )

    assert promoted.assurance_receipt_id == receipt.receipt_id
    descriptor = library.descriptor_for_candidate(candidate.candidate_id)
    assert descriptor.assurance_receipt_id == receipt.receipt_id
    assert descriptor.capability_id == abstraction.abstraction_id
    assert library.vocabulary.get(abstraction.abstraction_id) == abstraction
