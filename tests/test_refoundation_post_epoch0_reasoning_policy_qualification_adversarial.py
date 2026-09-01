from __future__ import annotations

import math

import pytest

from nolane.external_core.reasoning_metacontrol import MetaActionKind
from nolane.external_core.reasoning_policy_evolution import (
    MetareasoningPolicy,
    PolicyAdoptionReceipt,
    PolicyEvidenceSplit,
    PolicyMetricVector,
    PolicyRevisionProposal,
    evaluate_policy_shadow,
)
from nolane.external_core.reasoning_policy_qualification import (
    MatchedPolicyTrial,
    PolicyApplicabilityReceipt,
    PolicyEffectVector,
    PolicyRegime,
    PolicyRegimeQualification,
    PolicyTrialContext,
    bind_matched_policy_trial,
    evaluate_policy_applicability,
    qualify_policy_regime,
)


def _base():
    kinds = tuple(kind.value for kind in MetaActionKind)
    parent = MetareasoningPolicy(1, None, 6, 12.0, 0.1, kinds)
    candidate = MetareasoningPolicy(2, parent.policy_id, 5, 10.0, 0.15, kinds[:-1])
    split = PolicyEvidenceSplit(("dev-a", "dev-b"), ("ca", "cb", "pa", "pb"))
    proposal = PolicyRevisionProposal(
        parent.policy_id,
        candidate.policy_id,
        2,
        split,
        ("learning-1",),
        "producer",
        "producer-session",
        ("rationale-1",),
    )
    base = PolicyMetricVector(0.70, 0.60, 0.50, 5.0, 0.20, 1)
    better = PolicyMetricVector(0.75, 0.60, 0.50, 4.9, 0.20, 1)
    shadow = evaluate_policy_shadow(
        proposal,
        parent_metrics=base,
        candidate_metrics=better,
        holdout_episode_ids=split.holdout_episode_ids,
    )
    adoption = PolicyAdoptionReceipt(
        parent.policy_id,
        candidate.policy_id,
        proposal.proposal_id,
        shadow.evaluation_id,
        "review-1",
        "authorization-1",
    )
    regime = PolicyRegime("env", "world-1", "ontology", "library", "reasoning", ("bounded",))
    return parent, candidate, proposal, shadow, adoption, regime


def _context(task: str, *, world: str = "world-1", tags=("bounded",)):
    return PolicyTrialContext(
        task,
        f"objective-{task}",
        "env",
        world,
        "ontology",
        f"evidence-{task}",
        "library",
        "reasoning",
        f"frontier-{task}",
        tags,
    )


def _metric(*, accuracy=0.70, gain=0.60, cost=5.0, risk=0.20):
    return PolicyMetricVector(accuracy, gain, 0.50, cost, risk, 1)


def _trial(task: str, pe: str, ce: str, *, candidate_metrics=None, world="world-1"):
    parent, candidate, proposal, shadow, adoption, regime = _base()
    trial = bind_matched_policy_trial(
        proposal,
        shadow,
        parent_policy=parent,
        candidate_policy=candidate,
        context=_context(task, world=world),
        parent_episode_id=pe,
        candidate_episode_id=ce,
        parent_metrics=_metric(),
        candidate_metrics=candidate_metrics or _metric(accuracy=0.75),
    )
    return parent, candidate, proposal, shadow, adoption, regime, trial


def test_duplicate_tags_and_nonfinite_effect_state_fail_closed() -> None:
    with pytest.raises(ValueError):
        _context("a", tags=("bounded", "bounded"))
    effect = PolicyEffectVector(0.1, 0.0, 0.0, 0.0, 0.0, 0).to_state()
    effect["decision_accuracy_gain"] = True
    with pytest.raises(TypeError):
        PolicyEffectVector.from_state(effect)
    effect["decision_accuracy_gain"] = math.nan
    with pytest.raises(ValueError):
        PolicyEffectVector.from_state(effect)


def test_trial_requires_distinct_holdout_episode_authority() -> None:
    parent, candidate, proposal, shadow, _, _ = _base()
    with pytest.raises(ValueError):
        bind_matched_policy_trial(
            proposal,
            shadow,
            parent_policy=parent,
            candidate_policy=candidate,
            context=_context("a"),
            parent_episode_id="dev-a",
            candidate_episode_id="ca",
            parent_metrics=_metric(),
            candidate_metrics=_metric(accuracy=0.75),
        )
    with pytest.raises(ValueError):
        bind_matched_policy_trial(
            proposal,
            shadow,
            parent_policy=parent,
            candidate_policy=candidate,
            context=_context("a"),
            parent_episode_id="pa",
            candidate_episode_id="pa",
            parent_metrics=_metric(),
            candidate_metrics=_metric(accuracy=0.75),
        )


