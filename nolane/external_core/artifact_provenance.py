from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


class ArtifactCurrentness(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    REVOKED = "revoked"
    DEPENDENCY_INVALID = "dependency_invalid"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ArtifactCurrentnessAssessment:
    status: ArtifactCurrentness
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArtifactRevocationReceipt:
    receipt_id: str
    artifact_id: str
    actor_component_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "actor_component_id": self.actor_component_id,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def create(
        cls,
        *,
        artifact_id: str,
        actor_component_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> "ArtifactRevocationReceipt":
        evidence = _unique_strings(evidence_refs, "revocation evidence")
        if not evidence:
            raise ValueError("artifact revocation requires evidence refs")
        payload = {
            "artifact_id": _explicit(artifact_id, "artifact id"),
            "actor_component_id": _explicit(actor_component_id, "actor component id"),
            "reason": _explicit(reason, "revocation reason"),
            "evidence_refs": list(evidence),
        }
        digest = canonical_digest(payload)
        return cls(
            receipt_id="artifact-revocation-" + digest[:24],
            artifact_id=payload["artifact_id"],
            actor_component_id=payload["actor_component_id"],
            reason=payload["reason"],
            evidence_refs=evidence,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArtifactRevocationReceipt":
        expected = cls.create(
            artifact_id=str(state["artifact_id"]),
            actor_component_id=str(state["actor_component_id"]),
            reason=str(state["reason"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
        )
        if str(state.get("receipt_id", "")) != expected.receipt_id:
            raise ValueError("artifact revocation identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("artifact revocation digest mismatch")
        return expected


@dataclass(frozen=True, slots=True)
class ArtifactSupersessionReceipt:
    receipt_id: str
    artifact_id: str
    successor_artifact_id: str
    actor_component_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "successor_artifact_id": self.successor_artifact_id,
            "actor_component_id": self.actor_component_id,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def create(
        cls,
        *,
        artifact_id: str,
        successor_artifact_id: str,
        actor_component_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> "ArtifactSupersessionReceipt":
        artifact = _explicit(artifact_id, "artifact id")
        successor = _explicit(successor_artifact_id, "successor artifact id")
        if artifact == successor:
            raise ValueError("artifact cannot supersede itself")
        evidence = _unique_strings(evidence_refs, "supersession evidence")
        if not evidence:
            raise ValueError("artifact supersession requires evidence refs")
        payload = {
            "artifact_id": artifact,
            "successor_artifact_id": successor,
            "actor_component_id": _explicit(actor_component_id, "actor component id"),
            "reason": _explicit(reason, "supersession reason"),
            "evidence_refs": list(evidence),
        }
        digest = canonical_digest(payload)
        return cls(
            receipt_id="artifact-supersession-" + digest[:24],
            artifact_id=artifact,
            successor_artifact_id=successor,
            actor_component_id=payload["actor_component_id"],
            reason=payload["reason"],
            evidence_refs=evidence,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArtifactSupersessionReceipt":
        expected = cls.create(
            artifact_id=str(state["artifact_id"]),
            successor_artifact_id=str(state["successor_artifact_id"]),
            actor_component_id=str(state["actor_component_id"]),
            reason=str(state["reason"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
        )
        if str(state.get("receipt_id", "")) != expected.receipt_id:
            raise ValueError("artifact supersession identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("artifact supersession digest mismatch")
        return expected


class ArtifactProvenanceGraph:
    """Append-only artifact lineage with fail-closed revocation closure.

    Edges point from an artifact to the artifacts it depends on. The graph is
    deliberately authority-neutral: it records lineage and invalidation facts,
    but does not assert Truth or Assurance.
    """

    def __init__(self) -> None:
        self._nodes: set[str] = set()
        self._dependencies: dict[str, set[str]] = {}
        self._revocations: dict[str, ArtifactRevocationReceipt] = {}
        self._supersessions: dict[str, ArtifactSupersessionReceipt] = {}

    @property
    def nodes(self) -> tuple[str, ...]:
        return tuple(sorted(self._nodes))

    @property
    def digest(self) -> str:
        return canonical_digest(self._payload())

    def register_artifact(self, artifact_id: str) -> None:
        artifact = _explicit(artifact_id, "artifact id")
        self._nodes.add(artifact)
        self._dependencies.setdefault(artifact, set())

    def dependencies_for(self, artifact_id: str) -> tuple[str, ...]:
        artifact = self._require_node(artifact_id)
        return tuple(sorted(self._dependencies[artifact]))

    def bind_dependency(self, artifact_id: str, dependency_artifact_id: str) -> None:
        artifact = self._require_node(artifact_id)
        dependency = self._require_node(dependency_artifact_id)
        if artifact == dependency:
            raise ValueError("artifact provenance cycle detected")
        if artifact in self._reachable_from(dependency):
            raise ValueError("artifact provenance cycle detected")
        self._dependencies[artifact].add(dependency)

    def revoke(
        self,
        artifact_id: str,
        *,
        actor_component_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> ArtifactRevocationReceipt:
        artifact = self._require_node(artifact_id)
        row = ArtifactRevocationReceipt.create(
            artifact_id=artifact,
            actor_component_id=actor_component_id,
            reason=reason,
            evidence_refs=evidence_refs,
        )
        existing = self._revocations.get(artifact)
        if existing is not None:
            if existing != row:
                raise ValueError("artifact revocation cannot be rebound")
            return existing
        self._revocations[artifact] = row
        return row

    def supersede(
        self,
        artifact_id: str,
        *,
        successor_artifact_id: str,
        actor_component_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> ArtifactSupersessionReceipt:
        artifact = self._require_node(artifact_id)
        successor = self._require_node(successor_artifact_id)
        row = ArtifactSupersessionReceipt.create(
            artifact_id=artifact,
            successor_artifact_id=successor,
            actor_component_id=actor_component_id,
            reason=reason,
            evidence_refs=evidence_refs,
        )
        existing = self._supersessions.get(artifact)
        if existing is not None:
            if existing != row:
                raise ValueError("artifact supersession cannot be rebound")
            return existing
        self._supersessions[artifact] = row
        return row

    def revocation_receipt(self, artifact_id: str) -> ArtifactRevocationReceipt | None:
        return self._revocations.get(str(artifact_id))

    def supersession_receipt(self, artifact_id: str) -> ArtifactSupersessionReceipt | None:
        return self._supersessions.get(str(artifact_id))

    def invalid_ancestor(self, artifact_id: str) -> str | None:
        artifact = self._require_node(artifact_id)
        seen: set[str] = set()
        stack = list(self._dependencies[artifact])
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in self._revocations or current in self._supersessions:
                return current
            stack.extend(self._dependencies[current])
        return None

    def to_state(self) -> dict[str, Any]:
        payload = self._payload()
        return {**payload, "digest": canonical_digest(payload)}

    def _payload(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "dependencies": [
                {"artifact_id": artifact_id, "dependency_ids": list(self.dependencies_for(artifact_id))}
                for artifact_id in self.nodes
            ],
            "revocations": [self._revocations[key].to_state() for key in sorted(self._revocations)],
            "supersessions": [self._supersessions[key].to_state() for key in sorted(self._supersessions)],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArtifactProvenanceGraph":
        graph = cls()
        for raw in state.get("nodes", ()):
            graph.register_artifact(str(raw))
        for raw in state.get("dependencies", ()):
            artifact_id = str(raw["artifact_id"])
            for dependency_id in raw.get("dependency_ids", ()):
                graph.bind_dependency(artifact_id, str(dependency_id))
        for raw in state.get("revocations", ()):
            row = ArtifactRevocationReceipt.from_state(raw)
            graph._require_node(row.artifact_id)
            existing = graph._revocations.get(row.artifact_id)
            if existing is not None:
                raise ValueError("duplicate artifact revocation in state")
            graph._revocations[row.artifact_id] = row
        for raw in state.get("supersessions", ()):
            row = ArtifactSupersessionReceipt.from_state(raw)
            graph._require_node(row.artifact_id)
            graph._require_node(row.successor_artifact_id)
            existing = graph._supersessions.get(row.artifact_id)
            if existing is not None:
                raise ValueError("duplicate artifact supersession in state")
            graph._supersessions[row.artifact_id] = row
        expected_digest = canonical_digest(graph._payload())
        if state and str(state.get("digest", "")) != expected_digest:
            raise ValueError("artifact provenance digest mismatch")
        return graph

    def _reachable_from(self, artifact_id: str) -> set[str]:
        seen: set[str] = set()
        stack = list(self._dependencies[artifact_id])
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self._dependencies[current])
        return seen

    def _require_node(self, artifact_id: str) -> str:
        artifact = _explicit(artifact_id, "artifact id")
        if artifact not in self._nodes:
            raise KeyError(f"unknown artifact dependency: {artifact}")
        return artifact


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


def _unique_strings(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    rows = tuple(str(value) for value in values)
    if any(not value.strip() for value in rows):
        raise ValueError(f"{label} must contain explicit values")
    if len(set(rows)) != len(rows):
        raise ValueError(f"{label} cannot contain duplicates")
    return tuple(sorted(rows))


__all__ = (
    "ArtifactCurrentness",
    "ArtifactCurrentnessAssessment",
    "ArtifactProvenanceGraph",
    "ArtifactRevocationReceipt",
    "ArtifactSupersessionReceipt",
)
