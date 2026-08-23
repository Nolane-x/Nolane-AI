from __future__ import annotations

from dataclasses import dataclass
from typing import Any


UNIVERSAL_COGNITIVE_CAPABILITIES: tuple[str, ...] = (
    "goal_understanding",
    "task_decomposition",
    "local_planning",
    "causal_reasoning",
    "memory_use",
    "tool_use",
    "uncertainty",
    "evidence_handling",
    "communication",
    "self_evaluation",
    "skill_induction",
    "learning_from_feedback",
)

GENERAL_TOOLS: tuple[str, ...] = (
    "filesystem",
    "git",
    "terminal",
    "code-search",
    "memory",
    "task-graph",
    "event-ledger",
    "evidence-store",
)

CENTRAL_TOOLS: tuple[str, ...] = GENERAL_TOOLS + (
    "browser",
    "lsp",
    "ast",
    "compiler",
    "test-runner",
    "plan-graph",
    "architecture-graph",
    "repo-graph",
    "knowledge-graph",
    "browser-automation",
    "runtime-observation",
    "research",
    "agent-control",
    "resource-control",
)

SHARED_CORE_PARAMETERS = 56_000_000
LOCAL_PARAMETER_BANDS: dict[str, int] = {
    "central": 40_000_000,
    "chief": 34_000_000,
    "senior_specialist": 20_000_000,
    "specialist": 8_000_000,
}


@dataclass(frozen=True, slots=True)
class CanonicalRoleSpec:
    agent_id: str
    name: str
    role: str
    senior: bool = False


@dataclass(frozen=True, slots=True)
class CanonicalRegionSpec:
    region_id: str
    chief_id: str
    chief_name: str
    chief_role: str
    external_cores: tuple[str, ...]
    specialists: tuple[CanonicalRoleSpec, ...]


