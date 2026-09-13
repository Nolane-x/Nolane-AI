from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.compatibility import CompatibilityAssessment, CompatibilityClass
from cogcoder.organization.integration import ChangeCandidate
from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest


def _runtime_with_integrated_candidate() -> OrganizationRuntime:
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
        actor_agent_id="integration.chief",
        evidence_refs=("EV-INTEGRATE",),
    )
    return runtime


def test_live_integration_receipt_persists_exact_actor_authority_provenance() -> None:
    runtime = _runtime_with_integrated_candidate()
    state = runtime.integration.to_state()
    receipt = state["receipts"][0]

    provenance = receipt["authority_provenance"]
    expected = {
        "artifact_id": "integration-state",
        "actor_agent_id": "integration.chief",
        "authorization_mode": "owner",
        "owner_agent_id": "integration.chief",
        "active_block_ids": [],
    }
    assert provenance == {**expected, "digest": canonical_digest(expected)}


def test_restore_rejects_legacy_receipt_without_authority_provenance() -> None:
    state = _runtime_with_integrated_candidate().to_state()

    with pytest.raises(ValueError, match="authority provenance|required"):
        OrganizationRuntime.from_state(deepcopy(state))
