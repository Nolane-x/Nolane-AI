from __future__ import annotations

from dataclasses import dataclass

from .types import AgentIdentity, AgentRank, ParameterAccounting


UNIVERSAL_COGNITIVE_CAPABILITIES = (
    'goal_understanding',
    'task_decomposition',
    'local_planning',
    'causal_reasoning',
    'memory_use',
    'tool_use',
    'uncertainty',
    'evidence_handling',
    'communication',
    'self_evaluation',
    'skill_induction',
    'learning_from_feedback',
)

GENERAL_TOOLS = (
    'filesystem',
    'git',
    'terminal',
    'code-search',
    'memory',
    'task-graph',
    'event-ledger',
    'evidence-store',
)

CENTRAL_TOOLS = GENERAL_TOOLS + (
    'browser',
    'lsp',
    'ast',
    'compiler',
    'test-runner',
    'plan-graph',
    'architecture-graph',
    'repo-graph',
    'knowledge-graph',
    'browser-automation',
    'runtime-observation',
    'research',
    'agent-control',
    'resource-control',
)

SHARED_CORE_PARAMETERS = 56_000_000
CENTRAL_PARAMETERS = ParameterAccounting(SHARED_CORE_PARAMETERS, 40_000_000)
CHIEF_PARAMETERS = ParameterAccounting(SHARED_CORE_PARAMETERS, 34_000_000)
SENIOR_PARAMETERS = ParameterAccounting(SHARED_CORE_PARAMETERS, 20_000_000)
SPECIALIST_PARAMETERS = ParameterAccounting(SHARED_CORE_PARAMETERS, 8_000_000)


@dataclass(frozen=True, slots=True)
class _RoleSpec:
    agent_id: str
    name: str
    role: str
    senior: bool = False


@dataclass(frozen=True, slots=True)
class _RegionSpec:
    region: str
    chief_id: str
    chief_name: str
    chief_role: str
    external_cores: tuple[str, ...]
    specialists: tuple[_RoleSpec, ...]


