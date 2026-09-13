from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.compatibility import CompatibilityAssessment, CompatibilityClass
from cogcoder.organization.integration import ChangeCandidate, ChangeCandidateStatus
from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest


def _seed_architecture(runtime: OrganizationRuntime) -> None:
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="seed integration live-transition fixture",
        evidence_refs=("EV-ARCH",),
        upsert_components=(
            ArchitectureComponent(
                "A",
                "A",
                ComponentKind.MODULE,
                "core-coding",
                "internal",
            ),
        ),
    )


def _assessment(candidate_id: str) -> CompatibilityAssessment:
    return CompatibilityAssessment(
        assessment_id=f"CA-{candidate_id}",
        compatibility=CompatibilityClass.COMPATIBLE,
        integration_safe=True,
        reason="compatible",
        evidence_refs=("EV-COMP",),
        digest=f"digest-{candidate_id}",
    )


def _candidate(
    candidate_id: str = "C-1",
    *,
    status: ChangeCandidateStatus = ChangeCandidateStatus.PROPOSED,
    conflicts: tuple[str, ...] = (),
) -> ChangeCandidate:
    return ChangeCandidate(
        candidate_id=candidate_id,
        producer_agent_id="coding.backend.01",
        task_refs=("T-1",),
        plan_refs=("P-1",),
        requirement_refs=("REQ-1",),
        architecture_version_expected=1,
        changed_component_refs=("A",),
        changed_interface_refs=(),
        dependency_candidate_ids=(),
        conflicts_with=conflicts,
        compatibility_assessments=(_assessment(candidate_id),),
        verification_evidence_refs=("EV-VERIFY",),
        status=status,
    )


def _runtime_with_proposed_candidate() -> OrganizationRuntime:
    runtime = OrganizationRuntime.first_generation()
    _seed_architecture(runtime)
    runtime.integration.add_candidate(
        actor_agent_id="integration.chief",
        candidate=_candidate(),
    )
    return runtime


def _integrated_runtime_state() -> dict[str, object]:
    runtime = _runtime_with_proposed_candidate()
    runtime.integration.integrate(
        "C-1",
        actor_agent_id="integration.chief",
        evidence_refs=("EV-INTEGRATE",),
    )
    return runtime.to_state()


def _candidate_row(state: dict[str, object]) -> dict[str, object]:
    integration = state["integration"]
    assert isinstance(integration, dict)
    graph = integration["graph"]
    assert isinstance(graph, dict)
    candidates = graph["candidates"]
    assert isinstance(candidates, list)
    row = candidates[0]
    assert isinstance(row, dict)
    return row


def _receipt_rows(state: dict[str, object]) -> list[dict[str, object]]:
    integration = state["integration"]
    assert isinstance(integration, dict)
    receipts = integration["receipts"]
    assert isinstance(receipts, list)
    return receipts


def _receipt_digest(receipt_index: int, receipt: dict[str, object]) -> str:
    return canonical_digest(
        {
            "receipt_index": receipt_index,
            "candidate_id": receipt["candidate_id"],
            "actor_agent_id": receipt["actor_agent_id"],
            "status": receipt["status"],
            "evidence_refs": receipt["evidence_refs"],
            "architecture_version": receipt["architecture_version"],
        }
    )


