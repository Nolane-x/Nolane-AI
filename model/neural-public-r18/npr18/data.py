from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Iterable, Sequence

import torch
from torch import Tensor

from .core import encode_public_actions, encode_public_text

R18_FAMILIES = (
    "conditional_regimes",
    "regime_switch",
    "implicit_goal_regimes",
    "causal_prerequisites",
)


@dataclass(frozen=True)
class PublicTeacherStep:
    observation_text: str
    action_descriptions: tuple[str, ...]
    previous_action: int
    previous_feedback: tuple[float, float, float]
    target_action: int


@dataclass(frozen=True)
class PublicTeacherEpisode:
    task_id: str
    family: str
    index: int
    steps: tuple[PublicTeacherStep, ...]
    solved: bool


def _context_key(observation: dict[str, object]) -> str:
    regime = observation.get("regime")
    if isinstance(regime, str):
        return f"regime:{regime}"
    return "prerequisite"


def _public_exploration_action(
    task,
    *,
    explored: dict[str, dict[int, int]],
    post_gate_explored: set[int],
) -> int | None:
    observation = task.observe()
    descriptions = tuple(str(value) for value in task.action_descriptions)
    non_submit = [
        index for index, description in enumerate(descriptions)
        if "submit" not in description.lower()
    ]
    key = _context_key(observation)
    counts = explored.setdefault(key, {})

    if task.family == "causal_prerequisites":
        resources = observation.get("resources")
        if not isinstance(resources, dict):
            raise ValueError("public prerequisite observation is missing resources")
        gate_open = int(resources.get("gate_open", 0))
        charge = int(resources.get("charge_level", 0))
        if gate_open:
            candidates = [index for index in non_submit if index not in post_gate_explored]
            if candidates:
                return min(candidates, key=lambda index: descriptions[index])
            return None

        # Before the gate opens, cycle opaque actuators. Repeating public probes
        # is intentional: one failed unlock at charge<2 cannot identify its role.
        target_repeats = 3 if charge < 2 else 4
        candidates = [index for index in non_submit if counts.get(index, 0) < target_repeats]
        if candidates:
            return min(candidates, key=lambda index: (counts.get(index, 0), descriptions[index]))
        return None

    repeats = 1 if task.family == "regime_switch" else 2
    candidates = [index for index in non_submit if counts.get(index, 0) < repeats]
    if candidates:
        return min(candidates, key=lambda index: (counts.get(index, 0), descriptions[index]))
    return None


def collect_public_teacher_episode(
    task,
    *,
    oracle_plan,
    max_steps: int | None = None,
) -> PublicTeacherEpisode:
    if task.split != "train":
        raise ValueError("public teacher collection is train-split only")
    explored: dict[str, dict[int, int]] = {}
    post_gate_explored: set[int] = set()
    previous_action = -1
    previous_feedback = (0.0, 0.0, 0.0)
    rows: list[PublicTeacherStep] = []
    limit = task.budget_remaining if max_steps is None else min(task.budget_remaining, int(max_steps))

    while not task.done and len(rows) < limit:
        plan = oracle_plan(copy.deepcopy(task))
        if not plan:
            break
        observation = task.observe()
        descriptions = tuple(str(value) for value in task.action_descriptions)
        proposal = _public_exploration_action(
            task,
            explored=explored,
            post_gate_explored=post_gate_explored,
        )
        # Never let exploration destroy oracle solvability: reserve the complete
        # current shortest plan plus one transition of slack.
        target = int(plan[0])
        if proposal is not None and task.budget_remaining > len(plan) + 1:
            branch = copy.deepcopy(task)
            branch.step(int(proposal))
            try:
                oracle_plan(copy.deepcopy(branch))
            except RuntimeError:
                proposal = None
            if proposal is not None:
                target = int(proposal)

        rows.append(
            PublicTeacherStep(
                observation_text=task.render_observation(),
                action_descriptions=descriptions,
                previous_action=previous_action,
                previous_feedback=previous_feedback,
                target_action=target,
            )
        )

        context_before = _context_key(observation)
        result = task.step(target)
        if "submit" not in descriptions[target].lower():
            bucket = explored.setdefault(context_before, {})
            bucket[target] = bucket.get(target, 0) + 1
            after = result.observation
            resources = after.get("resources") if isinstance(after, dict) else None
            if isinstance(resources, dict) and int(resources.get("gate_open", 0)):
                post_gate_explored.add(target)
        previous_action = target
        previous_feedback = (
            float(result.progress_delta),
            float(result.information_gain),
            float(result.failed),
        )

    return PublicTeacherEpisode(
        task_id=task.task_id,
        family=task.family,
        index=int(task.index),
        steps=tuple(rows),
        solved=bool(task.solved),
    )


def tensorize_public_step(
    row: PublicTeacherStep,
    *,
    observation_bytes: int,
    action_bytes: int,
    max_actions: int,
) -> dict[str, Tensor]:
    action_tokens, action_mask = encode_public_actions(
        row.action_descriptions,
        max_actions=max_actions,
        max_bytes=action_bytes,
    )
    return {
        "observation_tokens": encode_public_text(
            row.observation_text, max_bytes=observation_bytes
        ).unsqueeze(0),
        "action_tokens": action_tokens.unsqueeze(0),
        "action_mask": action_mask.unsqueeze(0),
        "previous_action": torch.tensor([row.previous_action], dtype=torch.long),
        "previous_feedback": torch.tensor([row.previous_feedback], dtype=torch.float32),
        "target_action": torch.tensor([row.target_action], dtype=torch.long),
    }


def collect_public_teacher_corpus(
    *,
    make_task,
    oracle_plan,
    start_index: int,
    count_per_family: int,
) -> list[PublicTeacherEpisode]:
    if type(start_index) is not int or start_index < 0:
        raise ValueError("start_index must be a non-negative exact integer")
    if type(count_per_family) is not int or count_per_family < 1:
        raise ValueError("count_per_family must be a positive exact integer")
    episodes: list[PublicTeacherEpisode] = []
    for family in R18_FAMILIES:
        for index in range(start_index, start_index + count_per_family):
            episodes.append(
                collect_public_teacher_episode(
                    make_task(family, "train", index),
                    oracle_plan=oracle_plan,
                )
            )
    return episodes
