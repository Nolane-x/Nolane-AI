from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.compatibility import CompatibilityAssessment, CompatibilityClass
from cogcoder.organization.integration import ChangeCandidate
from cogcoder.organization.runtime import OrganizationRuntime


def _seed_architecture(runtime: OrganizationRuntime) -> None:
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="seed exact live Integration authority fixture",
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


def _candidate(candidate_id: str = "7") -> ChangeCandidate:
    return ChangeCandidate(
        candidate_id=candidate_id,
        producer_agent_id="coding.backend.01",
        task_refs=("T-1",),
        plan_refs=("P-1",),
        requirement_refs=("REQ-1",),
        architecture_version_expected=1,
        changed_component_refs=("A",),
        changed_interface_refs=(),
        compatibility_assessments=(
            CompatibilityAssessment(
                assessment_id=f"CA-{candidate_id}",
                compatibility=CompatibilityClass.COMPATIBLE,
                integration_safe=True,
                reason="compatible",
                evidence_refs=("EV-COMP",),
                digest=f"digest-{candidate_id}",
            ),
        ),
        verification_evidence_refs=("EV-VERIFY",),
    )


def _runtime_with_candidate(candidate_id: str = "7") -> OrganizationRuntime:
    runtime = OrganizationRuntime.first_generation()
    _seed_architecture(runtime)
    runtime.integration.add_candidate(
        actor_agent_id="integration.chief",
        candidate=_candidate(candidate_id),
    )
    return runtime


def test_graph_get_rejects_non_string_candidate_alias() -> None:
    runtime = _runtime_with_candidate("7")

    with pytest.raises(ValueError, match="candidate.*exact string|string"):
        runtime.integration.graph.get(7)  # type: ignore[arg-type]


def test_integrate_rejects_non_string_candidate_alias_atomically() -> None:
    runtime = _runtime_with_candidate("7")
    before = deepcopy(runtime.integration.to_state())

    with pytest.raises(ValueError, match="candidate.*exact string|string"):
        runtime.integration.integrate(
            7,  # type: ignore[arg-type]
            actor_agent_id="integration.chief",
            evidence_refs=("EV-INTEGRATE",),
        )

    assert runtime.integration.to_state() == before


@pytest.mark.parametrize("bad_evidence", (7, True, 1.5))
def test_integrate_rejects_non_string_evidence_atomically(bad_evidence: object) -> None:
    runtime = _runtime_with_candidate()
    before = deepcopy(runtime.integration.to_state())

    with pytest.raises(ValueError, match="evidence.*exact string|string"):
        runtime.integration.integrate(
            "7",
            actor_agent_id="integration.chief",
            evidence_refs=(bad_evidence,),  # type: ignore[arg-type]
        )

    assert runtime.integration.to_state() == before


def test_integrate_rejects_scalar_string_evidence_collection_atomically() -> None:
    runtime = _runtime_with_candidate()
    before = deepcopy(runtime.integration.to_state())

    with pytest.raises(ValueError, match="evidence.*tuple|canonical|collection"):
        runtime.integration.integrate(
            "7",
            actor_agent_id="integration.chief",
            evidence_refs="EV-INTEGRATE",  # type: ignore[arg-type]
        )

    assert runtime.integration.to_state() == before


def test_integrate_preserves_exact_valid_evidence_without_normalization() -> None:
    runtime = _runtime_with_candidate()

    receipt = runtime.integration.integrate(
        "7",
        actor_agent_id="integration.chief",
        evidence_refs=(" EV-INTEGRATE ",),
    )

    assert receipt.candidate_id == "7"
    assert receipt.evidence_refs == (" EV-INTEGRATE ",)
