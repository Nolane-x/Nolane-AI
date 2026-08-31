from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering import EngineeringEvidenceKind
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane
from nolane.external_core.software_engineering_property_evidence import (
    EngineeringClaimClass,
    EngineeringProofMethod,
    EngineeringWitnessRole,
)
from nolane.external_core.software_engineering_property_gate import (
    EngineeringPropertyRequirement,
    SoftwareEngineeringPropertyGate,
)


PATCH_REF = "patch-property-restore-0001"
PATCH_DIGEST = "sha256:patch-property-restore-0001"
SOURCE_REVISION = "git:property-restore-v1"


@dataclass(frozen=True)
class _FabricatedBaseClosure:
    receipt_id: str = "eng-closure-fabricated"
    digest: str = "sha256:fabricated-closure"
    patch_ref: str = PATCH_REF
    patch_digest: str = PATCH_DIGEST
    source_revision: str = SOURCE_REVISION
    ready: bool = True
    authority: str = "candidate_only"


def _requirement(claim_class: EngineeringClaimClass, property_ref: str) -> EngineeringPropertyRequirement:
    return EngineeringPropertyRequirement(
        claim_id=f"claim:{claim_class.value}:{property_ref}",
        claim_class=claim_class,
        property_ref=property_ref,
    )


def _ready_property(
    plane: SoftwareEngineeringControlPlane,
    requirement: EngineeringPropertyRequirement,
    *,
    suffix: str,
):
    obligation = plane.property_evidence.register_obligation(
        claim_id=requirement.claim_id,
        claim_class=requirement.claim_class,
        property_ref=requirement.property_ref,
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
    )
    oracle_ref = f"oracle:{requirement.property_ref}"
    attestation = plane.evidence.record(
        subject_ref=PATCH_REF,
        subject_digest=PATCH_DIGEST,
        producer_agent_id="coding.backend.01",
        verifier_agent_id=f"verification.testing.{suffix}",
        verifier_region="verification-testing",
        kind=EngineeringEvidenceKind.TEST,
        passed=True,
        evidence_refs=(f"run:{suffix}", oracle_ref),
        source_revision=SOURCE_REVISION,
        environment_digest=f"env:{suffix}",
    )
    witness = plane.property_evidence.record_witness(
        obligation_id=obligation.obligation_id,
        attestation_id=attestation.attestation_id,
        method=EngineeringProofMethod.PROPERTY_TEST,
        role=EngineeringWitnessRole.DIRECT,
        measured_property_ref=requirement.property_ref,
        oracle_ref=oracle_ref,
        source_family=f"independent:{suffix}",
    )
    closure = plane.property_evidence.assess(
        obligation.obligation_id,
        witness_ids=(witness.witness_id,),
    )
    assert closure.ready is True
    return obligation, closure


def _ready_gate(
    plane: SoftwareEngineeringControlPlane,
    requirements: tuple[EngineeringPropertyRequirement, ...],
):
    manifest = plane.property_gate.register_manifest(
        patch_ref=PATCH_REF,
        patch_digest=PATCH_DIGEST,
        source_revision=SOURCE_REVISION,
        source_authority_ref="goal-design:engineering-contract",
        requirements=requirements,
    )
    bindings = []
    for index, requirement in enumerate(requirements):
        obligation, closure = _ready_property(
            plane,
            requirement,
            suffix=f"property-{index}",
        )
        bindings.append((obligation.obligation_id, closure.receipt_id))
    receipt = plane.property_gate.assess(
        manifest.manifest_id,
        property_bindings=tuple(bindings),
    )
    assert receipt.ready is True
    return manifest, receipt


def _redigest_gate_receipt(row: dict) -> None:
    payload = {
        key: value
        for key, value in row.items()
        if key not in {"receipt_id", "digest"}
    }
    digest = canonical_digest(payload)
    row["digest"] = digest
    row["receipt_id"] = f"eng-property-gate-{digest[:20]}"


def test_restore_rejects_recomputed_ready_gate_with_missing_required_binding() -> None:
    plane = SoftwareEngineeringControlPlane(claims=CodeClaimLedger())
    functional = _requirement(
        EngineeringClaimClass.FUNCTIONAL_BEHAVIOR,
        "behavior:refresh-preserves-session",
    )
    second = _requirement(
        EngineeringClaimClass.FUNCTIONAL_BEHAVIOR,
        "behavior:refresh-preserves-csrf-state",
    )
    _, gate_receipt = _ready_gate(plane, (functional, second))
    assert len(gate_receipt.bindings) == 2

    state = deepcopy(plane.property_gate.to_state())
    forged = state["gate_receipts"][0]
    forged["bindings"] = forged["bindings"][:1]
    forged["ready"] = True
    forged["reasons"] = []
    _redigest_gate_receipt(forged)

    with pytest.raises(ValueError, match="complete|required|coverage|binding|manifest"):
        SoftwareEngineeringPropertyGate.from_state(
            property_evidence=plane.property_evidence,
            state=state,
        )


def test_public_control_rejects_fabricated_legacy_base_closure() -> None:
    plane = SoftwareEngineeringControlPlane(claims=CodeClaimLedger())
    requirement = _requirement(
        EngineeringClaimClass.FUNCTIONAL_BEHAVIOR,
        "behavior:refresh-preserves-session",
    )
    _, property_gate = _ready_gate(plane, (requirement,))

    with pytest.raises((KeyError, PermissionError, ValueError), match="canonical|closure|legacy"):
        plane.bind_property_terminal_closure(
            base_closure=_FabricatedBaseClosure(),
            property_gate_receipt_id=property_gate.receipt_id,
        )


def test_unified_restore_rejects_terminal_closure_without_canonical_base_lineage() -> None:
    plane = SoftwareEngineeringControlPlane(claims=CodeClaimLedger())
    requirement = _requirement(
        EngineeringClaimClass.FUNCTIONAL_BEHAVIOR,
        "behavior:refresh-preserves-session",
    )
    _, property_gate = _ready_gate(plane, (requirement,))

    fabricated = plane.property_gate.bind_terminal_closure(
        base_closure=_FabricatedBaseClosure(),
        property_gate_receipt_id=property_gate.receipt_id,
    )
    assert fabricated.ready is True
    state = plane.to_state()

    with pytest.raises(ValueError, match="canonical|base.*closure|terminal.*closure|lineage"):
        SoftwareEngineeringControlPlane.from_state(
            claims=CodeClaimLedger(),
            state=state,
        )
