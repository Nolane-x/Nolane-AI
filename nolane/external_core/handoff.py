from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.component_contracts import ExternalComponentManifest


HANDOFF_PROTOCOL = "external-handoff-v1"


class HandoffAuthorityClass(str, Enum):
    INFORMATIVE = "informative"
    PROPOSAL = "proposal"
    VERIFIED = "verified"
    ASSURED = "assured"
    AUTHORIZED = "authorized"
    EXECUTION_RESULT = "execution_result"
    LEARNING_INPUT = "learning_input"


class HandoffValidationDisposition(str, Enum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


_AUTHORITY_REQUIREMENT: dict[HandoffAuthorityClass, str | None] = {
    HandoffAuthorityClass.INFORMATIVE: None,
    HandoffAuthorityClass.PROPOSAL: "propose",
    HandoffAuthorityClass.VERIFIED: "verify",
    HandoffAuthorityClass.ASSURED: "assure",
    HandoffAuthorityClass.AUTHORIZED: "authorize",
    HandoffAuthorityClass.EXECUTION_RESULT: "execute",
    HandoffAuthorityClass.LEARNING_INPUT: "learn",
}


@dataclass(frozen=True, slots=True)
class ExternalHandoffEnvelope:
    handoff_id: str
    producer_component_id: str
    producer_component_version: str
    producer_agent_id: str
    consumer_component_id: str
    consumer_contract_range: str
    subject_id: str
    subject_digest: str
    contract_kind: str
    contract_version: str
    authority_class: HandoffAuthorityClass
    source_state_digest: str
    predecessor_handoff_ids: tuple[str, ...]
    evidence_bindings: tuple[tuple[str, str], ...]
    artifact_bindings: tuple[tuple[str, str], ...]
    freshness_fence: str | None
    limitations: tuple[str, ...]
    known_unknowns: tuple[str, ...]
    payload_json: str
    payload_digest: str
    digest: str

    @property
    def payload(self) -> Any:
        return json.loads(self.payload_json)

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "protocol": HANDOFF_PROTOCOL,
            "producer_component_id": self.producer_component_id,
            "producer_component_version": self.producer_component_version,
            "producer_agent_id": self.producer_agent_id,
            "consumer_component_id": self.consumer_component_id,
            "consumer_contract_range": self.consumer_contract_range,
            "subject_id": self.subject_id,
            "subject_digest": self.subject_digest,
            "contract_kind": self.contract_kind,
            "contract_version": self.contract_version,
            "authority_class": self.authority_class.value,
            "source_state_digest": self.source_state_digest,
            "predecessor_handoff_ids": list(self.predecessor_handoff_ids),
            "evidence_bindings": [
                {"ref": ref, "digest": digest} for ref, digest in self.evidence_bindings
            ],
            "artifact_bindings": [
                {"artifact_id": artifact_id, "digest": digest}
                for artifact_id, digest in self.artifact_bindings
            ],
            "freshness_fence": self.freshness_fence,
            "limitations": list(self.limitations),
            "known_unknowns": list(self.known_unknowns),
            "payload_digest": self.payload_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "producer_component_id": self.producer_component_id,
            "producer_component_version": self.producer_component_version,
            "producer_agent_id": self.producer_agent_id,
            "consumer_component_id": self.consumer_component_id,
            "consumer_contract_range": self.consumer_contract_range,
            "subject_id": self.subject_id,
            "subject_digest": self.subject_digest,
            "contract_kind": self.contract_kind,
            "contract_version": self.contract_version,
            "authority_class": self.authority_class.value,
            "source_state_digest": self.source_state_digest,
            "predecessor_handoff_ids": list(self.predecessor_handoff_ids),
            "evidence_bindings": [list(row) for row in self.evidence_bindings],
            "artifact_bindings": [list(row) for row in self.artifact_bindings],
            "freshness_fence": self.freshness_fence,
            "limitations": list(self.limitations),
            "known_unknowns": list(self.known_unknowns),
            "payload_json": self.payload_json,
            "payload_digest": self.payload_digest,
            "digest": self.digest,
        }

    @classmethod
    def create(
        cls,
        *,
        producer_component_id: str,
        producer_component_version: str,
        producer_agent_id: str,
        consumer_component_id: str,
        consumer_contract_range: str,
        subject_id: str,
        subject_digest: str,
        contract_kind: str,
        contract_version: str,
        authority_class: HandoffAuthorityClass | str,
        source_state_digest: str,
        predecessor_handoff_ids: tuple[str, ...],
        evidence_bindings: tuple[tuple[str, str], ...],
        artifact_bindings: tuple[tuple[str, str], ...],
        freshness_fence: str | None,
        limitations: tuple[str, ...],
        known_unknowns: tuple[str, ...],
        payload: Any,
    ) -> "ExternalHandoffEnvelope":
        _require_finite_json(payload, path="handoff.payload")
        payload_json = canonical_json(payload)
        payload_digest = canonical_digest(payload)
        predecessors = _unique_explicit(predecessor_handoff_ids, "predecessor handoff id")
        evidence = _normalize_bindings(evidence_bindings, "evidence")
        artifacts = _normalize_bindings(artifact_bindings, "artifact")
        limitation_rows = _unique_explicit(limitations, "handoff limitation")
        unknown_rows = _unique_explicit(known_unknowns, "handoff known unknown")
        fence = None if freshness_fence is None else _explicit(freshness_fence, "freshness fence")
        authority = HandoffAuthorityClass(authority_class)
        row = cls(
            handoff_id="",
            producer_component_id=_explicit(producer_component_id, "producer component id"),
            producer_component_version=_explicit(producer_component_version, "producer component version"),
            producer_agent_id=_explicit(producer_agent_id, "producer agent id"),
            consumer_component_id=_explicit(consumer_component_id, "consumer component id"),
            consumer_contract_range=_explicit(consumer_contract_range, "consumer contract range"),
            subject_id=_explicit(subject_id, "handoff subject id"),
            subject_digest=_explicit(subject_digest, "handoff subject digest"),
            contract_kind=_explicit(contract_kind, "handoff contract kind"),
            contract_version=_explicit(contract_version, "handoff contract version"),
            authority_class=authority,
            source_state_digest=_explicit(source_state_digest, "source state digest"),
            predecessor_handoff_ids=predecessors,
            evidence_bindings=evidence,
            artifact_bindings=artifacts,
            freshness_fence=fence,
            limitations=limitation_rows,
            known_unknowns=unknown_rows,
            payload_json=payload_json,
            payload_digest=payload_digest,
            digest="",
        )
        digest = canonical_digest(row.semantic_payload())
        return cls(
            handoff_id="external-handoff-" + digest[:24],
            producer_component_id=row.producer_component_id,
            producer_component_version=row.producer_component_version,
            producer_agent_id=row.producer_agent_id,
            consumer_component_id=row.consumer_component_id,
            consumer_contract_range=row.consumer_contract_range,
            subject_id=row.subject_id,
            subject_digest=row.subject_digest,
            contract_kind=row.contract_kind,
            contract_version=row.contract_version,
            authority_class=row.authority_class,
            source_state_digest=row.source_state_digest,
            predecessor_handoff_ids=row.predecessor_handoff_ids,
            evidence_bindings=row.evidence_bindings,
            artifact_bindings=row.artifact_bindings,
            freshness_fence=row.freshness_fence,
            limitations=row.limitations,
            known_unknowns=row.known_unknowns,
            payload_json=row.payload_json,
            payload_digest=row.payload_digest,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExternalHandoffEnvelope":
        payload_json = str(state["payload_json"])
        payload = json.loads(payload_json)
        expected = cls.create(
            producer_component_id=str(state["producer_component_id"]),
            producer_component_version=str(state["producer_component_version"]),
            producer_agent_id=str(state["producer_agent_id"]),
            consumer_component_id=str(state["consumer_component_id"]),
            consumer_contract_range=str(state["consumer_contract_range"]),
            subject_id=str(state["subject_id"]),
            subject_digest=str(state["subject_digest"]),
            contract_kind=str(state["contract_kind"]),
            contract_version=str(state["contract_version"]),
            authority_class=str(state["authority_class"]),
            source_state_digest=str(state["source_state_digest"]),
            predecessor_handoff_ids=tuple(str(x) for x in state.get("predecessor_handoff_ids", ())),
            evidence_bindings=_state_bindings(state.get("evidence_bindings", ()), "evidence"),
            artifact_bindings=_state_bindings(state.get("artifact_bindings", ()), "artifact"),
            freshness_fence=None if state.get("freshness_fence") is None else str(state["freshness_fence"]),
            limitations=tuple(str(x) for x in state.get("limitations", ())),
            known_unknowns=tuple(str(x) for x in state.get("known_unknowns", ())),
            payload=payload,
        )
        if payload_json != expected.payload_json:
            raise ValueError("handoff payload is not canonical")
        if str(state.get("payload_digest", "")) != expected.payload_digest:
            raise ValueError("handoff payload digest mismatch")
        if str(state.get("handoff_id", "")) != expected.handoff_id:
            raise ValueError("handoff identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("handoff digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("handoff state is non-canonical or semantically drifted")
        return expected


@dataclass(frozen=True, slots=True)
class HandoffValidationResult:
    handoff_id: str
    disposition: HandoffValidationDisposition
    reason_codes: tuple[str, ...]
    producer_manifest_digest: str
    consumer_manifest_digest: str
    digest: str

    @property
    def accepted(self) -> bool:
        return self.disposition is HandoffValidationDisposition.ACCEPTED

    def payload(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "disposition": self.disposition.value,
            "reason_codes": list(self.reason_codes),
            "producer_manifest_digest": self.producer_manifest_digest,
            "consumer_manifest_digest": self.consumer_manifest_digest,
        }


def validate_handoff_for_consumer(
    envelope: ExternalHandoffEnvelope,
    *,
    producer_manifest: ExternalComponentManifest,
    consumer_manifest: ExternalComponentManifest,
    current_source_state_digest: str | None,
    current_evidence_digests: Mapping[str, str],
    current_artifact_digests: Mapping[str, str],
    known_predecessor_handoff_ids: tuple[str, ...],
    current_freshness_fence: str | None,
) -> HandoffValidationResult:
    blocked: list[str] = []
    unknown: list[str] = []

    if producer_manifest.component_id != envelope.producer_component_id:
        blocked.append("PRODUCER_COMPONENT_MISMATCH")
    if consumer_manifest.component_id != envelope.consumer_component_id:
        blocked.append("CONSUMER_COMPONENT_MISMATCH")
    if producer_manifest.component_version != envelope.producer_component_version:
        blocked.append("PRODUCER_VERSION_DRIFT")
    if envelope.contract_kind not in producer_manifest.produces_contracts:
        blocked.append("PRODUCER_CONTRACT_UNDECLARED")
    if envelope.contract_kind not in consumer_manifest.consumes_contracts:
        blocked.append("CONSUMER_CONTRACT_UNDECLARED")
    if not _contract_range_accepts(envelope.consumer_contract_range, envelope.contract_version):
        blocked.append("CONTRACT_VERSION_OUT_OF_RANGE")

    required_authority = _AUTHORITY_REQUIREMENT[envelope.authority_class]
    if required_authority is not None:
        if required_authority not in producer_manifest.authority_capabilities:
            blocked.append("PRODUCER_LACKS_AUTHORITY")
        if required_authority in producer_manifest.forbidden_authorities:
            blocked.append("PRODUCER_FORBIDS_AUTHORITY")

    if current_source_state_digest is None:
        unknown.append("MISSING_CURRENT_SOURCE_STATE")
    elif str(current_source_state_digest) != envelope.source_state_digest:
        blocked.append("SOURCE_STATE_DRIFT")

    for ref, expected_digest in envelope.evidence_bindings:
        current = current_evidence_digests.get(ref)
        if current is None:
            unknown.append("MISSING_CURRENT_EVIDENCE")
        elif str(current) != expected_digest:
            blocked.append("EVIDENCE_DIGEST_DRIFT")

    for artifact_id, expected_digest in envelope.artifact_bindings:
        current = current_artifact_digests.get(artifact_id)
        if current is None:
            unknown.append("MISSING_CURRENT_ARTIFACT")
        elif str(current) != expected_digest:
            blocked.append("ARTIFACT_DIGEST_DRIFT")

    known_predecessors = set(str(x) for x in known_predecessor_handoff_ids)
    if any(predecessor not in known_predecessors for predecessor in envelope.predecessor_handoff_ids):
        blocked.append("MISSING_PREDECESSOR_HANDOFF")

    if envelope.freshness_fence is not None:
        if current_freshness_fence is None:
            unknown.append("MISSING_CURRENT_FRESHNESS_FENCE")
        elif str(current_freshness_fence) != envelope.freshness_fence:
            blocked.append("FRESHNESS_FENCE_DRIFT")

    blocked_codes = tuple(sorted(set(blocked)))
    unknown_codes = tuple(sorted(set(unknown)))
    if blocked_codes:
        disposition = HandoffValidationDisposition.BLOCKED
        reasons = blocked_codes + unknown_codes
    elif unknown_codes:
        disposition = HandoffValidationDisposition.UNKNOWN
        reasons = unknown_codes
    else:
        disposition = HandoffValidationDisposition.ACCEPTED
        reasons = ()
    payload = {
        "handoff_id": envelope.handoff_id,
        "disposition": disposition.value,
        "reason_codes": list(reasons),
        "producer_manifest_digest": producer_manifest.manifest_digest,
        "consumer_manifest_digest": consumer_manifest.manifest_digest,
    }
    return HandoffValidationResult(
        handoff_id=envelope.handoff_id,
        disposition=disposition,
        reason_codes=reasons,
        producer_manifest_digest=producer_manifest.manifest_digest,
        consumer_manifest_digest=consumer_manifest.manifest_digest,
        digest=canonical_digest(payload),
    )


def _state_bindings(values: Any, label: str) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    for value in values:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(f"handoff {label} binding must be a two-item row")
        rows.append((str(value[0]), str(value[1])))
    return tuple(rows)


def _normalize_bindings(values: tuple[tuple[str, str], ...], label: str) -> tuple[tuple[str, str], ...]:
    rows = tuple((_explicit(ref, f"{label} ref"), _explicit(digest, f"{label} digest")) for ref, digest in values)
    refs = tuple(ref for ref, _ in rows)
    if len(set(refs)) != len(refs):
        raise ValueError(f"duplicate {label} ref")
    return tuple(sorted(rows, key=lambda row: row[0]))


def _unique_explicit(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    rows = tuple(_explicit(value, label) for value in values)
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(rows))


def _contract_range_accepts(spec: str, version: str) -> bool:
    spec_value = _explicit(spec, "contract range")
    version_value = _explicit(version, "contract version")
    if spec_value == "*":
        return True
    if ".." not in spec_value:
        return spec_value == version_value
    floor, ceiling = spec_value.split("..", 1)
    return _version_key(floor) <= _version_key(version_value) <= _version_key(ceiling)


def _version_key(value: str) -> tuple[int, ...]:
    parts = str(value).split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError(f"contract version/range must be numeric: {value}")
    return tuple(int(part) for part in parts)


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


def _require_finite_json(value: Any, *, path: str) -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains non-finite numeric value")
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
    raise ValueError(f"{path} contains non-canonical JSON value")


__all__ = (
    "HANDOFF_PROTOCOL",
    "ExternalHandoffEnvelope",
    "HandoffAuthorityClass",
    "HandoffValidationDisposition",
    "HandoffValidationResult",
    "validate_handoff_for_consumer",
)
