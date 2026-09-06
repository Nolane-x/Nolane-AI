from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.authority_graph import AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest
from nolane.external_core.handoff import (
    HANDOFF_PROTOCOL,
    ExternalHandoffEnvelope,
    HandoffAuthorityClass,
    HandoffValidationDisposition,
    validate_handoff_for_consumer,
)
from nolane.external_core.work_trace import (
    WORK_TRACE_PROTOCOL,
    CognitiveWorkTrace,
    TraceNodeStatus,
)


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
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unknown:
            details.append("unknown=" + ",".join(unknown))
        raise ValueError(f"{label} state is non-canonical: " + ";".join(details))


def _canonical_strings(values: object, label: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{label} must be a tuple")
    rows = tuple(_explicit(value, label) for value in values)
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(rows))


def _serialized_strings(value: object, label: str) -> list[str]:
    if type(value) is not list:
        raise ValueError(f"{label} must be a serialized list")
    rows = [_explicit(item, label) for item in value]
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return rows


def _serialized_string_map(value: object, label: str) -> dict[str, str]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be a serialized object")
    rows: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = _explicit(raw_key, f"{label} key")
        item = _explicit(raw_value, f"{label} value")
        if key in rows:
            raise ValueError(f"duplicate {label} key")
        rows[key] = item
    return rows


def _canonical_current_objects() -> tuple[Any, Any]:
    from nolane.external_core.audit import build_canonical_fabric_profile, build_canonical_registry

    return build_canonical_registry(), build_canonical_fabric_profile()


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
            "source_state_frontier_digest": _explicit(source_state_frontier_digest, "admission source-state frontier digest"),
            "evidence_frontier_digest": _explicit(evidence_frontier_digest, "admission evidence frontier digest"),
            "artifact_frontier_digest": _explicit(artifact_frontier_digest, "admission artifact frontier digest"),
            "freshness_fence_frontier_digest": _explicit(freshness_fence_frontier_digest, "admission freshness frontier digest"),
            "handoff_frontier_digest": _explicit(handoff_frontier_digest, "admission handoff frontier digest"),
            "work_trace_frontier_digest": _explicit(work_trace_frontier_digest, "admission work-trace frontier digest"),
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
        _exact_state_keys(
            state,
            frozenset(
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
            ),
            "admission context",
        )
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
        if state.get("digest") != expected.digest or dict(state) != expected.to_state():
            raise ValueError("admission context state is non-canonical or digest-mismatched")
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
        _exact_state_keys(
            state,
            frozenset(
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
            ),
            "admission receipt",
        )
        if state.get("protocol") != ADMISSION_PROTOCOL:
            raise ValueError("admission receipt protocol mismatch")
        if state.get("owner_component_id") != COMPONENT_ID or state.get("owner_component_version") != COMPONENT_VERSION:
            raise ValueError("admission receipt owner mismatch")
        reasons = state.get("reason_codes")
        limits = state.get("limitations")
        if type(reasons) is not list or type(limits) is not list:
            raise ValueError("admission receipt reason_codes and limitations must be serialized lists")
        if any(not isinstance(value, str) for value in reasons + limits):
            raise ValueError("admission receipt reason_codes and limitations require strings")
        expected = cls.create(
            subject_kind=state.get("subject_kind"),  # type: ignore[arg-type]
            subject_protocol=state.get("subject_protocol"),  # type: ignore[arg-type]
            subject_id=state.get("subject_id"),  # type: ignore[arg-type]
            subject_state_digest=state.get("subject_state_digest"),  # type: ignore[arg-type]
            semantic_digest=state.get("semantic_digest"),  # type: ignore[arg-type]
            context_digest=state.get("context_digest"),  # type: ignore[arg-type]
            disposition=state.get("disposition"),  # type: ignore[arg-type]
            reason_codes=tuple(reasons),
            limitations=tuple(limits),
        )
        if state.get("receipt_id") != expected.receipt_id or dict(state) != expected.to_state():
            raise ValueError("admission receipt state is non-canonical or identity-mismatched")
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
_EDGE_KEYS = frozenset({"source_component_id", "target_component_id", "relation", "contract_kind", "digest"})
_HANDOFF_KEYS = frozenset(
    {
        "handoff_id",
        "producer_component_id",
        "producer_component_version",
        "producer_agent_id",
        "consumer_component_id",
        "consumer_contract_range",
        "subject_id",
        "subject_digest",
        "contract_kind",
        "contract_version",
        "authority_class",
        "source_state_digest",
        "predecessor_handoff_ids",
        "evidence_bindings",
        "artifact_bindings",
        "freshness_fence",
        "limitations",
        "known_unknowns",
        "payload_json",
        "payload_digest",
        "digest",
    }
)
_TRACE_KEYS = frozenset({"trace_id", "protocol", "nodes", "supersessions", "digest"})
_TRACE_NODE_KEYS = frozenset(
    {
        "node_id",
        "trace_id",
        "component_id",
        "subject_id",
        "subject_digest",
        "status",
        "predecessor_node_ids",
        "handoff_id",
        "evidence_refs",
        "limitations",
        "digest",
    }
)
_TRACE_SUPERSESSION_KEYS = frozenset(
    {"receipt_id", "trace_id", "predecessor_node_id", "successor_node_id", "reason", "evidence_refs", "digest"}
)
_FRONTIER_KINDS = frozenset({"source-state", "evidence", "artifact", "freshness", "handoff", "work-trace"})


