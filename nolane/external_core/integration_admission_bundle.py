from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.observation import CanonicalObservationEnvelope, ObservationFinding
from nolane.external_core.observation_integration import (
    CANONICAL_OBSERVATION_CHAIN_ID,
    build_observation_from_snapshot,
    validate_observation_against_snapshot,
)
from nolane.external_core.handoff import (
    HANDOFF_PROTOCOL,
    ExternalHandoffEnvelope,
    HandoffValidationDisposition,
    validate_handoff_for_consumer,
)
import nolane.external_core.integration_admission as admission_protocol
from nolane.external_core.integration_admission import (
    ADMISSION_PROTOCOL,
    AdmissionDisposition,
    AdmissionSubjectKind,
    AdmittedAuthorityGraph,
    AdmittedHandoff,
    AdmittedManifest,
    AdmittedWorkTrace,
    CanonicalAdmissionContext,
    ProtocolAdmissionReceipt,
    canonical_frontier_digest,
)
from nolane.external_core.work_trace import WORK_TRACE_PROTOCOL, CognitiveWorkTrace


COMPONENT_ID = "external.integration"
COMPONENT_VERSION = "0.0.8"
ADMISSION_BUNDLE_PROTOCOL = "external-integration-admission-bundle-v2"
HISTORICAL_ADMISSION_AUDIT_PROTOCOL = "external-integration-admission-audit-v3"
ADMISSION_AUDIT_PROTOCOL = "external-integration-admission-audit-v4"
CURRENT_ADMISSION_AUDIT_PROTOCOL = ADMISSION_AUDIT_PROTOCOL


