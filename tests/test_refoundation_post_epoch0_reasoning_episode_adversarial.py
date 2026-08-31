from __future__ import annotations

import importlib
import inspect
from copy import deepcopy
from dataclasses import replace

import pytest

from nolane.external_core import reasoning_frontier as frontier
from nolane.external_core import reasoning_metacontrol as control


def _episode_module():
    return importlib.import_module("nolane.external_core.reasoning_episode")


def _root_frontier() -> frontier.ReasoningFrontier:
    unknown = frontier.DecisionUnknown(
        description="The runtime dependency may have crossed a semantic regime boundary.",
        kind=frontier.UnknownKind.REGIME_SHIFT,
        impact=1.0,
        uncertainty=0.8,
        decision_relevance=1.0,
        discovery_path_ids=("experiment:pin",),
        could_overturn_decision=True,
    )
    incumbent = frontier.RivalHypothesisRef(
        hypothesis_id="hypothesis:local",
        category=frontier.HypothesisCategory.LOCAL,
        structural_family_id="family:local",
        prediction_ids=("prediction:local",),
        falsifier_ids=("falsifier:local",),
    )
    dependency = frontier.RivalHypothesisRef(
        hypothesis_id="hypothesis:dependency",
        category=frontier.HypothesisCategory.DEPENDENCY,
        structural_family_id="family:dependency",
        prediction_ids=("prediction:dependency",),
        falsifier_ids=("falsifier:dependency",),
    )
    return frontier.ReasoningFrontier(
        reasoning_receipt_id="reasoning-invention:adversarial",
        objective_id="objective:adversarial",
        cognitive_library_digest="library:adversarial",
        unknowns=(unknown,),
        rivals=(incumbent, dependency),
        assumption_ids=("assumption:compatibility",),
        hard_constraint_ids=("constraint:do-not-mutate-production",),
        branch_budget=3,
    )


def _action(row: frontier.ReasoningFrontier, *, cost: float = 0.5, suffix: str = "main"):
    return control.ReasoningActionProposal(
        frontier_id=row.frontier_id,
        kind=control.MetaActionKind.DESIGN_EXPERIMENT,
        target_ids=(f"hypothesis:dependency:{suffix}",),
        expected_decision_value=0.9,
        expected_information_gain=0.95,
        uncertainty_reduction=0.9,
        estimated_cost=cost,
        residual_risk=0.1,
        reason=f"Discriminate dependency regime {suffix}.",
    )


def _successor(row: frontier.ReasoningFrontier) -> frontier.ReasoningFrontier:
    non_overturning = frontier.DecisionUnknown(
        description="Only a low-impact logging ambiguity remains.",
        kind=frontier.UnknownKind.MISSING_EVIDENCE,
        impact=0.1,
        uncertainty=0.2,
        decision_relevance=0.1,
        discovery_path_ids=("inspect:logs",),
        could_overturn_decision=False,
    )
    dependency = frontier.RivalHypothesisRef(
        hypothesis_id="hypothesis:dependency",
        category=frontier.HypothesisCategory.DEPENDENCY,
        structural_family_id="family:dependency",
        prediction_ids=("prediction:dependency",),
        falsifier_ids=("falsifier:dependency",),
        evidence_for_ids=("evidence:pin-confirmed",),
    )
    return frontier.ReasoningFrontier(
        reasoning_receipt_id=row.reasoning_receipt_id,
        objective_id=row.objective_id,
        cognitive_library_digest=row.cognitive_library_digest,
        unknowns=(non_overturning,),
        rivals=(dependency,),
        assumption_ids=("assumption:incompatible",),
        hard_constraint_ids=row.hard_constraint_ids,
        branch_budget=row.branch_budget,
    )


def _opened():
    episode_mod = _episode_module()
    root = _root_frontier()
    episode = episode_mod.open_reasoning_episode(root, 3, 3.0, 0.2)
    action = _action(root)
    decision = control.plan_next_reasoning_actions(root, episode.current_budget, (action,))
    return episode_mod, root, episode, action, decision


