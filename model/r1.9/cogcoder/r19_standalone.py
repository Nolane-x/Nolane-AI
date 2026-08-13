from __future__ import annotations

from pathlib import Path
from typing import Any

import torch

from .neural_system2 import NeuralSystem2Workspace
from .r19_frontier import FrontierRolloutHead

SUPPORTED_FORMATS = {
    "nolane-r1.9-standalone-bundle-fp16-storage-v1",
    "nolane-r1.9-standalone-bundle-v1",
}


def load_r19_standalone(path: str | Path) -> tuple[NeuralSystem2Workspace, FrontierRolloutHead, dict[str, Any]]:
    """Load the current Nolane R1.9 parent + rollout delta from one checkpoint file.

    FP16-storage bundles are loaded into ordinary FP32 PyTorch modules. This keeps
    the distribution artifact compact while preserving the runtime interfaces of
    the original R1.8 parent and R1.9 FrontierRollout head.
    """
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") not in SUPPORTED_FORMATS:
        raise ValueError("unsupported Nolane R1.9 standalone checkpoint format")

    parent_payload = payload.get("parent")
    delta_payload = payload.get("frontier_delta")
    if not isinstance(parent_payload, dict) or not isinstance(delta_payload, dict):
        raise ValueError("standalone checkpoint is missing parent or frontier delta")

    parent = NeuralSystem2Workspace(**dict(parent_payload["architecture"]))
    parent_incompatible = parent.load_state_dict(parent_payload["model_state"], strict=True)
    if parent_incompatible.missing_keys or parent_incompatible.unexpected_keys:
        raise ValueError("standalone parent state is incompatible with its architecture")

    head = FrontierRolloutHead(**dict(delta_payload["architecture"]))
    head_incompatible = head.load_state_dict(delta_payload["head_state"], strict=True)
    if head_incompatible.missing_keys or head_incompatible.unexpected_keys:
        raise ValueError("standalone frontier state is incompatible with its architecture")

    parent.eval()
    head.eval()
    metadata = {
        "version": payload.get("version"),
        "format": payload.get("format"),
        "effective_parameters": int(payload.get("effective_parameters", 0)),
        "storage_dtype": payload.get("storage_dtype", "float32"),
        "provenance": dict(payload.get("provenance", {})),
    }
    return parent, head, metadata
