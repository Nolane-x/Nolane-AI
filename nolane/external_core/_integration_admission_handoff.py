from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.handoff import (
    HANDOFF_PROTOCOL,
    ExternalHandoffEnvelope,
    HandoffAuthorityClass,
    HandoffValidationDisposition,
    validate_handoff_for_consumer,
)
from nolane.external_core.integration_admission import (
    ADMISSION_PROTOCOL,
    AdmissionDisposition,
    AdmissionSubjectKind,
    CanonicalAdmissionContext,
    ProtocolAdmissionReceipt,
    _canonical_current_objects,
    _exact_state_keys,
    _explicit,
    _wrapper_digest,
)


_FRONTIER_KINDS = frozenset(
    {"source-state", "evidence", "artifact", "freshness", "handoff", "work-trace"}
)


def _strict_frontier(values: Mapping[str, str] | object, label: str) -> dict[str, str]:
    if not isinstance(values, Mapping):
        raise ValueError(f"{label} frontier must be an object")
    rows: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key = _explicit(raw_key, f"{label} frontier key")
        value = _explicit(raw_value, f"{label} frontier digest")
        if key in rows:
            raise ValueError(f"duplicate {label} frontier key")
        rows[key] = value
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


def _strict_serialized_string_list(value: object, label: str) -> list[str]:
    if type(value) is not list:
        raise ValueError(f"{label} must be a serialized list")
    rows = [_explicit(item, label) for item in value]
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return rows


def _strict_binding_rows(value: object, label: str) -> list[list[str]]:
    if type(value) is not list:
        raise ValueError(f"handoff {label} bindings must be a serialized list")
    rows: list[list[str]] = []
    refs: set[str] = set()
    for raw in value:
        if type(raw) is not list or len(raw) != 2:
            raise ValueError(f"handoff {label} binding must be an exact two-item serialized list")
        ref = _explicit(raw[0], f"handoff {label} ref")
        digest = _explicit(raw[1], f"handoff {label} digest")
        if ref in refs:
            raise ValueError(f"duplicate handoff {label} ref")
        refs.add(ref)
        rows.append([ref, digest])
    return rows


def strict_handoff_state(state: object) -> Mapping[str, Any]:
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
    _strict_serialized_string_list(state.get("predecessor_handoff_ids"), "handoff predecessor_handoff_ids")
    _strict_binding_rows(state.get("evidence_bindings"), "evidence")
    _strict_binding_rows(state.get("artifact_bindings"), "artifact")
    fence = state.get("freshness_fence")
    if fence is not None:
        _explicit(fence, "handoff freshness_fence")
    _strict_serialized_string_list(state.get("limitations"), "handoff limitations")
    _strict_serialized_string_list(state.get("known_unknowns"), "handoff known_unknowns")
    payload_json = state.get("payload_json")
    assert isinstance(payload_json, str)
    try:
        json.loads(payload_json)
    except (TypeError, ValueError) as exc:
        raise ValueError("handoff payload_json is invalid JSON") from exc
    return state


