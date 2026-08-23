from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from cogcoder.organization.types import canonical_digest, canonical_json


COMPONENT_ID = "external.artifacts"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.artifacts"


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    digest: str
    kind: str
    producer_agent_id: str
    content: str
    evidence_refs: tuple[str, ...]
    metadata_json: str

    @property
    def metadata(self) -> dict[str, Any]:
        value = json.loads(self.metadata_json)
        if not isinstance(value, dict):
            raise ValueError("artifact metadata must decode to an object")
        return value

    def to_state(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "digest": self.digest,
            "kind": self.kind,
            "producer_agent_id": self.producer_agent_id,
            "content": self.content,
            "evidence_refs": list(self.evidence_refs),
            "metadata_json": self.metadata_json,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArtifactRecord":
        return cls(
            artifact_id=str(state["artifact_id"]),
            digest=str(state["digest"]),
            kind=str(state["kind"]),
            producer_agent_id=str(state["producer_agent_id"]),
            content=str(state["content"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            metadata_json=str(state.get("metadata_json", "{}")),
        )


class ArtifactStore:
    """Canonical content-addressed artifact authority."""

    def __init__(self) -> None:
        self._rows: dict[str, ArtifactRecord] = {}

    def put(
        self,
        *,
        kind: str,
        producer_agent_id: str,
        content: str,
        evidence_refs: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRecord:
        if not str(kind).strip() or not str(producer_agent_id).strip():
            raise ValueError("artifact kind and producer must be explicit")
        payload = {
            "kind": str(kind),
            "producer_agent_id": str(producer_agent_id),
            "content": str(content),
            "evidence_refs": sorted({str(x) for x in evidence_refs}),
            "metadata": dict(metadata or {}),
        }
        digest = canonical_digest(payload)
        artifact_id = "artifact-" + digest[:24]
        existing = self._rows.get(artifact_id)
        if existing is not None:
            return existing
        row = ArtifactRecord(
            artifact_id=artifact_id,
            digest=digest,
            kind=payload["kind"],
            producer_agent_id=payload["producer_agent_id"],
            content=payload["content"],
            evidence_refs=tuple(payload["evidence_refs"]),
            metadata_json=canonical_json(payload["metadata"]),
        )
        self._rows[row.artifact_id] = row
        return row

    def get(self, artifact_id: str) -> ArtifactRecord:
        try:
            return self._rows[str(artifact_id)]
        except KeyError as exc:
            raise KeyError(f"unknown artifact id: {artifact_id}") from exc

    def records(self) -> tuple[ArtifactRecord, ...]:
        return tuple(self._rows[key] for key in sorted(self._rows))

    def to_state(self) -> dict[str, Any]:
        return {"artifacts": [row.to_state() for row in self.records()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArtifactStore":
        store = cls()
        for value in state.get("artifacts", ()):
            row = ArtifactRecord.from_state(value)
            store._rows[row.artifact_id] = row
        return store


__all__ = (
    "ArtifactRecord",
    "ArtifactStore",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
