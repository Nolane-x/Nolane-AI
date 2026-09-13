from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.compatibility import CompatibilityAssessment, CompatibilityClass
from cogcoder.organization.integration import ChangeCandidate
from cogcoder.organization.runtime import OrganizationRuntime


def _seed_architecture(runtime: OrganizationRuntime) -> None:
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="seed integration canonical-state fixture",
        evidence_refs=("EV-ARCH",),
        upsert_components=(
            ArchitectureComponent(
                "204",
                "Canonical component",
                ComponentKind.MODULE,
                "core-coding",
                "internal",
            ),
        ),
    )


def _assessment() -> CompatibilityAssessment:
    return CompatibilityAssessment(
        assessment_id="301",
        compatibility=CompatibilityClass.COMPATIBLE,
        integration_safe=True,
        reason="401",
        evidence_refs=("501",),
        digest="601",
    )


def _candidate(
    candidate_id: str,
    *,
    dependencies: tuple[str, ...] = (),
    conflicts: tuple[str, ...] = ("102",),
) -> ChangeCandidate:
    return ChangeCandidate(
        candidate_id=candidate_id,
        producer_agent_id="coding.backend.01",
        task_refs=("201",),
        plan_refs=("202",),
        requirement_refs=("203",),
        architecture_version_expected=1,
        changed_component_refs=("204",),
        changed_interface_refs=(),
        dependency_candidate_ids=dependencies,
        conflicts_with=conflicts,
        compatibility_assessments=(_assessment(),),
        verification_evidence_refs=("206",),
    )


def _empty_runtime_state() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.integration.to_state() == state["integration"]
    return state