@dataclass(frozen=True, slots=True)
class AdmittedHandoff:
    subject_state_json: str
    receipt: ProtocolAdmissionReceipt
    digest: str

    @property
    def subject_state(self) -> dict[str, Any]:
        value = json.loads(self.subject_state_json)
        if not isinstance(value, dict):
            raise ValueError("admitted handoff state must decode to an object")
        return value

    def to_state(self) -> dict[str, Any]:
        return {
            "subject_state": self.subject_state,
            "receipt": self.receipt.to_state(),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AdmittedHandoff":
        _exact_state_keys(state, frozenset({"subject_state", "receipt", "digest"}), "admitted handoff")
        raw_subject = state.get("subject_state")
        raw_receipt = state.get("receipt")
        strict_handoff_state(raw_subject)
        if not isinstance(raw_receipt, Mapping):
            raise ValueError("admitted handoff receipt must be an object")
        receipt = ProtocolAdmissionReceipt.from_state(raw_receipt)
        subject_json = canonical_json(raw_subject)
        expected = cls(
            subject_state_json=subject_json,
            receipt=receipt,
            digest=_wrapper_digest(AdmissionSubjectKind.HANDOFF, subject_json, receipt),
        )
        if state.get("digest") != expected.digest or dict(state) != expected.to_state():
            raise ValueError("admitted handoff state is non-canonical")
        expected.validate_integrity()
        return expected

    def validate_integrity(self) -> None:
        self.receipt.validate_integrity()
        state = self.subject_state
        strict_handoff_state(state)
        envelope = ExternalHandoffEnvelope.from_state(state)
        if self.receipt.subject_kind is not AdmissionSubjectKind.HANDOFF:
            raise ValueError("admitted handoff receipt kind mismatch")
        if self.receipt.subject_protocol != HANDOFF_PROTOCOL:
            raise ValueError("admitted handoff receipt protocol mismatch")
        if self.receipt.subject_id != envelope.handoff_id:
            raise ValueError("admitted handoff receipt identity mismatch")
        if self.receipt.subject_state_digest != canonical_digest(state):
            raise ValueError("admitted handoff receipt state digest mismatch")
        if self.receipt.semantic_digest != envelope.digest:
            raise ValueError("admitted handoff receipt semantic digest mismatch")
        if self.digest != _wrapper_digest(AdmissionSubjectKind.HANDOFF, self.subject_state_json, self.receipt):
            raise ValueError("admitted handoff wrapper digest mismatch")


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
    strict_handoff_state(state)
    context.validate_integrity()
    envelope = ExternalHandoffEnvelope.from_state(state)
    registry, profile = _canonical_current_objects()

    source = _strict_frontier(current_source_state_digests, "source-state")
    evidence = _strict_frontier(current_evidence_digests, "evidence")
    artifact = _strict_frontier(current_artifact_digests, "artifact")
    freshness = _strict_frontier(current_freshness_fences, "freshness")
    handoffs = _strict_frontier(known_handoff_digests, "handoff")

    blocked: list[str] = []
    if context.registry_digest != registry.registry_digest:
        blocked.append("CANONICAL_REGISTRY_CONTEXT_MISMATCH")
    if context.authority_graph_digest != profile.authority_graph.digest:
        blocked.append("CANONICAL_AUTHORITY_GRAPH_CONTEXT_MISMATCH")
    frontier_checks = (
        (context.source_state_frontier_digest, canonical_frontier_digest("source-state", source), "SOURCE_STATE_FRONTIER_CONTEXT_MISMATCH"),
        (context.evidence_frontier_digest, canonical_frontier_digest("evidence", evidence), "EVIDENCE_FRONTIER_CONTEXT_MISMATCH"),
        (context.artifact_frontier_digest, canonical_frontier_digest("artifact", artifact), "ARTIFACT_FRONTIER_CONTEXT_MISMATCH"),
        (context.freshness_fence_frontier_digest, canonical_frontier_digest("freshness", freshness), "FRESHNESS_FRONTIER_CONTEXT_MISMATCH"),
        (context.handoff_frontier_digest, canonical_frontier_digest("handoff", handoffs), "HANDOFF_FRONTIER_CONTEXT_MISMATCH"),
    )
    for expected, actual, code in frontier_checks:
        if expected != actual:
            blocked.append(code)

    try:
        producer = registry.manifest_for(envelope.producer_component_id)
        consumer = registry.manifest_for(envelope.consumer_component_id)
    except KeyError:
        blocked.append("CANONICAL_HANDOFF_COMPONENT_UNKNOWN")
        validation = None
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

    unknown: list[str] = []
    if validation is not None:
        if validation.disposition is HandoffValidationDisposition.BLOCKED:
            blocked.extend(validation.reason_codes)
        elif validation.disposition is HandoffValidationDisposition.UNKNOWN:
            unknown.extend(validation.reason_codes)

    blocked_codes = tuple(sorted(set(blocked)))
    unknown_codes = tuple(sorted(set(unknown)))
    if blocked_codes:
        disposition = AdmissionDisposition.BLOCKED
        reasons = blocked_codes + unknown_codes
    elif unknown_codes:
        disposition = AdmissionDisposition.UNKNOWN
        reasons = unknown_codes
    else:
        disposition = AdmissionDisposition.ADMITTED
        reasons = ()

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
    subject_json = canonical_json(envelope.to_state())
    wrapper = AdmittedHandoff(
        subject_state_json=subject_json,
        receipt=receipt,
        digest=_wrapper_digest(AdmissionSubjectKind.HANDOFF, subject_json, receipt),
    )
    wrapper.validate_integrity()
    return wrapper


__all__ = ("AdmittedHandoff", "admit_handoff_state", "canonical_frontier_digest", "strict_handoff_state")
