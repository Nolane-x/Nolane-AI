from types import SimpleNamespace

from nolane.external_core.architecture import ArchitectureComponent, ArchitectureGraph, ComponentKind
from nolane.external_core.goal_design import (
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalObjective,
    GoalSpec,
    ObjectiveDirection,
    ProofObligation,
    ProofStatus,
    UncertaintyItem,
)
from nolane.external_core.goal_design_context import DecisionContextPolicy
from nolane.external_core.goal_design_integrity import (
    GOAL_DESIGN_PLANES,
    GoalIntegrityAttestation,
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
)
from nolane.external_core.goal_design_integrity_runtime import GoalIntegrityRuntime
from nolane.external_core.integration import ChangeCandidate, IntegrationGraph
from nolane.external_core.planning import MasterPlanGraph, PlanNode
from nolane.external_core.requirements import RequirementGraph, RequirementKind, RequirementNode


def _runtime(*, decision_context_policy=None):
    requirements_graph = RequirementGraph()
    requirements_graph.apply(
        actor_agent_id="requirements.chief",
        reason="seed decision-context requirement",
        evidence_refs=("ev:req",),
        upserts=(
            RequirementNode(
                "req:context",
                "Proof-carrying context",
                RequirementKind.QUALITY,
                "Decision context must preserve exact Goal/Design authority semantics.",
            ),
        ),
    )
    requirements = SimpleNamespace(graph=requirements_graph)

    planning_graph = MasterPlanGraph(requirements)
    planning_graph.apply(
        actor_agent_id="planning.chief",
        reason="seed decision-context plan",
        evidence_refs=("ev:plan",),
        upsert_nodes=(
            PlanNode(
                "plan:context",
                "Compile proof-carrying decision context",
                requirement_refs=("req:context",),
            ),
        ),
    )
    planning = SimpleNamespace(graph=planning_graph)

    architecture_graph = ArchitectureGraph()
    architecture_graph.apply(
        actor_agent_id="architecture.chief",
        reason="seed decision-context architecture",
        evidence_refs=("ev:arch",),
        upsert_components=(
            ArchitectureComponent(
                "cmp:context",
                "GoalDesign decision context compiler",
                ComponentKind.MODULE,
                "architecture-system",
                "internal",
                requirement_refs=("req:context",),
                plan_refs=("plan:context",),
            ),
        ),
    )
    architecture = SimpleNamespace(graph=architecture_graph)

    integration_graph = IntegrationGraph()
    integration_graph.add(
        ChangeCandidate(
            "cand:context",
            "integration.chief",
            ("task:context",),
            ("plan:context",),
            ("req:context",),
            architecture_graph.version,
            ("cmp:context",),
            (),
        )
    )
    integration = SimpleNamespace(graph=integration_graph, architecture=architecture)
    context = SimpleNamespace(
        max_memories=128,
        max_events=256,
        context_policy_version="policy:decision-context-v1",
    )
    kwargs = {}
    if decision_context_policy is not None:
        kwargs["decision_context_policy"] = decision_context_policy
    return GoalIntegrityRuntime(
        requirements=requirements,
        planning=planning,
        architecture=architecture,
        integration=integration,
        context=context,
        **kwargs,
    )


def _goal():
    return GoalSpec(
        "goal:decision-context",
        "Preserve explicit user intent while compiling decision context",
        objectives=(GoalObjective("quality", ObjectiveDirection.MAXIMIZE),),
        constraints=("Never replace terminal intent with a proxy metric.",),
        non_goals=("Do not infer hidden goals from context prose.",),
        evidence_refs=("evidence:goal",),
    )


def _scenarios():
    return (DesignScenario("base", 1.0, evidence_refs=("evidence:scenario",)),)


def _options():
    return (
        DesignOption(
            "champion",
            "Integrity-preserving context",
            {"base": 0.9},
            {"quality": 0.9},
            DecisionClass.REVERSIBLE,
            evidence_refs=("evidence:champion",),
            requirement_refs=("req:context",),
            component_refs=("cmp:context",),
        ),
        DesignOption(
            "rival",
            "Context without semantic pins",
            {"base": 0.4},
            {"quality": 0.4},
            DecisionClass.REVERSIBLE,
            evidence_refs=("evidence:rival",),
        ),
    )


