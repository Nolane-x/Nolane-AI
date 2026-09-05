from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.authority_graph import ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest
from nolane.external_core.handoff import (
    ExternalHandoffEnvelope,
    HandoffValidationDisposition,
    validate_handoff_for_consumer,
)
from nolane.external_core.work_trace import CognitiveWorkTrace


RESTORE_PROTOCOL = "external-core-restore-preflight-v1"
COHERENCE_AUDIT_PROTOCOL = "external-core-coherence-audit-v1"


@dataclass(frozen=True, slots=True)
class ExternalCoreRestoreSnapshot:
    snapshot_id: str
    registry_digest: str
    authority_graph_digest: str
    artifact_graph_digest: str
    handoff_frontier_digest: str
    component_versions: tuple[tuple[str, str], ...]
    digest: str

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "protocol": RESTORE_PROTOCOL,
            "registry_digest": self.registry_digest,
            "authority_graph_digest": self.authority_graph_digest,
            "artifact_graph_digest": self.artifact_graph_digest,
            "handoff_frontier_digest": self.handoff_frontier_digest,
            "component_versions": {key: value for key, value in self.component_versions},
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "registry_digest": self.registry_digest,
            "authority_graph_digest": self.authority_graph_digest,
            "artifact_graph_digest": self.artifact_graph_digest,
            "handoff_frontier_digest": self.handoff_frontier_digest,
            "component_versions": {key: value for key, value in self.component_versions},
            "digest": self.digest,
        }

    @classmethod
    def create(
        cls,
        *,
        registry_digest: str,
        authority_graph_digest: str,
        artifact_graph_digest: str,
        handoff_frontier_digest: str,
        component_versions: Mapping[str, str],
    ) -> "ExternalCoreRestoreSnapshot":
        versions = _normalize_versions(component_versions)
        row = cls(
            snapshot_id="",
            registry_digest=_explicit(registry_digest, "registry digest"),
            authority_graph_digest=_explicit(authority_graph_digest, "authority graph digest"),
            artifact_graph_digest=_explicit(artifact_graph_digest, "artifact graph digest"),
            handoff_frontier_digest=_explicit(handoff_frontier_digest, "handoff frontier digest"),
            component_versions=versions,
            digest="",
        )
        digest = canonical_digest(row.semantic_payload())
        return cls(
            snapshot_id="external-core-restore-" + digest[:24],
            registry_digest=row.registry_digest,
            authority_graph_digest=row.authority_graph_digest,
            artifact_graph_digest=row.artifact_graph_digest,
            handoff_frontier_digest=row.handoff_frontier_digest,
            component_versions=row.component_versions,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExternalCoreRestoreSnapshot":
        versions = state.get("component_versions")
        if not isinstance(versions, Mapping):
            raise ValueError("restore snapshot component_versions must be an object")
        expected = cls.create(
            registry_digest=str(state["registry_digest"]),
            authority_graph_digest=str(state["authority_graph_digest"]),
            artifact_graph_digest=str(state["artifact_graph_digest"]),
            handoff_frontier_digest=str(state["handoff_frontier_digest"]),
            component_versions={str(key): str(value) for key, value in versions.items()},
        )
        if str(state.get("snapshot_id", "")) != expected.snapshot_id:
            raise ValueError("restore snapshot identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("restore snapshot digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("restore snapshot state is non-canonical or semantically drifted")
        return expected


@dataclass(frozen=True, slots=True)
class RestorePreflightResult:
    snapshot_id: str
    accepted: bool
    reason_codes: tuple[str, ...]
    current_state_digest: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "accepted": self.accepted,
            "reason_codes": list(self.reason_codes),
            "current_state_digest": self.current_state_digest,
        }


def preflight_restore(
    *,
    snapshot: ExternalCoreRestoreSnapshot,
    current_registry_digest: str,
    current_authority_graph_digest: str,
    current_artifact_graph_digest: str,
    current_handoff_frontier_digest: str,
    current_component_versions: Mapping[str, str],
) -> RestorePreflightResult:
    reasons: list[str] = []
    registry = _explicit(current_registry_digest, "current registry digest")
    authority = _explicit(current_authority_graph_digest, "current authority graph digest")
    artifact = _explicit(current_artifact_graph_digest, "current artifact graph digest")
    handoff = _explicit(current_handoff_frontier_digest, "current handoff frontier digest")
    versions = _normalize_versions(current_component_versions)
    if registry != snapshot.registry_digest:
        reasons.append("REGISTRY_DIGEST_DRIFT")
    if authority != snapshot.authority_graph_digest:
        reasons.append("AUTHORITY_GRAPH_DIGEST_DRIFT")
    if artifact != snapshot.artifact_graph_digest:
        reasons.append("ARTIFACT_GRAPH_DIGEST_DRIFT")
    if handoff != snapshot.handoff_frontier_digest:
        reasons.append("HANDOFF_FRONTIER_DIGEST_DRIFT")
    if versions != snapshot.component_versions:
        reasons.append("COMPONENT_VERSION_DRIFT")
    reason_codes = tuple(sorted(set(reasons)))
    current_state_digest = canonical_digest(
        {
            "registry_digest": registry,
            "authority_graph_digest": authority,
            "artifact_graph_digest": artifact,
            "handoff_frontier_digest": handoff,
            "component_versions": {key: value for key, value in versions},
        }
    )
    payload = {
        "snapshot_id": snapshot.snapshot_id,
        "accepted": not reason_codes,
        "reason_codes": list(reason_codes),
        "current_state_digest": current_state_digest,
    }
    return RestorePreflightResult(
        snapshot_id=snapshot.snapshot_id,
        accepted=not reason_codes,
        reason_codes=reason_codes,
        current_state_digest=current_state_digest,
        digest=canonical_digest(payload),
    )


@dataclass(frozen=True, slots=True)
class CoherenceFinding:
    code: str
    subjects: tuple[str, ...]
    detail: str

    def payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "subjects": list(self.subjects),
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class CoherenceAuditReport:
    findings: tuple[CoherenceFinding, ...]
    authority_graph_digest: str
    manifest_set_digest: str
    handoff_frontier_digest: str
    trace_set_digest: str
    digest: str

    @property
    def clean(self) -> bool:
        return not self.findings

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": COHERENCE_AUDIT_PROTOCOL,
            "findings": [row.payload() for row in self.findings],
            "authority_graph_digest": self.authority_graph_digest,
            "manifest_set_digest": self.manifest_set_digest,
            "handoff_frontier_digest": self.handoff_frontier_digest,
            "trace_set_digest": self.trace_set_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}


