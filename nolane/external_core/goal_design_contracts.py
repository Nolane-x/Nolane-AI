"""Typed contracts that connect the five Goal/Design authority planes."""
from __future__ import annotations

from dataclasses import dataclass

from .goal_design import (
    CoherenceIssue,
    CoherenceReport,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
    IssueSeverity,
    PlaneState,
    TraceabilityState,
)


@dataclass(frozen=True)
class RequirementsState:
    state: PlaneState
    active_requirement_ids: tuple[str, ...] = ()
    acceptance_proof_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanningState:
    state: PlaneState
    requirement_refs: tuple[str, ...] = ()
    planned_component_ids: tuple[str, ...] = ()
    risk_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArchitectureState:
    state: PlaneState
    component_ids: tuple[str, ...] = ()
    interface_ids: tuple[str, ...] = ()
    invariant_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntegrationState:
    state: PlaneState
    component_refs: tuple[str, ...] = ()
    bound_snapshot_digest: str | None = None
    rollback_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextState:
    state: PlaneState
    component_refs: tuple[str, ...] = ()
    bound_snapshot_digest: str | None = None
    stale_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class GoalDesignStateBundle:
    """Immutable observation bundle emitted by the five specialist authorities."""

    requirements: RequirementsState
    planning: PlanningState
    architecture: ArchitectureState
    integration: IntegrationState
    context: ContextState

    @property
    def version_vector(self) -> GoalDesignVersionVector:
        return GoalDesignVersionVector(
            requirements=self.requirements.state,
            planning=self.planning.state,
            architecture=self.architecture.state,
            integration=self.integration.state,
            context=self.context.state,
        )

    @property
    def traceability(self) -> TraceabilityState:
        return TraceabilityState(
            active_requirement_ids=self.requirements.active_requirement_ids,
            planned_requirement_ids=self.planning.requirement_refs,
            planned_component_ids=self.planning.planned_component_ids,
            architecture_component_ids=self.architecture.component_ids,
            integration_component_refs=self.integration.component_refs,
            context_component_refs=self.context.component_refs,
        )

    def coherence_report(self, authority: GoalDesignCoherencePlane, *, expected_snapshot_digest: str | None = None) -> CoherenceReport:
        issues = list(authority.coherence_report(self.traceability).issues)
        if expected_snapshot_digest:
            if self.integration.bound_snapshot_digest != expected_snapshot_digest:
                issues.append(CoherenceIssue(
                    "INTEGRATION_SNAPSHOT_MISMATCH",
                    "integration candidate is not bound to the current Goal/Design snapshot",
                    IssueSeverity.BLOCKER,
                    "integration",
                ))
            if self.context.bound_snapshot_digest != expected_snapshot_digest:
                issues.append(CoherenceIssue(
                    "CONTEXT_SNAPSHOT_MISMATCH",
                    "compiled context is not bound to the current Goal/Design snapshot",
                    IssueSeverity.BLOCKER,
                    "context",
                ))
        for warning in self.context.stale_warnings:
            issues.append(CoherenceIssue("STALE_CONTEXT_WARNING", warning, IssueSeverity.WARNING, "context"))
        return CoherenceReport(tuple(issues))