def test_stale_control_and_action_authority_cannot_cross_frontier_generation() -> None:
    episode_mod, root, episode, action, decision = _opened()
    successor = _successor(root)
    advanced = episode_mod.advance_reasoning_episode(
        episode,
        decision,
        action,
        successor,
        observed_cost=0.5,
        evidence_ids=("evidence:pin-confirmed",),
    )

    with pytest.raises(ValueError, match="frontier|budget|stale"):
        episode_mod.advance_reasoning_episode(
            advanced,
            decision,
            action,
            successor,
            observed_cost=0.5,
            evidence_ids=("evidence:reuse",),
        )


def test_advance_rejects_wrong_budget_and_non_pareto_selected_action() -> None:
    episode_mod, root, episode, action, _ = _opened()
    wrong_budget = control.MetareasoningBudget(
        frontier_id=root.frontier_id,
        remaining_actions=99,
        remaining_cost=99.0,
        minimum_actionable_gain=0.2,
    )
    wrong_decision = control.plan_next_reasoning_actions(root, wrong_budget, (action,))
    successor = _successor(root)

    with pytest.raises(ValueError, match="budget|stale"):
        episode_mod.advance_reasoning_episode(
            episode,
            wrong_decision,
            action,
            successor,
            observed_cost=0.5,
            evidence_ids=("evidence:x",),
        )

    selected = _action(root, suffix="selected")
    other = _action(root, suffix="other")
    authorized = control.ReasoningControlDecision(
        frontier_id=root.frontier_id,
        budget_id=episode.current_budget.budget_id,
        disposition=control.ControlDisposition.CONTINUE,
        pareto_action_ids=(selected.action_id,),
        unresolved_overturning_unknown_ids=root.overturning_unknown_ids,
        reason="Only one action is authorized by this control decision.",
    )
    with pytest.raises(ValueError, match="Pareto|authorized|action"):
        episode_mod.advance_reasoning_episode(
            episode,
            authorized,
            other,
            successor,
            observed_cost=0.5,
            evidence_ids=("evidence:y",),
        )


def test_declared_estimated_cost_must_fit_budget_before_transition() -> None:
    episode_mod = _episode_module()
    root = _root_frontier()
    episode = episode_mod.open_reasoning_episode(root, 2, 0.5, 0.1)
    too_expensive = _action(root, cost=0.75)
    decision = control.ReasoningControlDecision(
        frontier_id=root.frontier_id,
        budget_id=episode.current_budget.budget_id,
        disposition=control.ControlDisposition.CONTINUE,
        pareto_action_ids=(too_expensive.action_id,),
        unresolved_overturning_unknown_ids=root.overturning_unknown_ids,
        reason="Adversarially names an action that cannot fit the current cost budget.",
    )
    with pytest.raises(ValueError, match="estimated|cost|budget"):
        episode_mod.advance_reasoning_episode(
            episode,
            decision,
            too_expensive,
            _successor(root),
            observed_cost=0.25,
            evidence_ids=("evidence:cheap-after-all",),
        )


def test_successor_cannot_drift_episode_owned_context_or_d_owned_constraints() -> None:
    episode_mod, root, episode, action, decision = _opened()
    successor = _successor(root)

    mutations = (
        {"reasoning_receipt_id": "reasoning-invention:other"},
        {"objective_id": "objective:other"},
        {"cognitive_library_digest": "library:other"},
        {"hard_constraint_ids": ("constraint:changed-by-D",)},
        {"branch_budget": 2},
    )
    for kwargs in mutations:
        drifted = replace(successor, **kwargs)
        with pytest.raises(ValueError, match="continuity|receipt|objective|library|constraint|branch"):
            episode_mod.advance_reasoning_episode(
                episode,
                decision,
                action,
                drifted,
                observed_cost=0.5,
                evidence_ids=("evidence:drift",),
            )


def test_advance_requires_new_frontier_and_nonempty_evidence() -> None:
    episode_mod, root, episode, action, decision = _opened()
    with pytest.raises(ValueError, match="frontier|change|successor"):
        episode_mod.advance_reasoning_episode(
            episode,
            decision,
            action,
            root,
            observed_cost=0.5,
            evidence_ids=("evidence:no-change",),
        )

    with pytest.raises(ValueError, match="evidence"):
        episode_mod.advance_reasoning_episode(
            episode,
            decision,
            action,
            _successor(root),
            observed_cost=0.5,
            evidence_ids=(),
        )