def _strict_manifest_state(state: object) -> Mapping[str, Any]:
    if not isinstance(state, Mapping):
        raise ValueError("component manifest state must be an object")
    _exact_state_keys(state, _MANIFEST_KEYS, "component manifest")
    _explicit(state.get("component_id"), "component manifest component_id")
    _explicit(state.get("component_version"), "component manifest component_version")
    if _explicit(state.get("family"), "component manifest family") not in set("ABCDEFG"):
        raise ValueError("component manifest family is invalid")
    _serialized_string_map(state.get("protocol_versions"), "component manifest protocol_versions")
    for field in _MANIFEST_LIST_FIELDS:
        _serialized_strings(state.get(field), f"component manifest {field}")
    for field in ("restore_protocol", "compatibility_floor", "compatibility_ceiling", "manifest_digest"):
        _explicit(state.get(field), f"component manifest {field}")
    return state


def _strict_edge_state(state: object) -> Mapping[str, Any]:
    if not isinstance(state, Mapping):
        raise ValueError("authority edge state must be an object")
    _exact_state_keys(state, _EDGE_KEYS, "authority edge")
    for field in ("source_component_id", "target_component_id", "contract_kind", "digest"):
        _explicit(state.get(field), f"authority edge {field}")
    relation = _explicit(state.get("relation"), "authority edge relation")
    try:
        AuthorityRelation(relation)
    except ValueError as exc:
        raise ValueError("authority edge relation is invalid") from exc
    return state


def _strict_graph_state(state: object) -> Mapping[str, Any]:
    if not isinstance(state, Mapping):
        raise ValueError("authority graph state must be an object")
    _exact_state_keys(state, frozenset({"manifests", "edges", "digest"}), "authority graph")
    manifests = state.get("manifests")
    edges = state.get("edges")
    if type(manifests) is not list or type(edges) is not list:
        raise ValueError("authority graph manifests and edges must be serialized lists")
    for row in manifests:
        _strict_manifest_state(row)
    for row in edges:
        _strict_edge_state(row)
    _explicit(state.get("digest"), "authority graph digest")
    return state


def _strict_frontier(values: object, label: str) -> dict[str, str]:
    if not isinstance(values, Mapping):
        raise ValueError(f"{label} frontier must be an object")
    rows: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key = _explicit(raw_key, f"{label} frontier key")
        digest = _explicit(raw_value, f"{label} frontier digest")
        if key in rows:
            raise ValueError(f"duplicate {label} frontier key")
        rows[key] = digest
    return dict(sorted(rows.items()))