REGION_SPECS: tuple[CanonicalRegionSpec, ...] = (
    CanonicalRegionSpec(
        "requirements-product", "requirements.chief", "Requirements Chief",
        "Requirements / Product Intelligence Chief",
        ("requirements-graph", "acceptance-criteria-engine", "constraint-ledger"),
        (
            CanonicalRoleSpec("requirements.analysis.01", "Requirement Analyst", "requirement analysis", True),
            CanonicalRoleSpec("requirements.acceptance.01", "Acceptance & Constraint Agent", "acceptance and constraint reasoning"),
        ),
    ),
    CanonicalRegionSpec(
        "planning-program", "planning.chief", "Planning Chief", "Planning / Program Intelligence Chief",
        ("task-dag", "critical-path-engine", "risk-graph", "progress-reconciler"),
        (
            CanonicalRoleSpec("planning.task-graph.01", "Task Graph Planner", "task decomposition and dependency planning", True),
            CanonicalRoleSpec("planning.milestone.01", "Milestone Planner", "strategic milestone planning"),
            CanonicalRoleSpec("planning.dependency-risk.01", "Dependency & Risk Planner", "dependency and risk analysis"),
            CanonicalRoleSpec("planning.audit.01", "Plan Auditor", "plan drift reconciliation"),
        ),
    ),
    CanonicalRegionSpec(
        "architecture-system", "architecture.chief", "Architecture Chief", "Architecture / System Design Chief",
        ("architecture-graph", "interface-contract-engine", "change-impact-graph", "adr-ledger"),
        (
            CanonicalRoleSpec("architecture.component.01", "Component Architect", "component architecture", True),
            CanonicalRoleSpec("architecture.api-interface.01", "API & Interface Architect", "interface and API architecture"),
            CanonicalRoleSpec("architecture.change-impact.01", "Change Impact Architect", "architectural impact reasoning"),
            CanonicalRoleSpec("architecture.system-boundary.01", "System Boundary Architect", "system boundary design"),
        ),
    ),
    CanonicalRegionSpec(
        "core-coding", "coding.chief", "Coding Chief", "Core Coding Chief",
        ("lsp", "ast", "symbol-graph", "compiler", "patch-engine", "worktree-manager", "test-selection"),
        (
            CanonicalRoleSpec("coding.core-algorithm.01", "Core Algorithm Coder", "core algorithm implementation", True),
            CanonicalRoleSpec("coding.backend.01", "Backend Coder", "backend and service implementation", True),
            CanonicalRoleSpec("coding.systems.01", "Systems Coder", "systems and low-level implementation", True),
            CanonicalRoleSpec("coding.refactor.01", "Refactoring Coder", "large-scale refactoring"),
            CanonicalRoleSpec("coding.api-interface.01", "API Coder", "API and interface implementation"),
            CanonicalRoleSpec("coding.build-dependency.01", "Build & Dependency Coder", "build and dependency engineering"),
        ),
    ),
    CanonicalRegionSpec(
        "frontend-ui", "frontend.chief", "Frontend UI Chief", "Frontend / UI Engineering Chief",
        ("browser-runtime", "dom-tree", "cssom", "playwright", "visual-diff"),
        (
            CanonicalRoleSpec("frontend.logic.01", "Frontend Logic Coder", "frontend state and application logic", True),
            CanonicalRoleSpec("frontend.component.01", "Component Engineer", "component implementation"),
            CanonicalRoleSpec("frontend.browser-runtime.01", "Browser Runtime Engineer", "browser runtime diagnosis"),
        ),
    ),
    CanonicalRegionSpec(
        "ux-product-design", "ux.chief", "UX Chief", "UX / Product Design Chief",
        ("interaction-model", "design-token-graph", "accessibility-tree"),
        (
            CanonicalRoleSpec("ux.flow.01", "UX Flow Architect", "interaction and information flow", True),
            CanonicalRoleSpec("ux.visual-accessibility.01", "Visual & Accessibility Designer", "visual and accessibility design"),
        ),
    ),
    CanonicalRegionSpec(
        "debugging-failure", "debug.chief", "Debug Chief", "Debugging / Failure Intelligence Chief",
        ("runtime-tracer", "stack-graph", "coverage-graph", "state-diff", "crash-analyzer", "git-bisect", "failure-minimizer"),
        (
            CanonicalRoleSpec("debug.reproducer.01", "Bug Reproducer", "minimal failure reproduction", True),
            CanonicalRoleSpec("debug.runtime-trace.01", "Runtime Trace Investigator", "runtime tracing and state diagnosis", True),
            CanonicalRoleSpec("debug.static-root-cause.01", "Static Root-Cause Investigator", "static defect and root-cause reasoning"),
            CanonicalRoleSpec("debug.concurrency-state.01", "Concurrency & State Debugger", "race, deadlock and state diagnosis", True),
            CanonicalRoleSpec("debug.regression-bisect.01", "Regression & Bisect Agent", "regression localization and historical causality"),
        ),
    ),
    CanonicalRegionSpec(
        "verification-testing", "verification.chief", "Verification Chief", "Verification / Testing Chief",
        ("fresh-sandbox", "property-testing", "fuzzer", "integration-runner", "acceptance-harness"),
        (
            CanonicalRoleSpec("verification.unit-property.01", "Unit & Property Verifier", "unit and property verification", True),
            CanonicalRoleSpec("verification.integration-e2e.01", "Integration & E2E Verifier", "integration and end-to-end verification", True),
            CanonicalRoleSpec("verification.spec-acceptance.01", "Specification Acceptance Verifier", "specification and acceptance verification"),
            CanonicalRoleSpec("verification.fuzz-regression.01", "Fuzz & Regression Verifier", "fuzzing and regression verification"),
        ),
    ),
    CanonicalRegionSpec(
        "security-adversarial", "security.chief", "Security Chief", "Security / Adversarial Engineering Chief",
        ("threat-model", "security-scanner", "attack-harness", "supply-chain-auditor"),
        (
            CanonicalRoleSpec("security.threat-model.01", "Threat Model Agent", "threat modeling", True),
            CanonicalRoleSpec("security.supply-chain.01", "Supply Chain Security Agent", "dependency and supply-chain security"),
            CanonicalRoleSpec("security.adversarial.01", "Adversarial Security Agent", "adversarial security validation"),
        ),
    ),
    CanonicalRegionSpec(
        "data-storage-migration", "data.chief", "Data Chief", "Data / Storage / Migration Chief",
        ("schema-graph", "migration-planner", "consistency-checker", "storage-profiler"),
        (
            CanonicalRoleSpec("data.schema-migration.01", "Schema & Migration Agent", "schema and migration engineering", True),
            CanonicalRoleSpec("data.persistence.01", "Persistence Agent", "storage and persistence implementation"),
            CanonicalRoleSpec("data.cache-consistency.01", "Cache & Consistency Agent", "cache and consistency reasoning"),
        ),
    ),
    CanonicalRegionSpec(
        "infrastructure-release", "infrastructure.chief", "Infrastructure Chief", "Infrastructure / DevOps / Release Chief",
        ("ci-engine", "container-runtime", "deployment-controller", "observability-stack", "release-packager"),
        (
            CanonicalRoleSpec("infrastructure.ci-env.01", "CI & Environment Agent", "CI and environment engineering", True),
            CanonicalRoleSpec("infrastructure.deployment.01", "Deployment Agent", "deployment engineering"),
            CanonicalRoleSpec("infrastructure.observability-release.01", "Observability & Release Agent", "observability and release packaging"),
        ),
    ),
    CanonicalRegionSpec(
        "performance-reliability", "reliability.chief", "Reliability Chief", "Performance / Reliability Chief",
        ("cpu-profiler", "memory-profiler", "race-detector", "recovery-simulator", "resilience-harness"),
        (
            CanonicalRoleSpec("reliability.performance.01", "Performance Agent", "performance diagnosis and optimization", True),
            CanonicalRoleSpec("reliability.concurrency.01", "Reliability Concurrency Agent", "concurrency reliability"),
            CanonicalRoleSpec("reliability.recovery.01", "Recovery Agent", "failure recovery and graceful degradation"),
        ),
    ),
    CanonicalRegionSpec(
        "research-external", "research.chief", "Research Chief", "Research / External Intelligence Chief",
        ("web-retrieval", "github-research", "docs-index", "paper-index", "package-registry", "provenance-store"),
        (
            CanonicalRoleSpec("research.repo-archaeology.01", "Repository Archaeologist", "repository history and convention research", True),
            CanonicalRoleSpec("research.docs-api.01", "Docs & API Researcher", "external documentation and API research"),
            CanonicalRoleSpec("research.prior-art.01", "Algorithm & Prior-Art Researcher", "algorithms, papers and prior art"),
        ),
    ),
    CanonicalRegionSpec(
        "integration-change-control", "integration.chief", "Integration Chief", "Integration / Change Control Chief",
        ("merge-graph", "compatibility-matrix", "change-control-ledger", "integration-sandbox"),
        (
            CanonicalRoleSpec("integration.merge.01", "Merge Integration Agent", "merge sequencing and conflict resolution", True),
            CanonicalRoleSpec("integration.compatibility.01", "Compatibility Agent", "cross-system compatibility validation"),
            CanonicalRoleSpec("integration.change-control.01", "Change Control Agent", "change authorization and propagation"),
        ),
    ),
    CanonicalRegionSpec(
        "memory-context-knowledge", "memory.chief", "Memory & Context Chief", "Memory / Context / Knowledge Chief",
        ("vector-retrieval", "knowledge-graph", "temporal-memory", "skill-store", "context-compiler", "semantic-diff"),
        (
            CanonicalRoleSpec("memory.context-compiler.01", "Context Compiler Agent", "context compilation and semantic delta", True),
            CanonicalRoleSpec("memory.knowledge-graph.01", "Knowledge Graph Agent", "structured organizational knowledge"),
            CanonicalRoleSpec("memory.lifecycle.01", "Memory Lifecycle Agent", "memory consolidation, forgetting and promotion"),
        ),
    ),
)