REGIONS = (
    _RegionSpec(
        'requirements-product', 'requirements.chief', 'Requirements Chief', 'Requirements / Product Intelligence Chief',
        ('requirements-graph', 'acceptance-criteria-engine', 'constraint-ledger'),
        (
            _RoleSpec('requirements.analysis.01', 'Requirement Analyst', 'requirement analysis', True),
            _RoleSpec('requirements.acceptance.01', 'Acceptance & Constraint Agent', 'acceptance and constraint reasoning'),
        ),
    ),
    _RegionSpec(
        'planning-program', 'planning.chief', 'Planning Chief', 'Planning / Program Intelligence Chief',
        ('task-dag', 'critical-path-engine', 'risk-graph', 'progress-reconciler'),
        (
            _RoleSpec('planning.task-graph.01', 'Task Graph Planner', 'task decomposition and dependency planning', True),
            _RoleSpec('planning.milestone.01', 'Milestone Planner', 'strategic milestone planning'),
            _RoleSpec('planning.dependency-risk.01', 'Dependency & Risk Planner', 'dependency and risk analysis'),
            _RoleSpec('planning.audit.01', 'Plan Auditor', 'plan drift reconciliation'),
        ),
    ),
    _RegionSpec(
        'architecture-system', 'architecture.chief', 'Architecture Chief', 'Architecture / System Design Chief',
        ('architecture-graph', 'interface-contract-engine', 'change-impact-graph', 'adr-ledger'),
        (
            _RoleSpec('architecture.component.01', 'Component Architect', 'component architecture', True),
            _RoleSpec('architecture.api-interface.01', 'API & Interface Architect', 'interface and API architecture'),
            _RoleSpec('architecture.change-impact.01', 'Change Impact Architect', 'architectural impact reasoning'),
            _RoleSpec('architecture.system-boundary.01', 'System Boundary Architect', 'system boundary design'),
        ),
    ),
    _RegionSpec(
        'core-coding', 'coding.chief', 'Coding Chief', 'Core Coding Chief',
        ('lsp', 'ast', 'symbol-graph', 'compiler', 'patch-engine', 'worktree-manager', 'test-selection'),
        (
            _RoleSpec('coding.core-algorithm.01', 'Core Algorithm Coder', 'core algorithm implementation', True),
            _RoleSpec('coding.backend.01', 'Backend Coder', 'backend and service implementation', True),
            _RoleSpec('coding.systems.01', 'Systems Coder', 'systems and low-level implementation', True),
            _RoleSpec('coding.refactor.01', 'Refactoring Coder', 'large-scale refactoring'),
            _RoleSpec('coding.api-interface.01', 'API Coder', 'API and interface implementation'),
            _RoleSpec('coding.build-dependency.01', 'Build & Dependency Coder', 'build and dependency engineering'),
        ),
    ),
    _RegionSpec(
        'frontend-ui', 'frontend.chief', 'Frontend UI Chief', 'Frontend / UI Engineering Chief',
        ('browser-runtime', 'dom-tree', 'cssom', 'playwright', 'visual-diff'),
        (
            _RoleSpec('frontend.logic.01', 'Frontend Logic Coder', 'frontend state and application logic', True),
            _RoleSpec('frontend.component.01', 'Component Engineer', 'component implementation'),
            _RoleSpec('frontend.browser-runtime.01', 'Browser Runtime Engineer', 'browser runtime diagnosis'),
        ),
    ),
    _RegionSpec(
        'ux-product-design', 'ux.chief', 'UX Chief', 'UX / Product Design Chief',
        ('interaction-model', 'design-token-graph', 'accessibility-tree'),
        (
            _RoleSpec('ux.flow.01', 'UX Flow Architect', 'interaction and information flow', True),
            _RoleSpec('ux.visual-accessibility.01', 'Visual & Accessibility Designer', 'visual and accessibility design'),
        ),
    ),
    _RegionSpec(
        'debugging-failure', 'debug.chief', 'Debug Chief', 'Debugging / Failure Intelligence Chief',
        ('runtime-tracer', 'stack-graph', 'coverage-graph', 'state-diff', 'crash-analyzer', 'git-bisect', 'failure-minimizer'),
        (
            _RoleSpec('debug.reproducer.01', 'Bug Reproducer', 'minimal failure reproduction', True),
            _RoleSpec('debug.runtime-trace.01', 'Runtime Trace Investigator', 'runtime tracing and state diagnosis', True),
            _RoleSpec('debug.static-root-cause.01', 'Static Root-Cause Investigator', 'static defect and root-cause reasoning'),
            _RoleSpec('debug.concurrency-state.01', 'Concurrency & State Debugger', 'race, deadlock and state diagnosis', True),
            _RoleSpec('debug.regression-bisect.01', 'Regression & Bisect Agent', 'regression localization and historical causality'),
        ),
    ),
    _RegionSpec(
        'verification-testing', 'verification.chief', 'Verification Chief', 'Verification / Testing Chief',
        ('fresh-sandbox', 'property-testing', 'fuzzer', 'integration-runner', 'acceptance-harness'),
        (
            _RoleSpec('verification.unit-property.01', 'Unit & Property Verifier', 'unit and property verification', True),
            _RoleSpec('verification.integration-e2e.01', 'Integration & E2E Verifier', 'integration and end-to-end verification', True),
            _RoleSpec('verification.spec-acceptance.01', 'Specification Acceptance Verifier', 'specification and acceptance verification'),
            _RoleSpec('verification.fuzz-regression.01', 'Fuzz & Regression Verifier', 'fuzzing and regression verification'),
        ),
    ),
    _RegionSpec(
        'security-adversarial', 'security.chief', 'Security Chief', 'Security / Adversarial Engineering Chief',
        ('threat-model', 'security-scanner', 'attack-harness', 'supply-chain-auditor'),
        (
            _RoleSpec('security.threat-model.01', 'Threat Model Agent', 'threat modeling', True),
            _RoleSpec('security.supply-chain.01', 'Supply Chain Security Agent', 'dependency and supply-chain security'),
            _RoleSpec('security.adversarial.01', 'Adversarial Security Agent', 'adversarial security validation'),
        ),
    ),
    _RegionSpec(
        'data-storage-migration', 'data.chief', 'Data Chief', 'Data / Storage / Migration Chief',
        ('schema-graph', 'migration-planner', 'consistency-checker', 'storage-profiler'),
        (
            _RoleSpec('data.schema-migration.01', 'Schema & Migration Agent', 'schema and migration engineering', True),
            _RoleSpec('data.persistence.01', 'Persistence Agent', 'storage and persistence implementation'),
            _RoleSpec('data.cache-consistency.01', 'Cache & Consistency Agent', 'cache and consistency reasoning'),
        ),
    ),
    _RegionSpec(
        'infrastructure-release', 'infrastructure.chief', 'Infrastructure Chief', 'Infrastructure / DevOps / Release Chief',
        ('ci-engine', 'container-runtime', 'deployment-controller', 'observability-stack', 'release-packager'),
        (
            _RoleSpec('infrastructure.ci-env.01', 'CI & Environment Agent', 'CI and environment engineering', True),
            _RoleSpec('infrastructure.deployment.01', 'Deployment Agent', 'deployment engineering'),
            _RoleSpec('infrastructure.observability-release.01', 'Observability & Release Agent', 'observability and release packaging'),
        ),
    ),
    _RegionSpec(
        'performance-reliability', 'reliability.chief', 'Reliability Chief', 'Performance / Reliability Chief',
        ('cpu-profiler', 'memory-profiler', 'race-detector', 'recovery-simulator', 'resilience-harness'),
        (
            _RoleSpec('reliability.performance.01', 'Performance Agent', 'performance diagnosis and optimization', True),
            _RoleSpec('reliability.concurrency.01', 'Reliability Concurrency Agent', 'concurrency reliability'),
            _RoleSpec('reliability.recovery.01', 'Recovery Agent', 'failure recovery and graceful degradation'),
        ),
    ),
    _RegionSpec(
        'research-external', 'research.chief', 'Research Chief', 'Research / External Intelligence Chief',
        ('web-retrieval', 'github-research', 'docs-index', 'paper-index', 'package-registry', 'provenance-store'),
        (
            _RoleSpec('research.repo-archaeology.01', 'Repository Archaeologist', 'repository history and convention research', True),
            _RoleSpec('research.docs-api.01', 'Docs & API Researcher', 'external documentation and API research'),
            _RoleSpec('research.prior-art.01', 'Algorithm & Prior-Art Researcher', 'algorithms, papers and prior art'),
        ),
    ),
    _RegionSpec(
        'integration-change-control', 'integration.chief', 'Integration Chief', 'Integration / Change Control Chief',
        ('merge-graph', 'compatibility-matrix', 'change-control-ledger', 'integration-sandbox'),
        (
            _RoleSpec('integration.merge.01', 'Merge Integration Agent', 'merge sequencing and conflict resolution', True),
            _RoleSpec('integration.compatibility.01', 'Compatibility Agent', 'cross-system compatibility validation'),
            _RoleSpec('integration.change-control.01', 'Change Control Agent', 'change authorization and propagation'),
        ),
    ),
    _RegionSpec(
        'memory-context-knowledge', 'memory.chief', 'Memory & Context Chief', 'Memory / Context / Knowledge Chief',
        ('vector-retrieval', 'knowledge-graph', 'temporal-memory', 'skill-store', 'context-compiler', 'semantic-diff'),
        (
            _RoleSpec('memory.context-compiler.01', 'Context Compiler Agent', 'context compilation and semantic delta', True),
            _RoleSpec('memory.knowledge-graph.01', 'Knowledge Graph Agent', 'structured organizational knowledge'),
            _RoleSpec('memory.lifecycle.01', 'Memory Lifecycle Agent', 'memory consolidation, forgetting and promotion'),
        ),
    ),
)


