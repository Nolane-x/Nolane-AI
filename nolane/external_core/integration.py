from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.compatibility import CompatibilityAssessment, CompatibilityClass
from nolane.external_core.integration_admission import (
    AdmissionDisposition,
    AdmissionSubjectKind,
    AdmittedAuthorityGraph,
    AdmittedHandoff,
    AdmittedManifest,
    AdmittedWorkTrace,
    CanonicalAdmissionContext,
    ProtocolAdmissionReceipt,
    admit_authority_graph_state,
    admit_handoff_state,
    admit_manifest_state,
    admit_work_trace_state,
    canonical_frontier_digest,
)
from nolane.external_core.integration_admission_bundle import (
    AdmissionAuditFinding,
    CanonicalAdmissionAuditReport,
    CanonicalAdmissionBundle,
    build_canonical_admission_bundle,
    build_canonical_admission_context,
    run_canonical_admission_audit,
)
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
from nolane.external_core.integration_scoped_revalidation import (
    RevalidationChallenge,
    RevalidationCompletionReceipt,
    RevalidationScope,
    ScopedRevalidationAssessment,
    ScopedRevalidationEvidenceBinding,
    assess_scoped_revalidation,
    build_revalidation_challenges,
    build_revalidation_scope,
    challenge_subject_digest,
)

COMPONENT_ID = "external.integration"
COMPONENT_VERSION = "0.0.8"
MIGRATED_FROM = "cogcoder.organization.integration"


def _canonical_state_record(
    state: object,
    expected_keys: tuple[str, ...],
    label: str,
) -> Mapping[str, Any]:
    if type(state) is not dict or set(state) != set(expected_keys):
        raise ValueError(f"{label} must use canonical serialized state")
    return state


def _canonical_state_list(value: object, label: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f"{label} must use canonical serialized state")
    return value


