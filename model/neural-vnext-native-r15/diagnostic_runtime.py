from __future__ import annotations

from typing import Any, Sequence

import torch

from native_core import PublicActionMemory, encode_public_state
from successor_core import PublicTransitionTrace
from attributed_core import PublicActionAttributedTrace
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from public_planner import PublicGoalConsistencyBelief
from causal_version_space import PublicCausalRuleMemory
from diagnostic_planner import choose_public_diagnostic_action


def rollout_r15(
    parent: NativeR4LatentGoalBeliefPolicy,
    task: Any,
    *,
    max_support: int,
    guard_mode: str,
) -> dict[str, Any]:
    exact_memory = PublicActionMemory(len(task.action_descriptions))
    causal_memory = PublicCausalRuleMemory()
    trace = PublicTransitionTrace(max_length=parent.parent.parent.trace_length)
    attributed = PublicActionAttributedTrace(max_length=parent.parent.attribution_length)
    belief = PublicGoalConsistencyBelief()
    hidden = parent.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    overrides_vs_r11 = 0
    diagnostic_decisions = 0
    supports: list[int] = []

    while not task.done:
        observation = task.observe()
        belief.update(observation)
        supports.append(belief.support_size())
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
        action, decision = choose_public_diagnostic_action(
            observation=observation,
            exact_memory=exact_memory,
            causal_memory=causal_memory,
            posterior=belief.encode(),
            parent_logits=output["action_logits"][0],
            max_support=int(max_support),
            guard_mode=str(guard_mode),
        )
        overrides_vs_r11 += int(bool(decision.get("override", False)))
        diagnostic_decisions += int(
            decision.get("reason") == "certified_broad_support_diagnostic"
        )

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
        "overrides_vs_r11": overrides_vs_r11,
        "diagnostic_decisions": diagnostic_decisions,
        "minimum_support": min(supports) if supports else 125,
    }


def evaluate_r15(
    parent: NativeR4LatentGoalBeliefPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    max_support: int,
    guard_mode: str,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R15 evaluation split must be dev or fresh")
    rows = []
    families_result = {}
    solved = steps = overrides = decisions = 0
    for family in families:
        fs = fst = fov = fdec = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r15(
                parent,
                make_task(str(family), str(split), int(index)),
                max_support=int(max_support),
                guard_mode=str(guard_mode),
            )
            fs += int(result["solved"])
            fst += int(result["steps"])
            fov += int(result["overrides_vs_r11"])
            fdec += int(result["diagnostic_decisions"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            overrides += int(result["overrides_vs_r11"])
            decisions += int(result["diagnostic_decisions"])
            episodes += 1
            rows.append({
                "family":str(family),"split":str(split),"index":int(index),**result,
            })
        families_result[str(family)]={
            "episodes":episodes,"solved":fs,"steps":fst,
            "overrides_vs_r11":fov,"diagnostic_decisions":fdec,
        }
    return {
        "split":str(split),"indices":[int(indices[0]),int(indices[1])],
        "episodes":len(rows),"solved":solved,
        "solve_rate":solved/max(1,len(rows)),"steps":steps,
        "overrides_vs_r11":overrides,"diagnostic_decisions":decisions,
        "families":families_result,"rows":rows,
    }
