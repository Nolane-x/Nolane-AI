from __future__ import annotations

from typing import Any, Mapping, Sequence

import torch
from torch import Tensor

from native_core import PublicActionMemory, encode_public_state
from successor_core import PublicTransitionTrace
from attributed_core import PublicActionAttributedTrace
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from public_planner import (
    GOAL_CARDINALITY,
    GOAL_TABLE,
    PublicGoalConsistencyBelief,
)
from causal_version_space import PublicCausalRuleMemory, choose_public_causal_action
from world_model import PublicDynamicsNet, ensemble_predictions

R11_HORIZON = 1


def _expected_distance(state: Tensor, posterior: Tensor) -> float:
    distances = torch.remainder(
        GOAL_TABLE - state.unsqueeze(0),
        GOAL_CARDINALITY,
    ).sum(dim=1).float()
    return float((posterior * distances).sum().item())


def choose_r16_action(
    *,
    observation: Mapping[str, Any],
    exact_memory: PublicActionMemory,
    causal_memory: PublicCausalRuleMemory,
    posterior: Tensor,
    parent_logits: Tensor,
    global_features: Tensor,
    action_features: Tensor,
    models: Sequence[PublicDynamicsNet],
    threshold: float,
    max_support: int,
    minimum_advantage: float,
) -> tuple[int, dict[str, Any]]:
    r11_action, r11_info = choose_public_causal_action(
        observation=observation,
        exact_memory=exact_memory,
        causal_memory=causal_memory,
        posterior=posterior,
        parent_logits=parent_logits,
        horizon=R11_HORIZON,
    )
    target = observation.get("target")
    if isinstance(target, list) and len(target) == 3:
        return int(r11_action), {"override": False, "reason": "visible_target_r11_exact"}
    if r11_info.get("reason") == "r9_public_progress_complete":
        return int(r11_action), {"override": False, "reason": "public_progress_complete"}

    posterior = posterior.detach().float()
    posterior = posterior / posterior.sum().clamp_min(1.0e-12)
    support = int((posterior > 0).sum().item())
    if support > int(max_support):
        return int(r11_action), {
            "override": False,
            "reason": "posterior_support_gate",
            "support": support,
        }

    predicted, agreement, confidence = ensemble_predictions(
        models,
        global_features.unsqueeze(0),
        action_features.unsqueeze(0),
    )
    predicted = predicted[0]
    agreement = agreement[0]
    confidence = confidence[0]

    descriptions = observation["actions"]
    submit = [
        i for i, description in enumerate(descriptions)
        if "submit" in str(description).lower()
    ]
    if len(submit) != 1:
        raise ValueError("expected one submit action")
    submit_action = int(submit[0])
    state = torch.tensor(observation["state"], dtype=torch.long)
    current_distance = _expected_distance(state, posterior)

    def neural_next(action: int) -> tuple[Tensor | None, float]:
        if int(action) == submit_action:
            return None, 0.0
        if not bool(agreement[int(action)].item()):
            return None, float(confidence[int(action)].item())
        conf = float(confidence[int(action)].item())
        if conf < float(threshold):
            return None, conf
        delta = predicted[int(action)].long()
        return torch.remainder(state + delta, GOAL_CARDINALITY), conf

    r11_next, _rules = causal_memory.predict_certified(
        context=exact_memory.context_key(observation),
        state=state,
        action=int(r11_action),
    ) if int(r11_action) != submit_action else (None, 0)
    if r11_next is None:
        r11_next, _ = neural_next(int(r11_action))
    reference_distance = (
        _expected_distance(r11_next, posterior)
        if r11_next is not None
        else current_distance
    )

    best_action = int(r11_action)
    best_distance = float(reference_distance)
    best_confidence = 0.0
    eligible_predictions = 0
    for action, description in enumerate(descriptions):
        if "submit" in str(description).lower():
            continue
        nxt, conf = neural_next(int(action))
        if nxt is None:
            continue
        eligible_predictions += 1
        distance = _expected_distance(nxt, posterior)
        if distance >= current_distance - 1.0e-8:
            continue
        if distance + float(minimum_advantage) >= best_distance - 1.0e-8:
            continue
        candidate_rank = (
            -float(distance),
            float(conf),
            float(parent_logits[int(action)].item()),
            -int(action),
        )
        incumbent_rank = (
            -float(best_distance),
            float(best_confidence),
            float(parent_logits[int(best_action)].item()),
            -int(best_action),
        )
        if best_action == int(r11_action) or candidate_rank > incumbent_rank:
            best_action = int(action)
            best_distance = float(distance)
            best_confidence = float(conf)

    if best_action == int(r11_action):
        return int(r11_action), {
            "override": False,
            "reason": "no_neural_dynamics_advantage",
            "support": support,
            "eligible_predictions": eligible_predictions,
        }
    return best_action, {
        "override": True,
        "reason": "neural_dynamics_advantage",
        "support": support,
        "eligible_predictions": eligible_predictions,
        "confidence": best_confidence,
        "reference_distance": float(reference_distance),
        "selected_distance": float(best_distance),
    }


