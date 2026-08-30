from types import SimpleNamespace

import pytest

from nolane.external_core.architecture import (
    ArchitectureComponent,
    ArchitectureEdge,
    ArchitectureGraph,
    ComponentKind,
    EdgeKind,
    InterfaceClass,
    InterfaceContract,
    InterfaceStability,
)
from nolane.external_core.goal_design import (
    CoherenceError,
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalObjective,
    GoalSpec,
    ObjectiveDirection,
)
from nolane.external_core.goal_design_runtime import (
    DecisionLifecycle,
    GoalDesignChangeSet,
    GoalDesignRuntime,
)
from nolane.external_core.integration import ChangeCandidate, IntegrationGraph
from nolane.external_core.planning import MasterPlanGraph, PlanNode
from nolane.external_core.requirements import (
    AcceptanceCriterion,
    RequirementGraph,
    RequirementKind,
    RequirementNode,
)


def _system():
    requirements_graph = RequirementGraph()
    requirements_graph.apply(
        actor_agent_id="requirements.chief",
        reason="seed requirement",
        evidence_refs=("ev:req",),
        upserts=(
            RequirementNode(
                "req:core",
                "Stable core",
                RequirementKind.QUALITY,
                "The core design must remain coherent across authority planes.",
                acceptance_criteria=(
                    AcceptanceCriterion(
                        "ac:core",
                        "Cross-plane design state is traceable",
                        evidence_expectations=("proof:traceability",),
                    ),
                ),
            ),
        ),
    )
    requirements = SimpleNamespace(graph=requirements_graph)

    planning_graph = MasterPlanGraph(requirements)
    planning_graph.apply(
        actor_agent_id="planning.chief",
        reason="seed plan",
        evidence_refs=("ev:plan",),
        upsert_nodes=(PlanNode("plan:core", "Implement coherent core", requirement_refs=("req:core",)),),
    )
    planning = SimpleNamespace(graph=planning_graph)

    architecture_graph = ArchitectureGraph()
    architecture_graph.apply(
        actor_agent_id="architecture.chief",
        reason="seed architecture",
        evidence_refs=("ev:arch",),
        upsert_components=(
            ArchitectureComponent(
                "cmp:core",
                "Goal design core",
                ComponentKind.MODULE,
                "architecture-system",
                "internal",
                requirement_refs=("req:core",),
                plan_refs=("plan:core",),
            ),
            ArchitectureComponent(
                "cmp:consumer",
                "Downstream consumer",
                ComponentKind.MODULE,
                "core-coding",
                "internal",
            ),
        ),
        upsert_interfaces=(
            InterfaceContract(
                "if:core",
                "cmp:core",
                InterfaceClass.API,
                "1.0.0",
                "sig:core:v1",
                InterfaceStability.INTERNAL,
                consumer_scope=("cmp:consumer",),
            ),
        ),
        upsert_edges=(
            ArchitectureEdge("edge:consumer-core", "cmp:consumer", "cmp:core", EdgeKind.DEPENDS_ON),
        ),
    )
    architecture = SimpleNamespace(graph=architecture_graph)

    integration_graph = IntegrationGraph()
    integration_graph.add(
        ChangeCandidate(
            "cand:core",
            "coding.chief",
            ("task:core",),
            ("plan:core",),
            ("req:core",),
            architecture_graph.version,
            ("cmp:core",),
            ("if:core",),
        )
    )
    integration_graph.add(
        ChangeCandidate(
            "cand:deploy",
            "integration.chief",
            ("task:deploy",),
            (),
            (),
            architecture_graph.version,
            ("cmp:consumer",),
            (),
            dependency_candidate_ids=("cand:core",),
        )
    )
    integration = SimpleNamespace(graph=integration_graph, architecture=architecture)

    context = SimpleNamespace(
        max_memories=128,
        max_events=256,
        context_policy_version="policy:v2",
    )
    return requirements, planning, architecture, integration, context


def _runtime():
    requirements, planning, architecture, integration, context = _system()
    return GoalDesignRuntime(
        requirements=requirements,
        planning=planning,
        architecture=architecture,
        integration=integration,
        context=context,
    )


def _goal():
    return GoalSpec(
        "goal:runtime",
        "Keep live Goal/Design authority coherent while the repository evolves",
        objectives=(
            GoalObjective("quality", ObjectiveDirection.MAXIMIZE),
            GoalObjective("risk", ObjectiveDirection.MINIMIZE),
        ),
    )


def _scenarios():
    return (
        DesignScenario("base", 0.8, tags=("baseline",)),
        DesignScenario("break", 0.2, tags=("counterfactual", "adversarial")),
    )


def _options():
    return (
        DesignOption(
            "federated",
            "Federated runtime",
            {"base": 0.88, "break": 0.72},
            {"quality": 0.9, "risk": 0.12},
            DecisionClass.REVERSIBLE,
            requirement_refs=("req:core",),
            component_refs=("cmp:core",),
        ),
        DesignOption(
            "legacy",
            "Legacy runtime",
            {"base": 0.60, "break": 0.40},
            {"quality": 0.6, "risk": 0.35},
        ),
    )


def test_live_observation_derives_all_five_plane_tokens_from_real_state():
    runtime = _runtime()
    bundle = runtime.observe()
    tokens = bundle.version_vector.tokens()
    assert tokens["requirements"].startswith("v1@")
    assert tokens["planning"].startswith("v1@")
    assert tokens["architecture"].startswith("v1@")
    assert tokens["integration"].startswith("v2@")
    assert tokens["context"].startswith("policy:v2@")
    assert bundle.requirements.active_requirement_ids == ("req:core",)
    assert "proof:traceability" in bundle.requirements.acceptance_proof_refs
    assert bundle.architecture.component_ids == ("cmp:consumer", "cmp:core")


