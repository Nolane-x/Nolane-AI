from __future__ import annotations

from typing import Any, Sequence

import torch

from native_core import PublicActionMemory, encode_public_state
from successor_core import PublicTransitionTrace
from attributed_core import PublicActionAttributedTrace
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from public_planner import (
    PublicGoalConsistencyBelief,
    choose_public_counterfactual_action,
)


def rollout_r9(
    parent: NativeR4LatentGoalBeliefPolicy,
    task: Any,
    *,
    max_support: int,
) -> dict[str, Any]:
    memory = PublicActionMemory(len(task.action_descriptions))
    trace = PublicTransitionTrace(max_length=parent.parent.parent.trace_length)
    attributed = PublicActionAttributedTrace(max_length=parent.parent.attribution_length)
    belief = PublicGoalConsistencyBelief()
    hidden = parent.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    overrides = 0
    submit_guards = 0
    planner_overrides = 0
    supports: list[int] = []

    while not task.done:
        observation = task.observe()
        belief.update(observation)
        supports.append(belief.support_size())
        global_features, action_features, valid = encode_public_state(
            observation,
            memory,
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
        parent_logits = output["action_logits"][0]
        action, decision = choose_public_counterfactual_action(
            observation=observation,
            memory=memory,
            posterior=belief.encode(),
            parent_logits=parent_logits,
            max_support=max_support,
        )
        overrides += int(decision["override"])
        submit_guards += int(decision["reason"] == "public_progress_complete")
        planner_overrides += int(
            decision["reason"] == "known_public_counterfactual_improvement"
            and decision["override"]
        )

        selected_action_features = action_features[action].detach().clone()
        before = observation
        result = task.step(action)
        after = result.observation
        memory.update(
            action=action,
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
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
        "overrides": overrides,
        "submit_guards": submit_guards,
        "planner_overrides": planner_overrides,
        "minimum_support": min(supports) if supports else 125,
    }


def evaluate_r9(
    parent: NativeR4LatentGoalBeliefPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    max_support: int,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R9 evaluation split must be dev or fresh")
    rows = []
    families_result = {}
    solved = steps = overrides = submit_guards = planner_overrides = 0
    for family in families:
        fs = fst = fov = fsg = fpo = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r9(
                parent,
                make_task(str(family), str(split), int(index)),
                max_support=max_support,
            )
            fs += int(result["solved"])
            fst += int(result["steps"])
            fov += int(result["overrides"])
            fsg += int(result["submit_guards"])
            fpo += int(result["planner_overrides"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            overrides += int(result["overrides"])
            submit_guards += int(result["submit_guards"])
            planner_overrides += int(result["planner_overrides"])
            episodes += 1
            rows.append({
                "family":str(family),"split":str(split),"index":int(index),
                **result,
            })
        families_result[str(family)]={
            "episodes":episodes,"solved":fs,"steps":fst,
            "overrides":fov,"submit_guards":fsg,"planner_overrides":fpo,
        }
    return {
        "split":str(split),"indices":[int(indices[0]),int(indices[1])],
        "episodes":len(rows),"solved":solved,
        "solve_rate":solved/max(1,len(rows)),"steps":steps,
        "overrides":overrides,"submit_guards":submit_guards,
        "planner_overrides":planner_overrides,
        "families":families_result,"rows":rows,
    }
