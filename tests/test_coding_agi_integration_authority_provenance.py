from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.compatibility import CompatibilityAssessment, CompatibilityClass
from cogcoder.organization.integration import ChangeCandidate
from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest


def _runtime_with_integrated_candidate(
    *, actor_agent_id: str = "integration.chief"
) -> OrganizationRuntime:
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="seed R2.16 authority provenance fixture",
        evidence_refs=("EV-ARCH",),
        upsert_components=(
            ArchitectureComponent("A", "A", ComponentKind.MODULE, "core-coding", "internal"),
        ),
    )
    runtime.integration.add_candidate(
        actor_agent_id="integration.chief",
        candidate=ChangeCandidate(
            candidate_id="C-1",
            producer_agent_id="coding.backend.01",
            task_refs=("T-1",),
            plan_refs=("P-1",),
            requirement_refs=("REQ-1",),
            architecture_version_expected=1,
            changed_component_refs=("A",),
            changed_interface_refs=(),
            compatibility_assessments=(
                CompatibilityAssessment(
                    assessment_id="CA-C-1",
                    compatibility=CompatibilityClass.COMPATIBLE,
                    integration_safe=True,
                    reason="compatible",
                    evidence_refs=("EV-COMP",),
                    digest="digest-C-1",
                ),
            ),
            verification_evidence_refs=("EV-VERIFY",),
        ),
    )
    runtime.integration.integrate(
        "C-1",
        actor_agent_id=actor_agent_id,
        evidence_refs=("EV-INTEGRATE",),
    )
    return runtime


def _integration_state(
    *, actor_agent_id: str = "integration.chief"
) -> dict[str, object]:
    return deepcopy(
        _runtime_with_integrated_candidate(actor_agent_id=actor_agent_id).to_state()
    )


def _provenance_row(state: dict[str, object]) -> dict[str, object]:
    integration = state["integration"]
    assert isinstance(integration, dict)
    rows = integration["authority_provenance"]
    assert isinstance(rows, list) and len(rows) == 1
    row = rows[0]
    assert isinstance(row, dict)
    return row


def _receipt_row(state: dict[str, object]) -> dict[str, object]:
    integration = state["integration"]
    assert isinstance(integration, dict)
    rows = integration["receipts"]
    assert isinstance(rows, list) and len(rows) == 1
    row = rows[0]
    assert isinstance(row, dict)
    return row


def _rehash_provenance(row: dict[str, object]) -> None:
    row["digest"] = canonical_digest(
        {
            "receipt_id": row["receipt_id"],
            "artifact_id": row["artifact_id"],
            "actor_agent_id": row["actor_agent_id"],
            "authorization_mode": row["authorization_mode"],
            "owner_agent_id": row["owner_agent_id"],
            "active_block_ids": row["active_block_ids"],
        }
    )


def _rehash_receipt(row: dict[str, object]) -> None:
    row["digest"] = canonical_digest(
        {
            "receipt_index": int(str(row["receipt_id"]).removeprefix("integration-")),
            "candidate_id": row["candidate_id"],
            "actor_agent_id": row["actor_agent_id"],
            "status": row["status"],
            "evidence_refs": row["evidence_refs"],
            "architecture_version": row["architecture_version"],
        }
    )


def test_live_integration_state_persists_exact_actor_authority_provenance() -> None:
    runtime = _runtime_with_integrated_candidate()
    state = runtime.integration.to_state()
    rows = state["authority_provenance"]
    assert isinstance(rows, list) and len(rows) == 1

    expected = {
        "receipt_id": "integration-00000001",
        "artifact_id": "integration-state",
        "actor_agent_id": "integration.chief",
        "authorization_mode": "owner",
        "owner_agent_id": "integration.chief",
        "active_block_ids": [],
    }
    assert rows[0] == {**expected, "digest": canonical_digest(expected)}


def test_live_central_integration_records_central_authority_mode() -> None:
    state = _integration_state(actor_agent_id="nolane.central")
    row = _provenance_row(state)

    assert row["actor_agent_id"] == "nolane.central"
    assert row["authorization_mode"] == "central"
    assert row["owner_agent_id"] == "integration.chief"
    assert row["active_block_ids"] == []