def _exact_keys(state: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if any(type(key) is not str for key in state):
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


def _strict_current_objects() -> tuple[Any, Any]:
    """Build current A3 objects only after exact source identity checks.

    A3 intentionally preserves its historical construction behavior. The A5
    current lane adds a stricter preflight so an object with a convincing
    ``__str__`` cannot be laundered into a canonical registry identity/version.
    """

    from nolane.external_core.audit import (
        _canonical_adapter_specs,
        build_canonical_fabric_profile,
        build_canonical_registry,
    )

    for spec in _canonical_adapter_specs():
        source = spec.source
        component_id = getattr(source, "COMPONENT_ID", None)
        component_version = getattr(source, "COMPONENT_VERSION", None)
        if type(component_id) is not str or not component_id.strip():
            raise ValueError("canonical source COMPONENT_ID must be an exact non-empty string")
        if type(component_version) is not str or not component_version.strip():
            raise ValueError("canonical source COMPONENT_VERSION must be an exact non-empty string")

    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    if profile.manifests != registry.manifests:
        raise ValueError("canonical admission profile does not match registry manifests")
    return registry, profile


def _strict_sequence_state(value: object, label: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f"{label} must be a serialized list")
    return value


def _require_admitted(child: Any, context: CanonicalAdmissionContext, label: str) -> None:
    child.validate_integrity()
    if child.receipt.context_digest != context.digest:
        raise ValueError(f"{label} receipt belongs to another admission context")
    if child.receipt.disposition is not AdmissionDisposition.ADMITTED:
        raise ValueError(f"{label} must be ADMITTED before bundle construction")


def _unique_subjects(children: Sequence[Any], label: str) -> tuple[Any, ...]:
    ordered = tuple(sorted(children, key=lambda row: row.receipt.subject_id))
    seen: set[str] = set()
    for child in ordered:
        subject_id = child.receipt.subject_id
        if subject_id in seen:
            raise ValueError(f"duplicate {label} subject identity: {subject_id}")
        seen.add(subject_id)
    return ordered


def _bundle_payload(
    *,
    context: CanonicalAdmissionContext,
    manifests: tuple[AdmittedManifest, ...],
    authority_graph: AdmittedAuthorityGraph,
    handoffs: tuple[AdmittedHandoff, ...],
    work_traces: tuple[AdmittedWorkTrace, ...],
) -> dict[str, Any]:
    return {
        "protocol": ADMISSION_BUNDLE_PROTOCOL,
        "admission_protocol": ADMISSION_PROTOCOL,
        "context_digest": context.digest,
        "manifest_digests": [row.digest for row in manifests],
        "authority_graph_digest": authority_graph.digest,
        "handoff_digests": [row.digest for row in handoffs],
        "work_trace_digests": [row.digest for row in work_traces],
    }


@dataclass(frozen=True, slots=True)
class CanonicalAdmissionBundle:
    protocol: str
    context: CanonicalAdmissionContext
    manifests: tuple[AdmittedManifest, ...]
    authority_graph: AdmittedAuthorityGraph
    handoffs: tuple[AdmittedHandoff, ...]
    work_traces: tuple[AdmittedWorkTrace, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        context: CanonicalAdmissionContext,
        manifests: Sequence[AdmittedManifest],
        authority_graph: AdmittedAuthorityGraph,
        handoffs: Sequence[AdmittedHandoff] = (),
        work_traces: Sequence[AdmittedWorkTrace] = (),
    ) -> "CanonicalAdmissionBundle":
        context.validate_integrity()
        manifest_rows = _unique_subjects(manifests, "manifest")
        handoff_rows = _unique_subjects(handoffs, "handoff")
        trace_rows = _unique_subjects(work_traces, "work-trace")

        for child in manifest_rows:
            _require_admitted(child, context, "manifest")
        _require_admitted(authority_graph, context, "authority graph")
        for child in handoff_rows:
            _require_admitted(child, context, "handoff")
        for child in trace_rows:
            _require_admitted(child, context, "work trace")

        manifest_states = {row.receipt.subject_id: row.subject_state for row in manifest_rows}
        graph_state = authority_graph.subject_state
        graph_manifests_raw = graph_state.get("manifests")
        if type(graph_manifests_raw) is not list:
            raise ValueError("admitted authority graph manifest population is non-canonical")
        graph_manifest_states: dict[str, Mapping[str, Any]] = {}
        for raw in graph_manifests_raw:
            if type(raw) is not dict:
                raise ValueError("admitted authority graph manifest state must be an object")
            component_id = raw.get("component_id")
            if type(component_id) is not str or not component_id.strip():
                raise ValueError("admitted authority graph manifest identity is invalid")
            if component_id in graph_manifest_states:
                raise ValueError(f"duplicate authority-graph manifest identity: {component_id}")
            graph_manifest_states[component_id] = raw
        if graph_manifest_states != manifest_states:
            raise ValueError("admitted manifest population does not exactly match authority graph")

        manifest_ids = frozenset(manifest_states)
        admitted_handoff_ids = frozenset(row.receipt.subject_id for row in handoff_rows)
        for handoff in handoff_rows:
            state = handoff.subject_state
            producer = state.get("producer_component_id")
            consumer = state.get("consumer_component_id")
            if producer not in manifest_ids or consumer not in manifest_ids:
                raise ValueError("admitted handoff references a component outside admitted manifest population")

        for trace in trace_rows:
            nodes = trace.subject_state.get("nodes")
            if type(nodes) is not list:
                raise ValueError("admitted work trace nodes are non-canonical")
            for node in nodes:
                if type(node) is not dict:
                    raise ValueError("admitted work trace node must be an object")
                handoff_id = node.get("handoff_id")
                if handoff_id is not None and handoff_id not in admitted_handoff_ids:
                    raise ValueError("admitted work trace references a handoff outside admitted handoff population")

        payload = _bundle_payload(
            context=context,
            manifests=manifest_rows,
            authority_graph=authority_graph,
            handoffs=handoff_rows,
            work_traces=trace_rows,
        )
        return cls(
            protocol=ADMISSION_BUNDLE_PROTOCOL,
            context=context,
            manifests=manifest_rows,
            authority_graph=authority_graph,
            handoffs=handoff_rows,
            work_traces=trace_rows,
            digest="admission-bundle-v2-" + canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "context": self.context.to_state(),
            "manifests": [row.to_state() for row in self.manifests],
            "authority_graph": self.authority_graph.to_state(),
            "handoffs": [row.to_state() for row in self.handoffs],
            "work_traces": [row.to_state() for row in self.work_traces],
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CanonicalAdmissionBundle":
        if not isinstance(state, Mapping):
            raise ValueError("canonical admission bundle state must be an object")
        _exact_keys(
            state,
            frozenset({"protocol", "context", "manifests", "authority_graph", "handoffs", "work_traces", "digest"}),
            "canonical admission bundle",
        )
        if state.get("protocol") != ADMISSION_BUNDLE_PROTOCOL:
            raise ValueError("canonical admission bundle protocol mismatch")
        raw_context = state.get("context")
        raw_graph = state.get("authority_graph")
        if not isinstance(raw_context, Mapping) or not isinstance(raw_graph, Mapping):
            raise ValueError("canonical admission bundle context and graph must be objects")
        manifests_raw = _strict_sequence_state(state.get("manifests"), "canonical admission bundle manifests")
        handoffs_raw = _strict_sequence_state(state.get("handoffs"), "canonical admission bundle handoffs")
        traces_raw = _strict_sequence_state(state.get("work_traces"), "canonical admission bundle work traces")
        context = CanonicalAdmissionContext.from_state(raw_context)
        manifests = tuple(AdmittedManifest.from_state(row) for row in manifests_raw)
        graph = AdmittedAuthorityGraph.from_state(raw_graph)
        handoffs = tuple(AdmittedHandoff.from_state(row) for row in handoffs_raw)
        traces = tuple(AdmittedWorkTrace.from_state(row) for row in traces_raw)
        expected = cls.create(
            context=context,
            manifests=manifests,
            authority_graph=graph,
            handoffs=handoffs,
            work_traces=traces,
        )
        if state.get("digest") != expected.digest or dict(state) != expected.to_state():
            raise ValueError("canonical admission bundle state is non-canonical or digest-mismatched")
        return expected

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("canonical admission bundle integrity validation failed") from exc
        if restored != self:
            raise ValueError("canonical admission bundle integrity validation failed")


def _frontier(value: Mapping[str, str] | None) -> Mapping[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("frontier must be an object")
    return dict(value.items())


def _current_observation_frontier(
    value: Mapping[str, str] | None,
    label: str,
) -> Mapping[str, str]:
    if value is None:
        raise ValueError(f"current observation {label} surface unavailable")
    return _frontier(value)


def _context_from_observation(
    registry: Any,
    profile: Any,
    *,
    observed_epoch: int,
    source: Mapping[str, str],
    evidence: Mapping[str, str],
    artifact: Mapping[str, str],
    freshness: Mapping[str, str],
    handoffs: Mapping[str, str],
    traces: Mapping[str, str],
) -> CanonicalAdmissionContext:
    return CanonicalAdmissionContext.create(
        registry_digest=registry.registry_digest,
        authority_graph_digest=profile.authority_graph.digest,
        source_state_frontier_digest=canonical_frontier_digest("source-state", source),
        evidence_frontier_digest=canonical_frontier_digest("evidence", evidence),
        artifact_frontier_digest=canonical_frontier_digest("artifact", artifact),
        freshness_fence_frontier_digest=canonical_frontier_digest("freshness", freshness),
        handoff_frontier_digest=canonical_frontier_digest("handoff", handoffs),
        work_trace_frontier_digest=canonical_frontier_digest("work-trace", traces),
        observed_epoch=observed_epoch,
    )


def _make_observed_wrapper(
    cls: type[AdmittedManifest] | type[AdmittedAuthorityGraph],
    *,
    kind: AdmissionSubjectKind,
    state: Mapping[str, Any],
    subject_id: str,
    semantic_digest: str,
    context: CanonicalAdmissionContext,
) -> AdmittedManifest | AdmittedAuthorityGraph:
    subject_state = dict(state)
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=kind,
        subject_protocol=kind.value,
        subject_id=subject_id,
        subject_state_digest=canonical_digest(subject_state),
        semantic_digest=semantic_digest,
        context_digest=context.digest,
        disposition=AdmissionDisposition.ADMITTED,
        reason_codes=(),
        limitations=("structural-currentness-only", "no-semantic-authority"),
    )
    subject_json = canonical_json(subject_state)
    wrapper = cls(
        subject_json,
        receipt,
        admission_protocol._wrapper_digest(kind, subject_json, receipt),
    )
    wrapper.validate_integrity()
    return wrapper


def build_canonical_admission_context(
    *,
    observed_epoch: int = 0,
    current_source_state_digests: Mapping[str, str] | None = None,
    current_evidence_digests: Mapping[str, str] | None = None,
    current_artifact_digests: Mapping[str, str] | None = None,
    current_freshness_fences: Mapping[str, str] | None = None,
    known_handoff_digests: Mapping[str, str] | None = None,
    current_work_trace_digests: Mapping[str, str] | None = None,
) -> CanonicalAdmissionContext:
    registry, profile = _strict_current_objects()
    source = _frontier(current_source_state_digests)
    evidence = _frontier(current_evidence_digests)
    artifact = _frontier(current_artifact_digests)
    freshness = _frontier(current_freshness_fences)
    handoffs = _frontier(known_handoff_digests)
    traces = _frontier(current_work_trace_digests)
    return _context_from_observation(
        registry,
        profile,
        observed_epoch=observed_epoch,
        source=source,
        evidence=evidence,
        artifact=artifact,
        freshness=freshness,
        handoffs=handoffs,
        traces=traces,
    )


def _context_reasons_from_observation(
    context: CanonicalAdmissionContext,
    *,
    registry: Any,
    profile: Any,
) -> tuple[str, ...]:
    context.validate_integrity()
    reasons: list[str] = []
    if context.registry_digest != registry.registry_digest:
        reasons.append("CANONICAL_REGISTRY_CONTEXT_MISMATCH")
    if context.authority_graph_digest != profile.authority_graph.digest:
        reasons.append("CANONICAL_AUTHORITY_GRAPH_CONTEXT_MISMATCH")
    return tuple(sorted(set(reasons)))


def _admit_handoff_from_observation(
    state: Mapping[str, Any],
    *,
    context: CanonicalAdmissionContext,
    registry: Any,
    profile: Any,
    current_source_state_digests: Mapping[str, str],
    current_evidence_digests: Mapping[str, str],
    current_artifact_digests: Mapping[str, str],
    current_freshness_fences: Mapping[str, str],
    known_handoff_digests: Mapping[str, str],
) -> AdmittedHandoff:
    admission_protocol._strict_handoff_state(state)
    envelope = ExternalHandoffEnvelope.from_state(state)
    source = admission_protocol._strict_frontier(current_source_state_digests, "source-state")
    evidence = admission_protocol._strict_frontier(current_evidence_digests, "evidence")
    artifact = admission_protocol._strict_frontier(current_artifact_digests, "artifact")
    freshness = admission_protocol._strict_frontier(current_freshness_fences, "freshness")
    handoffs = admission_protocol._strict_frontier(known_handoff_digests, "handoff")
    blocked = list(_context_reasons_from_observation(context, registry=registry, profile=profile))
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
    disposition, reasons = admission_protocol._disposition(blocked, unknown)
    subject_state = envelope.to_state()
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.HANDOFF,
        subject_protocol=HANDOFF_PROTOCOL,
        subject_id=envelope.handoff_id,
        subject_state_digest=canonical_digest(subject_state),
        semantic_digest=envelope.digest,
        context_digest=context.digest,
        disposition=disposition,
        reason_codes=reasons,
        limitations=("structural-currentness-only", "handoff-authority-class-does-not-mint-authority"),
    )
    subject_json = canonical_json(subject_state)
    wrapper = AdmittedHandoff(
        subject_json,
        receipt,
        admission_protocol._wrapper_digest(AdmissionSubjectKind.HANDOFF, subject_json, receipt),
    )
    wrapper.validate_integrity()
    return wrapper


def _admit_work_trace_from_observation(
    state: Mapping[str, Any],
    *,
    context: CanonicalAdmissionContext,
    registry: Any,
    profile: Any,
    known_handoff_digests: Mapping[str, str],
    current_work_trace_digests: Mapping[str, str],
) -> AdmittedWorkTrace:
    admission_protocol._strict_work_trace_state(state)
    trace = CognitiveWorkTrace.from_state(state)
    handoffs = admission_protocol._strict_frontier(known_handoff_digests, "handoff")
    traces = admission_protocol._strict_frontier(current_work_trace_digests, "work-trace")
    blocked = list(_context_reasons_from_observation(context, registry=registry, profile=profile))
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
    disposition, reasons = admission_protocol._disposition(blocked, unknown)
    subject_state = trace.to_state()
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.WORK_TRACE,
        subject_protocol=WORK_TRACE_PROTOCOL,
        subject_id=trace.trace_id,
        subject_state_digest=canonical_digest(subject_state),
        semantic_digest=trace.digest,
        context_digest=context.digest,
        disposition=disposition,
        reason_codes=reasons,
        limitations=("structural-currentness-only", "work-trace-provenance-does-not-mint-authority"),
    )
    subject_json = canonical_json(subject_state)
    wrapper = AdmittedWorkTrace(
        subject_json,
        receipt,
        admission_protocol._wrapper_digest(AdmissionSubjectKind.WORK_TRACE, subject_json, receipt),
    )
    wrapper.validate_integrity()
    return wrapper


