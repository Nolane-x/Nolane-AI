from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.compatibility import CompatibilityAssessment, CompatibilityClass
from nolane.external_core.integration_evolution import (
    ComponentEvolutionDelta,
    EvolutionCompatibilityDisposition,
    EvolutionCompatibilityQualification,
    IntegrationImpactClosure,
    IntegrationImpactReason,
    build_integration_impact_closure,
    qualify_component_evolution,
)
from nolane.external_core.integration_revalidation import (
    ComponentRevalidationRequirement,
    RevalidationAssessment,
    RevalidationDisposition,
    RevalidationEvidenceBinding,
    RevalidationPlan,
    assess_revalidation,
    build_revalidation_plan,
)

COMPONENT_ID = "external.integration"
COMPONENT_VERSION = "0.0.2"
MIGRATED_FROM = "cogcoder.organization.integration"


class ChangeCandidateStatus(str, Enum):
    PROPOSED = "proposed"
    READY = "ready"
    BLOCKED = "blocked"
    INTEGRATED = "integrated"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class ChangeCandidate:
    candidate_id: str
    producer_agent_id: str
    task_refs: tuple[str, ...]
    plan_refs: tuple[str, ...]
    requirement_refs: tuple[str, ...]
    architecture_version_expected: int
    changed_component_refs: tuple[str, ...]
    changed_interface_refs: tuple[str, ...]
    dependency_candidate_ids: tuple[str, ...] = ()
    conflicts_with: tuple[str, ...] = ()
    compatibility_assessments: tuple[CompatibilityAssessment, ...] = ()
    verification_evidence_refs: tuple[str, ...] = ()
    status: ChangeCandidateStatus = ChangeCandidateStatus.PROPOSED

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.producer_agent_id.strip():
            raise ValueError("candidate identity and producer must be non-empty")
        if self.architecture_version_expected < 0:
            raise ValueError("expected architecture version must be non-negative")

    def to_state(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "producer_agent_id": self.producer_agent_id,
            "task_refs": list(self.task_refs),
            "plan_refs": list(self.plan_refs),
            "requirement_refs": list(self.requirement_refs),
            "architecture_version_expected": self.architecture_version_expected,
            "changed_component_refs": list(self.changed_component_refs),
            "changed_interface_refs": list(self.changed_interface_refs),
            "dependency_candidate_ids": list(self.dependency_candidate_ids),
            "conflicts_with": list(self.conflicts_with),
            "compatibility_assessments": [x.to_state() for x in self.compatibility_assessments],
            "verification_evidence_refs": list(self.verification_evidence_refs),
            "status": self.status.value,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ChangeCandidate":
        return cls(
            str(state["candidate_id"]),
            str(state["producer_agent_id"]),
            tuple(str(x) for x in state.get("task_refs", ())),
            tuple(str(x) for x in state.get("plan_refs", ())),
            tuple(str(x) for x in state.get("requirement_refs", ())),
            int(state["architecture_version_expected"]),
            tuple(str(x) for x in state.get("changed_component_refs", ())),
            tuple(str(x) for x in state.get("changed_interface_refs", ())),
            tuple(str(x) for x in state.get("dependency_candidate_ids", ())),
            tuple(str(x) for x in state.get("conflicts_with", ())),
            tuple(CompatibilityAssessment.from_state(x) for x in state.get("compatibility_assessments", ())),
            tuple(str(x) for x in state.get("verification_evidence_refs", ())),
            ChangeCandidateStatus(str(state.get("status", ChangeCandidateStatus.PROPOSED.value))),
        )


@dataclass(frozen=True, slots=True)
class IntegrationReceipt:
    receipt_id: str
    candidate_id: str
    actor_agent_id: str
    status: ChangeCandidateStatus
    evidence_refs: tuple[str, ...]
    architecture_version: int
    digest: str

    def to_state(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "candidate_id": self.candidate_id,
            "actor_agent_id": self.actor_agent_id,
            "status": self.status.value,
            "evidence_refs": list(self.evidence_refs),
            "architecture_version": self.architecture_version,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "IntegrationReceipt":
        return cls(
            str(state["receipt_id"]),
            str(state["candidate_id"]),
            str(state["actor_agent_id"]),
            ChangeCandidateStatus(str(state["status"])),
            tuple(str(x) for x in state.get("evidence_refs", ())),
            int(state["architecture_version"]),
            str(state["digest"]),
        )


class IntegrationGraph:
    def __init__(self) -> None:
        self._candidates: dict[str, ChangeCandidate] = {}
        self._version = 0

    @property
    def version(self) -> int:
        return self._version

    def candidates(self) -> tuple[ChangeCandidate, ...]:
        return tuple(self._candidates[k] for k in sorted(self._candidates))

    def get(self, candidate_id: str) -> ChangeCandidate:
        try:
            return self._candidates[str(candidate_id)]
        except KeyError as exc:
            raise KeyError(f"unknown integration candidate: {candidate_id}") from exc

    @staticmethod
    def _validate(rows: Mapping[str, ChangeCandidate]) -> None:
        for row in rows.values():
            for dep in row.dependency_candidate_ids:
                if dep not in rows:
                    raise ValueError(f"unknown integration candidate dependency: {dep}")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(key: str) -> None:
            if key in visiting:
                raise ValueError("integration candidate dependency cycle detected")
            if key in visited:
                return
            visiting.add(key)
            for dep in rows[key].dependency_candidate_ids:
                visit(dep)
            visiting.remove(key)
            visited.add(key)

        for key in sorted(rows):
            visit(key)

    def add(self, candidate: ChangeCandidate, *, replace_existing: bool = False) -> ChangeCandidate:
        if candidate.candidate_id in self._candidates and not replace_existing:
            raise ValueError(f"duplicate integration candidate: {candidate.candidate_id}")
        rows = dict(self._candidates)
        rows[candidate.candidate_id] = candidate
        self._validate(rows)
        self._candidates = rows
        self._version += 1
        return candidate

    def update(self, candidate: ChangeCandidate) -> ChangeCandidate:
        if candidate.candidate_id not in self._candidates:
            raise KeyError(f"unknown integration candidate: {candidate.candidate_id}")
        rows = dict(self._candidates)
        rows[candidate.candidate_id] = candidate
        self._validate(rows)
        self._candidates = rows
        self._version += 1
        return candidate

    def integration_order(self) -> tuple[str, ...]:
        indegree = {k: 0 for k in self._candidates}
        forward = {k: [] for k in self._candidates}
        for key, row in self._candidates.items():
            for dep in row.dependency_candidate_ids:
                indegree[key] += 1
                forward[dep].append(key)
        ready = sorted(k for k, degree in indegree.items() if degree == 0)
        order: list[str] = []
        while ready:
            key = ready.pop(0)
            order.append(key)
            for nxt in sorted(forward[key]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
                    ready.sort()
        return tuple(order)

    def to_state(self) -> dict[str, Any]:
        return {"version": self._version, "candidates": [x.to_state() for x in self.candidates()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "IntegrationGraph":
        graph = cls()
        graph._candidates = {
            x.candidate_id: x
            for x in (ChangeCandidate.from_state(v) for v in state.get("candidates", ()))
        }
        graph._validate(graph._candidates)
        graph._version = int(state.get("version", 0))
        if graph._version < len(graph._candidates):
            raise ValueError("non-canonical integration graph version")
        return graph


class IntegrationControlPlane:
    def __init__(
        self,
        *,
        registry: Any,
        authority: Any,
        architecture: Any,
        graph: IntegrationGraph | None = None,
        receipts: tuple[IntegrationReceipt, ...] = (),
    ) -> None:
        self.registry, self.authority, self.architecture = registry, authority, architecture
        self.graph = graph or IntegrationGraph()
        self._receipts: dict[str, IntegrationReceipt] = {x.receipt_id: x for x in receipts}
        self._receipt_counter = len(self._receipts)

    def add_candidate(
        self,
        *,
        actor_agent_id: str,
        candidate: ChangeCandidate,
        replace: bool = False,
    ) -> ChangeCandidate:
        self.registry.get(actor_agent_id)
        self.authority.require_write(actor_agent_id, "integration-state")
        self.registry.get(candidate.producer_agent_id)
        for ref in candidate.changed_component_refs:
            self.architecture.graph.get_component(ref)
        for ref in candidate.changed_interface_refs:
            self.architecture.graph.get_interface(ref)
        return self.graph.add(candidate, replace_existing=replace)

    def integrate(
        self,
        candidate_id: str,
        *,
        actor_agent_id: str,
        evidence_refs: tuple[str, ...],
    ) -> IntegrationReceipt:
        self.registry.get(actor_agent_id)
        self.authority.require_write(actor_agent_id, "integration-state")
        evidence = tuple(str(x) for x in evidence_refs if str(x).strip())
        if not evidence:
            raise ValueError("integration acceptance requires evidence")
        candidate = self.graph.get(candidate_id)
        if candidate.architecture_version_expected != self.architecture.graph.version:
            raise PermissionError("architecture version is stale for integration candidate")
        if not candidate.compatibility_assessments or any(
            (not row.integration_safe)
            or row.compatibility in {CompatibilityClass.UNKNOWN, CompatibilityClass.BREAKING}
            for row in candidate.compatibility_assessments
        ):
            raise PermissionError("compatibility evidence is insufficient for integration")
        if not candidate.verification_evidence_refs:
            raise PermissionError("verification evidence is required for integration")
        for dep in candidate.dependency_candidate_ids:
            if self.graph.get(dep).status is not ChangeCandidateStatus.INTEGRATED:
                raise PermissionError("integration dependency is not yet integrated")
        integrated_ids = {
            row.candidate_id
            for row in self.graph.candidates()
            if row.status is ChangeCandidateStatus.INTEGRATED
        }
        if integrated_ids.intersection(candidate.conflicts_with):
            raise PermissionError("integration conflict with already integrated candidate")
        updated = replace(candidate, status=ChangeCandidateStatus.INTEGRATED)
        self.graph.update(updated)
        self._receipt_counter += 1
        payload = {
            "receipt_index": self._receipt_counter,
            "candidate_id": candidate_id,
            "actor_agent_id": actor_agent_id,
            "status": ChangeCandidateStatus.INTEGRATED.value,
            "evidence_refs": list(evidence),
            "architecture_version": self.architecture.graph.version,
        }
        digest = canonical_digest(payload)
        receipt = IntegrationReceipt(
            f"integration-{self._receipt_counter:08d}",
            candidate_id,
            actor_agent_id,
            ChangeCandidateStatus.INTEGRATED,
            evidence,
            self.architecture.graph.version,
            digest,
        )
        self._receipts[receipt.receipt_id] = receipt
        return receipt

    def receipts(self) -> tuple[IntegrationReceipt, ...]:
        return tuple(self._receipts[k] for k in sorted(self._receipts))

    def to_state(self) -> dict[str, Any]:
        return {
            "graph": self.graph.to_state(),
            "receipt_counter": self._receipt_counter,
            "receipts": [x.to_state() for x in self.receipts()],
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: Any,
        authority: Any,
        architecture: Any,
        state: Mapping[str, Any],
    ) -> "IntegrationControlPlane":
        graph = IntegrationGraph.from_state(state.get("graph", {}))
        receipts = tuple(IntegrationReceipt.from_state(x) for x in state.get("receipts", ()))
        plane = cls(
            registry=registry,
            authority=authority,
            architecture=architecture,
            graph=graph,
            receipts=receipts,
        )
        plane._receipt_counter = int(state.get("receipt_counter", len(receipts)))
        if plane._receipt_counter < len(receipts):
            raise ValueError("non-canonical integration receipt counter")
        return plane


__all__ = [
    "ChangeCandidateStatus",
    "ChangeCandidate",
    "IntegrationReceipt",
    "IntegrationGraph",
    "IntegrationControlPlane",
    "ComponentEvolutionDelta",
    "EvolutionCompatibilityDisposition",
    "EvolutionCompatibilityQualification",
    "IntegrationImpactClosure",
    "IntegrationImpactReason",
    "build_integration_impact_closure",
    "qualify_component_evolution",
    "ComponentRevalidationRequirement",
    "RevalidationAssessment",
    "RevalidationDisposition",
    "RevalidationEvidenceBinding",
    "RevalidationPlan",
    "assess_revalidation",
    "build_revalidation_plan",
]