def test_authority_provenance_round_trips_with_integrated_receipt() -> None:
    state = _integration_state()

    restored = OrganizationRuntime.from_state(deepcopy(state))

    assert restored.integration.to_state() == state["integration"]


def test_restore_rejects_legacy_receipt_without_authority_provenance() -> None:
    state = _integration_state()
    integration = state["integration"]
    assert isinstance(integration, dict)
    integration.pop("authority_provenance", None)

    with pytest.raises(ValueError, match="authority provenance|required|canonical"):
        OrganizationRuntime.from_state(deepcopy(state))


def test_restore_allows_legacy_empty_integration_state_without_provenance() -> None:
    state = OrganizationRuntime.first_generation().to_state()
    integration = state["integration"]
    assert isinstance(integration, dict)
    integration.pop("authority_provenance", None)

    restored = OrganizationRuntime.from_state(deepcopy(state))

    assert restored.integration.receipts() == ()


def test_restore_rejects_missing_provenance_row_for_existing_receipt() -> None:
    state = _integration_state()
    integration = state["integration"]
    assert isinstance(integration, dict)
    integration["authority_provenance"] = []

    with pytest.raises(ValueError, match="authority provenance.*receipt|receipt.*provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_duplicate_authority_provenance_receipt_id() -> None:
    state = _integration_state()
    integration = state["integration"]
    assert isinstance(integration, dict)
    rows = integration["authority_provenance"]
    assert isinstance(rows, list)
    rows.append(deepcopy(rows[0]))

    with pytest.raises(ValueError, match="duplicate.*authority provenance|provenance.*duplicate"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_authority_provenance_digest_mismatch() -> None:
    state = _integration_state()
    _provenance_row(state)["digest"] = "forged"

    with pytest.raises(ValueError, match="authority provenance digest"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_rehashed_provenance_actor_mismatch() -> None:
    state = _integration_state()
    row = _provenance_row(state)
    row["actor_agent_id"] = "coding.backend.01"
    row["owner_agent_id"] = "coding.backend.01"
    _rehash_provenance(row)

    with pytest.raises(ValueError, match="authority provenance actor"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_rehashed_owner_mode_without_actor_ownership() -> None:
    state = _integration_state()
    row = _provenance_row(state)
    row["owner_agent_id"] = "planning.chief"
    _rehash_provenance(row)

    with pytest.raises(ValueError, match="authority provenance owner"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_rehashed_central_mode_for_noncentral_actor() -> None:
    state = _integration_state()
    row = _provenance_row(state)
    row["authorization_mode"] = "central"
    _rehash_provenance(row)

    with pytest.raises(ValueError, match="authority provenance central|central.*actor"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_rehashed_provenance_with_active_block() -> None:
    state = _integration_state()
    row = _provenance_row(state)
    row["active_block_ids"] = ["block-forged"]
    _rehash_provenance(row)

    with pytest.raises(ValueError, match="authority provenance.*block"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_coordinated_receipt_and_provenance_actor_forgery() -> None:
    state = _integration_state()
    receipt = _receipt_row(state)
    provenance = _provenance_row(state)
    receipt["actor_agent_id"] = "coding.backend.01"
    _rehash_receipt(receipt)
    provenance["actor_agent_id"] = "coding.backend.01"
    provenance["owner_agent_id"] = "coding.backend.01"
    _rehash_provenance(provenance)

    with pytest.raises(ValueError, match="authority provenance.*owner|canonical.*owner"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_restored_authority_owner_drift() -> None:
    state = _integration_state()
    authority = state["authority"]
    assert isinstance(authority, dict)
    owners = authority["owners"]
    assert isinstance(owners, dict)
    owners["integration-state"] = "coding.backend.01"

    with pytest.raises(ValueError, match="authority provenance.*owner|current.*owner"):
        OrganizationRuntime.from_state(state)
