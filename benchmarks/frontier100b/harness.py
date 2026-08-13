from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any, Sequence


def _valid_grid(grid: Any) -> bool:
    if not isinstance(grid, list) or not grid:
        return False
    width = None
    for row in grid:
        if not isinstance(row, list) or not row:
            return False
        if width is None:
            width = len(row)
        if len(row) != width:
            return False
        if not all(isinstance(cell, int) for cell in row):
            return False
    return True


def score_arc_exact(predictions: Sequence[Any], target: Any) -> int:
    """ARC-style exact task score with at most two candidate outputs."""
    if not _valid_grid(target):
        raise ValueError("target must be a rectangular integer grid")
    for prediction in list(predictions)[:2]:
        if _valid_grid(prediction) and prediction == target:
            return 1
    return 0


def normalize_closed_answer(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("closed answer must be text")
    return re.sub(r"\s+", " ", text.strip()).casefold()


def score_closed_answer(prediction: str, target: str) -> bool:
    """Conservative closed-answer scorer; no semantic equivalence guessing."""
    return normalize_closed_answer(prediction) == normalize_closed_answer(target)


def validate_comparison_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate benchmark-claim provenance and forbid unmeasured >100B claims."""
    if not isinstance(record, dict):
        raise TypeError("comparison record must be a dictionary")
    suite = record.get("suite")
    if not isinstance(suite, str) or not suite:
        raise ValueError("suite is required")
    digest = record.get("locked_protocol_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("locked_protocol_sha256 must be a lowercase SHA-256")

    runs = record.get("reference_runs", [])
    if not isinstance(runs, list):
        raise ValueError("reference_runs must be a list")
    qualifying = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        parameter_count = run.get("parameter_count")
        score = run.get("score")
        budget = run.get("budget")
        model = run.get("model")
        evaluated = run.get("evaluated") is True
        if (
            isinstance(model, str)
            and model.strip()
            and isinstance(parameter_count, int)
            and parameter_count > 100_000_000_000
            and evaluated
            and isinstance(score, (int, float))
            and math.isfinite(float(score))
            and isinstance(budget, dict)
            and budget
        ):
            qualifying.append(run)

    if record.get("hard_for_gt100b") is True and not qualifying:
        raise ValueError("hard_for_gt100b requires at least one evaluated >100B reference run")
    return deepcopy(record)
