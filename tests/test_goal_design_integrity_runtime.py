from types import SimpleNamespace

import pytest

from nolane.external_core.architecture import (
    ArchitectureComponent,
    ArchitectureGraph,
    ComponentKind,
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
from nolane.external_core.goal_design_integrity import (
    GOAL_DESIGN_PLANES,
    GoalIntegrityAttestation,
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
    verify_goal_integrity_receipt,
)
from nolane.external_core.goal_design_integrity_runtime import GoalIntegrityRuntime
from nolane.external_core.goal_design_runtime import DecisionLifecycle
from nolane.external_core.integration import ChangeCandidate, IntegrationGraph
from nolane.external_core.planning import MasterPlanGraph, PlanNode
from nolane.external_core.requirements import (
    RequirementGraph,
    RequirementKind,
    RequirementNode,
)


def _runtime():
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
                "The core design must preserve terminal intent while authority evolves.",
            ),
        ),
    )
    requirements = SimpleNamespace(graph=requirements_graph)

    planning_graph = MasterPlanGraph(requirements)
    planning_graph.apply(
        actor_agent_id="planning.chief",
        reason="seed plan",
        evidence_refs=("ev:plan",),
        upsert_nodes=(
            PlanNode(
                "plan:core",
                "Implement integrity-aware runtime",
                requirement_refs=("req:core",),
            ),
        ),
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
                "Goal integrity runtime",
                ComponentKind.MODULE,
                "architecture-system",
                "internal",
                requirement_refs=("req:core",),
                plan_refs=("plan:core",),
            ),
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
            (),
        )
    )
    integration = SimpleNamespace(graph=integration_graph, architecture=architecture)
    context = SimpleNamespace(
        max_memories=128,
        max_events=256,
        context_policy_version="policy:integrity-v1",
    )
    return GoalIntegrityRuntime(
        requirements=requirements,
        planning=planning,
        architecture=architecture,
        integration=integration,
        context=context,
    )


def _goal():
    return GoalSpec(
        "goal:runtime-integrity",
        "Preserve terminal user intent while Goal/Design authority evolves",
        objectives=(GoalObjective("quality", ObjectiveDirection.MAXIMIZE),),
    )


def _scenarios():
    return (DesignScenario("base", 1.0),)


def _options():
    return (
        DesignOption(
            "safe",
            "Integrity-preserving runtime",
            {"base": 0.9},
            {"quality": 0.9},
            DecisionClass.REVERSIBLE,
            requirement_refs=("req:core",),
            component_refs=("cmp:core",),
        ),
        DesignOption(
            "proxy",
            "Proxy-maximizing runtime",
            {"base": 0.4},
            {"quality": 0.4},
        ),
    )


def _contract(statement="Preserve explicit user intent and control."):
    return GoalIntegrityContract(
        goal_id="goal:runtime-integrity",
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                "goal:runtime-integrity",
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                statement,
                "prov:terminal",
            ),
            GoalIntegrityClause(
                "constraint:control",
                "goal:runtime-integrity",
                GoalIntegrityClauseKind.HARD_CONSTRAINT,
                "Do not remove explicit user control to improve a proxy metric.",
                "prov:control",
            ),
        ),
    )


def _attestations(contract, *, missing_plane=None):
    result = []
    for plane in GOAL_DESIGN_PLANES:
        if plane == missing_plane:
            continue
        result.append(
            GoalIntegrityAttestation(
                attestation_id=f"att:{plane}:{contract.digest[:12]}",
                goal_id=contract.goal_id,
                plane=plane,
                subject_ref=f"{plane}:authority-v1",
                contract_digest=contract.digest,
                preserved_clause_ids=tuple(clause.clause_id for clause in contract.clauses),
                evidence_refs=(f"evidence:{plane}",),
            )
        )
    return tuple(result)


def _admit(runtime, snapshot, contract):
    return runtime.admit(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_options(),
        selected_option_id="safe",
        snapshot=snapshot,
        integrity_attestations=_attestations(contract),
    )


def test_integrity_runtime_requires_installed_contract_before_decision_side_effects():
    runtime = _runtime()
    snapshot = runtime.freeze()
    ledger_events_before = runtime.ledger.events

    with pytest.raises(CoherenceError, match="integrity contract"):
        runtime.admit(
            goal=_goal(),
            scenarios=_scenarios(),
            options=_options(),
            selected_option_id="safe",
            snapshot=snapshot,
            integrity_attestations=(),
        )

    assert runtime.ledger.events == ledger_events_before
    assert runtime.decisions.records() == ()
    assert runtime.integrity_authority.records() == ()


def test_incomplete_integrity_attestation_blocks_before_decision_side_effects():
    runtime = _runtime()
    contract = _contract()
    runtime.install_integrity_contract(contract)
    snapshot = runtime.freeze()
    ledger_events_before = runtime.ledger.events

    with pytest.raises(CoherenceError, match="terminal integrity|integrity"):
        runtime.admit(
            goal=_goal(),
            scenarios=_scenarios(),
            options=_options(),
            selected_option_id="safe",
            snapshot=snapshot,
            integrity_attestations=_attestations(contract, missing_plane="integration"),
        )

    assert runtime.ledger.events == ledger_events_before
    assert runtime.decisions.records() == ()
    assert runtime.integrity_authority.records() == ()


