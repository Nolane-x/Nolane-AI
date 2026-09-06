from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.integration"
COMPONENT_VERSION = "0.0.4"
ADMISSION_PROTOCOL = "external-integration-admission-v2"


class AdmissionDisposition(str, Enum):
    ADMITTED = "admitted"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class AdmissionSubjectKind(str, Enum):
    COMPONENT_MANIFEST = "component-manifest-v1"
    AUTHORITY_GRAPH = "authority-graph-v1"
    HANDOFF = "external-handoff-v1"
    WORK_TRACE = "cognitive-work-trace-v1"


def _explicit(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be an explicit string")
    return value


def _strict_non_negative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _exact_state_keys(state: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(state)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        detail: list[str] = []
        if missing:
            detail.append("missing=" + ",".join(missing))
        if unknown:
            detail.append("unknown=" + ",".join(unknown))
        raise ValueError(f"{label} state is non-canonical: " + ";".join(detail))


def _canonical_strings(values: object, label: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{label} must be a tuple")
    rows = tuple(_explicit(value, label) for value in values)
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(rows))


@dataclass(frozen=True, slots=True)
class CanonicalAdmissionContext:
    protocol: str
    registry_digest: str
    authority_graph_digest: str
    source_state_frontier_digest: str
    evidence_frontier_digest: str
    artifact_frontier_digest: str
    freshness_fence_frontier_digest: str
    handoff_frontier_digest: str
    work_trace_frontier_digest: str
    observed_epoch: int
    digest: str

    @classmethod
    def create(
        cls,
        *,
        registry_digest: str,
        authority_graph_digest: str,
        source_state_frontier_digest: str,
        evidence_frontier_digest: str,
        artifact_frontier_digest: str,
        freshness_fence_frontier_digest: str,
        handoff_frontier_digest: str,
        work_trace_frontier_digest: str,
        observed_epoch: int,
    ) -> "CanonicalAdmissionContext":
        payload = {
            "protocol": ADMISSION_PROTOCOL,
            "registry_digest": _explicit(registry_digest, "admission registry digest"),
            "authority_graph_digest": _explicit(authority_graph_digest, "admission authority graph digest"),
            "source_state_frontier_digest": _explicit(
                source_state_frontier_digest, "admission source-state frontier digest"
            ),
            "evidence_frontier_digest": _explicit(
                evidence_frontier_digest, "admission evidence frontier digest"
            ),
            "artifact_frontier_digest": _explicit(
                artifact_frontier_digest, "admission artifact frontier digest"
            ),
            "freshness_fence_frontier_digest": _explicit(
                freshness_fence_frontier_digest, "admission freshness frontier digest"
            ),
            "handoff_frontier_digest": _explicit(
                handoff_frontier_digest, "admission handoff frontier digest"
            ),
            "work_trace_frontier_digest": _explicit(
                work_trace_frontier_digest, "admission work-trace frontier digest"
            ),
            "observed_epoch": _strict_non_negative_int(observed_epoch, "admission observed epoch"),
        }
        return cls(**payload, digest="admission-context-v2-" + canonical_digest(payload))

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "registry_digest": self.registry_digest,
            "authority_graph_digest": self.authority_graph_digest,
            "source_state_frontier_digest": self.source_state_frontier_digest,
            "evidence_frontier_digest": self.evidence_frontier_digest,
            "artifact_frontier_digest": self.artifact_frontier_digest,
            "freshness_fence_frontier_digest": self.freshness_fence_frontier_digest,
            "handoff_frontier_digest": self.handoff_frontier_digest,
            "work_trace_frontier_digest": self.work_trace_frontier_digest,
            "observed_epoch": self.observed_epoch,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CanonicalAdmissionContext":
        if not isinstance(state, Mapping):
            raise ValueError("admission context state must be an object")
        expected_keys = frozenset(
            {
                "protocol",
                "registry_digest",
                "authority_graph_digest",
                "source_state_frontier_digest",
                "evidence_frontier_digest",
                "artifact_frontier_digest",
                "freshness_fence_frontier_digest",
                "handoff_frontier_digest",
                "work_trace_frontier_digest",
                "observed_epoch",
                "digest",
            }
        )
        _exact_state_keys(state, expected_keys, "admission context")
        if state.get("protocol") != ADMISSION_PROTOCOL:
            raise ValueError("admission context protocol mismatch")
        expected = cls.create(
            registry_digest=state.get("registry_digest"),  # type: ignore[arg-type]
            authority_graph_digest=state.get("authority_graph_digest"),  # type: ignore[arg-type]
            source_state_frontier_digest=state.get("source_state_frontier_digest"),  # type: ignore[arg-type]
            evidence_frontier_digest=state.get("evidence_frontier_digest"),  # type: ignore[arg-type]
            artifact_frontier_digest=state.get("artifact_frontier_digest"),  # type: ignore[arg-type]
            freshness_fence_frontier_digest=state.get("freshness_fence_frontier_digest"),  # type: ignore[arg-type]
            handoff_frontier_digest=state.get("handoff_frontier_digest"),  # type: ignore[arg-type]
            work_trace_frontier_digest=state.get("work_trace_frontier_digest"),  # type: ignore[arg-type]
            observed_epoch=state.get("observed_epoch"),  # type: ignore[arg-type]
        )
        if state.get("digest") != expected.digest:
            raise ValueError("admission context digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("admission context state is non-canonical")
        return expected

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("admission context integrity validation failed") from exc
        if restored != self:
            raise ValueError("admission context integrity validation failed")


@dataclass(frozen=True, slots=True)
class ProtocolAdmissionReceipt:
    protocol: str
    subject_kind: AdmissionSubjectKind
    subject_protocol: str
    subject_id: str
    subject_state_digest: str
    semantic_digest: str
    context_digest: str
    owner_component_id: str
    owner_component_version: str
    disposition: AdmissionDisposition
    reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]
    receipt_id: str

    @classmethod
    def create(
        cls,
        *,
        subject_kind: AdmissionSubjectKind | str,
        subject_protocol: str,
        subject_id: str,
        subject_state_digest: str,
        semantic_digest: str,
        context_digest: str,
        disposition: AdmissionDisposition | str,
        reason_codes: tuple[str, ...],
        limitations: tuple[str, ...],
    ) -> "ProtocolAdmissionReceipt":
        kind = AdmissionSubjectKind(subject_kind)
        result = AdmissionDisposition(disposition)
        reasons = _canonical_strings(reason_codes, "admission reason code")
        limits = _canonical_strings(limitations, "admission limitation")
        payload = {
            "protocol": ADMISSION_PROTOCOL,
            "subject_kind": kind.value,
            "subject_protocol": _explicit(subject_protocol, "admission subject protocol"),
            "subject_id": _explicit(subject_id, "admission subject identity"),
            "subject_state_digest": _explicit(subject_state_digest, "admission subject state digest"),
            "semantic_digest": _explicit(semantic_digest, "admission semantic digest"),
            "context_digest": _explicit(context_digest, "admission context digest"),
            "owner_component_id": COMPONENT_ID,
            "owner_component_version": COMPONENT_VERSION,
            "disposition": result.value,
            "reason_codes": list(reasons),
            "limitations": list(limits),
        }
        return cls(
            protocol=ADMISSION_PROTOCOL,
            subject_kind=kind,
            subject_protocol=payload["subject_protocol"],
            subject_id=payload["subject_id"],
            subject_state_digest=payload["subject_state_digest"],
            semantic_digest=payload["semantic_digest"],
            context_digest=payload["context_digest"],
            owner_component_id=COMPONENT_ID,
            owner_component_version=COMPONENT_VERSION,
            disposition=result,
            reason_codes=reasons,
            limitations=limits,
            receipt_id="admission-receipt-v2-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "subject_kind": self.subject_kind.value,
            "subject_protocol": self.subject_protocol,
            "subject_id": self.subject_id,
            "subject_state_digest": self.subject_state_digest,
            "semantic_digest": self.semantic_digest,
            "context_digest": self.context_digest,
            "owner_component_id": self.owner_component_id,
            "owner_component_version": self.owner_component_version,
            "disposition": self.disposition.value,
            "reason_codes": list(self.reason_codes),
            "limitations": list(self.limitations),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": self.receipt_id}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ProtocolAdmissionReceipt":
        if not isinstance(state, Mapping):
            raise ValueError("admission receipt state must be an object")
        expected_keys = frozenset(
            {
                "protocol",
                "subject_kind",
                "subject_protocol",
                "subject_id",
                "subject_state_digest",
                "semantic_digest",
                "context_digest",
                "owner_component_id",
                "owner_component_version",
                "disposition",
                "reason_codes",
                "limitations",
                "receipt_id",
            }
        )
        _exact_state_keys(state, expected_keys, "admission receipt")
        if state.get("protocol") != ADMISSION_PROTOCOL:
            raise ValueError("admission receipt protocol mismatch")
        if state.get("owner_component_id") != COMPONENT_ID or state.get("owner_component_version") != COMPONENT_VERSION:
            raise ValueError("admission receipt owner mismatch")
        raw_reasons = state.get("reason_codes")
        raw_limits = state.get("limitations")
        if not isinstance(raw_reasons, list) or not isinstance(raw_limits, list):
            raise ValueError("admission receipt reason_codes and limitations must be lists")
        if any(not isinstance(value, str) for value in raw_reasons + raw_limits):
            raise ValueError("admission receipt reason_codes and limitations require strings")
        expected = cls.create(
            subject_kind=state.get("subject_kind"),  # type: ignore[arg-type]
            subject_protocol=state.get("subject_protocol"),  # type: ignore[arg-type]
            subject_id=state.get("subject_id"),  # type: ignore[arg-type]
            subject_state_digest=state.get("subject_state_digest"),  # type: ignore[arg-type]
            semantic_digest=state.get("semantic_digest"),  # type: ignore[arg-type]
            context_digest=state.get("context_digest"),  # type: ignore[arg-type]
            disposition=state.get("disposition"),  # type: ignore[arg-type]
            reason_codes=tuple(raw_reasons),
            limitations=tuple(raw_limits),
        )
        if state.get("receipt_id") != expected.receipt_id:
            raise ValueError("admission receipt identity mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("admission receipt state is non-canonical")
        return expected

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("admission receipt integrity validation failed") from exc
        if restored != self:
            raise ValueError("admission receipt integrity validation failed")


__all__ = (
    "ADMISSION_PROTOCOL",
    "AdmissionDisposition",
    "AdmissionSubjectKind",
    "CanonicalAdmissionContext",
    "ProtocolAdmissionReceipt",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
)
