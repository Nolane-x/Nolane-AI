from __future__ import annotations

# Permanent Neural R2.7 restore-authority regression gate.

from copy import deepcopy
from typing import Any

import pytest

from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.compatibility import CompatibilityAssessment, CompatibilityClass
from cogcoder.organization.integration import ChangeCandidate
from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest


def _candidate(candidate_id: str, *, expected_version: int = 1) -> ChangeCandidate:
    assessment = CompatibilityAssessment(
        assessment_id=f"CA-{candidate_id}",
        compatibility=CompatibilityClass.COMPATIBLE,
        integration_safe=True,
        reason="integration restore authority fixture",
        evidence_refs=(f"EV-COMP-{candidate_id}",),
        digest=f"digest-{candidate_id}",
    )
    return ChangeCandidate(
        candidate_id=candidate_id,
        producer_agent_id="coding.backend.01",
        task_refs=(f"T-{candidate_id}",),
        plan_refs=("P-1",),
        requirement_refs=("REQ-1",),
        architecture_version_expected=expected_version,
        changed_component_refs=("ARCH-A",),
        changed_interface_refs=(),
        compatibility_assessments=(assessment,),
        verification_evidence_refs=(f"EV-VERIFY-{candidate_id}",),
    )


def _runtime_state_with_receipts(count: int = 1) -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="establish integration component",
        evidence_refs=("EV-ARCH",),
        upsert_components=(
            ArchitectureComponent(
                "ARCH-A",
                "Architecture A",
                ComponentKind.MODULE,
                "core-coding",
                "internal",
            ),
        ),
    )
    for index in range(1, count + 1):
        candidate_id = f"CAND-{index}"
        runtime.integration.add_candidate(
            actor_agent_id="integration.chief",
            candidate=_candidate(candidate_id),
        )
        runtime.integration.integrate(
            candidate_id,
            actor_agent_id="integration.chief",
            evidence_refs=(f"EV-INTEGRATE-{index}",),
        )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.integration.to_state() == state["integration"]
    return state


def _recompute_receipt_digest(receipt: dict[str, Any], *, receipt_index: int) -> None:
    receipt["digest"] = canonical_digest(
        {
            "receipt_index": receipt_index,
            "candidate_id": receipt["candidate_id"],
            "actor_agent_id": receipt["actor_agent_id"],
            "status": receipt["status"],
            "evidence_refs": list(receipt.get("evidence_refs", ())),
            "architecture_version": receipt["architecture_version"],
        }
    )


@pytest.mark.parametrize("value", (True, "1", 1.0))
def test_restore_rejects_coercible_candidate_architecture_version(value: object) -> None:
    state = _runtime_state_with_receipts()
    state["integration"]["graph"]["candidates"][0]["architecture_version_expected"] = value

    with pytest.raises(ValueError, match="integration candidate architecture version"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("value", (True, "1", 1.0))
def test_restore_rejects_coercible_receipt_architecture_version(value: object) -> None:
    state = _runtime_state_with_receipts()
    state["integration"]["receipts"][0]["architecture_version"] = value

    with pytest.raises(ValueError, match="integration receipt architecture version"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("value", (True, "2", 2.0))
def test_restore_rejects_coercible_integration_graph_version(value: object) -> None:
    state = _runtime_state_with_receipts()
    state["integration"]["graph"]["version"] = value

    with pytest.raises(ValueError, match="integration graph version"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("value", (True, "1", 1.0))
def test_restore_rejects_coercible_integration_receipt_counter(value: object) -> None:
    state = _runtime_state_with_receipts()
    state["integration"]["receipt_counter"] = value

    with pytest.raises(ValueError, match="integration receipt counter"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_integration_receipt_digest_mismatch() -> None:
    state = _runtime_state_with_receipts()
    state["integration"]["receipts"][0]["digest"] = "forged-digest"

    with pytest.raises(ValueError, match="integration receipt digest"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_nonintegrated_receipt_with_valid_digest() -> None:
    state = _runtime_state_with_receipts()
    receipt = state["integration"]["receipts"][0]
    receipt["status"] = "proposed"
    _recompute_receipt_digest(receipt, receipt_index=1)

    with pytest.raises(ValueError, match="integration receipt status"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_receipt_without_evidence_with_valid_digest() -> None:
    state = _runtime_state_with_receipts()
    receipt = state["integration"]["receipts"][0]
    receipt["evidence_refs"] = []
    _recompute_receipt_digest(receipt, receipt_index=1)

    with pytest.raises(ValueError, match="integration receipt evidence"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_receipt_for_unknown_candidate_with_valid_digest() -> None:
    state = _runtime_state_with_receipts()
    receipt = state["integration"]["receipts"][0]
    receipt["candidate_id"] = "CAND-MISSING"
    _recompute_receipt_digest(receipt, receipt_index=1)

    with pytest.raises(ValueError, match="integration receipt candidate"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_receipt_from_unknown_actor_with_valid_digest() -> None:
    state = _runtime_state_with_receipts()
    receipt = state["integration"]["receipts"][0]
    receipt["actor_agent_id"] = "integration.unknown"
    _recompute_receipt_digest(receipt, receipt_index=1)

    with pytest.raises((KeyError, ValueError), match="integration.unknown|integration receipt actor"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_future_receipt_architecture_version_with_valid_digest() -> None:
    state = _runtime_state_with_receipts()
    receipt = state["integration"]["receipts"][0]
    receipt["architecture_version"] = 2
    _recompute_receipt_digest(receipt, receipt_index=1)

    with pytest.raises(ValueError, match="integration receipt architecture version"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_inflated_integration_receipt_counter() -> None:
    state = _runtime_state_with_receipts()
    state["integration"]["receipt_counter"] = 2

    with pytest.raises(ValueError, match="integration receipt counter"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_noncanonical_integration_receipt_id_with_valid_digest() -> None:
    state = _runtime_state_with_receipts()
    receipt = state["integration"]["receipts"][0]
    receipt["receipt_id"] = "integration-00000002"
    _recompute_receipt_digest(receipt, receipt_index=2)

    with pytest.raises(ValueError, match="integration receipt id sequence"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_duplicate_integration_receipt_ids() -> None:
    state = _runtime_state_with_receipts(2)
    receipts = state["integration"]["receipts"]
    receipts[1]["receipt_id"] = receipts[0]["receipt_id"]

    with pytest.raises(ValueError, match="duplicate integration receipt"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_duplicate_integration_candidate_ids() -> None:
    state = _runtime_state_with_receipts()
    duplicate = deepcopy(state["integration"]["graph"]["candidates"][0])
    state["integration"]["graph"]["candidates"].append(duplicate)

    with pytest.raises(ValueError, match="duplicate integration candidate"):
        OrganizationRuntime.from_state(state)
