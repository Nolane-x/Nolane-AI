from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
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
        self.lookups: list[str] = []

    def get(self, agent_id: str) -> Any:
        key = str(agent_id)
        self.lookups.append(key)
        return SimpleNamespace(agent_id=key, region="planning-program")


class _Authority:
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed
        self.calls: list[tuple[str, str]] = []

    def require_write(self, agent_id: str, resource: str) -> None:
        row = (str(agent_id), str(resource))
        self.calls.append(row)
        if not self.allowed:
            raise PermissionError(f"write denied: {row[0]} -> {row[1]}")


@dataclass(slots=True)
class _Event:
    event_id: str
    kind: Any
    source_agent_id: str
    target_agent_id: str | None
    region: str | None
    payload: dict[str, Any]
    evidence_refs: tuple[str, ...] = ()
    object_refs: tuple[str, ...] = ()
    causal_parent_ids: tuple[str, ...] = ()


class _Ledger:
    def __init__(self) -> None:
        self.events: list[_Event] = []

    def append(self, kind: Any, **kwargs: Any) -> _Event:
        event = _Event(
            event_id=f"event-{len(self.events) + 1}",
            kind=kind,
            source_agent_id=str(kwargs.get("source_agent_id", "")),
            target_agent_id=kwargs.get("target_agent_id"),
            region=kwargs.get("region"),
            payload=dict(kwargs.get("payload", {})),
            evidence_refs=tuple(kwargs.get("evidence_refs", ())),
            object_refs=tuple(kwargs.get("object_refs", ())),
            causal_parent_ids=tuple(kwargs.get("causal_parent_ids", ())),
        )
        self.events.append(event)
        return event

    def get(self, event_id: str) -> _Event:
        for event in self.events:
            if event.event_id == str(event_id):
                return event
        raise KeyError(f"unknown event: {event_id}")


def _requirements() -> Any:
    class _Graph:
        def get(self, requirement_id: str) -> Any:
            return SimpleNamespace(requirement_id=str(requirement_id))

    return SimpleNamespace(graph=_Graph())


def _task_graph(*, ledger: _Ledger | None = None):
    from nolane.organization.tasks import TaskGraph

    return TaskGraph(
        ledger=ledger or _Ledger(),
        registry=_Registry(),
        authority=_Authority(),
    )


def _planning(*, tasks: Any | None = None, ledger: _Ledger | None = None, graph: Any | None = None):
    from nolane.external_core.planning import PlanningControlPlane

    actual_ledger = ledger or _Ledger()
    actual_tasks = tasks or _task_graph(ledger=actual_ledger)
    kwargs = {
        "registry": _Registry(),
        "authority": _Authority(),
        "ledger": actual_ledger,
        "tasks": actual_tasks,
        "requirements": _requirements(),
    }
    if graph is not None:
        kwargs["graph"] = graph
    return PlanningControlPlane(**kwargs)


def test_wave5n_canonical_planning_owns_complete_public_implementation() -> None:
    import nolane.external_core.planning as canonical

    names = (
        "PlanNodeStatus",
        "PlanNode",
        "Milestone",
        "PlanRisk",
        "PlanRevision",
        "PlanDelta",
        "GapApplication",
        "MasterPlanGraph",
        "PlanningControlPlane",
    )
    assert all(getattr(canonical, name).__module__ == "nolane.external_core.planning" for name in names)
    assert canonical.COMPONENT_ID == "external.planning"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.planning"


