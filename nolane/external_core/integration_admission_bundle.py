from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.integration_admission import (
    ADMISSION_PROTOCOL,
    AdmissionDisposition,
    AdmittedAuthorityGraph,
    AdmittedHandoff,
    AdmittedManifest,
    AdmittedWorkTrace,
    CanonicalAdmissionContext,
    admit_authority_graph_state,
    admit_handoff_state,
    admit_manifest_state,
    admit_work_trace_state,
    canonical_frontier_digest,
)


COMPONENT_ID = "external.integration"
COMPONENT_VERSION = "0.0.4"
ADMISSION_BUNDLE_PROTOCOL = "external-integration-admission-bundle-v2"
ADMISSION_AUDIT_PROTOCOL = "external-integration-admission-audit-v1"


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
    return {} if value is None else value


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
    context = build_canonical_admission_context(
        observed_epoch=observed_epoch,
        current_source_state_digests=source,
        current_evidence_digests=evidence,
        current_artifact_digests=artifact,
        current_freshness_fences=freshness,
        known_handoff_digests=handoffs,
        current_work_trace_digests=traces,
    )
    registry, profile = _strict_current_objects()
    admitted_manifests = tuple(admit_manifest_state(row.to_state(), context=context) for row in registry.manifests)
    admitted_graph = admit_authority_graph_state(profile.authority_graph.to_state(), context=context)
    admitted_handoffs = tuple(
        admit_handoff_state(
            state,
            context=context,
            current_source_state_digests=source,
            current_evidence_digests=evidence,
            current_artifact_digests=artifact,
            current_freshness_fences=freshness,
            known_handoff_digests=handoffs,
        )
        for state in handoff_states
    )
    admitted_traces = tuple(
        admit_work_trace_state(
            state,
            context=context,
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

    @classmethod
    def create(cls, findings: Sequence[AdmissionAuditFinding]) -> "CanonicalAdmissionAuditReport":
        rows = tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))
        payload = {
            "protocol": ADMISSION_AUDIT_PROTOCOL,
            "findings": [row.to_state() for row in rows],
        }
        return cls(
            protocol=ADMISSION_AUDIT_PROTOCOL,
            findings=rows,
            digest="admission-audit-v1-" + canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "findings": [row.to_state() for row in self.findings],
            "digest": self.digest,
        }


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


def run_canonical_admission_audit(
    *,
    bundle: CanonicalAdmissionBundle | None = None,
    observed_epoch: int = 0,
    current_source_state_digests: Mapping[str, str] | None = None,
    current_evidence_digests: Mapping[str, str] | None = None,
    current_artifact_digests: Mapping[str, str] | None = None,
    current_freshness_fences: Mapping[str, str] | None = None,
    known_handoff_digests: Mapping[str, str] | None = None,
    current_work_trace_digests: Mapping[str, str] | None = None,
) -> CanonicalAdmissionAuditReport:
    if bundle is None:
        try:
            bundle = build_canonical_admission_bundle(
                observed_epoch=observed_epoch,
                current_source_state_digests=current_source_state_digests,
                current_evidence_digests=current_evidence_digests,
                current_artifact_digests=current_artifact_digests,
                current_freshness_fences=current_freshness_fences,
                known_handoff_digests=known_handoff_digests,
                current_work_trace_digests=current_work_trace_digests,
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            return CanonicalAdmissionAuditReport.create(
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
        return CanonicalAdmissionAuditReport.create(
            (
                AdmissionAuditFinding(
                    code="FORGED_ADMISSION_BUNDLE",
                    detail=str(exc),
                    subject_id="canonical-admission-bundle",
                ),
            )
        )

    try:
        registry, profile = _strict_current_objects()
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return CanonicalAdmissionAuditReport.create(
            (
                AdmissionAuditFinding(
                    code="CANONICAL_ADMISSION_CURRENT_STATE_BUILD_FAILED",
                    detail=str(exc),
                    subject_id="canonical-admission-bundle",
                ),
            )
        )

    findings: list[AdmissionAuditFinding] = []
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
            "CURRENT_SOURCE_STATE_FRONTIER_UNAVAILABLE",
            "SOURCE_STATE_FRONTIER_CONTEXT_MISMATCH",
        ),
        (
            "evidence",
            bundle.context.evidence_frontier_digest,
            current_evidence_digests,
            "CURRENT_EVIDENCE_FRONTIER_UNAVAILABLE",
            "EVIDENCE_FRONTIER_CONTEXT_MISMATCH",
        ),
        (
            "artifact",
            bundle.context.artifact_frontier_digest,
            current_artifact_digests,
            "CURRENT_ARTIFACT_FRONTIER_UNAVAILABLE",
            "ARTIFACT_FRONTIER_CONTEXT_MISMATCH",
        ),
        (
            "freshness",
            bundle.context.freshness_fence_frontier_digest,
            current_freshness_fences,
            "CURRENT_FRESHNESS_FRONTIER_UNAVAILABLE",
            "FRESHNESS_FRONTIER_CONTEXT_MISMATCH",
        ),
        (
            "handoff",
            bundle.context.handoff_frontier_digest,
            known_handoff_digests,
            "CURRENT_HANDOFF_FRONTIER_UNAVAILABLE",
            "HANDOFF_FRONTIER_CONTEXT_MISMATCH",
        ),
        (
            "work-trace",
            bundle.context.work_trace_frontier_digest,
            current_work_trace_digests,
            "CURRENT_WORK_TRACE_FRONTIER_UNAVAILABLE",
            "WORK_TRACE_FRONTIER_CONTEXT_MISMATCH",
        ),
    )
    for kind, bound_digest, current_values, unavailable_code, mismatch_code in frontier_specs:
        empty_digest = canonical_frontier_digest(kind, {})
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
            replay = admit_manifest_state(child.subject_state, context=bundle.context)
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
                disposition=replay.receipt.disposition,
                reason_codes=replay.receipt.reason_codes,
            )

    try:
        graph_replay = admit_authority_graph_state(bundle.authority_graph.subject_state, context=bundle.context)
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
            disposition=graph_replay.receipt.disposition,
            reason_codes=graph_replay.receipt.reason_codes,
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
                replay = admit_handoff_state(
                    child.subject_state,
                    context=bundle.context,
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
                replay = admit_work_trace_state(
                    child.subject_state,
                    context=bundle.context,
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

    return CanonicalAdmissionAuditReport.create(findings)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the canonical A5 current-admission bundle")
    parser.add_argument("--check", action="store_true", help="exit non-zero when categorical findings exist")
    parser.add_argument("--json", action="store_true", help="emit canonical audit JSON")
    parser.add_argument("--observed-epoch", type=int, default=0)
    args = parser.parse_args(argv)
    report = run_canonical_admission_audit(observed_epoch=args.observed_epoch)
    if args.json or not args.check:
        print(json.dumps(report.to_state(), sort_keys=True, separators=(",", ":")))
    elif report.findings:
        for finding in report.findings:
            print(f"{finding.code}: {finding.detail}")
    return 1 if args.check and report.findings else 0


__all__ = (
    "ADMISSION_AUDIT_PROTOCOL",
    "ADMISSION_BUNDLE_PROTOCOL",
    "AdmissionAuditFinding",
    "CanonicalAdmissionAuditReport",
    "CanonicalAdmissionBundle",
    "build_canonical_admission_bundle",
    "build_canonical_admission_context",
    "run_canonical_admission_audit",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
)


if __name__ == "__main__":
    raise SystemExit(_main())