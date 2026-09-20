from __future__ import annotations

from typing import Any, Sequence

import torch

from native_core import PublicActionMemory, encode_public_state
from successor_core import PublicTransitionTrace
from attributed_core import PublicActionAttributedTrace
from belief_correction_core import (
    NativeR8BeliefCorrectionPolicy,
    PublicGoalConsistencyBelief,
)


def rollout_r8(
    model: NativeR8BeliefCorrectionPolicy,
    task: Any,
) -> dict[str, Any]:
    memory = PublicActionMemory(len(task.action_descriptions))
    trace = PublicTransitionTrace(
        max_length=model.parent.parent.parent.trace_length
    )
    attributed = PublicActionAttributedTrace(
        max_length=model.parent.parent.attribution_length
    )
    consistency = PublicGoalConsistencyBelief()
    parent_hidden = model.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    actions: list[int] = []
    supports: list[int] = []
    active_steps = 0
    model.eval()

    while not task.done:
        observation = task.observe()
        consistency.update(observation)
        supports.append(consistency.support_size())
        global_features, action_features, valid = encode_public_state(
            observation,
            memory,
            previous_feedback=previous_feedback,
        )
        trace_features, trace_valid = trace.encode()
        attribution_features, attribution_valid = attributed.encode()
        with torch.no_grad():
            output = model.forward_step(
                global_features.unsqueeze(0),
                action_features.unsqueeze(0),
                valid.unsqueeze(0),
                parent_hidden,
                trace_features.unsqueeze(0),
                trace_valid.unsqueeze(0),
                attribution_features.unsqueeze(0),
                attribution_valid.unsqueeze(0),
                consistency.encode().unsqueeze(0),
            )
        parent_hidden = output["next_parent_hidden"]
        active_steps += int(output["correction_active"].item())
        action = int(output["action_logits"].argmax(-1).item())
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
        actions.append(action)

    return {
        "solved": bool(task.solved),
        "steps": int(task.step_count),
        "actions": actions,
        "correction_active_steps": active_steps,
        "final_consistency_support": supports[-1] if supports else 125,
        "minimum_consistency_support": min(supports) if supports else 125,
    }


def evaluate_r8(
    model: NativeR8BeliefCorrectionPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R8 evaluation split must be dev or fresh")
    rows: list[dict[str, Any]] = []
    families_result: dict[str, dict[str, int]] = {}
    solved = 0
    steps = 0
    active_steps = 0
    for family in families:
        family_solved = 0
        family_steps = 0
        family_active = 0
        episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r8(
                model,
                make_task(str(family), str(split), int(index)),
            )
            family_solved += int(result["solved"])
            family_steps += int(result["steps"])
            family_active += int(result["correction_active_steps"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            active_steps += int(result["correction_active_steps"])
            episodes += 1
            rows.append({
                "family": str(family),
                "split": str(split),
                "index": int(index),
                "solved": bool(result["solved"]),
                "steps": int(result["steps"]),
                "correction_active_steps": int(result["correction_active_steps"]),
                "final_consistency_support": int(result["final_consistency_support"]),
                "minimum_consistency_support": int(result["minimum_consistency_support"]),
            })
        families_result[str(family)] = {
            "episodes": episodes,
            "solved": family_solved,
            "steps": family_steps,
            "correction_active_steps": family_active,
        }
    return {
        "split": str(split),
        "indices": [int(indices[0]), int(indices[1])],
        "episodes": len(rows),
        "solved": solved,
        "solve_rate": solved / max(1, len(rows)),
        "steps": steps,
        "correction_active_steps": active_steps,
        "families": families_result,
        "rows": rows,
    }
