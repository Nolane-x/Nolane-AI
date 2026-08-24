from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


class _Registry:
    def __init__(self) -> None:
        self.known = {"requirements.chief", "coding.backend.01"}
        self.lookups: list[str] = []

    def get(self, agent_id: str) -> object:
        key = str(agent_id)
        self.lookups.append(key)
        if key not in self.known:
            raise KeyError(f"unknown agent: {key}")
        return object()


class _Authority:
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed
        self.calls: list[tuple[str, str]] = []

    def require_write(self, agent_id: str, resource: str) -> None:
        row = (str(agent_id), str(resource))
        self.calls.append(row)
        if not self.allowed:
            raise PermissionError(f"write denied: {row[0]} -> {row[1]}")


class _Ledger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append(self, kind: Any, **kwargs: Any) -> dict[str, Any]:
        event = {"kind": kind, **kwargs}
        self.events.append(event)
        return event


def _criterion():
    from nolane.external_core.requirements import AcceptanceCriterion

    return AcceptanceCriterion(
        "ac-1",
        "The result is independently verifiable.",
        verification_class="behavioral",
        evidence_expectations=("test", "receipt"),
    )


def _node(requirement_id: str = "req-a", *, dependencies: tuple[str, ...] = (), priority: int = 80):
    from nolane.external_core.requirements import RequirementKind, RequirementNode

    return RequirementNode(
        requirement_id=requirement_id,
        title=f"Requirement {requirement_id}",
        kind=RequirementKind.FUNCTIONAL,
        description=f"Preserve semantics for {requirement_id}.",
        dependencies=dependencies,
        acceptance_criteria=(_criterion(),),
        priority=priority,
    )


def test_wave5m_canonical_requirements_owns_public_implementation() -> None:
    import nolane.external_core.requirements as canonical

    public = (
        canonical.AcceptanceCriterion,
        canonical.RequirementKind,
        canonical.RequirementStatus,
        canonical.RequirementNode,
        canonical.RequirementRevision,
        canonical.RequirementGraph,
        canonical.RequirementsControlPlane,
    )
    assert all(symbol.__module__ == "nolane.external_core.requirements" for symbol in public)
    assert canonical.COMPONENT_ID == "external.requirements"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.requirements"


def test_wave5m_legacy_requirements_is_exact_public_object_bridge() -> None:
    import cogcoder.organization.requirements as legacy
    import nolane.external_core.requirements as canonical

    for name in (
        "AcceptanceCriterion",
        "RequirementKind",
        "RequirementStatus",
        "RequirementNode",
        "RequirementRevision",
        "RequirementGraph",
        "RequirementsControlPlane",
    ):
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5m_requirement_contracts_round_trip_with_stable_enum_values() -> None:
    from nolane.external_core.requirements import (
        AcceptanceCriterion,
        RequirementKind,
        RequirementNode,
        RequirementStatus,
    )

    assert [row.value for row in RequirementKind] == [
        "functional",
        "non_functional",
        "constraint",
        "security",
        "compatibility",
        "quality",
    ]
    assert [row.value for row in RequirementStatus] == [
        "active",
        "ambiguous",
        "superseded",
        "rejected",
    ]

    criterion = _criterion()
    assert AcceptanceCriterion.from_state(criterion.to_state()) == criterion
    node = RequirementNode(
        "req-contract",
        "Contract",
        RequirementKind.SECURITY,
        "Security behavior is explicit.",
        acceptance_criteria=(criterion,),
        priority=73,
        status=RequirementStatus.AMBIGUOUS,
    )
    assert RequirementNode.from_state(node.to_state()) == node


def test_wave5m_requirement_validation_fails_closed() -> None:
    from nolane.external_core.requirements import AcceptanceCriterion, RequirementKind, RequirementNode

    with pytest.raises(ValueError, match="non-empty"):
        AcceptanceCriterion("", "missing id")
    with pytest.raises(ValueError, match="non-empty"):
        AcceptanceCriterion("ac", "")
    with pytest.raises(ValueError, match=r"\[0,100\]"):
        RequirementNode("req", "title", RequirementKind.QUALITY, "description", priority=101)

    duplicate = AcceptanceCriterion("same", "criterion")
    with pytest.raises(ValueError, match="duplicate acceptance criterion id"):
        RequirementNode(
            "req",
            "title",
            RequirementKind.QUALITY,
            "description",
            acceptance_criteria=(duplicate, duplicate),
        )