def test_observation_is_stable_when_only_transient_context_attributes_change():
    runtime = _runtime()
    before = runtime.observe().context.state.token
    runtime.context.transient_memory_count = 9999
    runtime.context.last_event_id = "event:volatile"
    after = runtime.observe().context.state.token
    assert before == after


def test_requirement_change_impact_propagates_through_plan_architecture_interfaces_and_integration():
    runtime = _runtime()
    report = runtime.analyze_change(GoalDesignChangeSet(requirement_refs=("req:core",)))
    assert report.affected_plan_refs == ("plan:core",)
    assert set(report.affected_component_refs) == {"cmp:core", "cmp:consumer"}
    assert report.affected_interface_refs == ("if:core",)
    assert set(report.affected_candidate_refs) == {"cand:core", "cand:deploy"}
    assert report.context_invalidated
    assert report.digest


def test_architecture_dependency_propagates_from_dependency_to_consumer():
    runtime = _runtime()
    report = runtime.analyze_change(GoalDesignChangeSet(architecture_refs=("cmp:core",)))
    assert set(report.affected_component_refs) == {"cmp:core", "cmp:consumer"}
    assert "cand:deploy" in report.affected_candidate_refs


def test_runtime_admission_records_snapshot_decision_and_dependency_index():
    runtime = _runtime()
    snapshot = runtime.freeze()
    receipt = runtime.admit(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_options(),
        selected_option_id="federated",
        snapshot=snapshot,
    )
    record = runtime.decisions.get(receipt.receipt_id)
    assert record.lifecycle is DecisionLifecycle.ACTIVE
    assert set(record.dependency_refs) == {"req:core", "cmp:core"}
    assert record.snapshot_digest == snapshot.digest
    assert len(runtime.ledger.events) == 2
    assert runtime.ledger.events[-1].parent_ids == (runtime.ledger.events[0].event_id,)


def test_change_impact_invalidates_authorized_decision_by_dependency():
    runtime = _runtime()
    snapshot = runtime.freeze()
    receipt = runtime.admit(
        goal=_goal(), scenarios=_scenarios(), options=_options(), selected_option_id="federated", snapshot=snapshot
    )
    report = runtime.analyze_change(GoalDesignChangeSet(requirement_refs=("req:core",)))
    invalidated = runtime.invalidate_impacted_decisions(report)
    assert invalidated == (receipt.receipt_id,)
    record = runtime.decisions.get(receipt.receipt_id)
    assert record.lifecycle is DecisionLifecycle.STALE
    assert record.invalidation_reasons


def test_live_state_revision_invalidates_old_decision_even_without_explicit_change_set():
    runtime = _runtime()
    snapshot = runtime.freeze()
    receipt = runtime.admit(
        goal=_goal(), scenarios=_scenarios(), options=_options(), selected_option_id="federated", snapshot=snapshot
    )
    runtime.requirements.graph.apply(
        actor_agent_id="requirements.chief",
        reason="refine requirement",
        evidence_refs=("ev:req:2",),
        upserts=(
            RequirementNode(
                "req:core",
                "Stable core",
                RequirementKind.QUALITY,
                "The core design must remain coherent and revalidated after authority drift.",
            ),
        ),
    )
    stale = runtime.revalidate_decisions()
    assert stale == (receipt.receipt_id,)
    assert runtime.decisions.get(receipt.receipt_id).lifecycle is DecisionLifecycle.STALE


def test_integration_guard_binds_candidate_to_exact_goal_design_snapshot():
    runtime = _runtime()
    snapshot = runtime.freeze()
    guard = runtime.guard_integration("cand:core", snapshot=snapshot)
    assert guard.candidate_id == "cand:core"
    assert guard.snapshot_digest == snapshot.digest
    assert guard.digest

    runtime.architecture.graph.apply(
        actor_agent_id="architecture.chief",
        reason="new architecture revision",
        evidence_refs=("ev:arch:2",),
        upsert_components=(
            ArchitectureComponent(
                "cmp:core",
                "Goal design core v2",
                ComponentKind.MODULE,
                "architecture-system",
                "internal",
                requirement_refs=("req:core",),
                plan_refs=("plan:core",),
            ),
        ),
    )
    with pytest.raises(CoherenceError, match="stale|architecture"):
        runtime.guard_integration("cand:core", snapshot=snapshot)


def test_context_binding_rejects_capsule_with_stale_authoritative_artifacts():
    runtime = _runtime()
    snapshot = runtime.freeze()
    fresh = SimpleNamespace(
        authoritative_artifacts=(
            ("master-plan", 1),
            ("requirements", 1),
            ("architecture-graph", 1),
            ("integration-state", 2),
        )
    )
    bound = runtime.bind_context(fresh, snapshot=snapshot)
    assert bound.snapshot_digest == snapshot.digest
    assert bound.digest

    stale = SimpleNamespace(
        authoritative_artifacts=(
            ("master-plan", 1),
            ("requirements", 0),
            ("architecture-graph", 1),
            ("integration-state", 2),
        )
    )
    with pytest.raises(CoherenceError, match="context|requirements"):
        runtime.bind_context(stale, snapshot=snapshot)
