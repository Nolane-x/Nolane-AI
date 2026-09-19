from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor

from .core import encode_public_actions, encode_public_text

R18_FAMILIES = (
    "conditional_regimes",
    "regime_switch",
    "implicit_goal_regimes",
    "causal_prerequisites",
)
ACTION_MEMORY_DIM = 10


def _context_key(observation: dict[str, object]) -> str:
    regime = observation.get("regime")
    if isinstance(regime, str):
        return f"regime:{regime}"
    return "prerequisite"


def _state3(observation: dict[str, object]) -> tuple[float, float, float]:
    state = observation.get("state")
    if not isinstance(state, list) or len(state) != 3:
        raise ValueError("public observation is missing three-dimensional state")
    return float(state[0]), float(state[1]), float(state[2])


def _resource_pair(observation: dict[str, object]) -> tuple[float, float]:
    resources = observation.get("resources")
    if not isinstance(resources, dict):
        return 0.0, 0.0
    return float(resources.get("charge_level", 0.0)), float(resources.get("gate_open", 0.0))


class PublicActionMemory:
    """Deterministic per-action memory derived only from public transitions."""

    def __init__(self, max_actions: int) -> None:
        if type(max_actions) is not int or max_actions < 1:
            raise ValueError("max_actions must be a positive exact integer")
        self.max_actions = max_actions
        self.attempts = [0] * max_actions
        self.last_progress = [0.0] * max_actions
        self.last_information = [0.0] * max_actions
        self.failures = [0] * max_actions
        self.last_effect = [[0.0] * 5 for _ in range(max_actions)]
        self.context_attempts: dict[str, list[int]] = {}

    def features(
        self,
        observation: dict[str, object],
        *,
        action_count: int,
    ) -> tuple[tuple[float, ...], ...]:
        if not 1 <= action_count <= self.max_actions:
            raise ValueError("action_count is outside memory capacity")
        context = _context_key(observation)
        contextual = self.context_attempts.setdefault(context, [0] * self.max_actions)
        rows: list[tuple[float, ...]] = []
        for action in range(action_count):
            attempts = self.attempts[action]
            rows.append(
                (
                    min(1.0, attempts / 6.0),
                    min(1.0, contextual[action] / 4.0),
                    float(self.last_progress[action]),
                    float(self.last_information[action]),
                    float(self.failures[action]) / max(1.0, float(attempts)),
                    *tuple(float(value) for value in self.last_effect[action]),
                )
            )
        return tuple(rows)

    def update(
        self,
        *,
        action: int,
        before: dict[str, object],
        after: dict[str, object],
        progress_delta: float,
        information_gain: float,
        failed: bool,
    ) -> None:
        if not 0 <= action < self.max_actions:
            raise ValueError("action index is outside memory capacity")
        before_state = _state3(before)
        after_state = _state3(after)
        before_charge, before_gate = _resource_pair(before)
        after_charge, after_gate = _resource_pair(after)
        effect = [
            max(-1.0, min(1.0, (after_state[i] - before_state[i]) / 4.0))
            for i in range(3)
        ]
        effect.extend(
            (
                max(-1.0, min(1.0, (after_charge - before_charge) / 3.0)),
                max(-1.0, min(1.0, after_gate - before_gate)),
            )
        )
        self.attempts[action] += 1
        context = _context_key(before)
        bucket = self.context_attempts.setdefault(context, [0] * self.max_actions)
        bucket[action] += 1
        self.last_progress[action] = float(progress_delta)
        self.last_information[action] = float(information_gain)
        self.failures[action] += int(bool(failed))
        self.last_effect[action] = effect


@dataclass(frozen=True)
class PublicTeacherStep:
    observation_text: str
    action_descriptions: tuple[str, ...]
    action_memory: tuple[tuple[float, ...], ...]
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


