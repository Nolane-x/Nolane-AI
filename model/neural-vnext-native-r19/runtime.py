from __future__ import annotations

from typing import Any, Sequence
import torch
from torch import Tensor

from native_core import PublicActionMemory, encode_public_state
from successor_core import PublicTransitionTrace
from attributed_core import PublicActionAttributedTrace
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from public_planner import GOAL_TABLE, PublicGoalConsistencyBelief
from causal_version_space import PublicCausalRuleMemory, choose_public_causal_action


def fuse_public_with_neural_goal(
    public_posterior: Tensor,
    neural_goal_probabilities: Tensor,
    *,
    alpha: float,
) -> Tensor:
    if public_posterior.shape != (125,):
        raise ValueError("public posterior must contain 125 goal hypotheses")
    if neural_goal_probabilities.shape != (3, 5):
        raise ValueError("neural goal probabilities must be [3,5]")
    public = public_posterior.detach().float()
    goal = neural_goal_probabilities.detach().float().clamp_min(1.0e-9)
    joint = torch.ones(125, dtype=torch.float32)
    for dim in range(3):
        joint = joint * goal[dim, GOAL_TABLE[:, dim]]
    weighted = public * torch.pow(joint.clamp_min(1.0e-12), float(alpha))
    mass = float(weighted.sum().item())
    if mass <= 0.0:
        return public / public.sum().clamp_min(1.0e-12)
    return weighted / mass


def rollout_r19(
    parent: NativeR4LatentGoalBeliefPolicy,
    task: Any,
    *,
    alpha: float,
) -> dict[str, Any]:
    exact_memory = PublicActionMemory(len(task.action_descriptions))
    causal_memory = PublicCausalRuleMemory()
    trace = PublicTransitionTrace(max_length=parent.parent.parent.trace_length)
    attributed = PublicActionAttributedTrace(max_length=parent.parent.attribution_length)
    belief = PublicGoalConsistencyBelief()
    hidden = parent.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    overrides_vs_r11 = 0
    fusion_steps = 0
    fusion_l1_sum = 0.0

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
        public = belief.encode()
        fused = fuse_public_with_neural_goal(
            public,
            output["goal_probabilities"][0],
            alpha=float(alpha),
        )
        visible = observation.get("target")
        if not (isinstance(visible, list) and len(visible) == 3):
            fusion_steps += 1
            fusion_l1_sum += float((fused - public).abs().sum().item())

        fused_action, _ = choose_public_causal_action(
            observation=observation,
            exact_memory=exact_memory,
            causal_memory=causal_memory,
            posterior=fused,
            parent_logits=output["action_logits"][0],
            horizon=1,
        )
        r11_action, _ = choose_public_causal_action(
            observation=observation,
            exact_memory=exact_memory,
            causal_memory=causal_memory,
            posterior=public,
            parent_logits=output["action_logits"][0],
            horizon=1,
        )
        action = int(fused_action)
        overrides_vs_r11 += int(action != int(r11_action))

        selected_action_features = action_features[action].detach().clone()
        before = observation
        result = task.step(action)
        after = result.observation
        exact_memory.update(
            action=action,
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        causal_memory.update(action=action, before=before, after=after)
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
        "overrides_vs_r11": int(overrides_vs_r11),
        "fusion_steps": int(fusion_steps),
        "mean_fusion_l1": float(fusion_l1_sum / max(1, fusion_steps)),
    }


def evaluate_r19(
    parent: NativeR4LatentGoalBeliefPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    alpha: float,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R19 evaluation split must be dev or fresh")
    rows = []
    families_result = {}
    solved = steps = overrides = 0
    for family in families:
        fs = fst = fov = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            row = rollout_r19(
                parent,
                make_task(str(family), str(split), int(index)),
                alpha=float(alpha),
            )
            fs += int(row["solved"])
            fst += int(row["steps"])
            fov += int(row["overrides_vs_r11"])
            solved += int(row["solved"])
            steps += int(row["steps"])
            overrides += int(row["overrides_vs_r11"])
            episodes += 1
            rows.append({"family": str(family), "split": str(split), "index": int(index), **row})
        families_result[str(family)] = {
            "episodes": episodes,
            "solved": fs,
            "steps": fst,
            "overrides_vs_r11": fov,
        }
    return {
        "split": split,
        "indices": [int(indices[0]), int(indices[1])],
        "episodes": len(rows),
        "solved": solved,
        "steps": steps,
        "overrides_vs_r11": overrides,
        "families": families_result,
        "rows": rows,
    }