def _contract():
    goal_id = "goal:decision-context"
    return GoalIntegrityContract(
        goal_id=goal_id,
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                goal_id,
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                "Preserve explicit user intent.",
                "prov:terminal",
            ),
            GoalIntegrityClause(
                "constraint:no-proxy",
                goal_id,
                GoalIntegrityClauseKind.HARD_CONSTRAINT,
                "Never replace terminal intent with a proxy metric.",
                "prov:constraint",
            ),
            GoalIntegrityClause(
                "antigoal:inference",
                goal_id,
                GoalIntegrityClauseKind.ANTI_GOAL,
                "Do not invent hidden goals from context prose.",
                "prov:antigoal",
            ),
            GoalIntegrityClause(
                "criterion:traceable",
                goal_id,
                GoalIntegrityClauseKind.SUCCESS_CRITERION,
                "Every semantic pin retains exact authority provenance.",
                "prov:criterion",
            ),
        ),
    )


def _attestations(contract):
    clause_ids = tuple(clause.clause_id for clause in contract.clauses)
    return tuple(
        GoalIntegrityAttestation(
            attestation_id=f"att:{plane}:{contract.digest[:12]}",
            goal_id=contract.goal_id,
            plane=plane,
            subject_ref=f"{plane}:authority",
            contract_digest=contract.digest,
            preserved_clause_ids=clause_ids,
            evidence_refs=(f"evidence:{plane}",),
        )
        for plane in GOAL_DESIGN_PLANES
    )


def _proofs():
    return (
        ProofObligation(
            "proof:context-replay",
            "Decision context remains reproducible after restart.",
            status=ProofStatus.OPEN,
            evidence_refs=("evidence:proof-plan",),
            blocking=False,
        ),
    )


def _uncertainties():
    return (
        UncertaintyItem(
            "unknown:downstream-drift",
            "A downstream consumer may silently drop semantic pins.",
            uncertainty=0.9,
            impact=0.9,
            decision_sensitivity=0.9,
            observability=0.5,
            evidence_refs=("evidence:downstream-drift",),
        ),
    )


def _admitted_runtime(*, decision_context_policy=None):
    runtime = _runtime(decision_context_policy=decision_context_policy)
    contract = _contract()
    runtime.install_integrity_contract(contract)
    goal = _goal()
    scenarios = _scenarios()
    options = _options()
    proofs = _proofs()
    uncertainties = _uncertainties()
    admission = runtime.admit(
        goal=goal,
        scenarios=scenarios,
        options=options,
        selected_option_id="champion",
        snapshot=runtime.freeze(),
        proof_obligations=proofs,
        uncertainties=uncertainties,
        integrity_attestations=_attestations(contract),
    )
    return runtime, admission, goal, scenarios, options, proofs, uncertainties


def _compile(runtime, admission, goal, scenarios, options, proofs, uncertainties):
    return runtime.compile_decision_context(
        receipt_id=admission.decision_receipt.receipt_id,
        goal=goal,
        scenarios=scenarios,
        options=options,
        proof_obligations=proofs,
        uncertainties=uncertainties,
    )


def test_integrity_runtime_compiles_exact_semantic_decision_context():
    runtime, admission, goal, scenarios, options, proofs, uncertainties = _admitted_runtime()
    context = _compile(runtime, admission, goal, scenarios, options, proofs, uncertainties)

    kinds = {pin.kind.value for pin in context.pins}
    assert {
        "terminal_goal",
        "hard_constraint",
        "anti_goal",
        "success_criterion",
        "champion",
        "rival",
        "open_proof",
        "critical_unknown",
    } <= kinds
    assert context.decision_receipt_id == admission.decision_receipt.receipt_id
    assert context.integrity_receipt_id == admission.integrity_receipt.receipt_id
    assert context.integrity_contract_digest == _contract().digest
    assert context.context_id


def test_runtime_owned_context_policy_controls_critical_unknown_selection():
    strict_policy = DecisionContextPolicy(critical_uncertainty_threshold=0.99)
    runtime, admission, goal, scenarios, options, proofs, uncertainties = _admitted_runtime(
        decision_context_policy=strict_policy
    )

    context = _compile(runtime, admission, goal, scenarios, options, proofs, uncertainties)

    assert context.policy_digest == strict_policy.digest
    assert "critical_unknown" not in {pin.kind.value for pin in context.pins}
