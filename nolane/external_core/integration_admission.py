from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.authority_graph import AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest


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
    if any(not isinstance(key, str) for key in state):
        raise ValueError(f"{label} state keys must be exact strings")
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


def _strict_serialized_string_list(value: object, label: str) -> list[str]:
    if type(value) is not list:
        raise ValueError(f"{label} must be a serialized list")
    rows = [_explicit(item, label) for item in value]
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return rows


def _strict_serialized_string_map(value: object, label: str) -> dict[str, str]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be a serialized object")
    rows: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = _explicit(raw_key, f"{label} key")
        item = _explicit(raw_value, f"{label} value")
        rows[key] = item
    return rows


def _canonical_current_objects() -> tuple[Any, Any]:
    # Local import avoids turning the historical A2/A3 audit module into an
    # A5 dependency. These builders are read-only canonical-current sources.
    from nolane.external_core.audit import build_canonical_fabric_profile, build_canonical_registry

    return build_canonical_registry(), build_canonical_fabric_profile()


def _current_context_reasons(context: "CanonicalAdmissionContext") -> tuple[str, ...]:
    context.validate_integrity()
    registry, profile = _canonical_current_objects()
    reasons: list[str] = []
    if context.registry_digest != registry.registry_digest:
        reasons.append("CANONICAL_REGISTRY_CONTEXT_MISMATCH")
    if context.authority_graph_digest != profile.authority_graph.digest:
        reasons.append("CANONICAL_AUTHORITY_GRAPH_CONTEXT_MISMATCH")
    return tuple(sorted(reasons))


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


_MANIFEST_KEYS = frozenset(
    {
        "component_id",
        "component_version",
        "family",
        "protocol_versions",
        "consumes_contracts",
        "produces_contracts",
        "authority_capabilities",
        "forbidden_authorities",
        "mutable_resources",
        "evidence_inputs",
        "evidence_outputs",
        "restore_protocol",
        "compatibility_floor",
        "compatibility_ceiling",
        "manifest_digest",
    }
)
_MANIFEST_LIST_FIELDS = (
    "consumes_contracts",
    "produces_contracts",
    "authority_capabilities",
    "forbidden_authorities",
    "mutable_resources",
    "evidence_inputs",
    "evidence_outputs",
)


def _strict_manifest_state(state: object) -> Mapping[str, Any]:
    if not isinstance(state, Mapping):
        raise ValueError("component manifest state must be an object")
    _exact_state_keys(state, _MANIFEST_KEYS, "component manifest")
    _explicit(state.get("component_id"), "component manifest component_id")
    _explicit(state.get("component_version"), "component manifest component_version")
    family = _explicit(state.get("family"), "component manifest family")
    if family not in {"A", "B", "C", "D", "E", "F", "G"}:
        raise ValueError("component manifest family is invalid")
    _strict_serialized_string_map(state.get("protocol_versions"), "component manifest protocol_versions")
    for field in _MANIFEST_LIST_FIELDS:
        _strict_serialized_string_list(state.get(field), f"component manifest {field}")
    _explicit(state.get("restore_protocol"), "component manifest restore_protocol")
    _explicit(state.get("compatibility_floor"), "component manifest compatibility_floor")
    _explicit(state.get("compatibility_ceiling"), "component manifest compatibility_ceiling")
    _explicit(state.get("manifest_digest"), "component manifest manifest_digest")
    return state


_EDGE_KEYS = frozenset(
    {"source_component_id", "target_component_id", "relation", "contract_kind", "digest"}
)


def _strict_authority_edge_state(state: object) -> Mapping[str, Any]:
    if not isinstance(state, Mapping):
        raise ValueError("authority edge state must be an object")
    _exact_state_keys(state, _EDGE_KEYS, "authority edge")
    _explicit(state.get("source_component_id"), "authority edge source_component_id")
    _explicit(state.get("target_component_id"), "authority edge target_component_id")
    relation = _explicit(state.get("relation"), "authority edge relation")
    try:
        AuthorityRelation(relation)
    except ValueError as exc:
        raise ValueError("authority edge relation is invalid") from exc
    _explicit(state.get("contract_kind"), "authority edge contract_kind")
    _explicit(state.get("digest"), "authority edge digest")
    return state


_GRAPH_KEYS = frozenset({"manifests", "edges", "digest"})


def _strict_authority_graph_state(state: object) -> Mapping[str, Any]:
    if not isinstance(state, Mapping):
        raise ValueError("authority graph state must be an object")
    _exact_state_keys(state, _GRAPH_KEYS, "authority graph")
    manifests = state.get("manifests")
    edges = state.get("edges")
    if type(manifests) is not list or type(edges) is not list:
        raise ValueError("authority graph manifests and edges must be serialized lists")
    for row in manifests:
        _strict_manifest_state(row)
    for row in edges:
        _strict_authority_edge_state(row)
    _explicit(state.get("digest"), "authority graph digest")
    return state