def test_wave5m_requirement_graph_rejects_unknown_dependency_and_cycles() -> None:
    from nolane.external_core.requirements import RequirementGraph

    graph = RequirementGraph()
    with pytest.raises(ValueError, match="unknown requirement dependency"):
        graph.apply(
            actor_agent_id="requirements.chief",
            reason="unknown dependency must fail",
            evidence_refs=("ev-1",),
            upserts=(_node("req-a", dependencies=("req-missing",)),),
        )
    with pytest.raises(ValueError, match="dependency cycle"):
        graph.apply(
            actor_agent_id="requirements.chief",
            reason="cycle must fail",
            evidence_refs=("ev-2",),
            upserts=(
                _node("req-a", dependencies=("req-b",)),
                _node("req-b", dependencies=("req-a",)),
            ),
        )


def test_wave5m_requirement_graph_is_deterministic_evidence_bearing_and_round_trippable() -> None:
    from nolane.external_core.requirements import RequirementGraph

    first, second = RequirementGraph(), RequirementGraph()
    a = _node("req-a")
    b = _node("req-b", dependencies=("req-a",))
    left = first.apply(
        actor_agent_id="requirements.chief",
        reason="establish requirements",
        evidence_refs=("ev-2", "ev-1"),
        upserts=(b, a),
    )
    right = second.apply(
        actor_agent_id="requirements.chief",
        reason="establish requirements",
        evidence_refs=("ev-2", "ev-1"),
        upserts=(a, b),
    )

    assert tuple(row.requirement_id for row in first.nodes()) == ("req-a", "req-b")
    assert left.changed_requirement_ids == ("req-a", "req-b")
    assert left.graph_digest == right.graph_digest
    assert first.digest == second.digest
    assert left.version == 1 and left.parent_version is None
    assert left.evidence_refs == ("ev-2", "ev-1")

    restored = RequirementGraph.from_state(first.to_state())
    assert restored.to_state() == first.to_state()
    assert restored.digest == first.digest

    with pytest.raises(ValueError, match="reason, evidence and at least one mutation"):
        first.apply(actor_agent_id="requirements.chief", reason="", evidence_refs=("ev",), upserts=(a,))
    with pytest.raises(ValueError, match="reason, evidence and at least one mutation"):
        first.apply(
            actor_agent_id="requirements.chief",
            reason="missing evidence",
            evidence_refs=(),
            upserts=(a,),
        )


def test_wave5m_requirement_graph_rejects_tampered_persistence() -> None:
    from nolane.external_core.requirements import RequirementGraph

    graph = RequirementGraph()
    graph.apply(
        actor_agent_id="requirements.chief",
        reason="baseline",
        evidence_refs=("ev",),
        upserts=(_node(),),
    )
    bad_digest = copy.deepcopy(graph.to_state())
    bad_digest["revisions"][-1]["graph_digest"] = "tampered"
    with pytest.raises(ValueError, match="graph digest mismatch"):
        RequirementGraph.from_state(bad_digest)

    bad_sequence = copy.deepcopy(graph.to_state())
    bad_sequence["revisions"][-1]["version"] = 2
    with pytest.raises(ValueError, match="non-canonical requirement revision sequence"):
        RequirementGraph.from_state(bad_sequence)


def test_wave5m_requirements_control_plane_enforces_authority_and_emits_change_event() -> None:
    from nolane.external_core.requirements import RequirementsControlPlane

    registry, authority, ledger = _Registry(), _Authority(), _Ledger()
    control = RequirementsControlPlane(registry=registry, authority=authority, ledger=ledger)
    revision = control.apply_revision(
        actor_agent_id="requirements.chief",
        reason="accepted requirement",
        evidence_refs=("ev-accepted",),
        upserts=(_node("req-authority"),),
    )
    assert revision.version == 1
    assert registry.lookups == ["requirements.chief"]
    assert authority.calls == [("requirements.chief", "requirements")]
    event = ledger.events[-1]
    assert event["source_agent_id"] == "requirements.chief"
    assert event["target_agent_id"] == "requirements.chief"
    assert event["region"] == "requirements-product"
    assert event["evidence_refs"] == ("ev-accepted",)
    assert event["object_refs"] == ("req-authority",)
    assert event["payload"] == {
        "requirements_action": "changed",
        "version": 1,
        "reason": "accepted requirement",
    }

    denied = RequirementsControlPlane(registry=_Registry(), authority=_Authority(allowed=False), ledger=_Ledger())
    with pytest.raises(PermissionError, match="write denied"):
        denied.apply_revision(
            actor_agent_id="requirements.chief",
            reason="must be denied",
            evidence_refs=("ev-denied",),
            upserts=(_node("req-denied"),),
        )
    assert denied.graph.version == 0


