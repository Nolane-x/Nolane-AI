from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.artifact_provenance import (
    ArtifactCurrentness,
    ArtifactCurrentnessAssessment,
    ArtifactProvenanceGraph,
    ArtifactRevocationReceipt,
    ArtifactSupersessionReceipt,
)


COMPONENT_ID = "external.artifacts"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.artifacts"
ARTIFACT_PROTOCOL_VERSION = "2"


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


@dataclass(frozen=True, slots=True)
class ArtifactEnvelope:
    artifact_id: str
    digest: str
    kind: str
    schema_version: str
    producer_component_id: str
    producer_agent_id: str
    content: str
    content_digest: str
    source_state_digest: str
    evidence_refs: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    dependency_artifact_ids: tuple[str, ...]
    predecessor_artifact_ids: tuple[str, ...]
    contract_id: str
    contract_version: str
    created_epoch: int
    currentness_max_age_epochs: int | None
    metadata_json: str

    @property
    def metadata(self) -> dict[str, Any]:
        value = json.loads(self.metadata_json)
        if not isinstance(value, dict):
            raise ValueError("artifact envelope metadata must decode to an object")
        return value

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "schema_version": self.schema_version,
            "producer_component_id": self.producer_component_id,
            "producer_agent_id": self.producer_agent_id,
            "content_digest": self.content_digest,
            "source_state_digest": self.source_state_digest,
            "evidence_bindings": [
                {"evidence_ref": ref, "evidence_digest": digest}
                for ref, digest in zip(self.evidence_refs, self.evidence_digests, strict=True)
            ],
            "dependency_artifact_ids": list(self.dependency_artifact_ids),
            "predecessor_artifact_ids": list(self.predecessor_artifact_ids),
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "created_epoch": self.created_epoch,
            "currentness_max_age_epochs": self.currentness_max_age_epochs,
            "metadata": self.metadata,
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "digest": self.digest,
            "kind": self.kind,
            "schema_version": self.schema_version,
            "producer_component_id": self.producer_component_id,
            "producer_agent_id": self.producer_agent_id,
            "content": self.content,
            "content_digest": self.content_digest,
            "source_state_digest": self.source_state_digest,
            "evidence_refs": list(self.evidence_refs),
            "evidence_digests": list(self.evidence_digests),
            "dependency_artifact_ids": list(self.dependency_artifact_ids),
            "predecessor_artifact_ids": list(self.predecessor_artifact_ids),
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "created_epoch": self.created_epoch,
            "currentness_max_age_epochs": self.currentness_max_age_epochs,
            "metadata_json": self.metadata_json,
        }

    @classmethod
    def create(
        cls,
        *,
        kind: str,
        schema_version: str,
        producer_component_id: str,
        producer_agent_id: str,
        content: str,
        source_state_digest: str,
        evidence_refs: tuple[str, ...],
        evidence_digests: tuple[str, ...],
        dependency_artifact_ids: tuple[str, ...],
        predecessor_artifact_ids: tuple[str, ...],
        contract_id: str,
        contract_version: str,
        created_epoch: int,
        currentness_max_age_epochs: int | None,
        metadata: Mapping[str, Any] | None,
    ) -> "ArtifactEnvelope":
        epoch = _require_non_negative_int(created_epoch, "created_epoch")
        max_age = None
        if currentness_max_age_epochs is not None:
            max_age = _require_non_negative_int(currentness_max_age_epochs, "currentness_max_age_epochs")
        metadata_value = dict(metadata or {})
        _require_finite_json(metadata_value)
        bindings = _normalize_bindings(evidence_refs, evidence_digests)
        dependencies = _unique_explicit_strings(dependency_artifact_ids, "dependency artifact id")
        predecessors = _unique_explicit_strings(predecessor_artifact_ids, "predecessor artifact id")
        content_value = str(content)
        content_digest = canonical_digest({"content": content_value})
        evidence_rows = tuple(row[0] for row in bindings)
        evidence_digest_rows = tuple(row[1] for row in bindings)
        metadata_json = canonical_json(metadata_value)
        payload = {
            "kind": _explicit(kind, "artifact kind"),
            "schema_version": _explicit(schema_version, "artifact schema version"),
            "producer_component_id": _explicit(producer_component_id, "producer component id"),
            "producer_agent_id": _explicit(producer_agent_id, "producer agent id"),
            "content_digest": content_digest,
            "source_state_digest": _explicit(source_state_digest, "source state digest"),
            "evidence_bindings": [
                {"evidence_ref": ref, "evidence_digest": digest} for ref, digest in bindings
            ],
            "dependency_artifact_ids": list(dependencies),
            "predecessor_artifact_ids": list(predecessors),
            "contract_id": _explicit(contract_id, "artifact contract id"),
            "contract_version": _explicit(contract_version, "artifact contract version"),
            "created_epoch": epoch,
            "currentness_max_age_epochs": max_age,
            "metadata": metadata_value,
        }
        digest = canonical_digest(payload)
        return cls(
            artifact_id="artifact-v2-" + digest[:24],
            digest=digest,
            kind=payload["kind"],
            schema_version=payload["schema_version"],
            producer_component_id=payload["producer_component_id"],
            producer_agent_id=payload["producer_agent_id"],
            content=content_value,
            content_digest=content_digest,
            source_state_digest=payload["source_state_digest"],
            evidence_refs=evidence_rows,
            evidence_digests=evidence_digest_rows,
            dependency_artifact_ids=dependencies,
            predecessor_artifact_ids=predecessors,
            contract_id=payload["contract_id"],
            contract_version=payload["contract_version"],
            created_epoch=epoch,
            currentness_max_age_epochs=max_age,
            metadata_json=metadata_json,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArtifactEnvelope":
        created_raw = state["created_epoch"]
        max_age_raw = state.get("currentness_max_age_epochs")
        metadata_json = str(state.get("metadata_json", "{}"))
        metadata_value = json.loads(metadata_json)
        if not isinstance(metadata_value, dict):
            raise ValueError("artifact envelope metadata must decode to an object")
        expected = cls.create(
            kind=str(state["kind"]),
            schema_version=str(state["schema_version"]),
            producer_component_id=str(state["producer_component_id"]),
            producer_agent_id=str(state["producer_agent_id"]),
            content=str(state["content"]),
            source_state_digest=str(state["source_state_digest"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            evidence_digests=tuple(str(x) for x in state.get("evidence_digests", ())),
            dependency_artifact_ids=tuple(str(x) for x in state.get("dependency_artifact_ids", ())),
            predecessor_artifact_ids=tuple(str(x) for x in state.get("predecessor_artifact_ids", ())),
            contract_id=str(state["contract_id"]),
            contract_version=str(state["contract_version"]),
            created_epoch=created_raw,
            currentness_max_age_epochs=max_age_raw,
            metadata=metadata_value,
        )
        if str(state.get("artifact_id", "")) != expected.artifact_id:
            raise ValueError("artifact identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("artifact digest mismatch")
        if str(state.get("content_digest", "")) != expected.content_digest:
            raise ValueError("artifact content digest mismatch")
        if metadata_json != expected.metadata_json:
            raise ValueError("artifact metadata is not canonical")
        return expected


class ArtifactStore:
    """Canonical content-addressed artifact authority.

    Legacy v0.0.1 records remain available through ``put/get/records``. A2
    artifact envelopes are a separate protocol surface with explicit lineage,
    currentness, and revocation closure; legacy rows never silently gain those
    properties.
    """

    def __init__(self) -> None:
        self._rows: dict[str, ArtifactRecord] = {}
        self._v2_rows: dict[str, ArtifactEnvelope] = {}
        self.provenance = ArtifactProvenanceGraph()

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

    def put_v2(
        self,
        *,
        kind: str,
        schema_version: str,
        producer_component_id: str,
        producer_agent_id: str,
        content: str,
        source_state_digest: str,
        evidence_refs: tuple[str, ...] = (),
        evidence_digests: tuple[str, ...] = (),
        dependency_artifact_ids: tuple[str, ...] = (),
        predecessor_artifact_ids: tuple[str, ...] = (),
        contract_id: str,
        contract_version: str,
        created_epoch: int,
        currentness_max_age_epochs: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactEnvelope:
        row = ArtifactEnvelope.create(
            kind=kind,
            schema_version=schema_version,
            producer_component_id=producer_component_id,
            producer_agent_id=producer_agent_id,
            content=content,
            source_state_digest=source_state_digest,
            evidence_refs=evidence_refs,
            evidence_digests=evidence_digests,
            dependency_artifact_ids=dependency_artifact_ids,
            predecessor_artifact_ids=predecessor_artifact_ids,
            contract_id=contract_id,
            contract_version=contract_version,
            created_epoch=created_epoch,
            currentness_max_age_epochs=currentness_max_age_epochs,
            metadata=metadata,
        )
        lineage_ids = tuple(sorted(set(row.dependency_artifact_ids + row.predecessor_artifact_ids)))
        for dependency_id in lineage_ids:
            if dependency_id not in self._v2_rows:
                raise KeyError(f"unknown artifact dependency: {dependency_id}")
        existing = self._v2_rows.get(row.artifact_id)
        if existing is not None:
            if existing != row:
                raise ValueError("artifact semantic id cannot be rebound")
            return existing
        self.provenance.register_artifact(row.artifact_id)
        for dependency_id in lineage_ids:
            self.provenance.bind_dependency(row.artifact_id, dependency_id)
        self._v2_rows[row.artifact_id] = row
        return row

    def get(self, artifact_id: str) -> ArtifactRecord:
        try:
            return self._rows[str(artifact_id)]
        except KeyError as exc:
            raise KeyError(f"unknown artifact id: {artifact_id}") from exc

    def get_v2(self, artifact_id: str) -> ArtifactEnvelope:
        try:
            return self._v2_rows[str(artifact_id)]
        except KeyError as exc:
            raise KeyError(f"unknown v2 artifact id: {artifact_id}") from exc

    def records(self) -> tuple[ArtifactRecord, ...]:
        return tuple(self._rows[key] for key in sorted(self._rows))

    def v2_records(self) -> tuple[ArtifactEnvelope, ...]:
        return tuple(self._v2_rows[key] for key in sorted(self._v2_rows))

    def revoke_artifact(
        self,
        artifact_id: str,
        *,
        actor_component_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> ArtifactRevocationReceipt:
        self.get_v2(artifact_id)
        return self.provenance.revoke(
            artifact_id,
            actor_component_id=actor_component_id,
            reason=reason,
            evidence_refs=evidence_refs,
        )

    def supersede_artifact(
        self,
        artifact_id: str,
        *,
        successor_artifact_id: str,
        actor_component_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> ArtifactSupersessionReceipt:
        self.get_v2(artifact_id)
        self.get_v2(successor_artifact_id)
        return self.provenance.supersede(
            artifact_id,
            successor_artifact_id=successor_artifact_id,
            actor_component_id=actor_component_id,
            reason=reason,
            evidence_refs=evidence_refs,
        )

    def currentness(
        self,
        artifact_id: str,
        *,
        current_epoch: int | None = None,
    ) -> ArtifactCurrentnessAssessment:
        artifact = self.get_v2(artifact_id)
        memo: dict[str, ArtifactCurrentnessAssessment] = {}

        def assess(row: ArtifactEnvelope) -> ArtifactCurrentnessAssessment:
            cached = memo.get(row.artifact_id)
            if cached is not None:
                return cached
            revocation = self.provenance.revocation_receipt(row.artifact_id)
            if revocation is not None:
                result = ArtifactCurrentnessAssessment(
                    ArtifactCurrentness.REVOKED,
                    (f"revoked:{revocation.receipt_id}",),
                )
                memo[row.artifact_id] = result
                return result
            supersession = self.provenance.supersession_receipt(row.artifact_id)
            if supersession is not None:
                result = ArtifactCurrentnessAssessment(
                    ArtifactCurrentness.STALE,
                    (f"superseded:{supersession.successor_artifact_id}",),
                )
                memo[row.artifact_id] = result
                return result
            for dependency_id in self.provenance.dependencies_for(row.artifact_id):
                dependency = assess(self.get_v2(dependency_id))
                if dependency.status is ArtifactCurrentness.UNKNOWN:
                    result = ArtifactCurrentnessAssessment(
                        ArtifactCurrentness.UNKNOWN,
                        (f"dependency_unknown:{dependency_id}",),
                    )
                    memo[row.artifact_id] = result
                    return result
                if dependency.status is not ArtifactCurrentness.CURRENT:
                    result = ArtifactCurrentnessAssessment(
                        ArtifactCurrentness.DEPENDENCY_INVALID,
                        (f"dependency_not_current:{dependency_id}:{dependency.status.value}",),
                    )
                    memo[row.artifact_id] = result
                    return result
            if row.currentness_max_age_epochs is None:
                result = ArtifactCurrentnessAssessment(ArtifactCurrentness.CURRENT)
                memo[row.artifact_id] = result
                return result
            if current_epoch is None:
                result = ArtifactCurrentnessAssessment(
                    ArtifactCurrentness.UNKNOWN,
                    ("current_epoch_required",),
                )
                memo[row.artifact_id] = result
                return result
            epoch = _require_non_negative_int(current_epoch, "current_epoch")
            if epoch < row.created_epoch:
                result = ArtifactCurrentnessAssessment(
                    ArtifactCurrentness.UNKNOWN,
                    ("current_epoch_precedes_artifact",),
                )
                memo[row.artifact_id] = result
                return result
            if epoch - row.created_epoch > row.currentness_max_age_epochs:
                result = ArtifactCurrentnessAssessment(
                    ArtifactCurrentness.STALE,
                    ("artifact_age_exceeded",),
                )
                memo[row.artifact_id] = result
                return result
            result = ArtifactCurrentnessAssessment(ArtifactCurrentness.CURRENT)
            memo[row.artifact_id] = result
            return result

        return assess(artifact)

    def to_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            "artifacts": [row.to_state() for row in self.records()],
        }
        if self._v2_rows or self.provenance.nodes:
            state["artifact_envelopes"] = [row.to_state() for row in self.v2_records()]
            state["artifact_provenance"] = self.provenance.to_state()
        return state

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArtifactStore":
        store = cls()
        for value in state.get("artifacts", ()):
            row = ArtifactRecord.from_state(value)
            store._rows[row.artifact_id] = row

        envelopes = tuple(ArtifactEnvelope.from_state(value) for value in state.get("artifact_envelopes", ()))
        for row in envelopes:
            if row.artifact_id in store._v2_rows:
                raise ValueError("duplicate v2 artifact id in serialized state")
            store._v2_rows[row.artifact_id] = row

        if envelopes:
            if "artifact_provenance" not in state:
                raise ValueError("v2 artifact state is missing artifact provenance")
            provenance = ArtifactProvenanceGraph.from_state(state["artifact_provenance"])
            if set(provenance.nodes) != set(store._v2_rows):
                raise ValueError("artifact provenance node set mismatch")
            for row in envelopes:
                expected = tuple(sorted(set(row.dependency_artifact_ids + row.predecessor_artifact_ids)))
                if provenance.dependencies_for(row.artifact_id) != expected:
                    raise ValueError("artifact provenance dependency mismatch")
            store.provenance = provenance
        elif "artifact_provenance" in state:
            provenance = ArtifactProvenanceGraph.from_state(state["artifact_provenance"])
            if provenance.nodes:
                raise ValueError("artifact provenance references missing v2 artifacts")
            store.provenance = provenance
        return store


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


def _require_non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer, not bool or another scalar")
    if value < 0:
        raise ValueError(f"{label} must be non-negative")
    return value


def _unique_explicit_strings(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    rows = tuple(str(value) for value in values)
    if any(not value.strip() for value in rows):
        raise ValueError(f"{label} must be explicit")
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(rows))


def _normalize_bindings(
    evidence_refs: tuple[str, ...],
    evidence_digests: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    refs = tuple(str(value) for value in evidence_refs)
    digests = tuple(str(value) for value in evidence_digests)
    if len(refs) != len(digests):
        raise ValueError("artifact evidence refs and evidence digests must have equal cardinality")
    if any(not value.strip() for value in refs + digests):
        raise ValueError("artifact evidence bindings must be explicit")
    if len(set(refs)) != len(refs):
        raise ValueError("artifact evidence refs cannot contain duplicates")
    return tuple(sorted(zip(refs, digests, strict=True), key=lambda row: row[0]))


def _require_finite_json(value: Any, *, path: str = "metadata") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain only finite numeric values")
        return
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings")
            _require_finite_json(child, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _require_finite_json(child, path=f"{path}[{index}]")
        return
    raise ValueError(f"{path} contains a non-canonical JSON value")


__all__ = (
    "ARTIFACT_PROTOCOL_VERSION",
    "ArtifactCurrentness",
    "ArtifactCurrentnessAssessment",
    "ArtifactEnvelope",
    "ArtifactRecord",
    "ArtifactStore",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