def test_bool_nonfinite_and_nonpositive_budget_inputs_fail_closed() -> None:
    episode_mod = _episode_module()
    root = _root_frontier()
    bad_rows = (
        {"action_limit": True, "cost_limit": 1.0, "minimum_actionable_gain": 0.2},
        {"action_limit": 0, "cost_limit": 1.0, "minimum_actionable_gain": 0.2},
        {"action_limit": 1, "cost_limit": True, "minimum_actionable_gain": 0.2},
        {"action_limit": 1, "cost_limit": 0.0, "minimum_actionable_gain": 0.2},
        {"action_limit": 1, "cost_limit": float("nan"), "minimum_actionable_gain": 0.2},
        {"action_limit": 1, "cost_limit": 1.0, "minimum_actionable_gain": True},
        {"action_limit": 1, "cost_limit": 1.0, "minimum_actionable_gain": 1.1},
    )
    for kwargs in bad_rows:
        with pytest.raises((TypeError, ValueError)):
            episode_mod.open_reasoning_episode(root, **kwargs)


def test_replay_rejects_forged_generation_topology_current_frontier_and_status() -> None:
    episode_mod, root, episode, action, decision = _opened()
    advanced = episode_mod.advance_reasoning_episode(
        episode,
        decision,
        action,
        _successor(root),
        observed_cost=0.5,
        evidence_ids=("evidence:replay",),
    )
    state = advanced.to_state()

    forged_generation = deepcopy(state)
    forged_generation["transitions"][0]["generation"] = 7
    with pytest.raises(ValueError, match="generation|transition|canonical|identity"):
        episode_mod.ReasoningEpisode.from_state(forged_generation)

    duplicated_transition = deepcopy(state)
    duplicated_transition["transitions"].append(deepcopy(duplicated_transition["transitions"][0]))
    with pytest.raises(ValueError, match="transition|generation|consumed|frontier|canonical"):
        episode_mod.ReasoningEpisode.from_state(duplicated_transition)

    forged_current = deepcopy(state)
    forged_current["current_frontier"] = root.to_state()
    with pytest.raises(ValueError, match="current|frontier|canonical|snapshot"):
        episode_mod.ReasoningEpisode.from_state(forged_current)

    forged_status = deepcopy(state)
    forged_status["status"] = episode_mod.ReasoningEpisodeStatus.HALTED_NO_FURTHER_VALUE.value
    with pytest.raises(ValueError, match="status|terminal|canonical|snapshot"):
        episode_mod.ReasoningEpisode.from_state(forged_status)


def test_terminal_close_is_exactly_bound_to_current_frontier_and_budget() -> None:
    episode_mod, root, episode, action, _ = _opened()
    successor = _successor(root)
    decision = control.plan_next_reasoning_actions(root, episode.current_budget, (action,))
    advanced = episode_mod.advance_reasoning_episode(
        episode,
        decision,
        action,
        successor,
        observed_cost=0.5,
        evidence_ids=("evidence:done",),
    )

    stale_terminal = control.plan_next_reasoning_actions(
        root,
        control.MetareasoningBudget(
            frontier_id=root.frontier_id,
            remaining_actions=0,
            remaining_cost=0.0,
            minimum_actionable_gain=0.2,
        ),
        (),
    )
    with pytest.raises(ValueError, match="frontier|budget|stale"):
        episode_mod.close_reasoning_episode(advanced, stale_terminal)

    continuing = _action(successor, suffix="continue")
    continue_decision = control.plan_next_reasoning_actions(
        successor,
        advanced.current_budget,
        (continuing,),
    )
    assert continue_decision.disposition is control.ControlDisposition.CONTINUE
    with pytest.raises(ValueError, match="terminal|continue|close"):
        episode_mod.close_reasoning_episode(advanced, continue_decision)


def test_c9_source_exposes_no_execution_or_promotion_backdoor() -> None:
    episode_mod = _episode_module()
    source = inspect.getsource(episode_mod)
    forbidden = (
        "subprocess",
        "os.system",
        "execute_tool",
        "invoke_core",
        "CapabilityAcquisitionGovernor",
        "TransferMetaGovernor",
        "AssuranceControlPlane",
        ".promote(",
        ".accept(",
        "neural",
    )
    for token in forbidden:
        assert token not in source

    public = set(getattr(episode_mod, "__all__", ()))
    assert not any("execute" in name.lower() for name in public)
    assert not any("promote" in name.lower() for name in public)
    assert not any("assurance" in name.lower() for name in public)