def _identity(
    *,
    agent_id: str,
    name: str,
    region: str,
    role: str,
    rank: AgentRank,
    chief_id: str | None,
    external_cores: tuple[str, ...],
    parameter_accounting: ParameterAccounting,
    tools: tuple[str, ...],
) -> AgentIdentity:
    return AgentIdentity(
        agent_id=agent_id,
        name=name,
        region=region,
        role=role,
        rank=rank,
        neural_version=f'NUC-0.1+{agent_id}-delta-0.1',
        parameter_accounting=parameter_accounting,
        region_chief_id=chief_id,
        direct_work_capable=True,
        learning_capable=True,
        cognitive_capabilities=UNIVERSAL_COGNITIVE_CAPABILITIES,
        memory_namespace=f'agent/{agent_id}',
        skill_namespace=f'skills/personal/{agent_id}',
        external_core_bindings=external_cores,
        tool_permissions=tools,
    )


def build_first_generation_blueprint() -> tuple[AgentIdentity, ...]:
    rows: list[AgentIdentity] = [
        _identity(
            agent_id='nolane.central',
            name='Nolane Central',
            region='global-command',
            role='Global Coding AGI Coordinator and Direct Worker',
            rank=AgentRank.CENTRAL,
            chief_id=None,
            external_cores=('global-project-graph', 'resource-arbiter', 'direct-intervention-channel'),
            parameter_accounting=CENTRAL_PARAMETERS,
            tools=CENTRAL_TOOLS,
        )
    ]
    for region in REGIONS:
        rows.append(
            _identity(
                agent_id=region.chief_id,
                name=region.chief_name,
                region=region.region,
                role=region.chief_role,
                rank=AgentRank.CHIEF,
                chief_id=region.chief_id,
                external_cores=region.external_cores,
                parameter_accounting=CHIEF_PARAMETERS,
                tools=GENERAL_TOOLS + region.external_cores,
            )
        )
        for spec in region.specialists:
            rows.append(
                _identity(
                    agent_id=spec.agent_id,
                    name=spec.name,
                    region=region.region,
                    role=spec.role,
                    rank=AgentRank.SENIOR_SPECIALIST if spec.senior else AgentRank.SPECIALIST,
                    chief_id=region.chief_id,
                    external_cores=region.external_cores,
                    parameter_accounting=SENIOR_PARAMETERS if spec.senior else SPECIALIST_PARAMETERS,
                    tools=GENERAL_TOOLS + region.external_cores,
                )
            )
    result = tuple(rows)
    validate_blueprint(result)
    return result


