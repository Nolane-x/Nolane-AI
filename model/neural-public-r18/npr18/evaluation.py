from __future__ import annotations

import torch

from .core import PublicR18RecursiveCore, encode_public_actions, encode_public_text
from .data import PublicActionMemory

R18_FAMILIES = (
    "conditional_regimes",
    "regime_switch",
    "implicit_goal_regimes",
    "causal_prerequisites",
)


def run_public_episode(
    model: PublicR18RecursiveCore,
    task,
) -> dict[str, object]:
    """Closed-loop neural-only evaluation. No oracle is accepted by this API."""
    model.eval()
    memory = model.initial_memory(1)
    public_action_memory = PublicActionMemory(max_actions=model.max_actions)
    previous_action = -1
    previous_feedback = (0.0, 0.0, 0.0)
    actions_taken: list[int] = []

    with torch.no_grad():
        while not task.done:
            before = task.observe()
            descriptions = tuple(str(value) for value in task.action_descriptions)
            action_tokens, action_mask = encode_public_actions(
                descriptions,
                max_actions=model.max_actions,
                max_bytes=model.action_bytes,
            )
            public_memory_rows = public_action_memory.features(
                before,
                action_count=len(descriptions),
            )
            action_memory = torch.zeros(
                model.max_actions,
                model.action_memory_dim,
                dtype=torch.float32,
            )
            for index, values in enumerate(public_memory_rows):
                action_memory[index] = torch.tensor(values, dtype=torch.float32)

            output = model(
                observation_tokens=encode_public_text(
                    task.render_observation(),
                    max_bytes=model.observation_bytes,
                ).unsqueeze(0),
                action_tokens=action_tokens.unsqueeze(0),
                action_mask=action_mask.unsqueeze(0),
                action_memory=action_memory.unsqueeze(0),
                memory=memory,
                previous_action=torch.tensor([previous_action], dtype=torch.long),
                previous_feedback=torch.tensor(
                    [previous_feedback],
                    dtype=torch.float32,
                ),
            )
            memory = output["next_memory"]
            action = int(output["action_logits"].argmax(dim=-1).item())
            if action >= len(descriptions):
                raise RuntimeError("neural policy selected a padded action")
            result = task.step(action)
            public_action_memory.update(
                action=action,
                before=before,
                after=result.observation,
                progress_delta=float(result.progress_delta),
                information_gain=float(result.information_gain),
                failed=bool(result.failed),
            )
            actions_taken.append(action)
            previous_action = action
            previous_feedback = (
                float(result.progress_delta),
                float(result.information_gain),
                float(result.failed),
            )

    return {
        "task_id": task.task_id,
        "family": task.family,
        "index": int(task.index),
        "solved": bool(task.solved),
        "steps": len(actions_taken),
        "actions": actions_taken,
    }


def evaluate_public_r18(
    model: PublicR18RecursiveCore,
    *,
    make_task,
    split: str,
    start_index: int,
    count_per_family: int,
) -> dict[str, object]:
    if split == "fresh":
        raise ValueError(
            "generic evaluator refuses fresh; use the separately frozen fresh-court script"
        )
    rows = [
        run_public_episode(model, make_task(family, split, index))
        for family in R18_FAMILIES
        for index in range(start_index, start_index + count_per_family)
    ]
    families: dict[str, dict[str, int | float]] = {}
    for family in R18_FAMILIES:
        subset = [row for row in rows if row["family"] == family]
        solved = sum(int(row["solved"]) for row in subset)
        families[family] = {
            "episodes": len(subset),
            "solved": solved,
            "solve_rate": solved / max(1, len(subset)),
            "steps": sum(int(row["steps"]) for row in subset),
        }
    solved = sum(int(row["solved"]) for row in rows)
    return {
        "split": split,
        "indices": [start_index, start_index + count_per_family - 1],
        "episodes": len(rows),
        "solved": solved,
        "solve_rate": solved / max(1, len(rows)),
        "families": families,
        "rows": rows,
        "oracle_used_for_action_selection": False,
        "external_core_used": False,
    }
