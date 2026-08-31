from __future__ import annotations

import importlib
from copy import deepcopy

import pytest

from nolane.external_core import reasoning_frontier as frontier
from nolane.external_core import reasoning_metacontrol as control
from nolane.metadata.component_versions import component_version


def _episode_module():
    return importlib.import_module("nolane.external_core.reasoning_episode")


def _root_frontier() -> frontier.ReasoningFrontier:
    dependency_unknown = frontier.DecisionUnknown(
        description="The dependency may have changed semantics after the baseline snapshot.",
        kind=frontier.UnknownKind.REGIME_SHIFT,
        impact=0.9,
        uncertainty=0.8,
        decision_relevance=1.0,
        discovery_path_ids=("research:dependency-changelog", "experiment:dependency-version"),
        could_overturn_decision=True,
    )
    incidental_unknown = frontier.DecisionUnknown(
        description="The log timestamp format may have changed.",
        kind=frontier.UnknownKind.MISSING_EVIDENCE,
        impact=0.1,
        uncertainty=0.3,
        decision_relevance=0.1,
        discovery_path_ids=("inspect:log-format",),
        could_overturn_decision=False,
    )
    incumbent = frontier.RivalHypothesisRef(
        hypothesis_id="hypothesis:incumbent",
        category=frontier.HypothesisCategory.LOCAL,
        structural_family_id="family:local-implementation",
        prediction_ids=("prediction:local-fix-works",),
        falsifier_ids=("falsifier:clean-env-still-fails",),
        evidence_for_ids=("evidence:local-stack",),
    )
    dependency = frontier.RivalHypothesisRef(
        hypothesis_id="hypothesis:dependency",
        category=frontier.HypothesisCategory.DEPENDENCY,
        structural_family_id="family:dependency-regime",
        prediction_ids=("prediction:version-pinned-passes",),
        falsifier_ids=("falsifier:all-versions-fail",),
        evidence_for_ids=("evidence:version-drift",),
    )
    return frontier.ReasoningFrontier(
        reasoning_receipt_id="reasoning-invention:episode-case",
        objective_id="objective:repair-regression",
        cognitive_library_digest="library:digest:episode",
        unknowns=(dependency_unknown, incidental_unknown),
        rivals=(incumbent, dependency),
        assumption_ids=("assumption:dependency-compatible",),
        hard_constraint_ids=("constraint:no-production-mutation",),
        branch_budget=4,
    )


def _target_unknown_action(row: frontier.ReasoningFrontier, *, cost: float = 1.0):
    target = next(item for item in row.unknowns if item.could_overturn_decision)
    proposal = control.ReasoningActionProposal(
        frontier_id=row.frontier_id,
        kind=control.MetaActionKind.TARGET_UNKNOWN,
        target_ids=(target.unknown_id,),
        expected_decision_value=0.9,
        expected_information_gain=0.9,
        uncertainty_reduction=0.8,
        estimated_cost=cost,
        residual_risk=0.2,
        reason="Resolve the decision-overturning dependency regime unknown.",
    )
    return target, proposal


def _continue_decision(
    row: frontier.ReasoningFrontier,
    budget: control.MetareasoningBudget,
    proposal: control.ReasoningActionProposal,
) -> control.ReasoningControlDecision:
    return control.plan_next_reasoning_actions(row, budget, (proposal,))


def _resolved_successor(row: frontier.ReasoningFrontier) -> frontier.ReasoningFrontier:
    retained_unknowns = tuple(item for item in row.unknowns if not item.could_overturn_decision)
    revised_dependency = frontier.RivalHypothesisRef(
        hypothesis_id="hypothesis:dependency",
        category=frontier.HypothesisCategory.DEPENDENCY,
        structural_family_id="family:dependency-regime",
        prediction_ids=("prediction:version-pinned-passes",),
        falsifier_ids=("falsifier:all-versions-fail",),
        evidence_for_ids=("evidence:version-drift", "evidence:pin-reproduction"),
        evidence_against_ids=(),
    )
    replacement = frontier.RivalHypothesisRef(
        hypothesis_id="hypothesis:environment",
        category=frontier.HypothesisCategory.ENVIRONMENT,
        structural_family_id="family:environment-regime",
        prediction_ids=("prediction:clean-run-stable",),
        falsifier_ids=("falsifier:clean-run-fails",),
        evidence_for_ids=("evidence:clean-run",),
    )
    return frontier.ReasoningFrontier(
        reasoning_receipt_id=row.reasoning_receipt_id,
        objective_id=row.objective_id,
        cognitive_library_digest=row.cognitive_library_digest,
        unknowns=retained_unknowns,
        rivals=(revised_dependency, replacement),
        assumption_ids=("assumption:dependency-incompatible",),
        hard_constraint_ids=row.hard_constraint_ids,
        branch_budget=row.branch_budget,
    )