def validate_blueprint(identities: tuple[AgentIdentity, ...]) -> None:
    if len(identities) != 67:
        raise ValueError(f'first-generation blueprint must contain exactly 67 identities, got {len(identities)}')
    ids = [row.agent_id for row in identities]
    if len(ids) != len(set(ids)):
        raise ValueError('blueprint contains duplicate agent ids')
    centrals = [row for row in identities if row.rank is AgentRank.CENTRAL]
    chiefs = [row for row in identities if row.rank is AgentRank.CHIEF]
    specialists = [row for row in identities if row.rank in (AgentRank.SENIOR_SPECIALIST, AgentRank.SPECIALIST)]
    if len(centrals) != 1 or centrals[0].agent_id != 'nolane.central':
        raise ValueError('blueprint requires exactly one Nolane Central')
    if len(chiefs) != 15:
        raise ValueError('blueprint requires exactly 15 Regional Chiefs')
    if len(specialists) != 51:
        raise ValueError('blueprint requires exactly 51 permanent specialists')
    regions = {row.region for row in identities if row.rank is not AgentRank.CENTRAL}
    if len(regions) != 15:
        raise ValueError('blueprint requires exactly 15 non-Central regions')
    chief_by_region = {row.region: row.agent_id for row in chiefs}
    for row in identities:
        if row.parameter_accounting.total_physical_parameters >= 100_000_000:
            raise ValueError(f'{row.agent_id} violates the first-generation parameter ceiling')
        if not row.learning_capable:
            raise ValueError(f'{row.agent_id} must remain learning capable')
        if row.rank is AgentRank.CENTRAL:
            if not 90_000_000 <= row.parameter_accounting.total_physical_parameters <= 98_000_000:
                raise ValueError('Central parameter budget is outside the approved initial band')
            continue
        expected_chief = chief_by_region.get(row.region)
        if expected_chief is None or row.region_chief_id != expected_chief:
            raise ValueError(f'{row.agent_id} has invalid regional authority linkage')
        if row.rank is AgentRank.CHIEF:
            if not row.direct_work_capable:
                raise ValueError(f'{row.agent_id} Chief cannot be a pure dispatcher')
            if not 82_000_000 <= row.parameter_accounting.total_physical_parameters <= 94_000_000:
                raise ValueError(f'{row.agent_id} Chief parameter budget is outside the approved band')