def rollout_r16(
    parent: NativeR4LatentGoalBeliefPolicy,
    task: Any,
    *,
    models: Sequence[PublicDynamicsNet],
    threshold: float,
    max_support: int,
    minimum_advantage: float,
) -> dict[str, Any]:
    exact_memory = PublicActionMemory(len(task.action_descriptions))
    causal_memory = PublicCausalRuleMemory()
    trace = PublicTransitionTrace(max_length=parent.parent.parent.trace_length)
    attributed = PublicActionAttributedTrace(max_length=parent.parent.attribution_length)
    belief = PublicGoalConsistencyBelief()
    hidden = parent.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    overrides = 0
    neural_decisions = 0
    eligible_predictions = 0

    while not task.done:
        observation = task.observe()
        belief.update(observation)
        global_features, action_features, valid = encode_public_state(
            observation,
            exact_memory,
            previous_feedback=previous_feedback,
        )
        trace_features, trace_valid = trace.encode()
        attribution_features, attribution_valid = attributed.encode()
        with torch.no_grad():
            output = parent.forward_step(
                global_features.unsqueeze(0),
                action_features.unsqueeze(0),
                valid.unsqueeze(0),
                hidden,
                trace_features.unsqueeze(0),
                trace_valid.unsqueeze(0),
                attribution_features.unsqueeze(0),
                attribution_valid.unsqueeze(0),
            )
        hidden = output["next_parent_hidden"]
        posterior = belief.encode()
        action, info = choose_r16_action(
            observation=observation,
            exact_memory=exact_memory,
            causal_memory=causal_memory,
            posterior=posterior,
            parent_logits=output["action_logits"][0],
            global_features=global_features,
            action_features=action_features,
            models=models,
            threshold=float(threshold),
            max_support=int(max_support),
            minimum_advantage=float(minimum_advantage),
        )
        overrides += int(bool(info.get("override", False)))
        neural_decisions += int(info.get("reason") == "neural_dynamics_advantage")
        eligible_predictions += int(info.get("eligible_predictions", 0))

        selected_action_features = action_features[action].detach().clone()
        before = observation
        result = task.step(int(action))
        after = result.observation
        exact_memory.update(
            action=int(action),
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        causal_memory.update(action=int(action), before=before, after=after)
        trace.update(
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        attributed.update(
            selected_action_features=selected_action_features,
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        previous_feedback = [
            float(result.progress_delta),
            float(result.information_gain),
            float(result.failed),
        ]

    return {
        "solved": bool(task.solved),
        "steps": int(task.step_count),
        "overrides_vs_r11": int(overrides),
        "neural_dynamics_decisions": int(neural_decisions),
        "eligible_predictions": int(eligible_predictions),
    }


def evaluate_r16(
    parent: NativeR4LatentGoalBeliefPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    models: Sequence[PublicDynamicsNet],
    threshold: float,
    max_support: int,
    minimum_advantage: float,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R16 evaluation split must be dev or fresh")
    rows: list[dict[str, Any]] = []
    family_result: dict[str, dict[str, int]] = {}
    solved = steps = overrides = decisions = eligible = 0
    for family in families:
        fs = fst = fov = fdec = fel = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r16(
                parent,
                make_task(str(family), str(split), int(index)),
                models=models,
                threshold=float(threshold),
                max_support=int(max_support),
                minimum_advantage=float(minimum_advantage),
            )
            fs += int(result["solved"])
            fst += int(result["steps"])
            fov += int(result["overrides_vs_r11"])
            fdec += int(result["neural_dynamics_decisions"])
            fel += int(result["eligible_predictions"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            overrides += int(result["overrides_vs_r11"])
            decisions += int(result["neural_dynamics_decisions"])
            eligible += int(result["eligible_predictions"])
            episodes += 1
            rows.append({"family":str(family),"split":str(split),"index":int(index),**result})
        family_result[str(family)] = {
            "episodes": episodes,
            "solved": fs,
            "steps": fst,
            "overrides_vs_r11": fov,
            "neural_dynamics_decisions": fdec,
            "eligible_predictions": fel,
        }
    return {
        "split":str(split),
        "indices":[int(indices[0]),int(indices[1])],
        "episodes":len(rows),
        "solved":solved,
        "steps":steps,
        "overrides_vs_r11":overrides,
        "neural_dynamics_decisions":decisions,
        "eligible_predictions":eligible,
        "families":family_result,
        "rows":rows,
    }
