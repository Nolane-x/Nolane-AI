from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def test_public_control_owns_first_class_property_protocol_on_same_evidence_ledger() -> None:
    plane = SoftwareEngineeringControlPlane(claims=CodeClaimLedger())

    assert plane.property_evidence.evidence is plane.evidence
    assert plane.property_gate.property_evidence is plane.property_evidence
    assert plane.property_candidate_authority == "candidate_only"

    state = plane.to_state()
    assert state["component_version"] == "0.9.0"
    assert state["property_evidence"] == plane.property_evidence.to_state()
    assert state["property_gate"] == plane.property_gate.to_state()

    restored = SoftwareEngineeringControlPlane.from_state(
        claims=CodeClaimLedger(),
        state=state,
    )
    assert restored.digest == plane.digest
    assert restored.property_evidence.evidence is restored.evidence
    assert restored.property_gate.property_evidence is restored.property_evidence


def test_public_control_can_lift_exact_v08_snapshot_without_rewriting_legacy_state() -> None:
    from nolane.external_core._software_engineering_control_v08 import (
        SoftwareEngineeringControlPlane as SoftwareEngineeringControlPlaneV08,
    )

    claims = CodeClaimLedger()
    legacy = SoftwareEngineeringControlPlaneV08(claims=claims)
    legacy_state = legacy.to_state()
    assert legacy_state["component_version"] == "0.8.0"

    restored_legacy = SoftwareEngineeringControlPlaneV08.from_state(
        claims=CodeClaimLedger(),
        state=legacy_state,
    )
    assert restored_legacy.to_state() == legacy_state

    lifted = SoftwareEngineeringControlPlane.from_state(
        claims=CodeClaimLedger(),
        state=legacy_state,
    )
    lifted_state = lifted.to_state()
    assert lifted_state["component_version"] == "0.9.0"
    assert lifted_state["property_evidence"]["obligations"] == []
    assert lifted_state["property_evidence"]["witnesses"] == []
    assert lifted_state["property_gate"]["manifests"] == []
    assert legacy_state["digest"] != lifted_state["digest"]


def test_property_substate_tampering_is_covered_by_unified_control_digest() -> None:
    plane = SoftwareEngineeringControlPlane(claims=CodeClaimLedger())
    state = deepcopy(plane.to_state())
    state["property_gate"]["version"] = "forged-version"

    with pytest.raises(ValueError, match="digest|property|snapshot"):
        SoftwareEngineeringControlPlane.from_state(
            claims=CodeClaimLedger(),
            state=state,
        )