def _wrapper_digest(kind: AdmissionSubjectKind, subject_state_json: str, receipt: ProtocolAdmissionReceipt) -> str:
    payload = {
        "protocol": ADMISSION_PROTOCOL,
        "subject_kind": kind.value,
        "subject_state_digest": canonical_digest(json.loads(subject_state_json)),
        "receipt_id": receipt.receipt_id,
    }
    return "admission-wrapper-v2-" + canonical_digest(payload)


@dataclass(frozen=True, slots=True)
class AdmittedManifest:
    subject_state_json: str
    receipt: ProtocolAdmissionReceipt
    digest: str

    @property
    def subject_state(self) -> dict[str, Any]:
        value = json.loads(self.subject_state_json)
        if not isinstance(value, dict):
            raise ValueError("admitted manifest state must decode to an object")
        return value

    def to_state(self) -> dict[str, Any]:
        return {
            "subject_state": self.subject_state,
            "receipt": self.receipt.to_state(),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AdmittedManifest":
        _exact_state_keys(state, frozenset({"subject_state", "receipt", "digest"}), "admitted manifest")
        raw_subject = state.get("subject_state")
        raw_receipt = state.get("receipt")
        _strict_manifest_state(raw_subject)
        if not isinstance(raw_receipt, Mapping):
            raise ValueError("admitted manifest receipt must be an object")
        receipt = ProtocolAdmissionReceipt.from_state(raw_receipt)
        subject_json = canonical_json(raw_subject)
        expected = cls(
            subject_state_json=subject_json,
            receipt=receipt,
            digest=_wrapper_digest(AdmissionSubjectKind.COMPONENT_MANIFEST, subject_json, receipt),
        )
        if state.get("digest") != expected.digest or dict(state) != expected.to_state():
            raise ValueError("admitted manifest state is non-canonical")
        expected.validate_integrity()
        return expected

    def validate_integrity(self) -> None:
        self.receipt.validate_integrity()
        state = self.subject_state
        _strict_manifest_state(state)
        manifest = ExternalComponentManifest.from_state(state)
        if self.receipt.subject_kind is not AdmissionSubjectKind.COMPONENT_MANIFEST:
            raise ValueError("admitted manifest receipt kind mismatch")
        if self.receipt.subject_id != manifest.component_id:
            raise ValueError("admitted manifest receipt identity mismatch")
        if self.receipt.subject_state_digest != canonical_digest(state):
            raise ValueError("admitted manifest receipt state digest mismatch")
        if self.receipt.semantic_digest != manifest.manifest_digest:
            raise ValueError("admitted manifest receipt semantic digest mismatch")
        if self.digest != _wrapper_digest(AdmissionSubjectKind.COMPONENT_MANIFEST, self.subject_state_json, self.receipt):
            raise ValueError("admitted manifest wrapper digest mismatch")


@dataclass(frozen=True, slots=True)
class AdmittedAuthorityGraph:
    subject_state_json: str
    receipt: ProtocolAdmissionReceipt
    digest: str

    @property
    def subject_state(self) -> dict[str, Any]:
        value = json.loads(self.subject_state_json)
        if not isinstance(value, dict):
            raise ValueError("admitted authority graph state must decode to an object")
        return value

    def to_state(self) -> dict[str, Any]:
        return {
            "subject_state": self.subject_state,
            "receipt": self.receipt.to_state(),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AdmittedAuthorityGraph":
        _exact_state_keys(state, frozenset({"subject_state", "receipt", "digest"}), "admitted authority graph")
        raw_subject = state.get("subject_state")
        raw_receipt = state.get("receipt")
        _strict_authority_graph_state(raw_subject)
        if not isinstance(raw_receipt, Mapping):
            raise ValueError("admitted authority graph receipt must be an object")
        receipt = ProtocolAdmissionReceipt.from_state(raw_receipt)
        subject_json = canonical_json(raw_subject)
        expected = cls(
            subject_state_json=subject_json,
            receipt=receipt,
            digest=_wrapper_digest(AdmissionSubjectKind.AUTHORITY_GRAPH, subject_json, receipt),
        )
        if state.get("digest") != expected.digest or dict(state) != expected.to_state():
            raise ValueError("admitted authority graph state is non-canonical")
        expected.validate_integrity()
        return expected

    def validate_integrity(self) -> None:
        self.receipt.validate_integrity()
        state = self.subject_state
        _strict_authority_graph_state(state)
        graph = ExternalAuthorityGraph.from_state(state)
        graph.validate()
        if self.receipt.subject_kind is not AdmissionSubjectKind.AUTHORITY_GRAPH:
            raise ValueError("admitted authority graph receipt kind mismatch")
        if self.receipt.subject_id != "canonical-authority-graph":
            raise ValueError("admitted authority graph receipt identity mismatch")
        if self.receipt.subject_state_digest != canonical_digest(state):
            raise ValueError("admitted authority graph receipt state digest mismatch")
        if self.receipt.semantic_digest != graph.digest:
            raise ValueError("admitted authority graph receipt semantic digest mismatch")
        if self.digest != _wrapper_digest(AdmissionSubjectKind.AUTHORITY_GRAPH, self.subject_state_json, self.receipt):
            raise ValueError("admitted authority graph wrapper digest mismatch")


def admit_manifest_state(
    state: Mapping[str, Any],
    *,
    context: CanonicalAdmissionContext,
) -> AdmittedManifest:
    _strict_manifest_state(state)
    manifest = ExternalComponentManifest.from_state(state)
    registry, _profile = _canonical_current_objects()
    reasons = list(_current_context_reasons(context))
    try:
        current = registry.manifest_for(manifest.component_id)
    except KeyError:
        reasons.append("CANONICAL_MANIFEST_IDENTITY_UNKNOWN")
    else:
        if current.to_state() != manifest.to_state():
            reasons.append("CANONICAL_MANIFEST_MISMATCH")
    disposition = AdmissionDisposition.BLOCKED if reasons else AdmissionDisposition.ADMITTED
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.COMPONENT_MANIFEST,
        subject_protocol=AdmissionSubjectKind.COMPONENT_MANIFEST.value,
        subject_id=manifest.component_id,
        subject_state_digest=canonical_digest(manifest.to_state()),
        semantic_digest=manifest.manifest_digest,
        context_digest=context.digest,
        disposition=disposition,
        reason_codes=tuple(sorted(set(reasons))),
        limitations=("structural-currentness-only", "no-semantic-authority"),
    )
    subject_json = canonical_json(manifest.to_state())
    wrapper = AdmittedManifest(
        subject_state_json=subject_json,
        receipt=receipt,
        digest=_wrapper_digest(AdmissionSubjectKind.COMPONENT_MANIFEST, subject_json, receipt),
    )
    wrapper.validate_integrity()
    return wrapper


def admit_authority_graph_state(
    state: Mapping[str, Any],
    *,
    context: CanonicalAdmissionContext,
) -> AdmittedAuthorityGraph:
    _strict_authority_graph_state(state)
    graph = ExternalAuthorityGraph.from_state(state)
    graph.validate()
    registry, profile = _canonical_current_objects()
    reasons = list(_current_context_reasons(context))
    canonical_graph = profile.authority_graph
    if graph.to_state() != canonical_graph.to_state():
        reasons.append("CANONICAL_AUTHORITY_GRAPH_MISMATCH")
    graph_manifest_states = tuple(row.to_state() for row in graph.manifests)
    registry_manifest_states = tuple(row.to_state() for row in registry.manifests)
    if graph_manifest_states != registry_manifest_states:
        reasons.append("CANONICAL_GRAPH_REGISTRY_POPULATION_MISMATCH")
    disposition = AdmissionDisposition.BLOCKED if reasons else AdmissionDisposition.ADMITTED
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.AUTHORITY_GRAPH,
        subject_protocol=AdmissionSubjectKind.AUTHORITY_GRAPH.value,
        subject_id="canonical-authority-graph",
        subject_state_digest=canonical_digest(graph.to_state()),
        semantic_digest=graph.digest,
        context_digest=context.digest,
        disposition=disposition,
        reason_codes=tuple(sorted(set(reasons))),
        limitations=("structural-currentness-only", "no-semantic-authority"),
    )
    subject_json = canonical_json(graph.to_state())
    wrapper = AdmittedAuthorityGraph(
        subject_state_json=subject_json,
        receipt=receipt,
        digest=_wrapper_digest(AdmissionSubjectKind.AUTHORITY_GRAPH, subject_json, receipt),
    )
    wrapper.validate_integrity()
    return wrapper


__all__ = (
    "ADMISSION_PROTOCOL",
    "AdmissionDisposition",
    "AdmissionSubjectKind",
    "CanonicalAdmissionContext",
    "ProtocolAdmissionReceipt",
    "AdmittedManifest",
    "AdmittedAuthorityGraph",
    "admit_manifest_state",
    "admit_authority_graph_state",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
)