def _proposed_runtime_state() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    _seed_architecture(runtime)
    runtime.integration.add_candidate(
        actor_agent_id="integration.chief",
        candidate=_candidate("101"),
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.integration.to_state() == state["integration"]
    return state


def _two_candidate_runtime_state(*, with_receipts: bool) -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    _seed_architecture(runtime)
    runtime.integration.add_candidate(
        actor_agent_id="integration.chief",
        candidate=_candidate("101", conflicts=()),
    )
    if with_receipts:
        runtime.integration.integrate(
            "101",
            actor_agent_id="integration.chief",
            evidence_refs=("701",),
        )
    runtime.integration.add_candidate(
        actor_agent_id="integration.chief",
        candidate=_candidate("102", dependencies=("101",), conflicts=()),
    )
    if with_receipts:
        runtime.integration.integrate(
            "102",
            actor_agent_id="integration.chief",
            evidence_refs=("702",),
        )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.integration.to_state() == state["integration"]
    return state


def _candidate_row(state: dict[str, Any], candidate_id: str = "101") -> dict[str, Any]:
    return next(
        row
        for row in state["integration"]["graph"]["candidates"]
        if row["candidate_id"] == candidate_id
    )


def _assessment_row(state: dict[str, Any], candidate_id: str = "101") -> dict[str, Any]:
    return _candidate_row(state, candidate_id)["compatibility_assessments"][0]


def test_canonical_integration_runtime_state_round_trips() -> None:
    state = _two_candidate_runtime_state(with_receipts=True)
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.integration.to_state() == state["integration"]


@pytest.mark.parametrize("field", ("graph", "receipt_counter", "receipts"))
def test_restore_rejects_missing_integration_root_fields(field: str) -> None:
    state = _empty_runtime_state()
    del state["integration"][field]

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_extra_integration_root_field() -> None:
    state = _empty_runtime_state()
    state["integration"]["unexpected"] = "value"

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("field", ("version", "candidates"))
def test_restore_rejects_missing_integration_graph_fields(field: str) -> None:
    state = _empty_runtime_state()
    del state["integration"]["graph"][field]

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_extra_integration_graph_field() -> None:
    state = _empty_runtime_state()
    state["integration"]["graph"]["unexpected"] = "value"

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "field",
    (
        "task_refs",
        "plan_refs",
        "requirement_refs",
        "changed_component_refs",
        "changed_interface_refs",
        "dependency_candidate_ids",
        "conflicts_with",
        "compatibility_assessments",
        "verification_evidence_refs",
        "status",
    ),
)
def test_restore_rejects_missing_candidate_fields_that_used_to_default(field: str) -> None:
    state = _proposed_runtime_state()
    del _candidate_row(state)[field]

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_extra_candidate_field() -> None:
    state = _proposed_runtime_state()
    _candidate_row(state)["unexpected"] = "value"

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_missing_compatibility_evidence_refs_that_used_to_default() -> None:
    state = _proposed_runtime_state()
    del _assessment_row(state)["evidence_refs"]

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_extra_compatibility_assessment_field() -> None:
    state = _proposed_runtime_state()
    _assessment_row(state)["unexpected"] = "value"

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_extra_integration_receipt_field() -> None:
    state = _two_candidate_runtime_state(with_receipts=True)
    state["integration"]["receipts"][0]["unexpected"] = "value"

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "mutation",
    (
        "candidates",
        "receipts",
        "task_refs",
        "plan_refs",
        "requirement_refs",
        "changed_component_refs",
        "changed_interface_refs",
        "dependency_candidate_ids",
        "conflicts_with",
        "compatibility_assessments",
        "verification_evidence_refs",
        "receipt_evidence_refs",
        "compatibility_evidence_refs",
    ),
)
def test_restore_rejects_non_json_list_serialized_collections(mutation: str) -> None:
    state = _two_candidate_runtime_state(with_receipts=True)
    candidate = _candidate_row(state, "102")
    if mutation == "candidates":
        rows = state["integration"]["graph"]["candidates"]
        state["integration"]["graph"]["candidates"] = tuple(rows)
    elif mutation == "receipts":
        rows = state["integration"]["receipts"]
        state["integration"]["receipts"] = tuple(rows)
    elif mutation == "receipt_evidence_refs":
        refs = state["integration"]["receipts"][0]["evidence_refs"]
        state["integration"]["receipts"][0]["evidence_refs"] = tuple(refs)
    elif mutation == "compatibility_evidence_refs":
        assessment = _assessment_row(state, "102")
        assessment["evidence_refs"] = tuple(assessment["evidence_refs"])
    else:
        candidate[mutation] = tuple(candidate[mutation])

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("candidate_id", 101),
        ("task_refs", 201),
        ("plan_refs", 202),
        ("requirement_refs", 203),
        ("changed_component_refs", 204),
        ("conflicts_with", 102),
        ("verification_evidence_refs", 206),
    ),
)
def test_restore_rejects_candidate_string_type_laundering(
    field: str,
    replacement: object,
) -> None:
    state = _proposed_runtime_state()
    candidate = _candidate_row(state)
    if isinstance(candidate[field], list):
        candidate[field][0] = replacement
    else:
        candidate[field] = replacement

    with pytest.raises(ValueError, match="exact string"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_dependency_identity_type_laundering() -> None:
    state = _two_candidate_runtime_state(with_receipts=False)
    _candidate_row(state, "102")["dependency_candidate_ids"][0] = 101

    with pytest.raises(ValueError, match="exact string"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("assessment_id", 301),
        ("integration_safe", 1),
        ("reason", 401),
        ("evidence_refs", 501),
        ("digest", 601),
    ),
)
def test_restore_rejects_nested_compatibility_type_laundering(
    field: str,
    replacement: object,
) -> None:
    state = _proposed_runtime_state()
    assessment = _assessment_row(state)
    if isinstance(assessment[field], list):
        assessment[field][0] = replacement
    else:
        assessment[field] = replacement

    expected = "exact bool" if field == "integration_safe" else "exact string"
    with pytest.raises(ValueError, match=expected):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("candidate_id", 101),
        ("evidence_refs", 701),
    ),
)
def test_restore_rejects_receipt_string_type_laundering(
    field: str,
    replacement: object,
) -> None:
    state = _two_candidate_runtime_state(with_receipts=True)
    receipt = state["integration"]["receipts"][0]
    if isinstance(receipt[field], list):
        receipt[field][0] = replacement
    else:
        receipt[field] = replacement

    with pytest.raises(ValueError, match="exact string"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_noncanonical_candidate_row_order() -> None:
    state = _two_candidate_runtime_state(with_receipts=False)
    state["integration"]["graph"]["candidates"].reverse()

    with pytest.raises(ValueError, match="candidate order"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_noncanonical_receipt_row_order() -> None:
    state = _two_candidate_runtime_state(with_receipts=True)
    state["integration"]["receipts"].reverse()

    with pytest.raises(ValueError, match="receipt order"):
        OrganizationRuntime.from_state(state)
