"""Live Goal/Design authority runtime for Nolane AI.

The coherence plane defines the authority semantics. This module connects those
semantics to the existing Requirements, Planning, Architecture, Integration and
Context control planes without taking ownership away from them.

The runtime is deliberately adapter-oriented: specialist planes remain the
canonical writers of their own state, while Goal/Design observes exact state,
freezes content-addressed snapshots, propagates change impact, binds integration
and context to snapshots, and manages the lifecycle of admitted decisions.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import sys
from typing import Any, Iterable, Mapping, Sequence

from .goal_design import (
    CoherenceError,
    DecisionReceipt,
    DesignOption,
    DesignScenario,
    GoalDesignCoherencePlane,
    GoalDesignSnapshot,
    GoalDesignVersionVector,
    GoalSpec,
    PlaneState,
    ProofObligation,
    UncertaintyItem,
    stable_digest,
)
from .goal_design_contracts import (
    ArchitectureState,
    ContextState,
    GoalDesignStateBundle,
    IntegrationState,
    PlanningState,
    RequirementsState,
)
from .goal_design_ledger import GoalDesignLedger

__version__ = "0.3.2"


class DecisionLifecycle(str, Enum):
    ACTIVE = "active"
    STALE = "stale"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


@dataclass(frozen=True)
class GoalDesignChangeSet:
    """Explicit authority refs known to have changed.

    `architecture_refs` may contain component or interface ids. The impact
    engine resolves the concrete kind from the live architecture graph.
    """

    requirement_refs: tuple[str, ...] = ()
    plan_refs: tuple[str, ...] = ()
    architecture_refs: tuple[str, ...] = ()
    integration_candidate_refs: tuple[str, ...] = ()
    context_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "requirement_refs",
            "plan_refs",
            "architecture_refs",
            "integration_candidate_refs",
            "context_refs",
        ):
            values = getattr(self, field_name)
            if any(not str(value).strip() for value in values):
                raise ValueError(f"{field_name} cannot contain empty refs")


@dataclass(frozen=True)
class GoalDesignImpactReport:
    changed_requirement_refs: tuple[str, ...]
    changed_plan_refs: tuple[str, ...]
    changed_architecture_refs: tuple[str, ...]
    changed_candidate_refs: tuple[str, ...]
    affected_plan_refs: tuple[str, ...]
    affected_component_refs: tuple[str, ...]
    affected_interface_refs: tuple[str, ...]
    affected_candidate_refs: tuple[str, ...]
    context_invalidated: bool
    reasons: tuple[str, ...]
    digest: str

    @property
    def affected_refs(self) -> tuple[str, ...]:
        refs = (
            set(self.changed_requirement_refs)
            | set(self.changed_plan_refs)
            | set(self.changed_architecture_refs)
            | set(self.changed_candidate_refs)
            | set(self.affected_plan_refs)
            | set(self.affected_component_refs)
            | set(self.affected_interface_refs)
            | set(self.affected_candidate_refs)
        )
        return tuple(sorted(refs))


@dataclass(frozen=True)
class DecisionAuthorityRecord:
    receipt: DecisionReceipt
    dependency_refs: tuple[str, ...]
    snapshot_digest: str
    lifecycle: DecisionLifecycle = DecisionLifecycle.ACTIVE
    invalidation_reasons: tuple[str, ...] = ()
    authority_event_id: str | None = None
    superseded_by: str | None = None


class DecisionAuthorityIndex:
    """Persistent authority index over immutable content-addressed receipts."""

    SCHEMA_VERSION = 1
    TERMINAL_LIFECYCLES = frozenset({DecisionLifecycle.SUPERSEDED, DecisionLifecycle.REVOKED})

    def __init__(self) -> None:
        self._records: dict[str, DecisionAuthorityRecord] = {}

    @property
    def digest(self) -> str:
        return stable_digest({"decision_authority_index": self.to_state()})

    @staticmethod
    def _receipt_to_state(receipt: DecisionReceipt) -> dict[str, Any]:
        return {
            "receipt_id": receipt.receipt_id,
            "goal_id": receipt.goal_id,
            "selected_option_id": receipt.selected_option_id,
            "snapshot_digest": receipt.snapshot_digest,
            "version_vector": dict(receipt.version_vector),
            "evaluation_digest": receipt.evaluation_digest,
            "proof_obligation_ids": list(receipt.proof_obligation_ids),
            "uncertainty_ids": list(receipt.uncertainty_ids),
            "evidence_refs": list(receipt.evidence_refs),
            "goal_digest": receipt.goal_digest,
            "scenario_set_digest": receipt.scenario_set_digest,
            "option_set_digest": receipt.option_set_digest,
            "proof_state_digest": receipt.proof_state_digest,
            "uncertainty_state_digest": receipt.uncertainty_state_digest,
            "traceability_digest": receipt.traceability_digest,
            "input_manifest_digest": receipt.input_manifest_digest,
        }

    @staticmethod
    def _receipt_from_state(state: Mapping[str, Any]) -> DecisionReceipt:
        return DecisionReceipt(
            receipt_id=str(state["receipt_id"]),
            goal_id=str(state["goal_id"]),
            selected_option_id=str(state["selected_option_id"]),
            snapshot_digest=str(state["snapshot_digest"]),
            version_vector={str(k): str(v) for k, v in dict(state.get("version_vector", {})).items()},
            evaluation_digest=str(state["evaluation_digest"]),
            proof_obligation_ids=tuple(str(x) for x in state.get("proof_obligation_ids", ())),
            uncertainty_ids=tuple(str(x) for x in state.get("uncertainty_ids", ())),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            goal_digest=str(state.get("goal_digest", "")),
            scenario_set_digest=str(state.get("scenario_set_digest", "")),
            option_set_digest=str(state.get("option_set_digest", "")),
            proof_state_digest=str(state.get("proof_state_digest", "")),
            uncertainty_state_digest=str(state.get("uncertainty_state_digest", "")),
            traceability_digest=str(state.get("traceability_digest", "")),
            input_manifest_digest=str(state.get("input_manifest_digest", "")),
        )

    @classmethod
    def _ensure_mutable(cls, record: DecisionAuthorityRecord, *, action: str) -> None:
        if record.lifecycle in cls.TERMINAL_LIFECYCLES:
            raise ValueError(
                f"decision lifecycle is terminal ({record.lifecycle.value}); cannot {action}"
            )

    def register(
        self,
        receipt: DecisionReceipt,
        *,
        dependency_refs: Iterable[str] = (),
        authority_event_id: str | None = None,
    ) -> DecisionAuthorityRecord:
        dependencies = tuple(sorted({str(ref) for ref in dependency_refs if str(ref).strip()}))
        existing = self._records.get(receipt.receipt_id)
        if existing is not None:
            if existing.dependency_refs != dependencies or existing.snapshot_digest != receipt.snapshot_digest:
                raise ValueError("decision receipt identity cannot be rebound to different authority dependencies")
            return existing
        record = DecisionAuthorityRecord(
            receipt=receipt,
            dependency_refs=dependencies,
            snapshot_digest=receipt.snapshot_digest,
            authority_event_id=authority_event_id,
        )
        self._records[receipt.receipt_id] = record
        return record

    def get(self, receipt_id: str) -> DecisionAuthorityRecord:
        try:
            return self._records[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown Goal/Design decision receipt: {receipt_id}") from exc

    def records(self) -> tuple[DecisionAuthorityRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def active(self) -> tuple[DecisionAuthorityRecord, ...]:
        return tuple(record for record in self.records() if record.lifecycle is DecisionLifecycle.ACTIVE)

    def mark_stale(self, receipt_id: str, reasons: Iterable[str]) -> DecisionAuthorityRecord:
        normalized = tuple(sorted({str(reason).strip() for reason in reasons if str(reason).strip()}))
        if not normalized:
            raise ValueError("decision staleness requires at least one authority reason")
        record = self.get(receipt_id)
        self._ensure_mutable(record, action="mark stale")
        merged = tuple(sorted(set(record.invalidation_reasons) | set(normalized)))
        if record.lifecycle is DecisionLifecycle.STALE and merged == record.invalidation_reasons:
            return record
        updated = replace(record, lifecycle=DecisionLifecycle.STALE, invalidation_reasons=merged)
        self._records[receipt_id] = updated
        return updated

    def revoke(self, receipt_id: str, reason: str) -> DecisionAuthorityRecord:
        reason = str(reason).strip()
        if not reason:
            raise ValueError("decision revocation requires a reason")
        record = self.get(receipt_id)
        self._ensure_mutable(record, action="revoke")
        updated = replace(
            record,
            lifecycle=DecisionLifecycle.REVOKED,
            invalidation_reasons=tuple(sorted(set(record.invalidation_reasons) | {reason})),
        )
        self._records[receipt_id] = updated
        return updated

    def supersede(self, receipt_id: str, *, by_receipt_id: str) -> DecisionAuthorityRecord:
        if receipt_id == by_receipt_id:
            raise ValueError("a decision cannot supersede itself")
        record = self.get(receipt_id)
        replacement = self.get(by_receipt_id)
        self._ensure_mutable(record, action="supersede")
        if replacement.lifecycle is not DecisionLifecycle.ACTIVE:
            qualifier = "terminal " if replacement.lifecycle in self.TERMINAL_LIFECYCLES else ""
            raise ValueError(
                "replacement decision must be active; "
                f"observed {qualifier}{replacement.lifecycle.value}"
            )
        updated = replace(record, lifecycle=DecisionLifecycle.SUPERSEDED, superseded_by=by_receipt_id)
        self._records[receipt_id] = updated
        return updated

    def to_state(self) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        for record in self.records():
            records.append(
                {
                    "receipt": self._receipt_to_state(record.receipt),
                    "dependency_refs": list(record.dependency_refs),
                    "snapshot_digest": record.snapshot_digest,
                    "lifecycle": record.lifecycle.value,
                    "invalidation_reasons": list(record.invalidation_reasons),
                    "authority_event_id": record.authority_event_id,
                    "superseded_by": record.superseded_by,
                }
            )
        return {"schema_version": self.SCHEMA_VERSION, "records": records}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "DecisionAuthorityIndex":
        if int(state.get("schema_version", cls.SCHEMA_VERSION)) != cls.SCHEMA_VERSION:
            raise ValueError("unsupported Goal/Design decision index schema version")
        index = cls()
        for row in state.get("records", ()):
            receipt = cls._receipt_from_state(row["receipt"])
            if receipt.receipt_id in index._records:
                raise ValueError(f"duplicate Goal/Design decision receipt identity: {receipt.receipt_id}")
            snapshot_digest = str(row.get("snapshot_digest", receipt.snapshot_digest))
            if snapshot_digest != receipt.snapshot_digest:
                raise ValueError("decision authority snapshot digest disagrees with receipt")
            dependency_refs = tuple(sorted({str(x) for x in row.get("dependency_refs", ()) if str(x).strip()}))
            invalidation_reasons = tuple(
                sorted({str(x) for x in row.get("invalidation_reasons", ()) if str(x).strip()})
            )
            index._records[receipt.receipt_id] = DecisionAuthorityRecord(
                receipt=receipt,
                dependency_refs=dependency_refs,
                snapshot_digest=snapshot_digest,
                lifecycle=DecisionLifecycle(str(row.get("lifecycle", DecisionLifecycle.ACTIVE.value))),
                invalidation_reasons=invalidation_reasons,
                authority_event_id=(
                    None if row.get("authority_event_id") is None else str(row.get("authority_event_id"))
                ),
                superseded_by=None if row.get("superseded_by") is None else str(row.get("superseded_by")),
            )
        known = set(index._records)
        for record in index._records.values():
            if record.lifecycle is DecisionLifecycle.SUPERSEDED:
                if not record.superseded_by or record.superseded_by not in known:
                    raise ValueError("superseded decision references unknown replacement receipt")
            elif record.superseded_by is not None:
                raise ValueError("non-superseded decision cannot carry superseded_by")

        for start_id in sorted(index._records):
            seen: set[str] = set()
            current_id = start_id
            while index._records[current_id].lifecycle is DecisionLifecycle.SUPERSEDED:
                target_id = index._records[current_id].superseded_by
                assert target_id is not None
                if target_id in seen:
                    raise ValueError("decision authority supersession cycle detected")
                seen.add(current_id)
                current_id = target_id
        return index


@dataclass(frozen=True)
class IntegrationGuardReceipt:
    candidate_id: str
    snapshot_digest: str
    architecture_version: int
    dependency_refs: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class ContextBindingReceipt:
    snapshot_digest: str
    artifact_versions: tuple[tuple[str, int], ...]
    context_policy_token: str
    digest: str


class GoalDesignRuntime:
    """Operational membrane over the five existing D control planes.

    This object never writes Requirements, Planning, Architecture, Integration
    or Context state. It observes those authorities, creates Goal/Design
    authority snapshots/receipts, and rejects actions compiled against stale
    state.
    """

    def __init__(
        self,
        *,
        requirements: Any,
        planning: Any,
        architecture: Any,
        integration: Any,
        context: Any,
        authority: GoalDesignCoherencePlane | None = None,
        ledger: GoalDesignLedger | None = None,
        decisions: DecisionAuthorityIndex | None = None,
    ) -> None:
        self.requirements = requirements
        self.planning = planning
        self.architecture = architecture
        self.integration = integration
        self.context = context
        self.authority = authority or GoalDesignCoherencePlane()
        self.ledger = ledger or GoalDesignLedger()
        self.decisions = decisions or DecisionAuthorityIndex()
        self._snapshot_events: dict[str, str] = {}

    @staticmethod
    def _graph_plane_state(graph: Any) -> PlaneState:
        version = int(getattr(graph, "version", 0))
        digest = getattr(graph, "digest", None)
        if callable(digest):
            digest = digest()
        if not digest:
            if not hasattr(graph, "to_state"):
                raise TypeError("Goal/Design live graph requires digest or to_state()")
            digest = stable_digest(graph.to_state())
        return PlaneState(f"v{version}", str(digest))

    def _context_plane_state(self) -> PlaneState:
        version = str(getattr(self.context, "context_policy_version", "policy:v1"))
        module = sys.modules.get(type(self.context).__module__)
        component_version = None if module is None else getattr(module, "COMPONENT_VERSION", None)
        payload = {
            "context_policy_version": version,
            "context_component_version": None if component_version is None else str(component_version),
            "max_memories": int(getattr(self.context, "max_memories", 0)),
            "max_events": int(getattr(self.context, "max_events", 0)),
        }
        return PlaneState(version, stable_digest(payload))

    @staticmethod
    def _status_value(value: Any) -> str:
        return str(getattr(value, "value", value))

    def observe(self) -> GoalDesignStateBundle:
        """Observe a deterministic authority bundle from the live five planes."""

        requirements_graph = self.requirements.graph
        requirement_nodes = tuple(requirements_graph.nodes())
        active_requirements = tuple(
            sorted(node.requirement_id for node in requirement_nodes if self._status_value(node.status) == "active")
        )
        acceptance_refs = tuple(
            sorted(
                {
                    str(ref)
                    for node in requirement_nodes
                    if node.requirement_id in active_requirements
                    for criterion in getattr(node, "acceptance_criteria", ())
                    for ref in getattr(criterion, "evidence_expectations", ())
                    if str(ref).strip()
                }
            )
        )

        planning_graph = self.planning.graph
        plan_nodes = tuple(planning_graph.nodes())
        planned_requirement_refs = tuple(
            sorted(
                {
                    str(ref)
                    for node in plan_nodes
                    if self._status_value(getattr(node, "status", "active")) != "superseded"
                    for ref in getattr(node, "requirement_refs", ())
                }
            )
        )
        plan_state = planning_graph.to_state() if hasattr(planning_graph, "to_state") else {}
        risk_refs = tuple(
            sorted(str(row.get("risk_id")) for row in plan_state.get("risks", ()) if str(row.get("risk_id", "")).strip())
        )

        architecture_graph = self.architecture.graph
        architecture_components = tuple(
            component
            for component in architecture_graph.components()
            if self._status_value(getattr(component, "status", "active")) not in {"removed", "superseded"}
        )
        active_component_ids = {component.component_id for component in architecture_components}
        architecture_interfaces = tuple(
            interface
            for interface in architecture_graph.interfaces()
            if interface.producer_component_id in active_component_ids
        )

        integration_graph = self.integration.graph
        integration_candidates = tuple(
            candidate
            for candidate in integration_graph.candidates()
            if self._status_value(getattr(candidate, "status", "proposed")) not in {"rejected", "superseded"}
        )
        integration_component_refs = tuple(
            sorted(
                {
                    str(ref)
                    for candidate in integration_candidates
                    for ref in getattr(candidate, "changed_component_refs", ())
                    if str(ref).strip()
                }
            )
        )

        return GoalDesignStateBundle(
            requirements=RequirementsState(
                state=self._graph_plane_state(requirements_graph),
                active_requirement_ids=active_requirements,
                acceptance_proof_refs=acceptance_refs,
            ),
            planning=PlanningState(
                state=self._graph_plane_state(planning_graph),
                requirement_refs=planned_requirement_refs,
                planned_component_ids=(),
                risk_refs=risk_refs,
            ),
            architecture=ArchitectureState(
                state=self._graph_plane_state(architecture_graph),
                component_ids=tuple(sorted(active_component_ids)),
                interface_ids=tuple(sorted(interface.interface_id for interface in architecture_interfaces)),
                invariant_ids=(),
            ),
            integration=IntegrationState(
                state=self._graph_plane_state(integration_graph),
                component_refs=integration_component_refs,
                bound_snapshot_digest=None,
                rollback_refs=(),
            ),
            context=ContextState(
                state=self._context_plane_state(),
                component_refs=(),
                bound_snapshot_digest=None,
                stale_warnings=(),
            ),
        )

    def freeze(self) -> GoalDesignSnapshot:
        bundle = self.observe()
        snapshot = self.authority.freeze_snapshot(bundle.version_vector)
        event = self.ledger.record_snapshot(snapshot)
        self._snapshot_events[snapshot.digest] = event.event_id
        return snapshot

    def _ensure_snapshot_event(self, snapshot: GoalDesignSnapshot) -> str:
        event_id = self._snapshot_events.get(snapshot.digest)
        if event_id is not None:
            return event_id
        event = self.ledger.record_snapshot(snapshot)
        self._snapshot_events[snapshot.digest] = event.event_id
        return event.event_id

    def admit(
        self,
        *,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
        selected_option_id: str,
        snapshot: GoalDesignSnapshot,
        proof_obligations: Sequence[ProofObligation] = (),
        uncertainties: Sequence[UncertaintyItem] = (),
    ) -> DecisionReceipt:
        bundle = self.observe()
        receipt = self.authority.admit_decision(
            goal=goal,
            scenarios=scenarios,
            options=options,
            selected_option_id=selected_option_id,
            snapshot=snapshot,
            current_vector=bundle.version_vector,
            proof_obligations=proof_obligations,
            uncertainties=uncertainties,
            traceability=bundle.traceability,
        )
        selected = next(option for option in options if option.option_id == selected_option_id)
        dependencies = tuple(sorted(set(selected.requirement_refs) | set(selected.component_refs)))
        snapshot_event_id = self._ensure_snapshot_event(snapshot)
        decision_event = self.ledger.record_decision(receipt, parent_ids=(snapshot_event_id,))
        self.decisions.register(
            receipt,
            dependency_refs=dependencies,
            authority_event_id=decision_event.event_id,
        )
        return receipt

    def analyze_change(self, change: GoalDesignChangeSet) -> GoalDesignImpactReport:
        """Compute downstream transitive impact using the live D authority graphs."""

        requirements = set(change.requirement_refs)
        plans = set(change.plan_refs)
        architecture_seeds = set(change.architecture_refs)
        candidates = set(change.integration_candidate_refs)

        planning_nodes = {node.node_id: node for node in self.planning.graph.nodes()}
        components = {component.component_id: component for component in self.architecture.graph.components()}
        interfaces = {interface.interface_id: interface for interface in self.architecture.graph.interfaces()}
        edges = tuple(self.architecture.graph.edges())
        integration_candidates = {candidate.candidate_id: candidate for candidate in self.integration.graph.candidates()}

        affected_plans = {ref for ref in plans if ref in planning_nodes}
        affected_components = {ref for ref in architecture_seeds if ref in components}
        affected_interfaces = {ref for ref in architecture_seeds if ref in interfaces}
        affected_candidates = {ref for ref in candidates if ref in integration_candidates}
        reasons: set[str] = set()

        changed = True
        while changed:
            before = (
                len(affected_plans),
                len(affected_components),
                len(affected_interfaces),
                len(affected_candidates),
            )

            for node in planning_nodes.values():
                if requirements.intersection(getattr(node, "requirement_refs", ())):
                    if node.node_id not in affected_plans:
                        reasons.add(f"plan {node.node_id} traces a changed requirement")
                    affected_plans.add(node.node_id)

            for component in components.values():
                if requirements.intersection(getattr(component, "requirement_refs", ())):
                    if component.component_id not in affected_components:
                        reasons.add(f"component {component.component_id} traces a changed requirement")
                    affected_components.add(component.component_id)
                if affected_plans.intersection(getattr(component, "plan_refs", ())):
                    if component.component_id not in affected_components:
                        reasons.add(f"component {component.component_id} implements an affected plan node")
                    affected_components.add(component.component_id)

            # Dependency edges are directional: source depends on target. A
            # changed target can invalidate its source/consumer, not vice versa.
            for edge in edges:
                if edge.target_component_id in affected_components and edge.source_component_id not in affected_components:
                    affected_components.add(edge.source_component_id)
                    reasons.add(
                        f"component {edge.source_component_id} depends on affected component {edge.target_component_id}"
                    )

            for interface in interfaces.values():
                consumers = set(getattr(interface, "consumer_scope", ()))
                if interface.producer_component_id in affected_components:
                    if interface.interface_id not in affected_interfaces:
                        reasons.add(f"interface {interface.interface_id} is produced by an affected component")
                    affected_interfaces.add(interface.interface_id)
                if interface.interface_id in affected_interfaces:
                    for consumer in consumers.intersection(components):
                        if consumer not in affected_components:
                            reasons.add(f"component {consumer} consumes affected interface {interface.interface_id}")
                        affected_components.add(consumer)

            for candidate in integration_candidates.values():
                impacted = (
                    bool(requirements.intersection(getattr(candidate, "requirement_refs", ())))
                    or bool(affected_plans.intersection(getattr(candidate, "plan_refs", ())))
                    or bool(affected_components.intersection(getattr(candidate, "changed_component_refs", ())))
                    or bool(affected_interfaces.intersection(getattr(candidate, "changed_interface_refs", ())))
                    or bool(affected_candidates.intersection(getattr(candidate, "dependency_candidate_ids", ())))
                )
                if impacted:
                    if candidate.candidate_id not in affected_candidates:
                        reasons.add(f"integration candidate {candidate.candidate_id} depends on affected authority state")
                    affected_candidates.add(candidate.candidate_id)

            after = (
                len(affected_plans),
                len(affected_components),
                len(affected_interfaces),
                len(affected_candidates),
            )
            changed = after != before

        context_invalidated = bool(
            requirements
            or plans
            or architecture_seeds
            or candidates
            or change.context_refs
            or affected_plans
            or affected_components
            or affected_interfaces
            or affected_candidates
        )
        if context_invalidated:
            reasons.add("compiled Goal/Design context must be revalidated after authority impact")

        payload = {
            "changed_requirement_refs": sorted(requirements),
            "changed_plan_refs": sorted(plans),
            "changed_architecture_refs": sorted(architecture_seeds),
            "changed_candidate_refs": sorted(candidates),
            "affected_plan_refs": sorted(affected_plans),
            "affected_component_refs": sorted(affected_components),
            "affected_interface_refs": sorted(affected_interfaces),
            "affected_candidate_refs": sorted(affected_candidates),
            "context_invalidated": context_invalidated,
            "reasons": sorted(reasons),
        }
        return GoalDesignImpactReport(
            changed_requirement_refs=tuple(payload["changed_requirement_refs"]),
            changed_plan_refs=tuple(payload["changed_plan_refs"]),
            changed_architecture_refs=tuple(payload["changed_architecture_refs"]),
            changed_candidate_refs=tuple(payload["changed_candidate_refs"]),
            affected_plan_refs=tuple(payload["affected_plan_refs"]),
            affected_component_refs=tuple(payload["affected_component_refs"]),
            affected_interface_refs=tuple(payload["affected_interface_refs"]),
            affected_candidate_refs=tuple(payload["affected_candidate_refs"]),
            context_invalidated=context_invalidated,
            reasons=tuple(payload["reasons"]),
            digest=stable_digest({"goal_design_impact": payload}),
        )

    def _record_invalidation(self, record: DecisionAuthorityRecord, reasons: Sequence[str]) -> None:
        parent_ids = (record.authority_event_id,) if record.authority_event_id else ()
        self.ledger.record_invalidation(
            receipt_id=record.receipt.receipt_id,
            snapshot_digest=record.snapshot_digest,
            reasons=tuple(str(reason) for reason in reasons),
            parent_ids=parent_ids,
        )

    def invalidate_impacted_decisions(self, report: GoalDesignImpactReport) -> tuple[str, ...]:
        impacted = set(report.affected_refs)
        invalidated: list[str] = []
        for record in self.decisions.active():
            overlap = sorted(impacted.intersection(record.dependency_refs))
            if not overlap:
                continue
            reasons = ("authority dependency impact: " + ", ".join(overlap),)
            self.decisions.mark_stale(record.receipt.receipt_id, reasons)
            self._record_invalidation(record, reasons)
            invalidated.append(record.receipt.receipt_id)
        return tuple(sorted(invalidated))

    def revalidate_decisions(self) -> tuple[str, ...]:
        current = self.observe().version_vector
        stale: list[str] = []
        for record in self.decisions.active():
            vector = GoalDesignVersionVector(**dict(record.receipt.version_vector))
            snapshot = GoalDesignSnapshot(version_vector=vector, digest=record.snapshot_digest)
            report = self.authority.verify_snapshot(snapshot, current)
            blockers = tuple(issue.message for issue in report.issues if issue.blocking)
            if not blockers:
                continue
            self.decisions.mark_stale(record.receipt.receipt_id, blockers)
            self._record_invalidation(record, blockers)
            stale.append(record.receipt.receipt_id)
        return tuple(sorted(stale))

    def guard_integration(self, candidate_id: str, *, snapshot: GoalDesignSnapshot) -> IntegrationGuardReceipt:
        bundle = self.observe()
        snapshot_report = self.authority.verify_snapshot(snapshot, bundle.version_vector)
        blockers = [issue.message for issue in snapshot_report.issues if issue.blocking]
        candidate = self.integration.graph.get(candidate_id)
        candidate_status = self._status_value(getattr(candidate, "status", "proposed"))
        if candidate_status in {"rejected", "superseded"}:
            blockers.append(f"integration candidate is terminal and cannot be admitted: {candidate_status}")

        current_architecture_version = int(self.architecture.graph.version)
        if int(candidate.architecture_version_expected) != current_architecture_version:
            blockers.append(
                "architecture version is stale for integration candidate: "
                f"expected {candidate.architecture_version_expected}, current {current_architecture_version}"
            )

        dependency_refs: set[str] = set()
        for ref in getattr(candidate, "requirement_refs", ()):
            dependency_refs.add(str(ref))
            try:
                node = self.requirements.graph.get(ref)
            except KeyError:
                blockers.append(f"integration candidate references unknown requirement {ref}")
                continue
            if self._status_value(getattr(node, "status", "active")) != "active":
                blockers.append(f"integration candidate references non-active requirement {ref}")

        for ref in getattr(candidate, "plan_refs", ()):
            dependency_refs.add(str(ref))
            try:
                node = self.planning.graph.get(ref)
            except KeyError:
                blockers.append(f"integration candidate references unknown plan node {ref}")
                continue
            if self._status_value(getattr(node, "status", "active")) == "superseded":
                blockers.append(f"integration candidate references superseded plan node {ref}")

        for ref in getattr(candidate, "changed_component_refs", ()):
            dependency_refs.add(str(ref))
            try:
                component = self.architecture.graph.get_component(ref)
            except KeyError:
                blockers.append(f"integration candidate references unknown architecture component {ref}")
                continue
            if self._status_value(getattr(component, "status", "active")) in {"removed", "superseded"}:
                blockers.append(f"integration candidate references inactive architecture component {ref}")

        for ref in getattr(candidate, "changed_interface_refs", ()):
            dependency_refs.add(str(ref))
            try:
                interface = self.architecture.graph.get_interface(ref)
            except KeyError:
                blockers.append(f"integration candidate references unknown architecture interface {ref}")
                continue
            try:
                producer = self.architecture.graph.get_component(interface.producer_component_id)
            except KeyError:
                blockers.append(
                    f"integration interface {ref} has unknown producer {interface.producer_component_id}"
                )
                continue
            if self._status_value(getattr(producer, "status", "active")) in {"removed", "superseded"}:
                blockers.append(f"integration interface {ref} is produced by inactive component")

        if blockers:
            raise CoherenceError("Goal/Design integration guard blocked: " + "; ".join(blockers))

        payload = {
            "candidate_id": candidate.candidate_id,
            "snapshot_digest": snapshot.digest,
            "architecture_version": current_architecture_version,
            "dependency_refs": sorted(dependency_refs),
        }
        return IntegrationGuardReceipt(
            candidate_id=candidate.candidate_id,
            snapshot_digest=snapshot.digest,
            architecture_version=current_architecture_version,
            dependency_refs=tuple(payload["dependency_refs"]),
            digest=stable_digest({"goal_design_integration_guard": payload}),
        )

    def bind_context(self, capsule: Any, *, snapshot: GoalDesignSnapshot) -> ContextBindingReceipt:
        bundle = self.observe()
        snapshot_report = self.authority.verify_snapshot(snapshot, bundle.version_vector)
        blockers = [issue.message for issue in snapshot_report.issues if issue.blocking]

        artifacts = {str(name): value for name, value in getattr(capsule, "authoritative_artifacts", ())}
        expected = {
            "master-plan": int(self.planning.graph.version),
            "requirements": int(self.requirements.graph.version),
            "architecture-graph": int(self.architecture.graph.version),
            "integration-state": int(self.integration.graph.version),
        }
        for artifact_name, expected_version in expected.items():
            actual = artifacts.get(artifact_name)
            if actual is None:
                blockers.append(f"context is missing authoritative artifact {artifact_name}")
                continue
            try:
                actual_version = int(actual)
            except (TypeError, ValueError):
                blockers.append(f"context artifact {artifact_name} has non-version value {actual!r}")
                continue
            if actual_version != expected_version:
                blockers.append(
                    f"context {artifact_name} is stale: expected {expected_version}, observed {actual_version}"
                )

        if blockers:
            raise CoherenceError("Goal/Design context binding blocked: " + "; ".join(blockers))

        artifact_versions = tuple(sorted((name, int(artifacts[name])) for name in expected))
        payload = {
            "snapshot_digest": snapshot.digest,
            "artifact_versions": artifact_versions,
            "context_policy_token": bundle.context.state.token,
        }
        return ContextBindingReceipt(
            snapshot_digest=snapshot.digest,
            artifact_versions=artifact_versions,
            context_policy_token=bundle.context.state.token,
            digest=stable_digest({"goal_design_context_binding": payload}),
        )


__all__ = [
    "ContextBindingReceipt",
    "DecisionAuthorityIndex",
    "DecisionAuthorityRecord",
    "DecisionLifecycle",
    "GoalDesignChangeSet",
    "GoalDesignImpactReport",
    "GoalDesignRuntime",
    "IntegrationGuardReceipt",
]