def test_reasoning_episode_revision_is_coherent_at_v003() -> None:
    module_names = (
        "reasoning_invention",
        "reasoning_evaluation",
        "reasoning_frontier",
        "reasoning_metacontrol",
        "reasoning_review",
        "reasoning_meta_learning",
        "reasoning_episode",
    )
    modules = [importlib.import_module(f"nolane.external_core.{name}") for name in module_names]
    assert {module.COMPONENT_ID for module in modules} == {"external.reasoning_invention"}
    assert {module.COMPONENT_VERSION for module in modules} == {"0.0.3"}
    assert str(component_version("external.reasoning_invention")) == "0.0.3"


def test_episode_open_derives_exact_current_budget() -> None:
    episode_mod = _episode_module()
    root = _root_frontier()
    episode = episode_mod.open_reasoning_episode(
        root,
        action_limit=3,
        cost_limit=5.0,
        minimum_actionable_gain=0.2,
    )

    assert episode.status is episode_mod.ReasoningEpisodeStatus.ACTIVE
    assert episode.root_frontier == root
    assert episode.current_frontier == root
    assert episode.transitions == ()
    assert episode.terminal_control_decision is None
    assert episode.spent_actions == 0
    assert episode.spent_cost == 0.0
    assert episode.current_budget.frontier_id == root.frontier_id
    assert episode.current_budget.remaining_actions == 3
    assert episode.current_budget.remaining_cost == 5.0
    assert episode.current_budget.minimum_actionable_gain == 0.2
    assert episode.episode_key.startswith("reasoning-episode:")
    assert episode.snapshot_id.startswith("reasoning-episode-snapshot:")


def test_advance_consumes_budget_and_derives_exact_frontier_delta() -> None:
    episode_mod = _episode_module()
    root = _root_frontier()
    episode = episode_mod.open_reasoning_episode(root, 3, 5.0, 0.2)
    target, action = _target_unknown_action(root, cost=1.0)
    decision = _continue_decision(root, episode.current_budget, action)
    successor = _resolved_successor(root)

    advanced = episode_mod.advance_reasoning_episode(
        episode,
        decision,
        action,
        successor,
        observed_cost=1.25,
        evidence_ids=("evidence:pin-reproduction", "evidence:clean-run"),
    )

    assert advanced.status is episode_mod.ReasoningEpisodeStatus.ACTIVE
    assert advanced.current_frontier == successor
    assert advanced.spent_actions == 1
    assert advanced.spent_cost == pytest.approx(1.25)
    assert advanced.current_budget.remaining_actions == 2
    assert advanced.current_budget.remaining_cost == pytest.approx(3.75)
    assert len(advanced.transitions) == 1

    transition = advanced.transitions[0]
    assert transition.generation == 1
    assert transition.episode_key == episode.episode_key
    assert transition.previous_frontier_id == root.frontier_id
    assert transition.next_frontier == successor
    assert transition.control_decision == decision
    assert transition.selected_action == action
    assert transition.observed_cost == pytest.approx(1.25)
    assert transition.budget_overrun is False

    delta = transition.delta
    assert delta.previous_frontier_id == root.frontier_id
    assert delta.next_frontier_id == successor.frontier_id
    assert delta.resolved_unknown_ids == (target.unknown_id,)
    assert delta.introduced_unknown_ids == ()
    assert delta.retired_hypothesis_ids == ("hypothesis:incumbent",)
    assert delta.introduced_hypothesis_ids == ("hypothesis:environment",)
    assert delta.revised_hypothesis_ids == ("hypothesis:dependency",)
    assert delta.retired_assumption_ids == ("assumption:dependency-compatible",)
    assert delta.introduced_assumption_ids == ("assumption:dependency-incompatible",)
    assert delta.evidence_ids == ("evidence:clean-run", "evidence:pin-reproduction")
    assert delta.delta_id.startswith("reasoning-frontier-delta:")
    assert transition.transition_id.startswith("reasoning-frontier-transition:")
    assert advanced.snapshot_id != episode.snapshot_id


