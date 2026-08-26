from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from nolane.organization.events import EventKind
from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.requirements"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.requirements"


# Preserve the historical Part-I event wire schema. These semantic names are
# aliases over the accepted event value; requirements_action remains the
# discriminator carried in the payload until EventKind itself is refounded.
for _name in (
    "REQUIREMENT_AMBIGUITY",
    "REQUIREMENT_CHANGE_PROPOSED",
    "REQUIREMENT_CHANGED",
    "ACCEPTANCE_GAP",
):
    if not hasattr(EventKind, _name):
        setattr(EventKind, _name, EventKind.PLAN_CHANGE_PROPOSED)


class RequirementKind(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    CONSTRAINT = "constraint"
    SECURITY = "security"
    COMPATIBILITY = "compatibility"
    QUALITY = "quality"


class RequirementStatus(str, Enum):
    ACTIVE = "active"
    AMBIGUOUS = "ambiguous"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class AcceptanceCriterion:
    criterion_id: str
    statement: str
    verification_class: str = "behavioral"
    evidence_expectations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.criterion_id.strip() or not self.statement.strip():
            raise ValueError("acceptance criterion id and statement must be non-empty")

    def to_state(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "statement": self.statement,
            "verification_class": self.verification_class,
            "evidence_expectations": list(self.evidence_expectations),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AcceptanceCriterion":
        return cls(
            str(state["criterion_id"]),
            str(state["statement"]),
            str(state.get("verification_class", "behavioral")),
            tuple(str(x) for x in state.get("evidence_expectations", ())),
        )


@dataclass(frozen=True, slots=True)
class RequirementNode:
    requirement_id: str
    title: str
    kind: RequirementKind
    description: str
    dependencies: tuple[str, ...] = ()
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = ()
    priority: int = 50
    status: RequirementStatus = RequirementStatus.ACTIVE

    def __post_init__(self) -> None:
        if not self.requirement_id.strip() or not self.title.strip() or not self.description.strip():
            raise ValueError("requirement identity, title and description must be non-empty")
        if not 0 <= int(self.priority) <= 100:
            raise ValueError("requirement priority must be in [0,100]")
        if len({x.criterion_id for x in self.acceptance_criteria}) != len(self.acceptance_criteria):
            raise ValueError("duplicate acceptance criterion id")

    def to_state(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "title": self.title,
            "kind": self.kind.value,
            "description": self.description,
            "dependencies": list(self.dependencies),
            "acceptance_criteria": [x.to_state() for x in self.acceptance_criteria],
            "priority": self.priority,
            "status": self.status.value,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "RequirementNode":
        return cls(
            requirement_id=str(state["requirement_id"]),
            title=str(state["title"]),
            kind=RequirementKind(str(state["kind"])),
            description=str(state["description"]),
            dependencies=tuple(str(x) for x in state.get("dependencies", ())),
            acceptance_criteria=tuple(AcceptanceCriterion.from_state(x) for x in state.get("acceptance_criteria", ())),
            priority=int(state.get("priority", 50)),
            status=RequirementStatus(str(state.get("status", RequirementStatus.ACTIVE.value))),
        )


@dataclass(frozen=True, slots=True)
class RequirementRevision:
    version: int
    parent_version: int | None
    actor_agent_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    changed_requirement_ids: tuple[str, ...]
    graph_digest: str

    def to_state(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "parent_version": self.parent_version,
            "actor_agent_id": self.actor_agent_id,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "changed_requirement_ids": list(self.changed_requirement_ids),
            "graph_digest": self.graph_digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "RequirementRevision":
        return cls(
            int(state["version"]),
            None if state.get("parent_version") is None else int(state["parent_version"]),
            str(state["actor_agent_id"]),
            str(state["reason"]),
            tuple(str(x) for x in state.get("evidence_refs", ())),
            tuple(str(x) for x in state.get("changed_requirement_ids", ())),
            str(state["graph_digest"]),
        )


class RequirementGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, RequirementNode] = {}
        self._revisions: list[RequirementRevision] = []

    @property
    def version(self) -> int:
        return len(self._revisions)

    @property
    def digest(self) -> str:
        return canonical_digest({"version": self.version, "nodes": [x.to_state() for x in self.nodes()]})

    def nodes(self) -> tuple[RequirementNode, ...]:
        return tuple(self._nodes[k] for k in sorted(self._nodes))

    def get(self, requirement_id: str) -> RequirementNode:
        try:
            return self._nodes[str(requirement_id)]
        except KeyError as exc:
            raise KeyError(f"unknown requirement: {requirement_id}") from exc

    def active_ids(self) -> tuple[str, ...]:
        return tuple(x.requirement_id for x in self.nodes() if x.status is RequirementStatus.ACTIVE)

    @staticmethod
    def _validate(nodes: Mapping[str, RequirementNode]) -> None:
        for node in nodes.values():
            for dep in node.dependencies:
                if dep not in nodes:
                    raise ValueError(f"unknown requirement dependency: {dep}")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(key: str) -> None:
            if key in visiting:
                raise ValueError("requirement dependency cycle detected")
            if key in visited:
                return
            visiting.add(key)
            for dep in nodes[key].dependencies:
                visit(dep)
            visiting.remove(key)
            visited.add(key)

        for key in sorted(nodes):
            visit(key)

    def apply(
        self,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
        upserts: Iterable[RequirementNode],
    ) -> RequirementRevision:
        reason = str(reason).strip()
        evidence = tuple(str(x).strip() for x in evidence_refs if str(x).strip())
        rows = tuple(upserts)
        if not reason or not evidence or not rows:
            raise ValueError("requirement revision requires reason, evidence and at least one mutation")

        candidate = dict(self._nodes)
        changed: list[str] = []
        for row in rows:
            candidate[row.requirement_id] = row
            changed.append(row.requirement_id)
        self._validate(candidate)

        next_version = self.version + 1
        graph_digest = canonical_digest(
            {"version": next_version, "nodes": [candidate[k].to_state() for k in sorted(candidate)]}
        )
        revision = RequirementRevision(
            next_version,
            self.version or None,
            str(actor_agent_id),
            reason,
            evidence,
            tuple(sorted(set(changed))),
            graph_digest,
        )
        self._nodes = candidate
        self._revisions.append(revision)
        return revision

    def revisions(self) -> tuple[RequirementRevision, ...]:
        return tuple(self._revisions)

    def to_state(self) -> dict[str, Any]:
        return {
            "nodes": [x.to_state() for x in self.nodes()],
            "revisions": [x.to_state() for x in self._revisions],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "RequirementGraph":
        graph = cls()
        graph._nodes = {
            x.requirement_id: x
            for x in (RequirementNode.from_state(v) for v in state.get("nodes", ()))
        }
        graph._validate(graph._nodes)
        graph._revisions = [RequirementRevision.from_state(v) for v in state.get("revisions", ())]
        for index, revision in enumerate(graph._revisions, 1):
            if revision.version != index:
                raise ValueError("non-canonical requirement revision sequence")
        if graph._revisions and graph._revisions[-1].graph_digest != graph.digest:
            raise ValueError("requirement graph digest mismatch")
        return graph


class RequirementsControlPlane:
    def __init__(
        self,
        *,
        registry: Any,
        authority: Any,
        ledger: Any,
        graph: RequirementGraph | None = None,
    ) -> None:
        self.registry = registry
        self.authority = authority
        self.ledger = ledger
        self.graph = graph or RequirementGraph()

    def apply_revision(
        self,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
        upserts: tuple[RequirementNode, ...],
    ) -> RequirementRevision:
        self.registry.get(actor_agent_id)
        self.authority.require_write(actor_agent_id, "requirements")
        revision = self.graph.apply(
            actor_agent_id=actor_agent_id,
            reason=reason,
            evidence_refs=evidence_refs,
            upserts=upserts,
        )
        self.ledger.append(
            EventKind.REQUIREMENT_CHANGED,
            source_agent_id=actor_agent_id,
            target_agent_id="requirements.chief",
            region="requirements-product",
            evidence_refs=revision.evidence_refs,
            object_refs=revision.changed_requirement_ids,
            payload={
                "requirements_action": "changed",
                "version": revision.version,
                "reason": revision.reason,
            },
        )
        return revision

    def _proposal(
        self,
        kind: EventKind,
        *,
        source_agent_id: str,
        requirement_id: str,
        text: str,
        evidence_refs: tuple[str, ...],
        action: str,
    ) -> Any:
        self.registry.get(source_agent_id)
        self.graph.get(requirement_id)
        text = str(text).strip()
        if not text:
            raise ValueError("requirement proposal text must be non-empty")
        return self.ledger.append(
            kind,
            source_agent_id=source_agent_id,
            target_agent_id="requirements.chief",
            region="requirements-product",
            evidence_refs=tuple(str(x) for x in evidence_refs),
            object_refs=(requirement_id,),
            payload={
                "requirements_action": action,
                "requirement_id": requirement_id,
                "text": text,
            },
        )

    def propose_ambiguity(
        self,
        *,
        source_agent_id: str,
        requirement_id: str,
        question: str,
        evidence_refs: tuple[str, ...],
    ) -> Any:
        return self._proposal(
            EventKind.REQUIREMENT_AMBIGUITY,
            source_agent_id=source_agent_id,
            requirement_id=requirement_id,
            text=question,
            evidence_refs=evidence_refs,
            action="ambiguity",
        )

    def propose_change(
        self,
        *,
        source_agent_id: str,
        requirement_id: str,
        proposal: str,
        evidence_refs: tuple[str, ...],
    ) -> Any:
        return self._proposal(
            EventKind.REQUIREMENT_CHANGE_PROPOSED,
            source_agent_id=source_agent_id,
            requirement_id=requirement_id,
            text=proposal,
            evidence_refs=evidence_refs,
            action="change_proposed",
        )

    def propose_acceptance_gap(
        self,
        *,
        source_agent_id: str,
        requirement_id: str,
        gap: str,
        evidence_refs: tuple[str, ...],
    ) -> Any:
        return self._proposal(
            EventKind.ACCEPTANCE_GAP,
            source_agent_id=source_agent_id,
            requirement_id=requirement_id,
            text=gap,
            evidence_refs=evidence_refs,
            action="acceptance_gap",
        )

    def to_state(self) -> dict[str, Any]:
        return {"graph": self.graph.to_state()}

    @classmethod
    def from_state(
        cls,
        *,
        registry: Any,
        authority: Any,
        ledger: Any,
        state: Mapping[str, Any],
    ) -> "RequirementsControlPlane":
        return cls(
            registry=registry,
            authority=authority,
            ledger=ledger,
            graph=RequirementGraph.from_state(state.get("graph", {})),
        )


__all__ = [
    "AcceptanceCriterion",
    "RequirementGraph",
    "RequirementKind",
    "RequirementNode",
    "RequirementRevision",
    "RequirementStatus",
    "RequirementsControlPlane",
]