def canonical_frontier_digest(kind: str, values: Mapping[str, str]) -> str:
    frontier_kind = _explicit(kind, "admission frontier kind")
    if frontier_kind not in _FRONTIER_KINDS:
        raise ValueError(f"unsupported admission frontier kind: {frontier_kind}")
    rows = _strict_frontier(values, frontier_kind)
    payload = {
        "protocol": ADMISSION_PROTOCOL,
        "frontier_kind": frontier_kind,
        "entries": [{"id": key, "digest": value} for key, value in rows.items()],
    }
    return f"admission-{frontier_kind}-frontier-v2-" + canonical_digest(payload)


def _strict_bindings(value: object, label: str) -> None:
    if type(value) is not list:
        raise ValueError(f"handoff {label} bindings must be a serialized list")
    refs: set[str] = set()
    for row in value:
        if type(row) is not list or len(row) != 2:
            raise ValueError(f"handoff {label} binding must be an exact two-item serialized list")
        ref = _explicit(row[0], f"handoff {label} ref")
        _explicit(row[1], f"handoff {label} digest")
        if ref in refs:
            raise ValueError(f"duplicate handoff {label} ref")
        refs.add(ref)


def _strict_handoff_state(state: object) -> Mapping[str, Any]:
    if not isinstance(state, Mapping):
        raise ValueError("handoff state must be an object")
    _exact_state_keys(state, _HANDOFF_KEYS, "handoff")
    for field in (
        "handoff_id",
        "producer_component_id",
        "producer_component_version",
        "producer_agent_id",
        "consumer_component_id",
        "consumer_contract_range",
        "subject_id",
        "subject_digest",
        "contract_kind",
        "contract_version",
        "source_state_digest",
        "payload_json",
        "payload_digest",
        "digest",
    ):
        _explicit(state.get(field), f"handoff {field}")
    authority = _explicit(state.get("authority_class"), "handoff authority_class")
    try:
        HandoffAuthorityClass(authority)
    except ValueError as exc:
        raise ValueError("handoff authority_class is invalid") from exc
    _serialized_strings(state.get("predecessor_handoff_ids"), "handoff predecessor_handoff_ids")
    _strict_bindings(state.get("evidence_bindings"), "evidence")
    _strict_bindings(state.get("artifact_bindings"), "artifact")
    if state.get("freshness_fence") is not None:
        _explicit(state.get("freshness_fence"), "handoff freshness_fence")
    _serialized_strings(state.get("limitations"), "handoff limitations")
    _serialized_strings(state.get("known_unknowns"), "handoff known_unknowns")
    try:
        json.loads(state["payload_json"])
    except (TypeError, ValueError) as exc:
        raise ValueError("handoff payload_json is invalid JSON") from exc
    return state


def _strict_trace_node_state(state: object) -> Mapping[str, Any]:
    if not isinstance(state, Mapping):
        raise ValueError("work trace node state must be an object")
    _exact_state_keys(state, _TRACE_NODE_KEYS, "work trace node")
    for field in ("node_id", "trace_id", "component_id", "subject_id", "subject_digest", "digest"):
        _explicit(state.get(field), f"work trace node {field}")
    status = _explicit(state.get("status"), "work trace node status")
    try:
        TraceNodeStatus(status)
    except ValueError as exc:
        raise ValueError("work trace node status is invalid") from exc
    _serialized_strings(state.get("predecessor_node_ids"), "work trace node predecessor_node_ids")
    if state.get("handoff_id") is not None:
        _explicit(state.get("handoff_id"), "work trace node handoff_id")
    _serialized_strings(state.get("evidence_refs"), "work trace node evidence_refs")
    _serialized_strings(state.get("limitations"), "work trace node limitations")
    return state


