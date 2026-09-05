from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from nolane.external_core import artifacts, assurance, candidate_synthesis, capability_acquisition, coding, evidence, execution, planning, research
from nolane.memory import skills
from nolane.external_core.authority_graph import AuthorityEdge, AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.coherence_audit import CoherenceAuditReport, audit_external_core
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily


@dataclass(frozen=True, slots=True)
class CanonicalFabricProfile:
    manifests: tuple[ExternalComponentManifest, ...]
    authority_graph: ExternalAuthorityGraph


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


def build_canonical_fabric_profile() -> CanonicalFabricProfile:
    """Build the post-Epoch-0 representative A–G fabric topology.

    Versions are imported from canonical implementations so this profile cannot
    silently remain green after a component version changes. The profile is an
    interoperability contract only; it grants no runtime authority.
    """

    manifests = (
        _manifest(
            component_id=evidence.COMPONENT_ID,
            component_version=evidence.COMPONENT_VERSION,
            family=ExternalCoreFamily.A,
            produces=("evidence-basis",),
            authorities=("observe",),
            resources=("truth.evidence.records",),
            evidence_outputs=("evidence",),
        ),
        _manifest(
            component_id=assurance.COMPONENT_ID,
            component_version=assurance.COMPONENT_VERSION,
            family=ExternalCoreFamily.A,
            consumes=("engineering-evidence",),
            produces=("assured-capability-input",),
            authorities=("assure",),
            resources=("truth.assurance.receipts",),
            evidence_inputs=("verification", "engineering-evidence"),
            evidence_outputs=("assurance-receipt",),
        ),
        _manifest(
            component_id=skills.COMPONENT_ID,
            component_version=skills.COMPONENT_VERSION,
            family=ExternalCoreFamily.B,
            consumes=("learning-input",),
            produces=("skill-capability",),
            authorities=("learn",),
            resources=("memory.skills",),
            evidence_inputs=("verified-experience",),
            evidence_outputs=("skill-evolution-receipt",),
        ),
        _manifest(
            component_id=candidate_synthesis.COMPONENT_ID,
            component_version=candidate_synthesis.COMPONENT_VERSION,
            family=ExternalCoreFamily.C,
            consumes=("evidence-basis", "skill-capability"),
            produces=("capability-proposal",),
            authorities=("propose",),
            forbidden=("assure", "authorize", "execute", "promote"),
            evidence_inputs=("discovery",),
            evidence_outputs=("candidate-proposal",),
        ),
        _manifest(
            component_id=capability_acquisition.COMPONENT_ID,
            component_version=capability_acquisition.COMPONENT_VERSION,
            family=ExternalCoreFamily.C,
            consumes=("capability-proposal", "assured-capability-input"),
            produces=("promoted-capability",),
            authorities=("promote",),
            resources=("reasoning.capability-acquisition",),
            evidence_inputs=("assurance-receipt", "probation-evidence"),
            evidence_outputs=("promotion-receipt",),
        ),
        _manifest(
            component_id=planning.COMPONENT_ID,
            component_version=planning.COMPONENT_VERSION,
            family=ExternalCoreFamily.D,
            consumes=("promoted-capability", "research-input"),
            produces=("execution-plan",),
            authorities=("plan",),
            resources=("goal-design.planning",),
            evidence_inputs=("requirements", "research"),
            evidence_outputs=("plan-receipt",),
        ),
        _manifest(
            component_id=execution.COMPONENT_ID,
            component_version=execution.COMPONENT_VERSION,
            family=ExternalCoreFamily.E,
            consumes=("execution-plan",),
            produces=("execution-result",),
            authorities=("execute",),
            resources=("acting.execution-sessions",),
            evidence_inputs=("authorized-action",),
            evidence_outputs=("execution-proof",),
        ),
        _manifest(
            component_id=coding.COMPONENT_ID,
            component_version=coding.COMPONENT_VERSION,
            family=ExternalCoreFamily.F,
            consumes=("execution-result",),
            produces=("engineering-evidence",),
            authorities=("engineer",),
            resources=("software-engineering.control",),
            evidence_inputs=("execution-result",),
            evidence_outputs=("engineering-evidence",),
        ),
        _manifest(
            component_id=research.COMPONENT_ID,
            component_version=research.COMPONENT_VERSION,
            family=ExternalCoreFamily.G,
            consumes=("evidence-basis",),
            produces=("research-input",),
            authorities=("research",),
            resources=("infrastructure.research-ledger",),
            evidence_inputs=("evidence",),
            evidence_outputs=("research-synthesis",),
        ),
        _manifest(
            component_id=artifacts.COMPONENT_ID,
            component_version=artifacts.COMPONENT_VERSION,
            family=ExternalCoreFamily.G,
            consumes=("engineering-evidence",),
            produces=("artifact-binding",),
            authorities=("publish", "revoke"),
            resources=("infrastructure.artifacts",),
            evidence_inputs=("engineering-evidence",),
            evidence_outputs=("artifact-envelope",),
        ),
    )
    by_id = {row.component_id: row for row in manifests}

    def edge(source: str, target: str, relation: AuthorityRelation, contract: str) -> AuthorityEdge:
        if source not in by_id or target not in by_id:
            raise RuntimeError("canonical fabric edge references unknown manifest")
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
    graph = ExternalAuthorityGraph(tuple(manifests), edges)
    graph.validate()
    return CanonicalFabricProfile(tuple(sorted(manifests, key=lambda row: row.component_id)), graph)


def run_canonical_audit() -> CoherenceAuditReport:
    profile = build_canonical_fabric_profile()
    return audit_external_core(
        manifests=profile.manifests,
        authority_graph=profile.authority_graph,
        handoffs=(),
        traces=(),
        current_source_state_digests={},
        current_evidence_digests={},
        current_artifact_digests={},
        current_freshness_fences={},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m nolane.external_core.audit",
        description="Read-only External Core A2 coherence audit.",
    )
    parser.add_argument("--check", action="store_true", help="exit non-zero when coherence findings exist")
    parser.add_argument("--json", action="store_true", help="emit canonical JSON report")
    args = parser.parse_args(argv)

    report = run_canonical_audit()
    if args.json:
        print(json.dumps(report.to_state(), sort_keys=True, separators=(",", ":")))
    else:
        status = "PASS" if report.clean else "FAIL"
        print(f"External Core A2 coherence audit: {status} ({len(report.findings)} finding(s))")
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
    "build_canonical_fabric_profile",
    "main",
    "run_canonical_audit",
)