@pytest.mark.parametrize(
    "status",
    (
        ChangeCandidateStatus.READY,
        ChangeCandidateStatus.BLOCKED,
        ChangeCandidateStatus.INTEGRATED,
        ChangeCandidateStatus.REJECTED,
        ChangeCandidateStatus.SUPERSEDED,
    ),
)
def test_add_candidate_rejects_non_proposed_status_atomically(
    status: ChangeCandidateStatus,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    _seed_architecture(runtime)
    before = deepcopy(runtime.integration.to_state())

    with pytest.raises(ValueError, match="proposed"):
        runtime.integration.add_candidate(
            actor_agent_id="integration.chief",
            candidate=_candidate(status=status),
        )

    assert runtime.integration.to_state() == before


def test_replace_preserves_supported_proposed_to_proposed_flow() -> None:
    runtime = _runtime_with_proposed_candidate()

    replacement = _candidate(conflicts=("C-2",))
    result = runtime.integration.add_candidate(
        actor_agent_id="integration.chief",
        candidate=replacement,
        replace=True,
    )

    assert result.status is ChangeCandidateStatus.PROPOSED
    assert result.conflicts_with == ("C-2",)


def test_replace_rejects_integrated_candidate_atomically() -> None:
    runtime = _runtime_with_proposed_candidate()
    runtime.integration.integrate(
        "C-1",
        actor_agent_id="integration.chief",
        evidence_refs=("EV-INTEGRATE",),
    )
    before = deepcopy(runtime.integration.to_state())

    with pytest.raises(ValueError, match="integrated|replace|transition"):
        runtime.integration.add_candidate(
            actor_agent_id="integration.chief",
            candidate=_candidate(),
            replace=True,
        )

    assert runtime.integration.to_state() == before


@pytest.mark.parametrize(
    "status",
    (
        ChangeCandidateStatus.BLOCKED,
        ChangeCandidateStatus.REJECTED,
        ChangeCandidateStatus.SUPERSEDED,
    ),
)
def test_integrate_rejects_non_integratable_restored_status_atomically(
    status: ChangeCandidateStatus,
) -> None:
    state = _runtime_with_proposed_candidate().to_state()
    _candidate_row(state)["status"] = status.value
    runtime = OrganizationRuntime.from_state(deepcopy(state))
    before = deepcopy(runtime.integration.to_state())

    with pytest.raises(ValueError, match="status|transition"):
        runtime.integration.integrate(
            "C-1",
            actor_agent_id="integration.chief",
            evidence_refs=("EV-INTEGRATE",),
        )

    assert runtime.integration.to_state() == before


def test_integrate_accepts_ready_restored_candidate() -> None:
    state = _runtime_with_proposed_candidate().to_state()
    _candidate_row(state)["status"] = ChangeCandidateStatus.READY.value
    runtime = OrganizationRuntime.from_state(deepcopy(state))

    receipt = runtime.integration.integrate(
        "C-1",
        actor_agent_id="integration.chief",
        evidence_refs=("EV-INTEGRATE",),
    )

    assert receipt.status is ChangeCandidateStatus.INTEGRATED
    assert runtime.integration.graph.get("C-1").status is ChangeCandidateStatus.INTEGRATED


def test_repeat_integration_is_rejected_atomically() -> None:
    runtime = _runtime_with_proposed_candidate()
    runtime.integration.integrate(
        "C-1",
        actor_agent_id="integration.chief",
        evidence_refs=("EV-INTEGRATE",),
    )
    before = deepcopy(runtime.integration.to_state())

    with pytest.raises(ValueError, match="integrated|status|transition"):
        runtime.integration.integrate(
            "C-1",
            actor_agent_id="integration.chief",
            evidence_refs=("EV-INTEGRATE-AGAIN",),
        )

    assert runtime.integration.to_state() == before


def test_restore_accepts_one_receipt_for_one_integrated_candidate() -> None:
    state = _integrated_runtime_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.integration.to_state() == state["integration"]


def test_restore_rejects_integrated_candidate_without_receipt() -> None:
    state = _integrated_runtime_state()
    integration = state["integration"]
    assert isinstance(integration, dict)
    integration["receipt_counter"] = 0
    integration["receipts"] = []

    with pytest.raises(ValueError, match="receipt|integrated"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_receipt_for_non_integrated_candidate() -> None:
    state = _integrated_runtime_state()
    _candidate_row(state)["status"] = ChangeCandidateStatus.PROPOSED.value

    with pytest.raises(ValueError, match="receipt|integrated"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_multiple_receipts_for_same_candidate() -> None:
    state = _integrated_runtime_state()
    integration = state["integration"]
    assert isinstance(integration, dict)
    receipts = _receipt_rows(state)
    duplicate = deepcopy(receipts[0])
    duplicate["receipt_id"] = "integration-00000002"
    duplicate["digest"] = _receipt_digest(2, duplicate)
    receipts.append(duplicate)
    integration["receipt_counter"] = 2

    with pytest.raises(ValueError, match="receipt|candidate"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_receipt_candidate_architecture_version_mismatch() -> None:
    state = _integrated_runtime_state()
    _candidate_row(state)["architecture_version_expected"] = 0

    with pytest.raises(ValueError, match="architecture version"):
        OrganizationRuntime.from_state(state)