def _build_canonical_admission_bundle_from_observation(
    registry: Any,
    profile: Any,
    *,
    observed_epoch: int,
    source: Mapping[str, str],
    evidence: Mapping[str, str],
    artifact: Mapping[str, str],
    freshness: Mapping[str, str],
    handoffs: Mapping[str, str],
    traces: Mapping[str, str],
    handoff_states: Sequence[Mapping[str, Any]] = (),
    work_trace_states: Sequence[Mapping[str, Any]] = (),
) -> CanonicalAdmissionBundle:
    context = _context_from_observation(
        registry,
        profile,
        observed_epoch=observed_epoch,
        source=source,
        evidence=evidence,
        artifact=artifact,
        freshness=freshness,
        handoffs=handoffs,
        traces=traces,
    )
    admitted_manifests = tuple(
        _make_observed_wrapper(
            AdmittedManifest,
            kind=AdmissionSubjectKind.COMPONENT_MANIFEST,
            state=row.to_state(),
            subject_id=row.component_id,
            semantic_digest=row.manifest_digest,
            context=context,
        )
        for row in registry.manifests
    )
    admitted_graph = _make_observed_wrapper(
        AdmittedAuthorityGraph,
        kind=AdmissionSubjectKind.AUTHORITY_GRAPH,
        state=profile.authority_graph.to_state(),
        subject_id="canonical-authority-graph",
        semantic_digest=profile.authority_graph.digest,
        context=context,
    )
    assert isinstance(admitted_graph, AdmittedAuthorityGraph)
    admitted_handoffs = tuple(
        _admit_handoff_from_observation(
            state,
            context=context,
            registry=registry,
            profile=profile,
            current_source_state_digests=source,
            current_evidence_digests=evidence,
            current_artifact_digests=artifact,
            current_freshness_fences=freshness,
            known_handoff_digests=handoffs,
        )
        for state in handoff_states
    )
    admitted_traces = tuple(
        _admit_work_trace_from_observation(
            state,
            context=context,
            registry=registry,
            profile=profile,
            known_handoff_digests=handoffs,
            current_work_trace_digests=traces,
        )
        for state in work_trace_states
    )
    return CanonicalAdmissionBundle.create(
        context=context,
        manifests=admitted_manifests,
        authority_graph=admitted_graph,
        handoffs=admitted_handoffs,
        work_traces=admitted_traces,
    )