def test_exact_budget_exhaustion_is_closed_by_current_zero_budget_decision() -> None:
    episode_mod = _episode_module()
    root = _root_frontier()
    episode = episode_mod.open_reasoning_episode(root, 1, 1.0, 0.2)
    _, action = _target_unknown_action(root, cost=1.0)
    decision = _continue_decision(root, episode.current_budget, action)
    successor = _resolved_successor(root)
    advanced = episode_mod.advance_reasoning_episode(
        episode,
        decision,
        action,
        successor,
        observed_cost=1.0,
        evidence_ids=("evidence:pin-reproduction",),
    )

    assert advanced.status is episode_mod.ReasoningEpisodeStatus.ACTIVE
    assert advanced.current_budget.remaining_actions == 0
    assert advanced.current_budget.remaining_cost == 0.0

    terminal = control.plan_next_reasoning_actions(
        successor,
        advanced.current_budget,
        (),
    )
    assert terminal.disposition is control.ControlDisposition.HALT_NO_FURTHER_VALUE
    closed = episode_mod.close_reasoning_episode(advanced, terminal)
    assert closed.status is episode_mod.ReasoningEpisodeStatus.HALTED_NO_FURTHER_VALUE
    assert closed.terminal_control_decision == terminal
    assert closed.current_frontier == successor


def test_observed_cost_overrun_is_recorded_and_terminalizes_fail_closed() -> None:
    episode_mod = _episode_module()
    root = _root_frontier()
    episode = episode_mod.open_reasoning_episode(root, 2, 1.0, 0.2)
    _, action = _target_unknown_action(root, cost=0.5)
    decision = _continue_decision(root, episode.current_budget, action)
    successor = _resolved_successor(root)

    overrun = episode_mod.advance_reasoning_episode(
        episode,
        decision,
        action,
        successor,
        observed_cost=1.5,
        evidence_ids=("evidence:unexpected-cost",),
    )

    assert overrun.status is episode_mod.ReasoningEpisodeStatus.ABSTAINED_BUDGET_OVERRUN
    assert overrun.spent_actions == 1
    assert overrun.spent_cost == pytest.approx(1.5)
    assert overrun.current_budget.remaining_cost == 0.0
    assert overrun.transitions[-1].budget_overrun is True
    assert overrun.terminal_control_decision is None

    with pytest.raises(ValueError, match="terminal|active|overrun"):
        episode_mod.advance_reasoning_episode(
            overrun,
            decision,
            action,
            successor,
            observed_cost=0.1,
            evidence_ids=("evidence:illegal",),
        )


def test_episode_round_trip_replays_transition_prefix_exactly() -> None:
    episode_mod = _episode_module()
    root = _root_frontier()
    episode = episode_mod.open_reasoning_episode(root, 2, 3.0, 0.2)
    _, action = _target_unknown_action(root, cost=1.0)
    decision = _continue_decision(root, episode.current_budget, action)
    successor = _resolved_successor(root)
    advanced = episode_mod.advance_reasoning_episode(
        episode,
        decision,
        action,
        successor,
        observed_cost=1.2,
        evidence_ids=("evidence:transition",),
    )

    restored = episode_mod.ReasoningEpisode.from_state(advanced.to_state())
    assert restored == advanced
    assert restored.to_state() == advanced.to_state()

    tampered = deepcopy(advanced.to_state())
    tampered["snapshot_id"] = "reasoning-episode-snapshot:forged"
    with pytest.raises(ValueError, match="snapshot|canonical|identity"):
        episode_mod.ReasoningEpisode.from_state(tampered)
