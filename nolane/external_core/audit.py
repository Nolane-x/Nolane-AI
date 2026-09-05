from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core import artifacts, assurance, candidate_synthesis, capability_acquisition, coding, evidence, execution, planning, research
from nolane.external_core.authority_graph import AuthorityEdge, AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.coherence_audit import (
    CoherenceAuditReport,
    artifact_state_digest,
    audit_live_external_core,
)
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.handoff import ExternalHandoffEnvelope
from nolane.external_core.live_fabric import (
    LiveExternalCoreSnapshot,
    handoff_frontier_digest,
    source_state_frontier_digest,
    work_trace_frontier_digest,
)
from nolane.external_core.registry import (
    CapabilityCatalogBindingReceipt,
    CanonicalComponentRegistry,
    ManifestAdapter,
)
from nolane.external_core.work_trace import CognitiveWorkTrace
from nolane.memory import skills
from nolane.metadata.capabilities import build_external_core_catalog


@dataclass(frozen=True, slots=True)
class CanonicalFabricProfile:
    manifests: tuple[ExternalComponentManifest, ...]
    authority_graph: ExternalAuthorityGraph


@dataclass(frozen=True, slots=True)
class _CanonicalAdapterSpec:
    source: Any
    family: ExternalCoreFamily
    consumes: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    authorities: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()
    evidence_inputs: tuple[str, ...] = ()
    evidence_outputs: tuple[str, ...] = ()


def _canonical_adapter_specs() -> tuple[_CanonicalAdapterSpec, ...]:
    return (
        _CanonicalAdapterSpec(
            source=evidence,
            family=ExternalCoreFamily.A,
            produces=("evidence-basis",),
            authorities=("observe",),
            resources=("truth.evidence.records",),
            evidence_outputs=("evidence",),
        ),
        _CanonicalAdapterSpec(
            source=assurance,
            family=ExternalCoreFamily.A,
            consumes=("engineering-evidence",),
            produces=("assured-capability-input",),
            authorities=("assure",),
            resources=("truth.assurance.receipts",),
            evidence_inputs=("verification", "engineering-evidence"),
            evidence_outputs=("assurance-receipt",),
        ),
        _CanonicalAdapterSpec(
            source=skills,
            family=ExternalCoreFamily.B,
            consumes=("learning-input",),
            produces=("skill-capability",),
            authorities=("learn",),
            resources=("memory.skills",),
            evidence_inputs=("verified-experience",),
            evidence_outputs=("skill-evolution-receipt",),
        ),
        _CanonicalAdapterSpec(
            source=candidate_synthesis,
            family=ExternalCoreFamily.C,
            consumes=("evidence-basis", "skill-capability"),
            produces=("capability-proposal",),
            authorities=("propose",),
            forbidden=("assure", "authorize", "execute", "promote"),
            evidence_inputs=("discovery",),
            evidence_outputs=("candidate-proposal",),
        ),
        _CanonicalAdapterSpec(
            source=capability_acquisition,
            family=ExternalCoreFamily.C,
            consumes=("capability-proposal", "assured-capability-input"),
            produces=("promoted-capability",),
            authorities=("promote",),
            resources=("reasoning.capability-acquisition",),
            evidence_inputs=("assurance-receipt", "probation-evidence"),
            evidence_outputs=("promotion-receipt",),
        ),
        _CanonicalAdapterSpec(
            source=planning,
            family=ExternalCoreFamily.D,
            consumes=("promoted-capability", "research-input"),
            produces=("execution-plan",),
            authorities=("plan",),
            resources=("goal-design.planning",),
            evidence_inputs=("requirements", "research"),
            evidence_outputs=("plan-receipt",),
        ),
        _CanonicalAdapterSpec(
            source=execution,
            family=ExternalCoreFamily.E,
            consumes=("execution-plan",),
            produces=("execution-result",),
            authorities=("execute",),
            resources=("acting.execution-sessions",),
            evidence_inputs=("authorized-action",),
            evidence_outputs=("execution-proof",),
        ),
        _CanonicalAdapterSpec(
            source=coding,
            family=ExternalCoreFamily.F,
            consumes=("execution-result",),
            produces=("engineering-evidence",),
            authorities=("engineer",),
            resources=("software-engineering.control",),
            evidence_inputs=("execution-result",),
            evidence_outputs=("engineering-evidence",),
        ),
        _CanonicalAdapterSpec(
            source=research,
            family=ExternalCoreFamily.G,
            consumes=("evidence-basis",),
            produces=("research-input",),
            authorities=("research",),
            resources=("infrastructure.research-ledger",),
            evidence_inputs=("evidence",),
            evidence_outputs=("research-synthesis",),
        ),
        _CanonicalAdapterSpec(
            source=artifacts,
            family=ExternalCoreFamily.G,
            consumes=("engineering-evidence",),
            produces=("artifact-binding",),
            authorities=("publish", "revoke"),
            resources=("infrastructure.artifacts",),
            evidence_inputs=("engineering-evidence",),
            evidence_outputs=("artifact-envelope",),
        ),
    )