def _strict_trace_supersession_state(state: object) -> Mapping[str, Any]:
    if not isinstance(state, Mapping):
        raise ValueError("work trace supersession state must be an object")
    _exact_state_keys(state, _TRACE_SUPERSESSION_KEYS, "work trace supersession")
    for field in ("receipt_id", "trace_id", "predecessor_node_id", "successor_node_id", "reason", "digest"):
        _explicit(state.get(field), f"work trace supersession {field}")
    _serialized_strings(state.get("evidence_refs"), "work trace supersession evidence_refs")
    return state


def _strict_work_trace_state(state: object) -> Mapping[str, Any]:
    if not isinstance(state, Mapping):
        raise ValueError("work trace state must be an object")
    _exact_state_keys(state, _TRACE_KEYS, "work trace")
    _explicit(state.get("trace_id"), "work trace trace_id")
    if state.get("protocol") != WORK_TRACE_PROTOCOL:
        raise ValueError("work trace protocol mismatch")
    nodes = state.get("nodes")
    supersessions = state.get("supersessions")
    if type(nodes) is not list or type(supersessions) is not list:
        raise ValueError("work trace nodes and supersessions must be serialized lists")
    node_ids: set[str] = set()
    for row in nodes:
        _strict_trace_node_state(row)
        node_id = row["node_id"]
        if node_id in node_ids:
            raise ValueError("duplicate work trace node id")
        node_ids.add(node_id)
    predecessor_ids: set[str] = set()
    for row in supersessions:
        _strict_trace_supersession_state(row)
        predecessor = row["predecessor_node_id"]
        if predecessor in predecessor_ids:
            raise ValueError("duplicate work trace supersession predecessor")
        predecessor_ids.add(predecessor)
    _explicit(state.get("digest"), "work trace digest")
    return state


def _wrapper_digest(kind: AdmissionSubjectKind, subject_state_json: str, receipt: ProtocolAdmissionReceipt) -> str:
    return "admission-wrapper-v2-" + canonical_digest(
        {
            "protocol": ADMISSION_PROTOCOL,
            "subject_kind": kind.value,
            "subject_state_digest": canonical_digest(json.loads(subject_state_json)),
            "receipt_id": receipt.receipt_id,
        }
    )


