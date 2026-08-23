from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from cogcoder.organization.blueprint import build_first_generation_blueprint

from .versioning import ComponentVersion


FIRST_GENERATION_SNAPSHOT = "1a8f333f72dd02abacf1a1bd6e2288c1025521de"
REFUNDATION_EPOCH = "REFOUNDATION-0"


@dataclass(frozen=True, slots=True)
class AgentManifest:
    """Zero-loss bootstrap view of one permanent first-generation identity.

    Wave 1 intentionally derives these manifests from the accepted blueprint
    and proves field-for-field parity before a later wave flips source-of-truth
    authority from ``blueprint.py`` to persisted manifests.
    """

    agent_id: str
    name: str
    region: str
    role: str
    rank: str
    neural_version: str
    parameter_accounting: Mapping[str, int]
    direct_work_capable: bool
    learning_capable: bool
    cognitive_capabilities: tuple[str, ...]
    memory_namespace: str
    skill_namespace: str
    external_core_bindings: tuple[str, ...]
    tool_permissions: tuple[str, ...]
    agent_definition_version: str = "0.0.0"
    permanent: bool = True

    def __post_init__(self) -> None:
        if not self.agent_id.strip() or not self.name.strip() or not self.region.strip() or not self.role.strip():
            raise ValueError("agent manifest identity/name/region/role must be explicit")
        if self.agent_definition_version != "0.0.0":
            ComponentVersion.parse(self.agent_definition_version)
        if not self.permanent:
            raise ValueError("bootstrap AgentManifest is reserved for permanent identities")
        total = int(self.parameter_accounting["total_physical_parameters"])
        if total >= 100_000_000:
            raise ValueError("first-generation permanent identity must remain below 100M physical parameters")
        if not self.memory_namespace or not self.skill_namespace:
            raise ValueError("permanent identity requires memory and skill namespaces")

    def to_state(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "region": self.region,
            "role": self.role,
            "rank": self.rank,
            "neural_version": self.neural_version,
            "parameter_accounting": dict(self.parameter_accounting),
            "direct_work_capable": self.direct_work_capable,
            "learning_capable": self.learning_capable,
            "cognitive_capabilities": list(self.cognitive_capabilities),
            "memory_namespace": self.memory_namespace,
            "skill_namespace": self.skill_namespace,
            "external_core_bindings": list(self.external_core_bindings),
            "tool_permissions": list(self.tool_permissions),
            "agent_definition_version": self.agent_definition_version,
            "permanent": self.permanent,
        }


@dataclass(frozen=True, slots=True)
class ComponentManifest:
    component_id: str
    version: ComponentVersion
    layer: str
    responsibility: str
    state_schema: str
    dependencies: tuple[str, ...] = ()
    version_identity: str = "component_version"

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.component_id, self.layer, self.responsibility, self.state_schema)):
            raise ValueError("component id/layer/responsibility/state schema must be explicit")
        if self.version_identity != "component_version":
            raise ValueError("component software revision must not be conflated with other version identities")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("component dependencies must be unique")
        if self.component_id in self.dependencies:
            raise ValueError("component cannot depend on itself")

    def to_state(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "version": str(self.version),
            "layer": self.layer,
            "responsibility": self.responsibility,
            "state_schema": self.state_schema,
            "dependencies": list(self.dependencies),
            "version_identity": self.version_identity,
        }


def build_bootstrap_agent_manifests() -> tuple[AgentManifest, ...]:
    rows: list[AgentManifest] = []
    for identity in build_first_generation_blueprint():
        rows.append(
            AgentManifest(
                agent_id=identity.agent_id,
                name=identity.name,
                region=identity.region,
                role=identity.role,
                rank=identity.rank.value,
                neural_version=identity.neural_version,
                parameter_accounting=identity.parameter_accounting.to_state(),
                direct_work_capable=identity.direct_work_capable,
                learning_capable=identity.learning_capable,
                cognitive_capabilities=identity.cognitive_capabilities,
                memory_namespace=identity.memory_namespace,
                skill_namespace=identity.skill_namespace,
                external_core_bindings=identity.external_core_bindings,
                tool_permissions=identity.tool_permissions,
            )
        )
    return tuple(rows)