def _manifest(
    *,
    component_id: str,
    component_version: str,
    family: ExternalCoreFamily,
    consumes: tuple[str, ...] = (),
    produces: tuple[str, ...] = (),
    authorities: tuple[str, ...] = (),
    forbidden: tuple[str, ...] = (),
    resources: tuple[str, ...] = (),
    evidence_inputs: tuple[str, ...] = (),
    evidence_outputs: tuple[str, ...] = (),
) -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version=component_version,
        family=family,
        protocol_versions={"external-fabric": "1"},
        consumes_contracts=consumes,
        produces_contracts=produces,
        authority_capabilities=authorities,
        forbidden_authorities=forbidden,
        mutable_resources=resources,
        evidence_inputs=evidence_inputs,
        evidence_outputs=evidence_outputs,
        restore_protocol="exact-revalidation",
        compatibility_floor=component_version,
        compatibility_ceiling=component_version,
    )


def build_canonical_registry() -> CanonicalComponentRegistry:
    """Build the A3 registry from current canonical component constants.

    Semantic declarations live in adapter specs, but component identity/version
    are read from the imported canonical module on every build. Registration is
    descriptive and never creates authority beyond the underlying A–G owner.
    """

    adapters: list[ManifestAdapter] = []
    for spec in _canonical_adapter_specs():
        source = spec.source
        component_id = str(source.COMPONENT_ID)
        component_version = str(source.COMPONENT_VERSION)
        manifest = _manifest(
            component_id=component_id,
            component_version=component_version,
            family=spec.family,
            consumes=spec.consumes,
            produces=spec.produces,
            authorities=spec.authorities,
            forbidden=spec.forbidden,
            resources=spec.resources,
            evidence_inputs=spec.evidence_inputs,
            evidence_outputs=spec.evidence_outputs,
        )
        adapters.append(
            ManifestAdapter.create(
                adapter_id=f"canonical:{component_id}",
                source_locator=str(source.__name__),
                source_component_id=component_id,
                source_component_version=component_version,
                manifest=manifest,
            )
        )
    return CanonicalComponentRegistry.create(tuple(adapters))


def build_canonical_fabric_profile() -> CanonicalFabricProfile:
    """Build the registry-derived post-Epoch-0 A–G fabric topology."""

    registry = build_canonical_registry()
    manifests = registry.manifests
    by_id = {row.component_id: row for row in manifests}

    def edge(source: str, target: str, relation: AuthorityRelation, contract: str) -> AuthorityEdge:
        if source not in by_id or target not in by_id:
            raise RuntimeError("canonical fabric edge references unknown registry component")
        return AuthorityEdge.create(
            source_component_id=source,
            target_component_id=target,
            relation=relation,
            contract_kind=contract,
        )

    edges = (
        edge(evidence.COMPONENT_ID, research.COMPONENT_ID, AuthorityRelation.EVIDENCE_FOR, "evidence-basis"),
        edge(evidence.COMPONENT_ID, candidate_synthesis.COMPONENT_ID, AuthorityRelation.EVIDENCE_FOR, "evidence-basis"),
        edge(skills.COMPONENT_ID, candidate_synthesis.COMPONENT_ID, AuthorityRelation.LEARNING_INPUT_TO, "skill-capability"),
        edge(candidate_synthesis.COMPONENT_ID, capability_acquisition.COMPONENT_ID, AuthorityRelation.PROPOSES_TO, "capability-proposal"),
        edge(assurance.COMPONENT_ID, capability_acquisition.COMPONENT_ID, AuthorityRelation.ASSURES, "assured-capability-input"),
        edge(capability_acquisition.COMPONENT_ID, planning.COMPONENT_ID, AuthorityRelation.PROPOSES_TO, "promoted-capability"),
        edge(research.COMPONENT_ID, planning.COMPONENT_ID, AuthorityRelation.PUBLISHES_ARTIFACT_TO, "research-input"),
        edge(planning.COMPONENT_ID, execution.COMPONENT_ID, AuthorityRelation.PROPOSES_TO, "execution-plan"),
        edge(execution.COMPONENT_ID, coding.COMPONENT_ID, AuthorityRelation.PUBLISHES_ARTIFACT_TO, "execution-result"),
        edge(coding.COMPONENT_ID, assurance.COMPONENT_ID, AuthorityRelation.EVIDENCE_FOR, "engineering-evidence"),
        edge(coding.COMPONENT_ID, artifacts.COMPONENT_ID, AuthorityRelation.PUBLISHES_ARTIFACT_TO, "engineering-evidence"),
    )
    graph = ExternalAuthorityGraph(manifests, edges)
    graph.validate()
    return CanonicalFabricProfile(manifests, graph)