@dataclass(frozen=True, slots=True)
class _AdmittedSubject:
    subject_state_json: str
    receipt: ProtocolAdmissionReceipt
    digest: str
    KIND: ClassVar[AdmissionSubjectKind]

    @property
    def subject_state(self) -> dict[str, Any]:
        value = json.loads(self.subject_state_json)
        if not isinstance(value, dict):
            raise ValueError("admitted subject state must decode to an object")
        return value

    def to_state(self) -> dict[str, Any]:
        return {"subject_state": self.subject_state, "receipt": self.receipt.to_state(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "_AdmittedSubject":
        _exact_state_keys(state, frozenset({"subject_state", "receipt", "digest"}), f"admitted {cls.KIND.value}")
        raw_subject = state.get("subject_state")
        raw_receipt = state.get("receipt")
        cls._strict_state(raw_subject)
        if not isinstance(raw_receipt, Mapping):
            raise ValueError("admitted subject receipt must be an object")
        receipt = ProtocolAdmissionReceipt.from_state(raw_receipt)
        subject_json = canonical_json(raw_subject)
        expected = cls(subject_json, receipt, _wrapper_digest(cls.KIND, subject_json, receipt))
        if state.get("digest") != expected.digest or dict(state) != expected.to_state():
            raise ValueError("admitted subject state is non-canonical")
        expected.validate_integrity()
        return expected

    @classmethod
    def _strict_state(cls, state: object) -> Mapping[str, Any]:
        raise NotImplementedError

    def _semantic(self) -> tuple[str, str, str]:
        raise NotImplementedError

    def validate_integrity(self) -> None:
        self.receipt.validate_integrity()
        self._strict_state(self.subject_state)
        subject_id, semantic_digest, protocol = self._semantic()
        if self.receipt.subject_kind is not self.KIND:
            raise ValueError("admitted subject receipt kind mismatch")
        if self.receipt.subject_protocol != protocol:
            raise ValueError("admitted subject receipt protocol mismatch")
        if self.receipt.subject_id != subject_id:
            raise ValueError("admitted subject receipt identity mismatch")
        if self.receipt.subject_state_digest != canonical_digest(self.subject_state):
            raise ValueError("admitted subject receipt state digest mismatch")
        if self.receipt.semantic_digest != semantic_digest:
            raise ValueError("admitted subject receipt semantic digest mismatch")
        if self.digest != _wrapper_digest(self.KIND, self.subject_state_json, self.receipt):
            raise ValueError("admitted subject wrapper digest mismatch")


class AdmittedManifest(_AdmittedSubject):
    KIND = AdmissionSubjectKind.COMPONENT_MANIFEST

    @classmethod
    def _strict_state(cls, state: object) -> Mapping[str, Any]:
        return _strict_manifest_state(state)

    def _semantic(self) -> tuple[str, str, str]:
        manifest = ExternalComponentManifest.from_state(self.subject_state)
        return manifest.component_id, manifest.manifest_digest, self.KIND.value


class AdmittedAuthorityGraph(_AdmittedSubject):
    KIND = AdmissionSubjectKind.AUTHORITY_GRAPH

    @classmethod
    def _strict_state(cls, state: object) -> Mapping[str, Any]:
        return _strict_graph_state(state)

    def _semantic(self) -> tuple[str, str, str]:
        graph = ExternalAuthorityGraph.from_state(self.subject_state)
        graph.validate()
        return "canonical-authority-graph", graph.digest, self.KIND.value


class AdmittedHandoff(_AdmittedSubject):
    KIND = AdmissionSubjectKind.HANDOFF

    @classmethod
    def _strict_state(cls, state: object) -> Mapping[str, Any]:
        return _strict_handoff_state(state)

    def _semantic(self) -> tuple[str, str, str]:
        envelope = ExternalHandoffEnvelope.from_state(self.subject_state)
        return envelope.handoff_id, envelope.digest, HANDOFF_PROTOCOL


class AdmittedWorkTrace(_AdmittedSubject):
    KIND = AdmissionSubjectKind.WORK_TRACE

    @classmethod
    def _strict_state(cls, state: object) -> Mapping[str, Any]:
        return _strict_work_trace_state(state)

    def _semantic(self) -> tuple[str, str, str]:
        trace = CognitiveWorkTrace.from_state(self.subject_state)
        return trace.trace_id, trace.digest, WORK_TRACE_PROTOCOL


def _make_wrapper(cls: type[_AdmittedSubject], state: Mapping[str, Any], receipt: ProtocolAdmissionReceipt) -> _AdmittedSubject:
    subject_json = canonical_json(state)
    wrapper = cls(subject_json, receipt, _wrapper_digest(cls.KIND, subject_json, receipt))
    wrapper.validate_integrity()
    return wrapper


def _context_reasons(context: CanonicalAdmissionContext) -> list[str]:
    context.validate_integrity()
    registry, profile = _canonical_current_objects()
    reasons: list[str] = []
    if context.registry_digest != registry.registry_digest:
        reasons.append("CANONICAL_REGISTRY_CONTEXT_MISMATCH")
    if context.authority_graph_digest != profile.authority_graph.digest:
        reasons.append("CANONICAL_AUTHORITY_GRAPH_CONTEXT_MISMATCH")
    return reasons


def _disposition(blocked: list[str], unknown: list[str]) -> tuple[AdmissionDisposition, tuple[str, ...]]:
    blocked_codes = tuple(sorted(set(blocked)))
    unknown_codes = tuple(sorted(set(unknown)))
    if blocked_codes:
        return AdmissionDisposition.BLOCKED, blocked_codes + unknown_codes
    if unknown_codes:
        return AdmissionDisposition.UNKNOWN, unknown_codes
    return AdmissionDisposition.ADMITTED, ()


def admit_manifest_state(state: Mapping[str, Any], *, context: CanonicalAdmissionContext) -> AdmittedManifest:
    _strict_manifest_state(state)
    manifest = ExternalComponentManifest.from_state(state)
    registry, _ = _canonical_current_objects()
    reasons = _context_reasons(context)
    try:
        current = registry.manifest_for(manifest.component_id)
    except KeyError:
        reasons.append("CANONICAL_MANIFEST_IDENTITY_UNKNOWN")
    else:
        if current.to_state() != manifest.to_state():
            reasons.append("CANONICAL_MANIFEST_MISMATCH")
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.COMPONENT_MANIFEST,
        subject_protocol=AdmissionSubjectKind.COMPONENT_MANIFEST.value,
        subject_id=manifest.component_id,
        subject_state_digest=canonical_digest(manifest.to_state()),
        semantic_digest=manifest.manifest_digest,
        context_digest=context.digest,
        disposition=AdmissionDisposition.BLOCKED if reasons else AdmissionDisposition.ADMITTED,
        reason_codes=tuple(sorted(set(reasons))),
        limitations=("structural-currentness-only", "no-semantic-authority"),
    )
    return _make_wrapper(AdmittedManifest, manifest.to_state(), receipt)  # type: ignore[return-value]


def admit_authority_graph_state(state: Mapping[str, Any], *, context: CanonicalAdmissionContext) -> AdmittedAuthorityGraph:
    _strict_graph_state(state)
    graph = ExternalAuthorityGraph.from_state(state)
    graph.validate()
    registry, profile = _canonical_current_objects()
    reasons = _context_reasons(context)
    if graph.to_state() != profile.authority_graph.to_state():
        reasons.append("CANONICAL_AUTHORITY_GRAPH_MISMATCH")
    if tuple(row.to_state() for row in graph.manifests) != tuple(row.to_state() for row in registry.manifests):
        reasons.append("CANONICAL_GRAPH_REGISTRY_POPULATION_MISMATCH")
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.AUTHORITY_GRAPH,
        subject_protocol=AdmissionSubjectKind.AUTHORITY_GRAPH.value,
        subject_id="canonical-authority-graph",
        subject_state_digest=canonical_digest(graph.to_state()),
        semantic_digest=graph.digest,
        context_digest=context.digest,
        disposition=AdmissionDisposition.BLOCKED if reasons else AdmissionDisposition.ADMITTED,
        reason_codes=tuple(sorted(set(reasons))),
        limitations=("structural-currentness-only", "no-semantic-authority"),
    )
    return _make_wrapper(AdmittedAuthorityGraph, graph.to_state(), receipt)  # type: ignore[return-value]