def test_wave5m_requirements_proposals_preserve_routing_and_action_semantics() -> None:
    from nolane.external_core.requirements import RequirementsControlPlane

    control = RequirementsControlPlane(registry=_Registry(), authority=_Authority(), ledger=_Ledger())
    control.apply_revision(
        actor_agent_id="requirements.chief",
        reason="seed",
        evidence_refs=("ev-seed",),
        upserts=(_node("req-proposal"),),
    )
    control.ledger.events.clear()

    events = (
        control.propose_ambiguity(
            source_agent_id="coding.backend.01",
            requirement_id="req-proposal",
            question="Which compatibility target is authoritative?",
            evidence_refs=("ev-a",),
        ),
        control.propose_change(
            source_agent_id="coding.backend.01",
            requirement_id="req-proposal",
            proposal="Clarify the compatibility target.",
            evidence_refs=("ev-b",),
        ),
        control.propose_acceptance_gap(
            source_agent_id="coding.backend.01",
            requirement_id="req-proposal",
            gap="No rollback criterion exists.",
            evidence_refs=("ev-c",),
        ),
    )
    assert [row["payload"]["requirements_action"] for row in events] == [
        "ambiguity",
        "change_proposed",
        "acceptance_gap",
    ]
    for event, evidence in zip(events, (("ev-a",), ("ev-b",), ("ev-c",))):
        assert event["source_agent_id"] == "coding.backend.01"
        assert event["target_agent_id"] == "requirements.chief"
        assert event["region"] == "requirements-product"
        assert event["object_refs"] == ("req-proposal",)
        assert event["evidence_refs"] == evidence
        assert event["payload"]["requirement_id"] == "req-proposal"

    with pytest.raises(ValueError, match="proposal text must be non-empty"):
        control.propose_change(
            source_agent_id="coding.backend.01",
            requirement_id="req-proposal",
            proposal="   ",
            evidence_refs=("ev",),
        )
    with pytest.raises(KeyError, match="unknown requirement"):
        control.propose_change(
            source_agent_id="coding.backend.01",
            requirement_id="missing",
            proposal="change",
            evidence_refs=("ev",),
        )


def test_wave5m_control_plane_state_round_trip_preserves_authoritative_state() -> None:
    from nolane.external_core.requirements import RequirementsControlPlane

    registry, authority, ledger = _Registry(), _Authority(), _Ledger()
    control = RequirementsControlPlane(registry=registry, authority=authority, ledger=ledger)
    control.apply_revision(
        actor_agent_id="requirements.chief",
        reason="persist",
        evidence_refs=("ev-persist",),
        upserts=(_node("req-persist"),),
    )
    state = control.to_state()
    restored = RequirementsControlPlane.from_state(
        registry=registry,
        authority=authority,
        ledger=ledger,
        state=state,
    )
    assert restored.to_state() == state
    assert restored.graph.digest == control.graph.digest


def test_wave5m_canonical_requirements_has_no_historical_requirements_reverse_import() -> None:
    import nolane.external_core.requirements as requirements

    source_path = Path(requirements.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cogcoder.organization.requirements" or alias.name.startswith(
                    "cogcoder.organization.requirements."
                ):
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cogcoder.organization.requirements" or module.startswith(
                "cogcoder.organization.requirements."
            ):
                offenders.append(f"from:{node.lineno}:{module}")
    assert offenders == [], "canonical Requirements reverse-imports historical Requirements authority: " + "; ".join(offenders)


def test_wave5m_requirements_component_is_native_revision_one_and_removed_from_facades() -> None:
    row = build_component_implementation_ledger()["external.requirements"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.requirements"
    assert row.legacy_sources == ("cogcoder/organization/requirements.py",)
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.requirements")) == "0.0.1"

    facade_ids = {binding.component_id for binding in build_active_facade_bindings()}
    assert "external.requirements" not in facade_ids
    for neighboring_facade in ("external.context", "external.planning", "external.architecture"):
        assert neighboring_facade in facade_ids


def test_wave5m_native_debt_reduces_only_requirements() -> None:
    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1

    assert len(non_native) == 32
    assert counts == {
        "compatibility_facade": 24,
        "frozen_asset": 1,
        "historical_only": 5,
        "legacy_internal": 2,
    }
    assert ledger["external.requirements"].status is ImplementationStatus.CANONICAL_NATIVE
    for unchanged in ("external.context", "external.planning", "external.architecture"):
        assert ledger[unchanged].status is ImplementationStatus.COMPATIBILITY_FACADE
        assert not ledger[unchanged].canonical_write_authority