def _parameter_state(rank: str) -> dict[str, int]:
    local = LOCAL_PARAMETER_BANDS[rank]
    return {
        "shared_physical_parameters": SHARED_CORE_PARAMETERS,
        "local_physical_parameters": local,
        "total_physical_parameters": SHARED_CORE_PARAMETERS + local,
    }


def _identity_state(
    *,
    agent_id: str,
    name: str,
    region: str,
    role: str,
    rank: str,
    region_chief_id: str | None,
    external_cores: tuple[str, ...],
    tools: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "name": name,
        "region": region,
        "role": role,
        "rank": rank,
        "neural_version": f"NUC-0.1+{agent_id}-delta-0.1",
        "parameter_accounting": _parameter_state(rank),
        "region_chief_id": region_chief_id,
        "direct_work_capable": True,
        "learning_capable": True,
        "cognitive_capabilities": list(UNIVERSAL_COGNITIVE_CAPABILITIES),
        "memory_namespace": f"agent/{agent_id}",
        "skill_namespace": f"skills/personal/{agent_id}",
        "external_core_bindings": list(external_cores),
        "tool_permissions": list(tools),
        "status": "sleeping",
        "current_task": None,
        "specialization_version": "specialization-0.1",
        "authority_scope": ["task"],
        "subscriptions": [],
        "checkpoint_id": None,
        "self_model_version": "self-model-0.1",
    }


def build_canonical_identity_states() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = [
        _identity_state(
            agent_id="nolane.central",
            name="Nolane Central",
            region="global-command",
            role="Global Coding AGI Coordinator and Direct Worker",
            rank="central",
            region_chief_id=None,
            external_cores=("global-project-graph", "resource-arbiter", "direct-intervention-channel"),
            tools=CENTRAL_TOOLS,
        )
    ]
    for region in REGION_SPECS:
        rows.append(
            _identity_state(
                agent_id=region.chief_id,
                name=region.chief_name,
                region=region.region_id,
                role=region.chief_role,
                rank="chief",
                region_chief_id=region.chief_id,
                external_cores=region.external_cores,
                tools=GENERAL_TOOLS + region.external_cores,
            )
        )
        for specialist in region.specialists:
            rank = "senior_specialist" if specialist.senior else "specialist"
            rows.append(
                _identity_state(
                    agent_id=specialist.agent_id,
                    name=specialist.name,
                    region=region.region_id,
                    role=specialist.role,
                    rank=rank,
                    region_chief_id=region.chief_id,
                    external_cores=region.external_cores,
                    tools=GENERAL_TOOLS + region.external_cores,
                )
            )

    ids = [row["agent_id"] for row in rows]
    if len(rows) != 67 or len(ids) != len(set(ids)):
        raise ValueError("canonical organization spec must produce exactly 67 unique identities")
    counts: dict[str, int] = {}
    for row in rows:
        rank = str(row["rank"])
        counts[rank] = counts.get(rank, 0) + 1
    if counts != {"central": 1, "chief": 15, "senior_specialist": 20, "specialist": 31}:
        raise ValueError(f"canonical organization rank cardinality mismatch: {counts!r}")
    return tuple(rows)