def admit_handoff_state(
    state: Mapping[str, Any],
    *,
    context: CanonicalAdmissionContext,
    current_source_state_digests: Mapping[str, str],
    current_evidence_digests: Mapping[str, str],
    current_artifact_digests: Mapping[str, str],
    current_freshness_fences: Mapping[str, str],
    known_handoff_digests: Mapping[str, str],
) -> AdmittedHandoff:
    _strict_handoff_state(state)
    envelope = ExternalHandoffEnvelope.from_state(state)
    registry, _profile = _canonical_current_objects()
    source = _strict_frontier(current_source_state_digests, "source-state")
    evidence = _strict_frontier(current_evidence_digests, "evidence")
    artifact = _strict_frontier(current_artifact_digests, "artifact")
    freshness = _strict_frontier(current_freshness_fences, "freshness")
    handoffs = _strict_frontier(known_handoff_digests, "handoff")
    blocked = _context_reasons(context)
    for expected, actual, code in (
        (context.source_state_frontier_digest, canonical_frontier_digest("source-state", source), "SOURCE_STATE_FRONTIER_CONTEXT_MISMATCH"),
        (context.evidence_frontier_digest, canonical_frontier_digest("evidence", evidence), "EVIDENCE_FRONTIER_CONTEXT_MISMATCH"),
        (context.artifact_frontier_digest, canonical_frontier_digest("artifact", artifact), "ARTIFACT_FRONTIER_CONTEXT_MISMATCH"),
        (context.freshness_fence_frontier_digest, canonical_frontier_digest("freshness", freshness), "FRESHNESS_FRONTIER_CONTEXT_MISMATCH"),
        (context.handoff_frontier_digest, canonical_frontier_digest("handoff", handoffs), "HANDOFF_FRONTIER_CONTEXT_MISMATCH"),
    ):
        if expected != actual:
            blocked.append(code)
    unknown: list[str] = []
    try:
        producer = registry.manifest_for(envelope.producer_component_id)
        consumer = registry.manifest_for(envelope.consumer_component_id)
    except KeyError:
        blocked.append("CANONICAL_HANDOFF_COMPONENT_UNKNOWN")
    else:
        validation = validate_handoff_for_consumer(
            envelope,
            producer_manifest=producer,
            consumer_manifest=consumer,
            current_source_state_digest=source.get(envelope.producer_component_id),
            current_evidence_digests=evidence,
            current_artifact_digests=artifact,
            known_predecessor_handoff_ids=tuple(handoffs),
            current_freshness_fence=freshness.get(envelope.producer_component_id),
        )
        if validation.disposition is HandoffValidationDisposition.BLOCKED:
            blocked.extend(validation.reason_codes)
        elif validation.disposition is HandoffValidationDisposition.UNKNOWN:
            unknown.extend(validation.reason_codes)
    disposition, reasons = _disposition(blocked, unknown)
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.HANDOFF,
        subject_protocol=HANDOFF_PROTOCOL,
        subject_id=envelope.handoff_id,
        subject_state_digest=canonical_digest(envelope.to_state()),
        semantic_digest=envelope.digest,
        context_digest=context.digest,
        disposition=disposition,
        reason_codes=reasons,
        limitations=("structural-currentness-only", "handoff-authority-class-does-not-mint-authority"),
    )
    return _make_wrapper(AdmittedHandoff, envelope.to_state(), receipt)  # type: ignore[return-value]