def audit_external_core(
    *,
    manifests: tuple[ExternalComponentManifest, ...],
    authority_graph: ExternalAuthorityGraph,
    handoffs: tuple[ExternalHandoffEnvelope, ...],
    traces: tuple[CognitiveWorkTrace, ...],
    current_source_state_digests: Mapping[str, str],
    current_evidence_digests: Mapping[str, str],
    current_artifact_digests: Mapping[str, str],
    current_freshness_fences: Mapping[str, str],
) -> CoherenceAuditReport:
    """Return a deterministic, read-only coherence report.

    The auditor never invokes a component, rewrites a receipt, repairs state,
    or upgrades a handoff. Findings are descriptive blockers for callers.
    """

    ordered_manifests = tuple(sorted(manifests, key=lambda row: row.component_id))
    manifest_by_id = {row.component_id: row for row in ordered_manifests}
    findings: list[CoherenceFinding] = []

    if len(manifest_by_id) != len(ordered_manifests):
        findings.append(
            CoherenceFinding(
                "DUPLICATE_COMPONENT_MANIFEST",
                tuple(row.component_id for row in ordered_manifests),
                "component manifest set contains duplicate component ids",
            )
        )

    graph_ids = tuple(row.component_id for row in authority_graph.manifests)
    manifest_ids = tuple(row.component_id for row in ordered_manifests)
    graph_digests = tuple(row.manifest_digest for row in authority_graph.manifests)
    manifest_digests = tuple(row.manifest_digest for row in ordered_manifests)
    if graph_ids != manifest_ids or graph_digests != manifest_digests:
        findings.append(
            CoherenceFinding(
                "MANIFEST_GRAPH_DRIFT",
                tuple(sorted(set(graph_ids) | set(manifest_ids))),
                "supplied manifests differ from authority graph manifest authority",
            )
        )

    for graph_finding in authority_graph.findings():
        findings.append(
            CoherenceFinding(
                graph_finding.code,
                graph_finding.component_ids,
                f"{graph_finding.subject}: {graph_finding.detail}",
            )
        )

    ordered_handoffs = tuple(sorted(handoffs, key=lambda row: row.handoff_id))
    handoff_ids = {row.handoff_id for row in ordered_handoffs}
    if len(handoff_ids) != len(ordered_handoffs):
        findings.append(
            CoherenceFinding(
                "DUPLICATE_HANDOFF_ID",
                tuple(sorted(handoff_ids)),
                "handoff set contains a duplicate semantic identity",
            )
        )

    for handoff in ordered_handoffs:
        missing_predecessors = tuple(
            predecessor
            for predecessor in handoff.predecessor_handoff_ids
            if predecessor not in handoff_ids
        )
        if missing_predecessors:
            findings.append(
                CoherenceFinding(
                    "ORPHAN_HANDOFF",
                    (handoff.handoff_id,) + tuple(sorted(missing_predecessors)),
                    "handoff predecessor is absent from the audited frontier",
                )
            )

        producer = manifest_by_id.get(handoff.producer_component_id)
        consumer = manifest_by_id.get(handoff.consumer_component_id)
        if producer is None or consumer is None:
            findings.append(
                CoherenceFinding(
                    "UNKNOWN_HANDOFF_COMPONENT",
                    tuple(
                        sorted(
                            component_id
                            for component_id, manifest in (
                                (handoff.producer_component_id, producer),
                                (handoff.consumer_component_id, consumer),
                            )
                            if manifest is None
                        )
                    ),
                    f"handoff {handoff.handoff_id} references a component without a manifest",
                )
            )
            continue

        validation = validate_handoff_for_consumer(
            handoff,
            producer_manifest=producer,
            consumer_manifest=consumer,
            current_source_state_digest=current_source_state_digests.get(handoff.producer_component_id),
            current_evidence_digests=current_evidence_digests,
            current_artifact_digests=current_artifact_digests,
            known_predecessor_handoff_ids=tuple(sorted(handoff_ids)),
            current_freshness_fence=current_freshness_fences.get(handoff.producer_component_id),
        )
        if validation.disposition is HandoffValidationDisposition.BLOCKED:
            findings.append(
                CoherenceFinding(
                    "STALE_HANDOFF",
                    (handoff.handoff_id,),
                    "current consumer revalidation blocked: " + ",".join(validation.reason_codes),
                )
            )
        elif validation.disposition is HandoffValidationDisposition.UNKNOWN:
            findings.append(
                CoherenceFinding(
                    "HANDOFF_CURRENTNESS_UNKNOWN",
                    (handoff.handoff_id,),
                    "current consumer proof is incomplete: " + ",".join(validation.reason_codes),
                )
            )

    ordered_traces = tuple(sorted(traces, key=lambda row: row.trace_id))
    if len({row.trace_id for row in ordered_traces}) != len(ordered_traces):
        findings.append(
            CoherenceFinding(
                "DUPLICATE_TRACE_ID",
                tuple(row.trace_id for row in ordered_traces),
                "trace set contains duplicate trace identities",
            )
        )
    for trace in ordered_traces:
        for diagnostic in trace.diagnostics(known_handoff_ids=tuple(sorted(handoff_ids))):
            findings.append(
                CoherenceFinding(
                    diagnostic.code,
                    (trace.trace_id,) + diagnostic.node_ids,
                    diagnostic.detail,
                )
            )

    unique: dict[tuple[str, tuple[str, ...], str], CoherenceFinding] = {}
    for finding in findings:
        key = (finding.code, finding.subjects, finding.detail)
        unique[key] = finding
    ordered_findings = tuple(
        sorted(unique.values(), key=lambda row: (row.code, row.subjects, row.detail))
    )
    manifest_set_digest = canonical_digest(
        {"manifests": [row.to_state() for row in ordered_manifests]}
    )
    handoff_frontier_digest = canonical_digest(
        {"handoffs": [row.to_state() for row in ordered_handoffs]}
    )
    trace_set_digest = canonical_digest(
        {"traces": [row.to_state() for row in ordered_traces]}
    )
    payload = {
        "protocol": COHERENCE_AUDIT_PROTOCOL,
        "findings": [row.payload() for row in ordered_findings],
        "authority_graph_digest": authority_graph.digest,
        "manifest_set_digest": manifest_set_digest,
        "handoff_frontier_digest": handoff_frontier_digest,
        "trace_set_digest": trace_set_digest,
    }
    return CoherenceAuditReport(
        findings=ordered_findings,
        authority_graph_digest=authority_graph.digest,
        manifest_set_digest=manifest_set_digest,
        handoff_frontier_digest=handoff_frontier_digest,
        trace_set_digest=trace_set_digest,
        digest=canonical_digest(payload),
    )


def _normalize_versions(values: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    rows = tuple(sorted((_explicit(key, "component id"), _explicit(value, "component version")) for key, value in values.items()))
    if len({key for key, _ in rows}) != len(rows):
        raise ValueError("duplicate component id in version map")
    return rows


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


__all__ = (
    "COHERENCE_AUDIT_PROTOCOL",
    "RESTORE_PROTOCOL",
    "CoherenceAuditReport",
    "CoherenceFinding",
    "ExternalCoreRestoreSnapshot",
    "RestorePreflightResult",
    "audit_external_core",
    "preflight_restore",
)