def build_canonical_capability_binding(
    registry: CanonicalComponentRegistry | None = None,
) -> CapabilityCatalogBindingReceipt:
    """Bind organization capability metadata to A3 for provenance only."""

    canonical_registry = registry or build_canonical_registry()
    catalog = build_external_core_catalog()
    catalog_payload = {
        "protocol": "metadata-external-core-catalog-v1",
        "bindings": [
            {
                "core_id": row.core_id,
                "scope": row.scope,
                "owner_region": row.owner_region,
                "component_version": row.component_version,
            }
            for row in catalog
        ],
    }
    return CapabilityCatalogBindingReceipt.create(
        catalog_version="metadata-external-core-catalog-v1",
        catalog_digest="metadata-catalog-v1-" + canonical_digest(catalog_payload),
        registry_digest=canonical_registry.registry_digest,
    )


def build_canonical_live_snapshot(
    *,
    registry: CanonicalComponentRegistry | None = None,
    profile: CanonicalFabricProfile | None = None,
    handoffs: tuple[ExternalHandoffEnvelope, ...] = (),
    traces: tuple[CognitiveWorkTrace, ...] = (),
    current_source_state_digests: Mapping[str, str] | None = None,
    current_artifact_digests: Mapping[str, str] | None = None,
) -> LiveExternalCoreSnapshot:
    canonical_registry = registry or build_canonical_registry()
    canonical_profile = profile or build_canonical_fabric_profile()
    if canonical_profile.manifests != canonical_registry.manifests:
        raise ValueError("canonical live snapshot profile does not match registry manifests")
    source_states = dict(current_source_state_digests or {})
    artifact_digests = dict(current_artifact_digests or {})
    return LiveExternalCoreSnapshot.create(
        registry_digest=canonical_registry.registry_digest,
        authority_graph_digest=canonical_profile.authority_graph.digest,
        artifact_graph_digest=artifact_state_digest(artifact_digests),
        handoff_frontier_digest=handoff_frontier_digest(tuple(row.to_state() for row in handoffs)),
        work_trace_frontier_digest=work_trace_frontier_digest(tuple(row.to_state() for row in traces)),
        source_state_frontier_digest=source_state_frontier_digest(source_states),
        component_versions=canonical_registry.component_versions,
    )


def run_canonical_live_audit() -> CoherenceAuditReport:
    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    snapshot = build_canonical_live_snapshot(registry=registry, profile=profile)
    return audit_live_external_core(
        registry=registry,
        authority_graph=profile.authority_graph,
        snapshot=snapshot,
        handoffs=(),
        traces=(),
        current_source_state_digests={},
        current_evidence_digests={},
        current_artifact_digests={},
        current_freshness_fences={},
    )


def run_canonical_audit() -> CoherenceAuditReport:
    """Compatibility entry point, now backed by the A3 canonical live registry."""

    return run_canonical_live_audit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m nolane.external_core.audit",
        description="Read-only External Core A2+A3 registry-bound coherence audit.",
    )
    parser.add_argument("--check", action="store_true", help="exit non-zero when coherence findings exist")
    parser.add_argument("--json", action="store_true", help="emit canonical JSON report")
    args = parser.parse_args(argv)

    report = run_canonical_audit()
    if args.json:
        print(json.dumps(report.to_state(), sort_keys=True, separators=(",", ":")))
    else:
        status = "PASS" if report.clean else "FAIL"
        print(f"External Core A2+A3 coherence audit: {status} ({len(report.findings)} finding(s))")
        for finding in report.findings:
            subjects = ",".join(finding.subjects)
            print(f"- {finding.code}: {subjects}: {finding.detail}")
    if args.check and not report.clean:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "CanonicalFabricProfile",
    "build_canonical_capability_binding",
    "build_canonical_fabric_profile",
    "build_canonical_live_snapshot",
    "build_canonical_registry",
    "main",
    "run_canonical_audit",
    "run_canonical_live_audit",
)