def admit_work_trace_state(
    state: Mapping[str, Any],
    *,
    context: CanonicalAdmissionContext,
    known_handoff_digests: Mapping[str, str],
    current_work_trace_digests: Mapping[str, str],
) -> AdmittedWorkTrace:
    _strict_work_trace_state(state)
    trace = CognitiveWorkTrace.from_state(state)
    handoffs = _strict_frontier(known_handoff_digests, "handoff")
    traces = _strict_frontier(current_work_trace_digests, "work-trace")
    blocked = _context_reasons(context)
    if context.handoff_frontier_digest != canonical_frontier_digest("handoff", handoffs):
        blocked.append("HANDOFF_FRONTIER_CONTEXT_MISMATCH")
    if context.work_trace_frontier_digest != canonical_frontier_digest("work-trace", traces):
        blocked.append("WORK_TRACE_FRONTIER_CONTEXT_MISMATCH")
    unknown: list[str] = []
    current = traces.get(trace.trace_id)
    if current is None:
        unknown.append("MISSING_CURRENT_WORK_TRACE")
    elif current != trace.digest:
        blocked.append("WORK_TRACE_DIGEST_DRIFT")
    diagnostics = trace.diagnostics(known_handoff_ids=tuple(handoffs))
    blocked.extend(row.code for row in diagnostics)
    disposition, reasons = _disposition(blocked, unknown)
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.WORK_TRACE,
        subject_protocol=WORK_TRACE_PROTOCOL,
        subject_id=trace.trace_id,
        subject_state_digest=canonical_digest(trace.to_state()),
        semantic_digest=trace.digest,
        context_digest=context.digest,
        disposition=disposition,
        reason_codes=reasons,
        limitations=("structural-currentness-only", "work-trace-provenance-does-not-mint-authority"),
    )
    return _make_wrapper(AdmittedWorkTrace, trace.to_state(), receipt)  # type: ignore[return-value]


__all__ = (
    "ADMISSION_PROTOCOL",
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
    "COMPONENT_ID",
    "COMPONENT_VERSION",
)