def build_canonical_admission_bundle(
    *,
    observed_epoch: int = 0,
    current_source_state_digests: Mapping[str, str] | None = None,
    current_evidence_digests: Mapping[str, str] | None = None,
    current_artifact_digests: Mapping[str, str] | None = None,
    current_freshness_fences: Mapping[str, str] | None = None,
    known_handoff_digests: Mapping[str, str] | None = None,
    current_work_trace_digests: Mapping[str, str] | None = None,
    handoff_states: Sequence[Mapping[str, Any]] = (),
    work_trace_states: Sequence[Mapping[str, Any]] = (),
) -> CanonicalAdmissionBundle:
    source = _frontier(current_source_state_digests)
    evidence = _frontier(current_evidence_digests)
    artifact = _frontier(current_artifact_digests)
    freshness = _frontier(current_freshness_fences)
    handoffs = _frontier(known_handoff_digests)
    traces = _frontier(current_work_trace_digests)
    registry, profile = _strict_current_objects()
    return _build_canonical_admission_bundle_from_observation(
        registry,
        profile,
        observed_epoch=observed_epoch,
        source=source,
        evidence=evidence,
        artifact=artifact,
        freshness=freshness,
        handoffs=handoffs,
        traces=traces,
        handoff_states=handoff_states,
        work_trace_states=work_trace_states,
    )


def build_canonical_observation(
    *,
    observed_epoch: int = 0,
    current_source_state_digests: Mapping[str, str] | None = None,
    current_evidence_digests: Mapping[str, str] | None = None,
    current_artifact_digests: Mapping[str, str] | None = None,
    current_freshness_fences: Mapping[str, str] | None = None,
    known_handoff_digests: Mapping[str, str] | None = None,
    current_work_trace_digests: Mapping[str, str] | None = None,
    chain_id: str = CANONICAL_OBSERVATION_CHAIN_ID,
    previous_observation_digest: str | None = None,
) -> CanonicalObservationEnvelope:
    source = _current_observation_frontier(current_source_state_digests, "source-state")
    evidence = _current_observation_frontier(current_evidence_digests, "evidence")
    artifact = _current_observation_frontier(current_artifact_digests, "artifact")
    freshness = _current_observation_frontier(current_freshness_fences, "freshness")
    handoffs = _current_observation_frontier(known_handoff_digests, "handoff")
    traces = _current_observation_frontier(current_work_trace_digests, "work-trace")
    registry, profile = _strict_current_objects()
    return build_observation_from_snapshot(
        registry,
        profile,
        observed_epoch=observed_epoch,
        source=source,
        evidence=evidence,
        artifact=artifact,
        freshness=freshness,
        handoffs=handoffs,
        traces=traces,
        chain_id=chain_id,
        previous_observation_digest=previous_observation_digest,
    )


@dataclass(frozen=True, slots=True)
class AdmissionAuditFinding:
    code: str
    detail: str
    subject_id: str

    def to_state(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail, "subject_id": self.subject_id}


@dataclass(frozen=True, slots=True)
class CanonicalAdmissionAuditReport:
    protocol: str
    findings: tuple[AdmissionAuditFinding, ...]
    digest: str
    observation_digest: str | None = None

    @classmethod
    def create(
        cls,
        findings: Sequence[AdmissionAuditFinding],
        *,
        current_observation: bool = False,
        observation_digest: str | None = None,
    ) -> "CanonicalAdmissionAuditReport":
        rows = tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))
        if current_observation:
            if observation_digest is not None and (
                type(observation_digest) is not str or not observation_digest.strip()
            ):
                raise ValueError("current observation audit observation digest must be an exact non-empty string")
            if not rows and observation_digest is None:
                raise ValueError("clean current observation audit requires an exact observation digest")
        protocol = ADMISSION_AUDIT_PROTOCOL if current_observation else HISTORICAL_ADMISSION_AUDIT_PROTOCOL
        payload: dict[str, Any] = {
            "protocol": protocol,
            "findings": [row.to_state() for row in rows],
        }
        namespace = "admission-audit-v4-" if current_observation else "admission-audit-v3-"
        if current_observation:
            payload["observation_digest"] = observation_digest
        return cls(
            protocol=protocol,
            findings=rows,
            digest=namespace + canonical_digest(payload),
            observation_digest=observation_digest if current_observation else None,
        )

    def to_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            "protocol": self.protocol,
            "findings": [row.to_state() for row in self.findings],
            "digest": self.digest,
        }
        if self.protocol == CURRENT_ADMISSION_AUDIT_PROTOCOL:
            state["observation_digest"] = self.observation_digest
        return state