def _exact_string(value: object, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{label} must be an exact string")
    return value


def _canonical_string_list(value: object, label: str) -> tuple[str, ...]:
    return tuple(
        _exact_string(item, label)
        for item in _canonical_state_list(value, label)
    )


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
        state = _canonical_state_record(
            state,
            (
                "candidate_id",
                "producer_agent_id",
                "task_refs",
                "plan_refs",
                "requirement_refs",
                "architecture_version_expected",
                "changed_component_refs",
                "changed_interface_refs",
                "dependency_candidate_ids",
                "conflicts_with",
                "compatibility_assessments",
                "verification_evidence_refs",
                "status",
            ),
            "integration candidate",
        )
        architecture_version_expected = state["architecture_version_expected"]
        if type(architecture_version_expected) is not int or architecture_version_expected < 0:
            raise ValueError("integration candidate architecture version must be a non-negative exact int")
        compatibility_rows = _canonical_state_list(
            state["compatibility_assessments"],
            "integration candidate compatibility assessments",
        )
        return cls(
            _exact_string(state["candidate_id"], "integration candidate identity"),
            _exact_string(state["producer_agent_id"], "integration candidate producer identity"),
            _canonical_string_list(state["task_refs"], "integration candidate task reference"),
            _canonical_string_list(state["plan_refs"], "integration candidate plan reference"),
            _canonical_string_list(state["requirement_refs"], "integration candidate requirement reference"),
            architecture_version_expected,
            _canonical_string_list(state["changed_component_refs"], "integration candidate component reference"),
            _canonical_string_list(state["changed_interface_refs"], "integration candidate interface reference"),
            _canonical_string_list(state["dependency_candidate_ids"], "integration candidate dependency identity"),
            _canonical_string_list(state["conflicts_with"], "integration candidate conflict identity"),
            tuple(CompatibilityAssessment.from_state(row) for row in compatibility_rows),
            _canonical_string_list(state["verification_evidence_refs"], "integration candidate verification evidence reference"),
            ChangeCandidateStatus(_exact_string(state["status"], "integration candidate status")),
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
        state = _canonical_state_record(
            state,
            (
                "receipt_id",
                "candidate_id",
                "actor_agent_id",
                "status",
                "evidence_refs",
                "architecture_version",
                "digest",
            ),
            "integration receipt",
        )
        architecture_version = state["architecture_version"]
        if type(architecture_version) is not int or architecture_version < 0:
            raise ValueError("integration receipt architecture version must be a non-negative exact int")
        return cls(
            _exact_string(state["receipt_id"], "integration receipt identity"),
            _exact_string(state["candidate_id"], "integration receipt candidate identity"),
            _exact_string(state["actor_agent_id"], "integration receipt actor identity"),
            ChangeCandidateStatus(_exact_string(state["status"], "integration receipt status")),
            _canonical_string_list(state["evidence_refs"], "integration receipt evidence reference"),
            architecture_version,
            _exact_string(state["digest"], "integration receipt digest"),
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
        candidate_key = _exact_string(candidate_id, "integration candidate identity")
        try:
            return self._candidates[candidate_key]
        except KeyError as exc:
            raise KeyError(f"unknown integration candidate: {candidate_key}") from exc

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
        state = _canonical_state_record(
            state,
            ("version", "candidates"),
            "integration graph",
        )
        serialized_candidates = _canonical_state_list(
            state["candidates"],
            "integration graph candidates",
        )
        graph = cls()
        candidates = tuple(ChangeCandidate.from_state(value) for value in serialized_candidates)
        candidate_ids: set[str] = set()
        for candidate in candidates:
            if candidate.candidate_id in candidate_ids:
                raise ValueError(f"duplicate integration candidate: {candidate.candidate_id}")
            candidate_ids.add(candidate.candidate_id)
        candidate_order = [candidate.candidate_id for candidate in candidates]
        if candidate_order != sorted(candidate_order):
            raise ValueError("integration candidate order is not canonical")
        graph._candidates = {candidate.candidate_id: candidate for candidate in candidates}
        graph._validate(graph._candidates)
        version = state["version"]
        if type(version) is not int or version < 0:
            raise ValueError("integration graph version must be a non-negative exact int")
        graph._version = version
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
        if candidate.status is not ChangeCandidateStatus.PROPOSED:
            raise ValueError("new integration candidate status must be proposed")
        if replace:
            existing = self.graph.get(candidate.candidate_id)
            if existing.status is not ChangeCandidateStatus.PROPOSED:
                raise ValueError(
                    f"integration candidate cannot replace {existing.status.value} state"
                )
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
        candidate_key = _exact_string(candidate_id, "integration candidate identity")
        if type(evidence_refs) is not tuple:
            raise ValueError("integration evidence refs must be a canonical tuple")
        evidence = tuple(
            _exact_string(value, "integration evidence reference")
            for value in evidence_refs
        )
        if not evidence or any(not ref.strip() for ref in evidence):
            raise ValueError("integration acceptance requires non-empty evidence refs")
        candidate = self.graph.get(candidate_key)
        if candidate.status not in {
            ChangeCandidateStatus.PROPOSED,
            ChangeCandidateStatus.READY,
        }:
            raise ValueError("integration candidate status transition is not permitted")
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
            "candidate_id": candidate_key,
            "actor_agent_id": actor_agent_id,
            "status": ChangeCandidateStatus.INTEGRATED.value,
            "evidence_refs": list(evidence),
            "architecture_version": self.architecture.graph.version,
        }
        digest = canonical_digest(payload)
        receipt = IntegrationReceipt(
            f"integration-{self._receipt_counter:08d}",
            candidate_key,
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
        state = _canonical_state_record(
            state,
            ("graph", "receipt_counter", "receipts"),
            "integration control plane",
        )
        graph = IntegrationGraph.from_state(state["graph"])
        serialized_receipts = _canonical_state_list(
            state["receipts"],
            "integration receipts",
        )
        receipts = tuple(IntegrationReceipt.from_state(value) for value in serialized_receipts)

        receipt_ids: set[str] = set()
        for receipt in receipts:
            if receipt.receipt_id in receipt_ids:
                raise ValueError(f"duplicate integration receipt: {receipt.receipt_id}")
            receipt_ids.add(receipt.receipt_id)

        receipt_counter = state["receipt_counter"]
        if type(receipt_counter) is not int or receipt_counter < 0:
            raise ValueError("integration receipt counter must be a non-negative exact int")
        if receipt_counter != len(receipts):
            raise ValueError("non-canonical integration receipt counter")

        expected_receipt_ids = {
            f"integration-{index:08d}" for index in range(1, receipt_counter + 1)
        }
        if receipt_ids != expected_receipt_ids:
            raise ValueError("integration receipt id sequence is not canonical")
        receipt_order = [receipt.receipt_id for receipt in receipts]
        if receipt_order != sorted(receipt_order):
            raise ValueError("integration receipt order is not canonical")

        receipt_candidate_ids: set[str] = set()
        for receipt in receipts:
            if receipt.status is not ChangeCandidateStatus.INTEGRATED:
                raise ValueError("integration receipt status must be integrated")
            if not receipt.evidence_refs or any(not ref.strip() for ref in receipt.evidence_refs):
                raise ValueError("integration receipt evidence must be non-empty")
            try:
                registry.get(receipt.actor_agent_id)
            except KeyError as exc:
                raise ValueError("integration receipt actor is unknown") from exc
            try:
                candidate = graph.get(receipt.candidate_id)
            except KeyError as exc:
                raise ValueError("integration receipt candidate is unknown") from exc
            if candidate.status is not ChangeCandidateStatus.INTEGRATED:
                raise ValueError("integration receipt candidate must be integrated")
            if receipt.candidate_id in receipt_candidate_ids:
                raise ValueError("integration candidate has multiple receipts")
            receipt_candidate_ids.add(receipt.candidate_id)
            if receipt.architecture_version != candidate.architecture_version_expected:
                raise ValueError(
                    "integration receipt architecture version must match candidate architecture version"
                )
            if receipt.architecture_version > architecture.graph.version:
                raise ValueError("integration receipt architecture version exceeds current architecture")

            receipt_index = int(receipt.receipt_id.removeprefix("integration-"))
            expected_digest = canonical_digest(
                {
                    "receipt_index": receipt_index,
                    "candidate_id": receipt.candidate_id,
                    "actor_agent_id": receipt.actor_agent_id,
                    "status": receipt.status.value,
                    "evidence_refs": list(receipt.evidence_refs),
                    "architecture_version": receipt.architecture_version,
                }
            )
            if receipt.digest != expected_digest:
                raise ValueError("integration receipt digest mismatch")

        for candidate in graph.candidates():
            if (
                candidate.status is ChangeCandidateStatus.INTEGRATED
                and candidate.candidate_id not in receipt_candidate_ids
            ):
                raise ValueError("integrated candidate requires exactly one integration receipt")

        plane = cls(
            registry=registry,
            authority=authority,
            architecture=architecture,
            graph=graph,
            receipts=receipts,
        )
        plane._receipt_counter = receipt_counter
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
    "RevalidationChallenge",
    "RevalidationCompletionReceipt",
    "RevalidationScope",
    "ScopedRevalidationAssessment",
    "ScopedRevalidationEvidenceBinding",
    "assess_scoped_revalidation",
    "build_revalidation_challenges",
    "build_revalidation_scope",
    "challenge_subject_digest",
    "AdmissionDisposition",
    "AdmissionSubjectKind",
    "CanonicalAdmissionContext",
    "ProtocolAdmissionReceipt",
    "AdmittedManifest",
    "AdmittedAuthorityGraph",
    "AdmittedHandoff",
    "AdmittedWorkTrace",
    "admit_manifest_state",
    "admit_authority_graph_state",
    "admit_handoff_state",
    "admit_work_trace_state",
    "canonical_frontier_digest",
    "CanonicalAdmissionBundle",
    "AdmissionAuditFinding",
    "CanonicalAdmissionAuditReport",
    "build_canonical_admission_context",
    "build_canonical_admission_bundle",
    "run_canonical_admission_audit",
]
