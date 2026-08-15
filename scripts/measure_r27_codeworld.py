from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from cogcoder.r27_codeworld_controller import (
    CodeWorldController,
    CodeWorldControllerConfig,
    controller_parameter_count,
)
from cogcoder.r27_codeworld_curriculum import build_curriculum, split_by_language_task_pair
from scripts.train_r27_codeworld_controller import PARENT_EFFECTIVE_PARAMETERS, _accuracy


def evaluate_bundle(
    path: Path, *, seed: int = 27, episodes_per_pair: int = 24
) -> dict[str, float | int | str]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    delta = payload.get("r27_codeworld_delta")
    if not isinstance(delta, dict):
        raise RuntimeError("bundle does not contain r27_codeworld_delta")
    architecture = delta.get("architecture")
    state = delta.get("state")
    if not isinstance(architecture, dict) or not isinstance(state, dict):
        raise RuntimeError("invalid R2.7 controller payload")

    cfg = CodeWorldControllerConfig(**architecture)
    model = CodeWorldController(cfg)
    model.load_state_dict(state, strict=True)

    rows = build_curriculum(seed=seed, episodes_per_pair=episodes_per_pair, config=cfg)
    train_rows, heldout_rows = split_by_language_task_pair(rows)
    count = controller_parameter_count(model)
    return {
        "format": str(payload.get("format", "")),
        "version": str(payload.get("version", "")),
        "controller_parameters": count,
        "effective_parameters": int(payload.get("effective_parameters", PARENT_EFFECTIVE_PARAMETERS + count)),
        "parameter_increase_fraction": count / PARENT_EFFECTIVE_PARAMETERS,
        "train_rows": len(train_rows),
        "heldout_rows": len(heldout_rows),
        "train_accuracy": _accuracy(model, train_rows),
        "heldout_pair_accuracy": _accuracy(model, heldout_rows),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--episodes-per-pair", type=int, default=24)
    args = parser.parse_args()
    print(
        json.dumps(
            evaluate_bundle(
                args.bundle,
                seed=args.seed,
                episodes_per_pair=args.episodes_per_pair,
            ),
            indent=2,
            sort_keys=True,
        )
    )