def test_wave5n_historical_planning_is_exact_public_object_bridge() -> None:
    import cogcoder.organization.planning as legacy
    import nolane.external_core.planning as canonical

    for name in (
        "PlanNodeStatus",
        "PlanNode",
        "Milestone",
        "PlanRisk",
        "PlanRevision",
        "PlanDelta",
        "GapApplication",
        "MasterPlanGraph",
        "PlanningControlPlane",
    ):
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5n_canonical_planning_has_no_historical_planning_reverse_import() -> None:
    import nolane.external_core.planning as planning

    source_path = Path(planning.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cogcoder.organization.planning" or alias.name.startswith(
                    "cogcoder.organization.planning."
                ):
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cogcoder.organization.planning" or module.startswith(
                "cogcoder.organization.planning."
            ):
                offenders.append(f"from:{node.lineno}:{module}")
    assert offenders == [], "canonical Planning reverse-imports historical Planning authority: " + "; ".join(offenders)


def test_wave5n_task_graph_plan_revision_is_read_only_projection_starting_at_zero() -> None:
    graph = _task_graph()
    assert graph.plan_version == 0
    with pytest.raises(AttributeError):
        graph.plan_version = 7


def test_wave5n_planning_composition_projects_single_revision_clock() -> None:
    from nolane.external_core.planning import PlanNode

    ledger = _Ledger()
    tasks = _task_graph(ledger=ledger)
    planning = _planning(tasks=tasks, ledger=ledger)
    assert planning.graph.version == tasks.plan_version == 0

    first = planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="establish first canonical plan node",
        evidence_refs=("ev-plan-1",),
        upsert_nodes=(PlanNode("plan-a", "Plan A"),),
    )
    assert first.version == planning.graph.version == tasks.plan_version == 1
    assert tasks.plan_nodes() == ("plan-a",)

    second = planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="establish dependent canonical plan node",
        evidence_refs=("ev-plan-2",),
        upsert_nodes=(PlanNode("plan-b", "Plan B", dependencies=("plan-a",)),),
    )
    assert second.version == planning.graph.version == tasks.plan_version == 2
    assert tasks.plan_nodes() == ("plan-a", "plan-b")

    rolled = planning.rollback(
        actor_agent_id="planning.chief",
        source_revision=1,
        reason="evidence requires rollback to first plan",
        evidence_refs=("ev-rollback",),
    )
    assert rolled.version == planning.graph.version == tasks.plan_version == 3
    assert tasks.plan_nodes() == ("plan-a",)


def test_wave5n_task_graph_state_marks_external_planning_as_revision_authority() -> None:
    graph = _task_graph()
    state = graph.to_state()
    assert state["plan_revision_authority"] == "external.planning"
    assert state["plan_version"] == 0


def test_wave5n_known_legacy_bootstrap_clock_is_normalized_once_by_planning() -> None:
    from nolane.organization.tasks import TaskGraph

    ledger = _Ledger()
    legacy_state = {"tasks": [], "plan_nodes": [], "plan_version": 1}
    tasks = TaskGraph.from_state(
        legacy_state,
        ledger=ledger,
        registry=_Registry(),
        authority=_Authority(),
    )
    assert tasks.plan_version == 1
    planning = _planning(tasks=tasks, ledger=ledger)
    assert planning.graph.version == 0
    assert tasks.plan_version == 0
    assert tasks.to_state()["plan_revision_authority"] == "external.planning"


def test_wave5n_marked_revision_mismatch_fails_closed() -> None:
    from nolane.organization.tasks import TaskGraph

    ledger = _Ledger()
    tasks = TaskGraph.from_state(
        {
            "tasks": [],
            "plan_nodes": [],
            "plan_version": 2,
            "plan_revision_authority": "external.planning",
        },
        ledger=ledger,
        registry=_Registry(),
        authority=_Authority(),
    )
    with pytest.raises(ValueError, match="plan revision.*mismatch"):
        _planning(tasks=tasks, ledger=ledger)


def test_wave5n_unexplained_legacy_revision_mismatch_fails_closed() -> None:
    from nolane.organization.tasks import TaskGraph

    ledger = _Ledger()
    tasks = TaskGraph.from_state(
        {"tasks": [], "plan_nodes": [], "plan_version": 9},
        ledger=ledger,
        registry=_Registry(),
        authority=_Authority(),
    )
    with pytest.raises(ValueError, match="legacy plan revision.*mismatch"):
        _planning(tasks=tasks, ledger=ledger)


