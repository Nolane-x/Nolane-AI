from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane, PromotionAssuranceReceipt
from nolane.external_core.capability_acquisition import (
    CapabilityAcquisitionGovernor,
    CapabilityCandidate,
    CapabilityState,
)
from nolane.external_core.cognitive_catalog import OperatorFamilyDescriptor, SubOperatorDescriptor
from nolane.external_core.cognitive_library import CognitiveLibrary
from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.reasoning_invention import (
    CapabilityGap,
    CapabilityKind as ReasoningCapabilityKind,
    EvidencePhase,
    ReasoningEvidenceRef,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _probation():
    return importlib.import_module("nolane.external_core.capability_probation")


def _family() -> OperatorFamilyDescriptor:
    return OperatorFamilyDescriptor(
        "reasoning_probation_candidate",
        "Operator family proposed from a verified Reasoning/Invention gap.",
        (
            SubOperatorDescriptor(
                "reasoning_probation_candidate.probe",
                "experimental",
                "Probe a bounded capability while it remains behind probation authority.",
                frozenset({"reasoning", "probation"}),
            ),
        ),
    )


def _prepared():
    library = CognitiveLibrary()
    governor = CapabilityAcquisitionGovernor(library)
    candidate = CapabilityCandidate.for_operator_family(_family(), display_name="probation candidate")
    governor.admit(candidate)
    probation = governor.begin_probation(candidate.candidate_id)
    assert probation.baseline_digest == library.digest
    gap = CapabilityGap(
        objective="Acquire the missing bounded operator family.",
        capability_kind=ReasoningCapabilityKind.OPERATOR,
        cognitive_library_digest=library.digest,
        insufficiency_evidence=(
            ReasoningEvidenceRef(
                "gap-discovery:e1",
                EvidencePhase.DISCOVERY,
                "external.cognitive_library",
                "research.source",
            ),
        ),
        acceptance_test_ids=("acceptance:a", "acceptance:b"),
        candidate_synthesis_id="candidate-synthesis:c1",
        verified_challenge_id="challenge:verified-c1",
    )
    return library, governor, candidate, gap


def _independent() -> tuple[EvidenceRecord, ...]:
    return (
        EvidenceRecord(
            "independent:e1",
            "verification.independent",
            True,
            0,
            0,
            "independent holdout passed",
        ),
    )


def _bind(native, governor, candidate, gap, **overrides):
    kwargs = {
        "candidate": candidate,
        "gap": gap,
        "holdout_test_ids": ("acceptance:a", "acceptance:b", "holdout:c"),
        "environment_ids": ("env:py3.11", "env:py3.13"),
        "independent_evidence": _independent(),
        "causal_challenge_ids": ("causal-challenge:c1",),
        "experiment_receipt_ids": ("experiment:x1",),
        "independent_passed": True,
        "challenge_passed": True,
        "reliability": 0.95,
    }
    kwargs.update(overrides)
    return native.bind_capability_probation_receipt(governor, **kwargs)


def _promotion_receipt(
    candidate_id: str,
    evidence_ids: tuple[str, ...],
    baseline: str,
) -> PromotionAssuranceReceipt:
    payload = {
        "receipt_id": "assurance-promotion-c4-drift",
        "subject_id": candidate_id,
        "evidence_ids": list(evidence_ids),
        "predecessor_version": baseline,
        "verifier_ids": ["verification.c4.drift"],
        "authorized": True,
        "reasons": [],
    }
    return PromotionAssuranceReceipt(
        receipt_id=str(payload["receipt_id"]),
        subject_id=candidate_id,
        evidence_ids=evidence_ids,
        predecessor_version=baseline,
        verifier_ids=("verification.c4.drift",),
        authorized=True,
        reasons=(),
        digest=canonical_digest(payload),
    )


def _assurance_plane(*receipts: PromotionAssuranceReceipt) -> AssuranceControlPlane:
    plane = object.__new__(AssuranceControlPlane)
    plane._promotion_receipts = {row.receipt_id: row for row in receipts}
    return plane


def test_c4_declares_capability_acquisition_v002_companion_boundary() -> None:
    native = _probation()
    assert native.COMPONENT_ID == "external.capability_acquisition"
    assert native.COMPONENT_VERSION == "0.0.2"
    assert native.SCHEMA_VERSION == "capability-probation-v1"
    for name in (
        "CapabilityProbationReceipt",
        "bind_capability_probation_receipt",
        "apply_capability_probation_receipt",
    ):
        assert hasattr(native, name), name


def test_c4_receipt_binds_exact_gap_candidate_baseline_and_probation_evidence() -> None:
    native = _probation()
    library, governor, candidate, gap = _prepared()
    receipt = _bind(native, governor, candidate, gap)

    assert receipt.candidate_id == candidate.candidate_id
    assert receipt.gap_id == gap.gap_id
    assert receipt.cognitive_library_baseline_digest == library.digest
    assert receipt.candidate_synthesis_id == gap.candidate_synthesis_id
    assert receipt.acceptance_test_ids == gap.acceptance_test_ids
    assert receipt.verified_challenge_id == gap.verified_challenge_id
    assert receipt.promoted is False
    assert set(receipt.probation_evidence_ids) == {
        "gap-discovery:e1",
        "independent:e1",
        "challenge:verified-c1",
        "causal-challenge:c1",
        "experiment:x1",
    }

    state = receipt.to_state()
    restored = native.CapabilityProbationReceipt.from_state(json.loads(json.dumps(state)))
    assert restored == receipt
    assert restored.to_state() == state

    forged = dict(state)
    forged["candidate_id"] = "capability:forged"
    with pytest.raises(ValueError, match="identity"):
        native.CapabilityProbationReceipt.from_state(forged)


def test_c4_requires_exact_library_baseline_kind_mapping_and_acceptance_coverage() -> None:
    native = _probation()
    library, governor, candidate, gap = _prepared()

    drifted_gap = CapabilityGap(
        objective=gap.objective,
        capability_kind=gap.capability_kind,
        cognitive_library_digest="library:other",
        insufficiency_evidence=gap.insufficiency_evidence,
        acceptance_test_ids=gap.acceptance_test_ids,
        candidate_synthesis_id=gap.candidate_synthesis_id,
        verified_challenge_id=gap.verified_challenge_id,
    )
    with pytest.raises(ValueError, match="baseline"):
        _bind(native, governor, candidate, drifted_gap)

    wrong_kind = CapabilityGap(
        objective=gap.objective,
        capability_kind=ReasoningCapabilityKind.ABSTRACTION,
        cognitive_library_digest=library.digest,
        insufficiency_evidence=gap.insufficiency_evidence,
        acceptance_test_ids=gap.acceptance_test_ids,
        candidate_synthesis_id=gap.candidate_synthesis_id,
        verified_challenge_id=gap.verified_challenge_id,
    )
    with pytest.raises(ValueError, match="kind"):
        _bind(native, governor, candidate, wrong_kind)

    with pytest.raises(ValueError, match="acceptance"):
        _bind(native, governor, candidate, gap, holdout_test_ids=("acceptance:a", "holdout:c"))


def test_c4_independent_evidence_is_clean_phase_separated_and_challenge_supported() -> None:
    native = _probation()
    _, governor, candidate, gap = _prepared()

    with pytest.raises(ValueError, match="clean"):
        _bind(
            native,
            governor,
            candidate,
            gap,
            independent_evidence=(EvidenceRecord("independent:dirty", "verification.independent", True, regressions=1),),
        )

    with pytest.raises(ValueError, match="independent verifier"):
        _bind(
            native,
            governor,
            candidate,
            gap,
            independent_evidence=(EvidenceRecord("independent:self", "research.source", True),),
        )

    no_verified_gap = CapabilityGap(
        objective=gap.objective,
        capability_kind=gap.capability_kind,
        cognitive_library_digest=gap.cognitive_library_digest,
        insufficiency_evidence=gap.insufficiency_evidence,
        acceptance_test_ids=gap.acceptance_test_ids,
        candidate_synthesis_id=gap.candidate_synthesis_id,
        verified_challenge_id=None,
    )
    with pytest.raises(ValueError, match="challenge support"):
        _bind(
            native,
            governor,
            candidate,
            no_verified_gap,
            causal_challenge_ids=(),
            experiment_receipt_ids=(),
            challenge_passed=True,
        )


def test_c4_reliability_is_finite_bounded_and_bool_is_not_numeric() -> None:
    native = _probation()
    _, governor, candidate, gap = _prepared()
    for value in (float("nan"), float("inf"), -0.01, 1.01):
        with pytest.raises((TypeError, ValueError)):
            _bind(native, governor, candidate, gap, reliability=value)
    with pytest.raises(TypeError):
        _bind(native, governor, candidate, gap, reliability=True)


def test_c4_apply_stops_at_probation_and_never_mutates_library_on_success() -> None:
    native = _probation()
    library, governor, candidate, gap = _prepared()
    baseline = library.digest
    receipt = _bind(native, governor, candidate, gap)

    updated = native.apply_capability_probation_receipt(governor, receipt)
    assert updated.state is CapabilityState.PROBATION
    assert updated.reliability == 0.95
    assert updated.independent_passed is True
    assert updated.challenge_passed is True
    assert updated.evidence_ids == receipt.probation_evidence_ids
    assert library.digest == baseline
    assert governor.retrievable_ids() == ()
    with pytest.raises(PermissionError):
        governor.retrieve(candidate.candidate_id)


def test_c4_failed_gate_quarantines_without_installing_candidate() -> None:
    native = _probation()
    library, governor, candidate, gap = _prepared()
    baseline = library.digest
    receipt = _bind(
        native,
        governor,
        candidate,
        gap,
        independent_passed=False,
        reliability=0.20,
    )
    updated = native.apply_capability_probation_receipt(governor, receipt)
    assert updated.state is CapabilityState.QUARANTINED
    assert library.digest == baseline
    assert governor.retrievable_ids() == ()


def test_c4_apply_rejects_stale_or_wrong_governor_state() -> None:
    native = _probation()
    library, governor, candidate, gap = _prepared()
    receipt = _bind(native, governor, candidate, gap)

    other = CapabilityAcquisitionGovernor(CognitiveLibrary())
    other_candidate = CapabilityCandidate.for_operator_family(_family())
    other.admit(other_candidate)
    with pytest.raises(ValueError, match="probation"):
        native.apply_capability_probation_receipt(other, receipt)

    drift = OperatorFamilyDescriptor(
        "unrelated_drift",
        "Unrelated mutation after probation binding.",
        (
            SubOperatorDescriptor(
                "unrelated_drift.probe",
                "experimental",
                "Changes the governed baseline to prove stale receipt rejection.",
                frozenset({"drift"}),
            ),
        ),
    )
    drift_governor = CapabilityAcquisitionGovernor(library)
    drift_candidate = CapabilityCandidate.for_operator_family(drift)
    drift_governor.admit(drift_candidate)
    drift_governor.begin_probation(drift_candidate.candidate_id)
    drift_evidence = ("independent:c4-drift", "challenge:c4-drift")
    drift_governor.record_probation(
        drift_candidate.candidate_id,
        evidence_ids=drift_evidence,
        independent_passed=True,
        challenge_passed=True,
        reliability=0.99,
    )
    drift_receipt = _promotion_receipt(drift_candidate.candidate_id, drift_evidence, library.digest)
    drift_governor.promote(
        drift_candidate.candidate_id,
        assurance=_assurance_plane(drift_receipt),
        receipt=drift_receipt,
    )
    with pytest.raises(ValueError, match="baseline"):
        native.apply_capability_probation_receipt(governor, receipt)


def test_c4_companion_has_no_assurance_promotion_or_library_write_authority() -> None:
    path = _root() / "nolane" / "external_core" / "capability_probation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    names: set[str] = set()
    attrs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            attrs.add(node.attr)

    assert "nolane.external_core.assurance" not in imports
    assert "AssuranceControlPlane" not in names
    assert "PromotionAssuranceReceipt" not in names
    assert "promote" not in attrs
    assert "register_family" not in attrs
    assert "register_abstraction" not in attrs