# Component graph for Wave 1.  These IDs are deliberately semantic rather than
# historical Part/R labels.  The implementation behind them is migrated in
# later waves; Wave 1 establishes their independent version identities and
# dependency contracts without deleting legacy code.
_COMPONENT_SPECS: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    ("core.canonical_digest", "core", "canonical JSON, digest and content identity", "canonical-digest-v1", ()),
    ("schemas.identity", "schemas", "stable identity/rank/status/namespace schemas", "identity-schema-v1", ("core.canonical_digest",)),
    ("organization.identity", "organization", "67 permanent identity registry", "organization-identity-v1", ("schemas.identity",)),
    ("organization.authority", "organization", "authoritative ownership, block and override graph", "authority-v1", ("organization.identity",)),
    ("organization.events", "organization", "append-only causal cognitive events", "events-v1", ("organization.identity", "core.canonical_digest")),
    ("external.artifacts", "external_core", "content-addressed immutable artifact fabric", "artifacts-v1", ("organization.identity", "core.canonical_digest")),
    ("external.evidence", "external_core", "verification evidence references and subjects", "evidence-v1", ("external.artifacts", "organization.identity")),
    ("organization.tasks", "organization", "task DAG and execution projection", "tasks-v1", ("organization.identity", "organization.events", "organization.authority")),
    ("organization.coordination.leases", "organization", "canonical lease epoch and heartbeat authority", "coordination-leases-v1", ("organization.tasks",)),
    ("organization.coordination.delivery", "organization", "causal event delivery and ACK transport", "coordination-delivery-v1", ("organization.events",)),
    ("external.requirements", "external_core", "requirement DAG, constraints and acceptance revisions", "requirements-v1", ("organization.authority", "external.evidence")),
    ("external.planning", "external_core", "Master Plan DAG, milestones, risks and revisions", "master-plan-v1", ("external.requirements", "organization.authority")),
    ("external.architecture", "external_core", "component/interface/trust/ADR/change-impact graph", "architecture-v1", ("external.requirements", "external.planning", "organization.authority")),
    ("external.integration", "external_core", "compatibility and semantic integration authority", "integration-v1", ("external.architecture", "external.evidence", "organization.authority")),
    ("external.memory.fabric", "external_core", "scoped persistent memory ledger", "memory-fabric-v1", ("external.evidence",)),
    ("external.memory.lifecycle", "external_core", "memory status and semantic relation lifecycle", "memory-lifecycle-v1", ("external.memory.fabric",)),
    ("external.memory.retrieval", "external_core", "budgeted deterministic memory selection receipts", "memory-retrieval-v1", ("external.memory.fabric",)),
    ("external.knowledge", "external_core", "provenance-aware reusable knowledge fabric", "knowledge-v1", ("external.evidence",)),
    ("external.skills", "external_core", "personal/regional/global reusable skill fabric", "skills-v1", ("external.evidence",)),
    ("external.experience", "external_core", "identity-owned learning episodes and attribution", "experience-v1", ("organization.identity",)),
    ("external.self_model", "external_core", "evidence-backed competence and calibration state", "self-model-v1", ("external.evidence",)),
    ("external.epistemic", "external_core", "hypothesis, uncertainty and epistemic workspace", "epistemic-v1", ("external.evidence",)),
    ("external.context", "external_core", "context providers, continuity and semantic deltas", "context-v1", ("external.memory.retrieval", "external.knowledge", "external.skills", "external.self_model", "external.planning", "external.architecture")),
    ("external.invokable_cores", "external_core", "invokable external-core schema, permission and failure registry", "invokable-cores-v1", ("organization.identity",)),
    ("external.execution.workspace", "external_core", "exact isolated repository workspace", "execution-workspace-v1", ("external.artifacts",)),
    ("external.coding.claims", "external_core", "exclusive source mutation ownership", "coding-claims-v1", ("organization.coordination.leases",)),
    ("external.execution.executor", "external_core", "side-effect membrane for tools and cores", "execution-executor-v1", ("organization.coordination.leases", "external.invokable_cores", "external.execution.workspace", "external.coding.claims")),
    ("neural.shared", "neural", "shared neural substrate and checkpoint lineage", "neural-shared-manifest-v1", ("core.canonical_digest",)),
    ("neural.inference_bridge", "neural_boundary", "versioned context-to-neural inference adapter", "neural-inference-bridge-v1", ("neural.shared", "external.context")),
    ("external.execution.control", "external_core", "bounded inference/action session loop", "execution-control-v1", ("neural.inference_bridge", "external.execution.executor")),
    ("external.coding.patches", "external_core", "patch candidates, tool receipts and evidence lineage", "coding-patches-v1", ("external.coding.claims", "external.artifacts")),
    ("external.coding.control", "external_core", "coding work routing, patch readiness and handoff", "coding-control-v1", ("external.coding.patches", "external.planning", "external.architecture", "external.integration")),
    ("external.debugging", "external_core", "failure reproduction, hypotheses and root-cause handoff", "debugging-v1", ("external.coding.control", "external.evidence")),
    ("external.ui_ux", "external_core", "UX authority, frontend implementation and render-quality evidence", "ui-ux-v1", ("external.coding.control", "external.artifacts", "external.evidence")),
    ("external.assurance", "external_core", "policy/domain independent assurance and challenges", "assurance-v1", ("external.evidence", "organization.authority")),
    ("external.operations", "external_core", "migration, build, release, reliability and performance readiness", "operations-v1", ("external.assurance", "external.artifacts")),
    ("external.research", "external_core", "freshness/provenance research and governed handoff", "research-v1", ("external.assurance", "external.artifacts")),
    ("external.cognitive_library", "external_core", "typed operators, abstractions and reusable cognitive primitives", "cognitive-library-v1", ("external.evidence",)),
    ("external.capability_acquisition", "external_core", "probation, quarantine, promotion and retrieval firewall", "capability-acquisition-v1", ("external.cognitive_library", "external.assurance")),
    ("external.causal", "external_core", "bounded proof-carrying causal basis mechanisms", "causal-v1", ("external.cognitive_library", "external.evidence")),
    ("external.experimentation", "external_core", "active probes, interventions and version-space experiments", "experimentation-v1", ("external.causal", "external.evidence")),
    ("external.transfer_meta", "external_core", "portable verified experience and governed meta reuse", "transfer-meta-v1", ("external.causal", "external.experience", "external.assurance")),
    ("evaluation.regimes", "evaluation", "frozen benchmark regime and budget contracts", "evaluation-regimes-v1", ("external.evidence",)),
    ("evaluation.evidence", "evaluation", "observations, matched-budget comparisons and ablations", "evaluation-evidence-v1", ("evaluation.regimes",)),
    ("evaluation.stress", "evaluation", "long-horizon continuity and failure stress receipts", "evaluation-stress-v1", ("evaluation.evidence",)),
    ("evaluation.parameters", "evaluation", "physical/logical parameter accounting and scaling authority", "evaluation-parameters-v1", ("organization.identity", "evaluation.evidence")),
    ("evaluation.release", "evaluation", "exact scientific evaluation release and reproduction", "evaluation-release-v1", ("evaluation.evidence", "evaluation.parameters", "external.artifacts")),
    ("evaluation.claims", "evaluation", "fail-closed scientific claim boundary", "evaluation-claims-v1", ("evaluation.release", "evaluation.stress")),
    ("evaluation.campaign", "evaluation", "sealed real-repository evaluation campaign", "evaluation-campaign-v1", ("evaluation.regimes", "external.execution.control")),
    ("organization.central", "organization", "global direct-worker and governed control composition", "central-v1", ("organization.authority", "organization.tasks", "organization.coordination.delivery", "external.context", "external.invokable_cores")),
    ("organization.runtime", "organization", "manifest-driven canonical runtime assembly target", "runtime-composition-v1", ("organization.central", "external.coding.control", "external.debugging", "external.ui_ux", "external.operations", "external.research", "evaluation.claims", "evaluation.campaign")),
)


def build_component_manifests() -> tuple[ComponentManifest, ...]:
    version = ComponentVersion(0, 0, 0)
    return tuple(
        ComponentManifest(
            component_id=component_id,
            version=version,
            layer=layer,
            responsibility=responsibility,
            state_schema=state_schema,
            dependencies=dependencies,
        )
        for component_id, layer, responsibility, state_schema, dependencies in _COMPONENT_SPECS
    )