def _append_readmission_findings(
    findings: list[AdmissionAuditFinding],
    *,
    subject_id: str,
    label: str,
    disposition: AdmissionDisposition,
    reason_codes: tuple[str, ...],
) -> None:
    if disposition is AdmissionDisposition.ADMITTED:
        return
    codes = reason_codes or ("CANONICAL_ADMISSION_READMISSION_NOT_ADMITTED",)
    for code in codes:
        findings.append(
            AdmissionAuditFinding(
                code=code,
                detail=f"live {label} re-admission returned {disposition.value}",
                subject_id=subject_id,
            )
        )


def _manifest_readmission_from_observation(
    child: AdmittedManifest,
    *,
    context: CanonicalAdmissionContext,
    registry: Any,
    profile: Any,
) -> tuple[AdmissionDisposition, tuple[str, ...]]:
    reasons = list(_context_reasons_from_observation(context, registry=registry, profile=profile))
    try:
        current = registry.manifest_for(child.receipt.subject_id)
    except KeyError:
        reasons.append("CANONICAL_MANIFEST_IDENTITY_UNKNOWN")
    else:
        if current.to_state() != child.subject_state:
            reasons.append("CANONICAL_MANIFEST_MISMATCH")
    codes = tuple(sorted(set(reasons)))
    return (AdmissionDisposition.BLOCKED if codes else AdmissionDisposition.ADMITTED), codes


def _authority_graph_readmission_from_observation(
    child: AdmittedAuthorityGraph,
    *,
    context: CanonicalAdmissionContext,
    registry: Any,
    profile: Any,
) -> tuple[AdmissionDisposition, tuple[str, ...]]:
    reasons = list(_context_reasons_from_observation(context, registry=registry, profile=profile))
    state = child.subject_state
    if state != profile.authority_graph.to_state():
        reasons.append("CANONICAL_AUTHORITY_GRAPH_MISMATCH")
    graph_manifests = state.get("manifests")
    if type(graph_manifests) is not list:
        raise ValueError("admitted authority graph manifest population is non-canonical")
    if tuple(graph_manifests) != tuple(row.to_state() for row in registry.manifests):
        reasons.append("CANONICAL_GRAPH_REGISTRY_POPULATION_MISMATCH")
    codes = tuple(sorted(set(reasons)))
    return (AdmissionDisposition.BLOCKED if codes else AdmissionDisposition.ADMITTED), codes


def _snapshot_optional_frontier(
    kind: str,
    value: Mapping[str, str] | None,
) -> tuple[Mapping[str, str] | None, Exception | None]:
    if value is None:
        return None, None
    try:
        return admission_protocol._strict_frontier(value, kind), None
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return None, exc


def _observed_frontier(
    kind: str,
    *,
    bound_digest: str,
    current_values: Mapping[str, str] | None,
) -> Mapping[str, str] | None:
    if current_values is not None:
        try:
            canonical_frontier_digest(kind, current_values)
        except (AttributeError, KeyError, TypeError, ValueError):
            return None
        return current_values
    if bound_digest == canonical_frontier_digest(kind, {}):
        return {}
    return None