def test_successful_admission_mints_companion_authority_without_rewriting_decision_identity():
    runtime = _runtime()
    contract = _contract()
    runtime.install_integrity_contract(contract)
    snapshot = runtime.freeze()

    admission = _admit(runtime, snapshot, contract)
    decision = admission.decision_receipt
    integrity = admission.integrity_receipt

    assert decision.receipt_id == integrity.decision_receipt_id
    assert integrity.contract_digest == contract.digest
    assert runtime.decisions.get(decision.receipt_id).lifecycle is DecisionLifecycle.ACTIVE
    assert runtime.integrity_authority.get(decision.receipt_id).lifecycle is DecisionLifecycle.ACTIVE
    assert verify_goal_integrity_receipt(integrity, decision) is None


def test_contract_install_is_idempotent_but_revision_requires_exact_predecessor():
    runtime = _runtime()
    original = _contract()
    revised = _contract("Preserve explicit user intent, control, and reversible choice.")

    assert runtime.install_integrity_contract(original) == original.digest
    assert runtime.install_integrity_contract(original) == original.digest

    with pytest.raises(CoherenceError, match="predecessor|supersed"):
        runtime.install_integrity_contract(revised)
    with pytest.raises(CoherenceError, match="predecessor|supersed"):
        runtime.install_integrity_contract(revised, supersedes_digest="wrong:digest")

    assert runtime.current_integrity_contract(original.goal_id).digest == original.digest


def test_contract_supersession_atomically_stales_old_decision_and_integrity_authority():
    runtime = _runtime()
    original = _contract()
    revised = _contract("Preserve explicit user intent, control, and reversible choice.")
    runtime.install_integrity_contract(original)
    snapshot = runtime.freeze()
    admission = _admit(runtime, snapshot, original)

    runtime.install_integrity_contract(revised, supersedes_digest=original.digest)

    decision_id = admission.decision_receipt.receipt_id
    decision_record = runtime.decisions.get(decision_id)
    integrity_record = runtime.integrity_authority.get(decision_id)
    assert decision_record.lifecycle is DecisionLifecycle.STALE
    assert integrity_record.lifecycle is DecisionLifecycle.STALE
    assert any("integrity contract" in reason for reason in decision_record.invalidation_reasons)
    assert integrity_record.contract_digest == original.digest
    assert runtime.current_integrity_contract(original.goal_id).digest == revised.digest


def test_old_attestations_cannot_launder_authority_after_contract_supersession():
    runtime = _runtime()
    original = _contract()
    revised = _contract("Preserve explicit user intent, control, and reversible choice.")
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(revised, supersedes_digest=original.digest)
    snapshot = runtime.freeze()
    ledger_events_before = runtime.ledger.events

    with pytest.raises(CoherenceError, match="integrity"):
        runtime.admit(
            goal=_goal(),
            scenarios=_scenarios(),
            options=_options(),
            selected_option_id="safe",
            snapshot=snapshot,
            integrity_attestations=_attestations(original),
        )

    assert runtime.ledger.events == ledger_events_before
    assert runtime.decisions.records() == ()


def test_fresh_attestations_under_superseding_contract_authorize_new_decision():
    runtime = _runtime()
    original = _contract()
    revised = _contract("Preserve explicit user intent, control, and reversible choice.")
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(revised, supersedes_digest=original.digest)
    snapshot = runtime.freeze()

    admission = _admit(runtime, snapshot, revised)

    record = runtime.integrity_authority.get(admission.decision_receipt.receipt_id)
    assert record.lifecycle is DecisionLifecycle.ACTIVE
    assert record.contract_digest == revised.digest


def test_base_authority_drift_also_stales_companion_integrity_authority():
    runtime = _runtime()
    contract = _contract()
    runtime.install_integrity_contract(contract)
    snapshot = runtime.freeze()
    admission = _admit(runtime, snapshot, contract)

    runtime.requirements.graph.apply(
        actor_agent_id="requirements.chief",
        reason="refine requirement",
        evidence_refs=("ev:req:2",),
        upserts=(
            RequirementNode(
                "req:core",
                "Stable core",
                RequirementKind.QUALITY,
                "The core design must preserve terminal intent after authority drift.",
            ),
        ),
    )

    stale = runtime.revalidate_decisions()
    decision_id = admission.decision_receipt.receipt_id
    assert stale == (decision_id,)
    assert runtime.decisions.get(decision_id).lifecycle is DecisionLifecycle.STALE
    assert runtime.integrity_authority.get(decision_id).lifecycle is DecisionLifecycle.STALE


def test_integrity_runtime_state_is_canonical_and_round_trips_contract_and_authority():
    runtime = _runtime()
    contract = _contract()
    runtime.install_integrity_contract(contract)
    snapshot = runtime.freeze()
    admission = _admit(runtime, snapshot, contract)

    state = runtime.integrity_state()
    restored = _runtime()
    restored.restore_integrity_state(state)

    assert restored.integrity_state() == state
    assert restored.current_integrity_contract(contract.goal_id) == contract
    restored_record = restored.integrity_authority.get(admission.decision_receipt.receipt_id)
    assert restored_record.integrity_receipt == admission.integrity_receipt
    assert restored.integrity_digest == runtime.integrity_digest