def test_wave5n_unbound_legacy_task_amendment_entrypoint_cannot_mutate_clock() -> None:
    from cogcoder.organization.types import EventKind

    ledger = _Ledger()
    tasks = _task_graph(ledger=ledger)
    proposal = ledger.append(
        EventKind.PLAN_GAP_DETECTED,
        source_agent_id="coding.backend.01",
        target_agent_id="planning.chief",
        region="coding-backend",
        payload={
            "task_id": "task-a",
            "reason": "missing plan node",
            "suggested_nodes": ["plan-new"],
            "evidence_ids": ["ev-gap"],
            "plan_version": 0,
        },
    )
    before = tasks.plan_version
    with pytest.raises(RuntimeError, match="Planning authority is not bound"):
        tasks.apply_plan_amendment("planning.chief", proposal.event_id, added_nodes=("plan-new",))
    assert tasks.plan_version == before


def test_wave5n_bound_legacy_task_amendment_delegates_through_master_plan() -> None:
    from cogcoder.organization.types import EventKind

    ledger = _Ledger()
    tasks = _task_graph(ledger=ledger)
    tasks.add_task("task-a", title="Task A", plan_node_id="plan-new")
    planning = _planning(tasks=tasks, ledger=ledger)
    proposal = ledger.append(
        EventKind.PLAN_GAP_DETECTED,
        source_agent_id="coding.backend.01",
        target_agent_id="planning.chief",
        region="coding-backend",
        payload={
            "task_id": "task-a",
            "reason": "missing plan node",
            "suggested_nodes": ["plan-new"],
            "evidence_ids": ["ev-gap"],
            "plan_version": 0,
        },
    )
    event = tasks.apply_plan_amendment("planning.chief", proposal.event_id, added_nodes=("plan-new",))
    assert planning.graph.version == tasks.plan_version == 1
    assert tuple(node.node_id for node in planning.graph.nodes()) == ("plan-new",)
    assert event.kind is EventKind.PLAN_AMENDED
    assert event.payload["proposal_event_id"] == proposal.event_id
    assert event.payload["plan_version"] == 1
    assert event.payload["added_nodes"] == ["plan-new"]


def test_wave5n_planning_and_tasks_component_versions_reflect_authority_migration() -> None:
    ledger = build_component_implementation_ledger()
    planning = ledger["external.planning"]
    tasks = ledger["organization.tasks"]

    assert planning.status is ImplementationStatus.CANONICAL_NATIVE
    assert planning.canonical_module == "nolane.external_core.planning"
    assert planning.legacy_sources == ("cogcoder/organization/planning.py",)
    assert planning.canonical_write_authority
    assert planning.component_version == "0.0.1"
    assert str(component_version("external.planning")) == "0.0.1"

    assert tasks.status is ImplementationStatus.CANONICAL_NATIVE
    assert tasks.component_version == "0.0.2"
    assert str(component_version("organization.tasks")) == "0.0.2"

    facade_ids = {binding.component_id for binding in build_active_facade_bindings()}
    assert "external.planning" not in facade_ids
    # Architecture and Integration are downstream authorities. Historical
    # Wave 5N contracts must not require either one to remain a facade.


def test_wave5n_generated_native_debt_no_longer_contains_planning() -> None:
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    serialized = json.dumps(state, sort_keys=True)
    assert "external.planning" not in serialized

    implementation = build_component_implementation_ledger()
    non_native = [row for row in implementation.values() if row.status is not ImplementationStatus.CANONICAL_NATIVE]
    # Wave 5N established a ceiling of 31 (then Wave 5O reduced it to 30).
    # Later extraction waves may continue reducing debt without invalidating 5N.
    assert len(non_native) <= 31
