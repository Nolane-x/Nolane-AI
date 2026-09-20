from __future__ import annotations

from typing import Any, Sequence
import torch

from native_core import PublicActionMemory, encode_public_state
from successor_core import PublicTransitionTrace
from attributed_core import PublicActionAttributedTrace
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from public_planner import PublicGoalConsistencyBelief
from causal_version_space import PublicCausalRuleMemory, choose_public_causal_action


def _choose_probe(
    observation: dict[str, Any],
    memory: PublicActionMemory,
    parent_logits: torch.Tensor,
    r11_action: int,
) -> int | None:
    descriptions = observation["actions"]
    rows = []
    for action, description in enumerate(descriptions):
        if "submit" in str(description).lower():
            continue
        if int(action) == int(r11_action):
            continue
        seen = memory.seen_in_context(observation, int(action))
        total = memory.total[int(action)].count
        rows.append((
            int(seen),
            int(total),
            -float(parent_logits[int(action)].item()),
            int(action),
        ))
    if not rows:
        return None
    rows.sort()
    # A real probe must add context-local transition evidence.
    if rows[0][0] != 0:
        return None
    return int(rows[0][3])


def rollout_r20(
    parent: NativeR4LatentGoalBeliefPolicy,
    task: Any,
    *,
    max_probes: int,
    max_probe_step: int,
    minimum_budget_remaining: int,
) -> dict[str, Any]:
    exact_memory = PublicActionMemory(len(task.action_descriptions))
    causal_memory = PublicCausalRuleMemory()
    trace = PublicTransitionTrace(max_length=parent.parent.parent.trace_length)
    attributed = PublicActionAttributedTrace(max_length=parent.parent.attribution_length)
    belief = PublicGoalConsistencyBelief()
    hidden = parent.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    probes = 0
    overrides = 0
    probe_information = 0.0

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
        r11_action, info = choose_public_causal_action(
            observation=observation,
            exact_memory=exact_memory,
            causal_memory=causal_memory,
            posterior=belief.encode(),
            parent_logits=output["action_logits"][0],
            horizon=1,
        )
        action = int(r11_action)
        target = observation.get("target")
        hidden_target = not (isinstance(target, list) and len(target) == 3)
        trigger = info.get("reason") in {
            "posterior_too_broad_r9_fallback",
            "no_certified_causal_advantage",
        }
        if (
            hidden_target
            and trigger
            and probes < int(max_probes)
            and int(observation["step"]) <= int(max_probe_step)
            and int(observation["budget_remaining"]) >= int(minimum_budget_remaining)
        ):
            probe = _choose_probe(
                observation,
                exact_memory,
                output["action_logits"][0],
                int(r11_action),
            )
            if probe is not None:
                action = int(probe)
                probes += 1
                overrides += int(action != int(r11_action))

        selected_action_features = action_features[action].detach().clone()
        before = observation
        result = task.step(action)
        after = result.observation
        if action != int(r11_action):
            probe_information += float(result.information_gain)
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
        "probes": int(probes),
        "overrides_vs_r11": int(overrides),
        "probe_information_gain": float(probe_information),
    }


def evaluate_r20(
    parent: NativeR4LatentGoalBeliefPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    max_probes: int,
    max_probe_step: int,
    minimum_budget_remaining: int,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R20 split must be dev or fresh")
    rows = []
    families_result = {}
    solved = steps = probes = overrides = 0
    for family in families:
        fs = fst = fp = fov = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            row = rollout_r20(
                parent,
                make_task(str(family), str(split), int(index)),
                max_probes=int(max_probes),
                max_probe_step=int(max_probe_step),
                minimum_budget_remaining=int(minimum_budget_remaining),
            )
            fs += int(row["solved"])
            fst += int(row["steps"])
            fp += int(row["probes"])
            fov += int(row["overrides_vs_r11"])
            solved += int(row["solved"])
            steps += int(row["steps"])
            probes += int(row["probes"])
            overrides += int(row["overrides_vs_r11"])
            episodes += 1
            rows.append({"family": str(family), "split": str(split), "index": int(index), **row})
        families_result[str(family)] = {
            "episodes": episodes,
            "solved": fs,
            "steps": fst,
            "probes": fp,
            "overrides_vs_r11": fov,
        }
    return {
        "split": split,
        "indices": [int(indices[0]), int(indices[1])],
        "episodes": len(rows),
        "solved": solved,
        "steps": steps,
        "probes": probes,
        "overrides_vs_r11": overrides,
        "families": families_result,
        "rows": rows,
    }