def test_tail_regression_or_regime_mismatch_blocks_qualification() -> None:
    parent, candidate, proposal, shadow, adoption, regime = _base()
    good = bind_matched_policy_trial(
        proposal,
        shadow,
        parent_policy=parent,
        candidate_policy=candidate,
        context=_context("a"),
        parent_episode_id="pa",
        candidate_episode_id="ca",
        parent_metrics=_metric(),
        candidate_metrics=_metric(accuracy=0.80),
    )
    bad = bind_matched_policy_trial(
        proposal,
        shadow,
        parent_policy=parent,
        candidate_policy=candidate,
        context=_context("b"),
        parent_episode_id="pb",
        candidate_episode_id="cb",
        parent_metrics=_metric(),
        candidate_metrics=_metric(accuracy=0.90, risk=0.30),
    )
    assert bad.regressed_metric_ids == ("residual_risk",)
    with pytest.raises(ValueError):
        qualify_policy_regime(proposal, shadow, adoption, candidate_policy=candidate, regime=regime, trials=(good, bad))

    off_scope = bind_matched_policy_trial(
        proposal,
        shadow,
        parent_policy=parent,
        candidate_policy=candidate,
        context=_context("b", world="world-2"),
        parent_episode_id="pb",
        candidate_episode_id="cb",
        parent_metrics=_metric(),
        candidate_metrics=_metric(gain=0.65),
    )
    with pytest.raises(ValueError):
        qualify_policy_regime(proposal, shadow, adoption, candidate_policy=candidate, regime=regime, trials=(good, off_scope))


def test_episode_reuse_and_single_task_repetition_are_rejected() -> None:
    parent, candidate, proposal, shadow, adoption, regime = _base()
    first = bind_matched_policy_trial(
        proposal,
        shadow,
        parent_policy=parent,
        candidate_policy=candidate,
        context=_context("same"),
        parent_episode_id="pa",
        candidate_episode_id="ca",
        parent_metrics=_metric(),
        candidate_metrics=_metric(accuracy=0.75),
    )
    reused = bind_matched_policy_trial(
        proposal,
        shadow,
        parent_policy=parent,
        candidate_policy=candidate,
        context=_context("other"),
        parent_episode_id="pa",
        candidate_episode_id="cb",
        parent_metrics=_metric(),
        candidate_metrics=_metric(gain=0.65),
    )
    with pytest.raises(ValueError):
        qualify_policy_regime(proposal, shadow, adoption, candidate_policy=candidate, regime=regime, trials=(first, reused))

    second_same_task = bind_matched_policy_trial(
        proposal,
        shadow,
        parent_policy=parent,
        candidate_policy=candidate,
        context=PolicyTrialContext("same", "objective-2", "env", "world-1", "ontology", "evidence-2", "library", "reasoning", "frontier-2", ("bounded",)),
        parent_episode_id="pb",
        candidate_episode_id="cb",
        parent_metrics=_metric(),
        candidate_metrics=_metric(cost=4.8),
    )
    with pytest.raises(ValueError):
        qualify_policy_regime(proposal, shadow, adoption, candidate_policy=candidate, regime=regime, trials=(first, second_same_task))


def test_forged_content_ids_are_rejected_on_replay() -> None:
    parent, candidate, proposal, shadow, adoption, regime = _base()
    a = bind_matched_policy_trial(
        proposal, shadow, parent_policy=parent, candidate_policy=candidate, context=_context("a"),
        parent_episode_id="pa", candidate_episode_id="ca", parent_metrics=_metric(), candidate_metrics=_metric(accuracy=0.75),
    )
    b = bind_matched_policy_trial(
        proposal, shadow, parent_policy=parent, candidate_policy=candidate, context=_context("b"),
        parent_episode_id="pb", candidate_episode_id="cb", parent_metrics=_metric(), candidate_metrics=_metric(gain=0.65),
    )
    qualification = qualify_policy_regime(proposal, shadow, adoption, candidate_policy=candidate, regime=regime, trials=(a, b))
    receipt = evaluate_policy_applicability(qualification, _context("live"))

    context_state = a.context.to_state(); context_state["context_id"] = "forged"
    with pytest.raises(ValueError): PolicyTrialContext.from_state(context_state)
    trial_state = a.to_state(); trial_state["trial_id"] = "forged"
    with pytest.raises(ValueError): MatchedPolicyTrial.from_state(trial_state)
    q_state = qualification.to_state(); q_state["qualification_id"] = "forged"
    with pytest.raises(ValueError): PolicyRegimeQualification.from_state(q_state)
    r_state = receipt.to_state(); r_state["receipt_id"] = "forged"
    with pytest.raises(ValueError): PolicyApplicabilityReceipt.from_state(r_state)
