from __future__ import annotations

from dataclasses import dataclass
import random

import torch
from torch import Tensor

from .r27_codeworld_controller import ACTION_KINDS, CodeWorldControllerConfig

LANGUAGES: tuple[str, ...] = (
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
    "rust",
    "cpp",
    "c",
    "kotlin",
    "swift",
    "php",
    "ruby",
)
TASK_TYPES: tuple[str, ...] = (
    "bugfix",
    "feature",
    "refactor",
    "test_repair",
    "performance",
    "integration",
    "build_tooling",
    "code_review",
)


@dataclass(frozen=True)
class CurriculumRow:
    language_id: int
    task_type_id: int
    state_features: Tensor
    action_features: Tensor
    history_features: Tensor
    action_kinds: tuple[str, ...]
    target_action: str


def _target_for_stage(stage: int, risky: bool) -> str:
    if stage == 0:
        return "inspect_tree"
    if stage == 1:
        return "reproduce_failure"
    if stage == 2:
        return "search_code"
    if stage == 3:
        return "read_context"
    if stage == 4:
        return "edit_multi" if risky else "edit_small"
    if stage == 5:
        return "run_targeted_tests"
    if stage == 6:
        return "inspect_diff"
    if stage == 7:
        return "run_full_tests"
    return "finish"


def _state(stage: int, risky: bool, budget: int, cfg: CodeWorldControllerConfig) -> Tensor:
    values = torch.zeros(cfg.state_dim, dtype=torch.float32)
    flags = [
        stage >= 1,
        stage >= 2,
        stage >= 3,
        stage >= 5,
        stage >= 6,
        stage >= 8,
        stage >= 7,
    ]
    for index, flag in enumerate(flags):
        values[index] = float(flag)
    values[7] = float(risky)
    values[8] = min(1.0, stage / 9.0)
    values[9] = min(1.0, budget / 16.0)
    values[10] = 0.85 if risky else 0.15
    values[11] = float(stage >= 5 and risky)
    return values


def _action_features(
    cfg: CodeWorldControllerConfig, *, rng: random.Random, risky: bool
) -> Tensor:
    matrix = torch.zeros(len(ACTION_KINDS), cfg.action_feature_dim, dtype=torch.float32)
    for index, _kind in enumerate(ACTION_KINDS):
        matrix[index, index] = 1.0
        matrix[index, 12] = index / max(1, len(ACTION_KINDS) - 1)
        matrix[index, 13] = 1.0 if index in {4, 5, 9} else 0.0
        matrix[index, 14] = 1.0 if index in {6, 7} else 0.0
        matrix[index, 15] = 1.0 if risky and index == 5 else 0.0
        matrix[index, 16] = rng.random() * 0.05
    return matrix


def build_curriculum(
    *,
    seed: int = 27,
    episodes_per_pair: int = 24,
    config: CodeWorldControllerConfig | None = None,
) -> list[CurriculumRow]:
    cfg = config or CodeWorldControllerConfig()
    rng = random.Random(seed)
    rows: list[CurriculumRow] = []
    for language_id in range(min(len(LANGUAGES), cfg.language_count)):
        for task_type_id in range(min(len(TASK_TYPES), cfg.task_type_count)):
            for _ in range(episodes_per_pair):
                stage = rng.randrange(0, 10)
                risky = task_type_id in {2, 4, 5} and rng.random() < 0.65
                budget = rng.randrange(2, 17)
                history_len = rng.randrange(1, 7)
                history = torch.zeros(history_len, cfg.history_feature_dim, dtype=torch.float32)
                for step in range(history_len):
                    history[step, step % cfg.history_feature_dim] = 1.0
                    history[step, -1] = min(1.0, step / 6.0)
                rows.append(
                    CurriculumRow(
                        language_id=language_id,
                        task_type_id=task_type_id,
                        state_features=_state(stage, risky, budget, cfg),
                        action_features=_action_features(cfg, rng=rng, risky=risky),
                        history_features=history,
                        action_kinds=ACTION_KINDS,
                        target_action=_target_for_stage(stage, risky),
                    )
                )
    return rows


def _is_heldout_pair(language_id: int, task_type_id: int) -> bool:
    return ((language_id * 3 + task_type_id * 5 + 1) % 11) in {0, 1}


def split_by_language_task_pair(
    rows: list[CurriculumRow] | tuple[CurriculumRow, ...]
) -> tuple[list[CurriculumRow], list[CurriculumRow]]:
    train: list[CurriculumRow] = []
    heldout: list[CurriculumRow] = []
    for row in rows:
        destination = heldout if _is_heldout_pair(row.language_id, row.task_type_id) else train
        destination.append(row)
    return train, heldout