def _public_exploration_action(
    task,
    *,
    action_memory: PublicActionMemory,
    post_gate_explored: set[int],
) -> int | None:
    observation = task.observe()
    descriptions = tuple(str(value) for value in task.action_descriptions)
    non_submit = [
        index
        for index, description in enumerate(descriptions)
        if "submit" not in description.lower()
    ]
    context = _context_key(observation)
    contextual = action_memory.context_attempts.setdefault(
        context, [0] * action_memory.max_actions
    )

    if task.family == "causal_prerequisites":
        resources = observation.get("resources")
        if not isinstance(resources, dict):
            raise ValueError("public prerequisite observation is missing resources")
        gate_open = int(resources.get("gate_open", 0))
        charge = int(resources.get("charge_level", 0))
        if gate_open:
            candidates = [
                index for index in non_submit
                if index not in post_gate_explored
            ]
            if candidates:
                return min(candidates, key=lambda index: descriptions[index])
            return None

        target_repeats = 3 if charge < 2 else 4
        candidates = [
            index for index in non_submit
            if contextual[index] < target_repeats
        ]
        if candidates:
            return min(
                candidates,
                key=lambda index: (contextual[index], descriptions[index]),
            )
        return None

    repeats = 1 if task.family == "regime_switch" else 2
    candidates = [
        index for index in non_submit
        if contextual[index] < repeats
    ]
    if candidates:
        return min(
            candidates,
            key=lambda index: (contextual[index], descriptions[index]),
        )
    return None


def collect_public_teacher_episode(
    task,
    *,
    oracle_plan,
    max_steps: int | None = None,
) -> PublicTeacherEpisode:
    if task.split != "train":
        raise ValueError("public teacher collection is train-split only")
    action_memory = PublicActionMemory(max_actions=6)
    post_gate_explored: set[int] = set()
    previous_action = -1
    previous_feedback = (0.0, 0.0, 0.0)
    rows: list[PublicTeacherStep] = []
    limit = (
        task.budget_remaining
        if max_steps is None
        else min(task.budget_remaining, int(max_steps))
    )

    while not task.done and len(rows) < limit:
        plan = oracle_plan(copy.deepcopy(task))
        if not plan:
            break
        observation = task.observe()
        descriptions = tuple(str(value) for value in task.action_descriptions)
        proposal = _public_exploration_action(
            task,
            action_memory=action_memory,
            post_gate_explored=post_gate_explored,
        )
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

        memory_features = action_memory.features(
            observation,
            action_count=len(descriptions),
        )
        rows.append(
            PublicTeacherStep(
                observation_text=task.render_observation(),
                action_descriptions=descriptions,
                action_memory=memory_features,
                previous_action=previous_action,
                previous_feedback=previous_feedback,
                target_action=target,
            )
        )

        result = task.step(target)
        action_memory.update(
            action=target,
            before=observation,
            after=result.observation,
            progress_delta=float(result.progress_delta),
            information_gain=float(result.information_gain),
            failed=bool(result.failed),
        )
        resources = (
            result.observation.get("resources")
            if isinstance(result.observation, dict)
            else None
        )
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
    action_memory_dim: int,
) -> dict[str, Tensor]:
    if action_memory_dim != ACTION_MEMORY_DIM:
        raise ValueError("unsupported public action-memory dimension")
    action_tokens, action_mask = encode_public_actions(
        row.action_descriptions,
        max_actions=max_actions,
        max_bytes=action_bytes,
    )
    action_memory = torch.zeros(max_actions, action_memory_dim, dtype=torch.float32)
    if len(row.action_memory) != len(row.action_descriptions):
        raise ValueError("action-memory rows must match public actions")
    for index, values in enumerate(row.action_memory):
        if len(values) != action_memory_dim:
            raise ValueError("action-memory row has invalid width")
        action_memory[index] = torch.tensor(values, dtype=torch.float32)
    return {
        "observation_tokens": encode_public_text(
            row.observation_text,
            max_bytes=observation_bytes,
        ).unsqueeze(0),
        "action_tokens": action_tokens.unsqueeze(0),
        "action_mask": action_mask.unsqueeze(0),
        "action_memory": action_memory.unsqueeze(0),
        "previous_action": torch.tensor([row.previous_action], dtype=torch.long),
        "previous_feedback": torch.tensor(
            [row.previous_feedback],
            dtype=torch.float32,
        ),
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
