from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering_control import SoftwareEngineeringControlPlane


def test_public_control_owns_current_property_truth_maintenance_as_canonical_substate() -> None:
    plane = SoftwareEngineeringControlPlane(claims=CodeClaimLedger())

    assert plane.current_property_validity.validity is plane.validity
    assert plane.current_property_validity.property_gate is plane.property_gate
    assert plane.current_property_candidate_authority == "candidate_only"

    state = plane.to_state()
    assert state["component_version"] == "1.1.0"
    assert state["current_property_validity"] == plane.current_property_validity.to_state()

    restored = SoftwareEngineeringControlPlane.from_state(
        claims=CodeClaimLedger(),
        state=state,
    )
    assert restored.to_state() == state
    assert restored.digest == plane.digest
    assert restored.current_property_validity.validity is restored.validity
    assert restored.current_property_validity.property_gate is restored.property_gate


def test_public_control_lifts_v09_snapshot_without_rewriting_legacy_property_receipts() -> None:
    from nolane.external_core._software_engineering_control_v09 import (
        SoftwareEngineeringControlPlane as SoftwareEngineeringControlPlaneV09,
    )

    legacy = SoftwareEngineeringControlPlaneV09(claims=CodeClaimLedger())
    legacy_state = legacy.to_state()
    assert legacy_state["component_version"] == "0.9.0"

    lifted = SoftwareEngineeringControlPlane.from_state(
        claims=CodeClaimLedger(),
        state=legacy_state,
    )
    lifted_state = lifted.to_state()

    assert lifted_state["component_version"] == "1.1.0"
    assert lifted.property_evidence.to_state() == legacy.property_evidence.to_state()
    assert lifted.property_gate.to_state() == legacy.property_gate.to_state()
    assert lifted_state["current_property_validity"]["receipts"] == []
    assert lifted_state["digest"] != legacy_state["digest"]


def test_current_property_substate_tampering_is_rejected_even_with_recomputed_outer_digest() -> None:
    plane = SoftwareEngineeringControlPlane(claims=CodeClaimLedger())
    state = deepcopy(plane.to_state())
    state["current_property_validity"]["component_version"] = "forged-version"
    payload = {key: value for key, value in state.items() if key != "digest"}
    state["digest"] = canonical_digest(payload)

    with pytest.raises(ValueError, match="current property validity|component version"):
        SoftwareEngineeringControlPlane.from_state(
            claims=CodeClaimLedger(),
            state=state,
        )