def _live_observation_epoch(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("current observation epoch must be a non-negative integer")
    return value


def run_canonical_admission_audit(
    *,
    bundle: CanonicalAdmissionBundle | None = None,
    observed_epoch: int = 0,
    current_observed_epoch: int | None = None,
    current_source_state_digests: Mapping[str, str] | None = None,
    current_evidence_digests: Mapping[str, str] | None = None,
    current_artifact_digests: Mapping[str, str] | None = None,
    current_freshness_fences: Mapping[str, str] | None = None,
    known_handoff_digests: Mapping[str, str] | None = None,
    current_work_trace_digests: Mapping[str, str] | None = None,
    current_observation: CanonicalObservationEnvelope | None = None,
    predecessor_observation: CanonicalObservationEnvelope | None = None,
    competing_successors: Sequence[CanonicalObservationEnvelope] = (),
    observation_genesis: bool | None = None,
    observation_chain_id: str = CANONICAL_OBSERVATION_CHAIN_ID,
) -> CanonicalAdmissionAuditReport:
    current_observation_mode = (
        observation_genesis is not None
        or current_observation is not None
        or predecessor_observation is not None
        or bool(competing_successors)
    )
    current_observation_for_report = current_observation

    def make_report(rows: Sequence[AdmissionAuditFinding]) -> CanonicalAdmissionAuditReport:
        return CanonicalAdmissionAuditReport.create(
            rows,
            current_observation=current_observation_mode,
            observation_digest=(
                None
                if current_observation_for_report is None
                else current_observation_for_report.digest
            ),
        )

    persisted_bundle = bundle is not None
    registry: Any | None = None
    profile: Any | None = None
    raw_frontiers = (
        ("source-state", current_source_state_digests),
        ("evidence", current_evidence_digests),
        ("artifact", current_artifact_digests),
        ("freshness", current_freshness_fences),
        ("handoff", known_handoff_digests),
        ("work-trace", current_work_trace_digests),
    )
    frontier_snapshots: dict[str, Mapping[str, str] | None] = {}
    frontier_snapshot_errors: dict[str, Exception] = {}
    for kind, values in raw_frontiers:
        snapshot, snapshot_error = _snapshot_optional_frontier(kind, values)
        frontier_snapshots[kind] = snapshot
        if snapshot_error is not None:
            frontier_snapshot_errors[kind] = snapshot_error

    current_source_state_digests = frontier_snapshots["source-state"]
    current_evidence_digests = frontier_snapshots["evidence"]
    current_artifact_digests = frontier_snapshots["artifact"]
    current_freshness_fences = frontier_snapshots["freshness"]
    known_handoff_digests = frontier_snapshots["handoff"]
    current_work_trace_digests = frontier_snapshots["work-trace"]

    if bundle is None:
        if frontier_snapshot_errors:
            first_kind = next(kind for kind, _values in raw_frontiers if kind in frontier_snapshot_errors)
            exc = frontier_snapshot_errors[first_kind]
            return make_report(
                (
                    AdmissionAuditFinding(
                        code="CANONICAL_ADMISSION_BUILD_FAILED",
                        detail=str(exc),
                        subject_id="canonical-admission-bundle",
                    ),
                )
            )
        try:
            registry, profile = _strict_current_objects()
            bundle = _build_canonical_admission_bundle_from_observation(
                registry,
                profile,
                observed_epoch=observed_epoch,
                source={} if current_source_state_digests is None else current_source_state_digests,
                evidence={} if current_evidence_digests is None else current_evidence_digests,
                artifact={} if current_artifact_digests is None else current_artifact_digests,
                freshness={} if current_freshness_fences is None else current_freshness_fences,
                handoffs={} if known_handoff_digests is None else known_handoff_digests,
                traces={} if current_work_trace_digests is None else current_work_trace_digests,
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            return make_report(
                (
                    AdmissionAuditFinding(
                        code="CANONICAL_ADMISSION_BUILD_FAILED",
                        detail=str(exc),
                        subject_id="canonical-admission-bundle",
                    ),
                )
            )
    try:
        bundle.validate_integrity()
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return make_report(
            (
                AdmissionAuditFinding(
                    code="FORGED_ADMISSION_BUNDLE",
                    detail=str(exc),
                    subject_id="canonical-admission-bundle",
                ),
            )
        )

    if registry is None or profile is None:
        try:
            registry, profile = _strict_current_objects()
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            return make_report(
                (
                    AdmissionAuditFinding(
                        code="CANONICAL_ADMISSION_CURRENT_STATE_BUILD_FAILED",
                        detail=str(exc),
                        subject_id="canonical-admission-bundle",
                    ),
                )
            )

    findings: list[AdmissionAuditFinding] = []

    if current_observation_mode:
        if type(observation_genesis) not in (bool, type(None)):
            findings.append(
                AdmissionAuditFinding(
                    code="CURRENT_OBSERVATION_GENESIS_INVALID",
                    detail="observation_genesis must be an exact boolean when supplied",
                    subject_id="canonical-observation",
                )
            )
        snapshot_values = (
            current_source_state_digests,
            current_evidence_digests,
            current_artifact_digests,
            current_freshness_fences,
            known_handoff_digests,
            current_work_trace_digests,
        )
        snapshot_available = not frontier_snapshot_errors and all(
            row is not None for row in snapshot_values
        )
        if current_observation_for_report is None:
            if observation_genesis is True and snapshot_available:
                assert current_source_state_digests is not None
                assert current_evidence_digests is not None
                assert current_artifact_digests is not None
                assert current_freshness_fences is not None
                assert known_handoff_digests is not None
                assert current_work_trace_digests is not None
                current_observation_for_report = build_observation_from_snapshot(
                    registry,
                    profile,
                    observed_epoch=bundle.context.observed_epoch,
                    source=current_source_state_digests,
                    evidence=current_evidence_digests,
                    artifact=current_artifact_digests,
                    freshness=current_freshness_fences,
                    handoffs=known_handoff_digests,
                    traces=current_work_trace_digests,
                    chain_id=observation_chain_id,
                    previous_observation_digest=None,
                )
            else:
                findings.append(
                    AdmissionAuditFinding(
                        code="CURRENT_OBSERVATION_WITNESS_UNAVAILABLE",
                        detail="current observation audit requires an explicit canonical observation witness",
                        subject_id="canonical-observation",
                    )
                )

        if current_observation_for_report is not None:
            if not snapshot_available:
                findings.append(
                    AdmissionAuditFinding(
                        code="CURRENT_OBSERVATION_SURFACE_UNAVAILABLE",
                        detail="current observation witness cannot be re-attested without all six detached live frontiers",
                        subject_id="canonical-observation",
                    )
                )
            else:
                assert current_source_state_digests is not None
                assert current_evidence_digests is not None
                assert current_artifact_digests is not None
                assert current_freshness_fences is not None
                assert known_handoff_digests is not None
                assert current_work_trace_digests is not None
                try:
                    observation_findings = validate_observation_against_snapshot(
                        current_observation_for_report,
                        registry=registry,
                        profile=profile,
                        source=current_source_state_digests,
                        evidence=current_evidence_digests,
                        artifact=current_artifact_digests,
                        freshness=current_freshness_fences,
                        handoffs=known_handoff_digests,
                        traces=current_work_trace_digests,
                        predecessor=predecessor_observation,
                        genesis=bool(observation_genesis),
                        competing_successors=competing_successors,
                    )
                except (AttributeError, KeyError, TypeError, ValueError) as exc:
                    findings.append(
                        AdmissionAuditFinding(
                            code="CURRENT_OBSERVATION_WITNESS_INVALID",
                            detail=str(exc),
                            subject_id="canonical-observation",
                        )
                    )
                else:
                    findings.extend(
                        AdmissionAuditFinding(
                            code=row.code,
                            detail=row.detail,
                            subject_id=row.subject_id,
                        )
                        for row in observation_findings
                    )

                observation_context_pairs = (
                    ("registry", current_observation_for_report.registry_digest, bundle.context.registry_digest),
                    ("authority-graph", current_observation_for_report.authority_graph_digest, bundle.context.authority_graph_digest),
                    ("source-state", current_observation_for_report.source_state_frontier_digest, bundle.context.source_state_frontier_digest),
                    ("evidence", current_observation_for_report.evidence_frontier_digest, bundle.context.evidence_frontier_digest),
                    ("artifact", current_observation_for_report.artifact_frontier_digest, bundle.context.artifact_frontier_digest),
                    ("freshness", current_observation_for_report.freshness_fence_frontier_digest, bundle.context.freshness_fence_frontier_digest),
                    ("handoff", current_observation_for_report.handoff_frontier_digest, bundle.context.handoff_frontier_digest),
                    ("work-trace", current_observation_for_report.work_trace_frontier_digest, bundle.context.work_trace_frontier_digest),
                )
                for kind, observation_digest, context_digest in observation_context_pairs:
                    if observation_digest != context_digest:
                        findings.append(
                            AdmissionAuditFinding(
                                code="OBSERVATION_ADMISSION_CONTEXT_MISMATCH",
                                detail="canonical observation commitment does not match the audited admission context",
                                subject_id=kind,
                            )
                        )
                if current_observation_for_report.observed_epoch != bundle.context.observed_epoch:
                    findings.append(
                        AdmissionAuditFinding(
                            code="OBSERVATION_ADMISSION_CONTEXT_MISMATCH",
                            detail="canonical observation epoch does not match the audited admission context",
                            subject_id="observed-epoch",
                        )
                    )
    if persisted_bundle and current_observed_epoch is None:
        findings.append(
            AdmissionAuditFinding(
                code="CURRENT_OBSERVATION_EPOCH_UNAVAILABLE",
                detail="admission context observation epoch was not re-observed for the live audit",
                subject_id="canonical-admission-bundle",
            )
        )
    else:
        raw_live_epoch: object = observed_epoch if current_observed_epoch is None else current_observed_epoch
        try:
            live_epoch = _live_observation_epoch(raw_live_epoch)
        except ValueError as exc:
            findings.append(
                AdmissionAuditFinding(
                    code="CURRENT_OBSERVATION_EPOCH_INVALID",
                    detail=str(exc),
                    subject_id="canonical-admission-bundle",
                )
            )
        else:
            if live_epoch != bundle.context.observed_epoch:
                findings.append(
                    AdmissionAuditFinding(
                        code="OBSERVATION_EPOCH_CONTEXT_MISMATCH",
                        detail="admission context observation epoch does not match the live re-observation",
                        subject_id="canonical-admission-bundle",
                    )
                )
    if bundle.context.registry_digest != registry.registry_digest:
        findings.append(
            AdmissionAuditFinding(
                code="CANONICAL_REGISTRY_CONTEXT_MISMATCH",
                detail="admission context registry digest does not match the current canonical registry",
                subject_id="canonical-admission-bundle",
            )
        )
    if bundle.context.authority_graph_digest != profile.authority_graph.digest:
        findings.append(
            AdmissionAuditFinding(
                code="CANONICAL_AUTHORITY_GRAPH_CONTEXT_MISMATCH",
                detail="admission context authority graph digest does not match the current canonical authority graph",
                subject_id="canonical-admission-bundle",
            )
        )

    frontier_specs = (
        (
            "source-state",
            bundle.context.source_state_frontier_digest,
            current_source_state_digests,
            frontier_snapshot_errors.get("source-state"),
            "CURRENT_SOURCE_STATE_FRONTIER_UNAVAILABLE",
            "SOURCE_STATE_FRONTIER_CONTEXT_MISMATCH",
        ),
        (
            "evidence",
            bundle.context.evidence_frontier_digest,
            current_evidence_digests,
            frontier_snapshot_errors.get("evidence"),
            "CURRENT_EVIDENCE_FRONTIER_UNAVAILABLE",
            "EVIDENCE_FRONTIER_CONTEXT_MISMATCH",
        ),
        (
            "artifact",
            bundle.context.artifact_frontier_digest,
            current_artifact_digests,
            frontier_snapshot_errors.get("artifact"),
            "CURRENT_ARTIFACT_FRONTIER_UNAVAILABLE",
            "ARTIFACT_FRONTIER_CONTEXT_MISMATCH",
        ),
        (
            "freshness",
            bundle.context.freshness_fence_frontier_digest,
            current_freshness_fences,
            frontier_snapshot_errors.get("freshness"),
            "CURRENT_FRESHNESS_FRONTIER_UNAVAILABLE",
            "FRESHNESS_FRONTIER_CONTEXT_MISMATCH",
        ),
        (
            "handoff",
            bundle.context.handoff_frontier_digest,
            known_handoff_digests,
            frontier_snapshot_errors.get("handoff"),
            "CURRENT_HANDOFF_FRONTIER_UNAVAILABLE",
            "HANDOFF_FRONTIER_CONTEXT_MISMATCH",
        ),
        (
            "work-trace",
            bundle.context.work_trace_frontier_digest,
            current_work_trace_digests,
            frontier_snapshot_errors.get("work-trace"),
            "CURRENT_WORK_TRACE_FRONTIER_UNAVAILABLE",
            "WORK_TRACE_FRONTIER_CONTEXT_MISMATCH",
        ),
    )
    for kind, bound_digest, current_values, snapshot_error, unavailable_code, mismatch_code in frontier_specs:
        empty_digest = canonical_frontier_digest(kind, {})
        if snapshot_error is not None:
            findings.append(
                AdmissionAuditFinding(
                    code=f"CURRENT_{kind.upper().replace('-', '_')}_FRONTIER_INVALID",
                    detail=str(snapshot_error),
                    subject_id="canonical-admission-bundle",
                )
            )
            continue
        if current_values is None:
            if bound_digest != empty_digest:
                findings.append(
                    AdmissionAuditFinding(
                        code=unavailable_code,
                        detail=f"{kind} frontier was bound at admission but was not re-observed for the live audit",
                        subject_id="canonical-admission-bundle",
                    )
                )
            continue
        try:
            current_digest = canonical_frontier_digest(kind, current_values)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            findings.append(
                AdmissionAuditFinding(
                    code=f"CURRENT_{kind.upper().replace('-', '_')}_FRONTIER_INVALID",
                    detail=str(exc),
                    subject_id="canonical-admission-bundle",
                )
            )
            continue
        if current_digest != bound_digest:
            findings.append(
                AdmissionAuditFinding(
                    code=mismatch_code,
                    detail=f"admission context {kind} frontier digest does not match the live re-observation",
                    subject_id="canonical-admission-bundle",
                )
            )

    for child in bundle.manifests:
        try:
            disposition, reason_codes = _manifest_readmission_from_observation(
                child,
                context=bundle.context,
                registry=registry,
                profile=profile,
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            findings.append(
                AdmissionAuditFinding(
                    code="CANONICAL_MANIFEST_READMISSION_FAILED",
                    detail=str(exc),
                    subject_id=child.receipt.subject_id,
                )
            )
        else:
            _append_readmission_findings(
                findings,
                subject_id=child.receipt.subject_id,
                label="manifest",
                disposition=disposition,
                reason_codes=reason_codes,
            )

    try:
        graph_disposition, graph_reason_codes = _authority_graph_readmission_from_observation(
            bundle.authority_graph,
            context=bundle.context,
            registry=registry,
            profile=profile,
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        findings.append(
            AdmissionAuditFinding(
                code="CANONICAL_AUTHORITY_GRAPH_READMISSION_FAILED",
                detail=str(exc),
                subject_id=bundle.authority_graph.receipt.subject_id,
            )
        )
    else:
        _append_readmission_findings(
            findings,
            subject_id=bundle.authority_graph.receipt.subject_id,
            label="authority graph",
            disposition=graph_disposition,
            reason_codes=graph_reason_codes,
        )

    source = _observed_frontier(
        "source-state",
        bound_digest=bundle.context.source_state_frontier_digest,
        current_values=current_source_state_digests,
    )
    evidence = _observed_frontier(
        "evidence",
        bound_digest=bundle.context.evidence_frontier_digest,
        current_values=current_evidence_digests,
    )
    artifact = _observed_frontier(
        "artifact",
        bound_digest=bundle.context.artifact_frontier_digest,
        current_values=current_artifact_digests,
    )
    freshness = _observed_frontier(
        "freshness",
        bound_digest=bundle.context.freshness_fence_frontier_digest,
        current_values=current_freshness_fences,
    )
    handoffs = _observed_frontier(
        "handoff",
        bound_digest=bundle.context.handoff_frontier_digest,
        current_values=known_handoff_digests,
    )
    traces = _observed_frontier(
        "work-trace",
        bound_digest=bundle.context.work_trace_frontier_digest,
        current_values=current_work_trace_digests,
    )

    if all(row is not None for row in (source, evidence, artifact, freshness, handoffs)):
        assert source is not None
        assert evidence is not None
        assert artifact is not None
        assert freshness is not None
        assert handoffs is not None
        for child in bundle.handoffs:
            try:
                replay = _admit_handoff_from_observation(
                    child.subject_state,
                    context=bundle.context,
                    registry=registry,
                    profile=profile,
                    current_source_state_digests=source,
                    current_evidence_digests=evidence,
                    current_artifact_digests=artifact,
                    current_freshness_fences=freshness,
                    known_handoff_digests=handoffs,
                )
            except (AttributeError, KeyError, TypeError, ValueError) as exc:
                findings.append(
                    AdmissionAuditFinding(
                        code="CANONICAL_HANDOFF_READMISSION_FAILED",
                        detail=str(exc),
                        subject_id=child.receipt.subject_id,
                    )
                )
            else:
                _append_readmission_findings(
                    findings,
                    subject_id=child.receipt.subject_id,
                    label="handoff",
                    disposition=replay.receipt.disposition,
                    reason_codes=replay.receipt.reason_codes,
                )

    if handoffs is not None and traces is not None:
        for child in bundle.work_traces:
            try:
                replay = _admit_work_trace_from_observation(
                    child.subject_state,
                    context=bundle.context,
                    registry=registry,
                    profile=profile,
                    known_handoff_digests=handoffs,
                    current_work_trace_digests=traces,
                )
            except (AttributeError, KeyError, TypeError, ValueError) as exc:
                findings.append(
                    AdmissionAuditFinding(
                        code="CANONICAL_WORK_TRACE_READMISSION_FAILED",
                        detail=str(exc),
                        subject_id=child.receipt.subject_id,
                    )
                )
            else:
                _append_readmission_findings(
                    findings,
                    subject_id=child.receipt.subject_id,
                    label="work trace",
                    disposition=replay.receipt.disposition,
                    reason_codes=replay.receipt.reason_codes,
                )

    return make_report(findings)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the canonical A10 External Core v1 observation-bound admission surface")
    parser.add_argument("--check", action="store_true", help="exit non-zero when categorical findings exist")
    parser.add_argument("--json", action="store_true", help="emit canonical audit JSON")
    parser.add_argument("--observed-epoch", type=int, default=0)
    args = parser.parse_args(argv)
    report = run_canonical_admission_audit(
        observed_epoch=args.observed_epoch,
        observation_genesis=True,
        current_source_state_digests={},
        current_evidence_digests={},
        current_artifact_digests={},
        current_freshness_fences={},
        known_handoff_digests={},
        current_work_trace_digests={},
    )
    if args.json or not args.check:
        print(json.dumps(report.to_state(), sort_keys=True, separators=(",", ":")))
    elif report.findings:
        for finding in report.findings:
            print(f"{finding.code}: {finding.detail}")
    return 1 if args.check and report.findings else 0


__all__ = (
    "ADMISSION_AUDIT_PROTOCOL",
    "CURRENT_ADMISSION_AUDIT_PROTOCOL",
    "ADMISSION_BUNDLE_PROTOCOL",
    "AdmissionAuditFinding",
    "CanonicalAdmissionAuditReport",
    "CanonicalAdmissionBundle",
    "build_canonical_admission_bundle",
    "build_canonical_admission_context",
    "build_canonical_observation",
    "run_canonical_admission_audit",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
)


if __name__ == "__main__":
    raise SystemExit(_main())
