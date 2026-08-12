from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

import torch

from .neural_system2 import NeuralSystem2Workspace, system2_parameter_count

R1_2_EFFECTIVE_PARAMETERS = 49_528_677
PARAMETER_CEILING = 75_000_000
CHECKPOINT_FORMAT = "nolane-r1.6-neural-system2-v1"


def sha256_file(path: Path) -> str:
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _architecture(model: NeuralSystem2Workspace) -> dict[str, int]:
    return {
        "d_model": model.d_model,
        "workspace_dim": model.workspace_dim,
        "slot_count": model.slot_count,
        "n_heads": model.n_heads,
        "ff_mult": model.ff_mult,
        "action_embedding_dim": model.action_embedding_dim,
        "action_gru_hidden": model.action_gru_hidden,
        "observation_embedding_dim": model.observation_embedding_dim,
        "observation_gru_hidden": model.observation_gru_hidden,
        "action_memory_dim": model.action_memory_dim,
        "feedback_dim": model.feedback_dim,
        "structured_atom_dim": model.structured_atom_dim,
        "structured_layers": model.structured_layers,
        "failure_penalty_weight": model.failure_penalty_weight,
        "max_refinement_steps": model.max_refinement_steps,
    }


def save_system2_checkpoint(
    path: Path,
    model: NeuralSystem2Workspace,
    *,
    r1_2_checkpoint: Path,
    r1_2_effective_parameters: int = R1_2_EFFECTIVE_PARAMETERS,
    report: Mapping[str, object] | None = None,
) -> dict[str, object]:
    path = Path(path)
    parent = Path(r1_2_checkpoint)
    if not parent.is_file():
        raise FileNotFoundError(parent)
    added = system2_parameter_count(model)
    candidate = int(r1_2_effective_parameters) + added
    if candidate >= PARAMETER_CEILING:
        raise RuntimeError(
            f"R1.6 candidate violates parameter ceiling: {candidate:,} >= {PARAMETER_CEILING:,}"
        )
    payload = {
        "format": CHECKPOINT_FORMAT,
        "architecture": _architecture(model),
        "r1_2_sha256": sha256_file(parent),
        "r1_2_effective_parameters": int(r1_2_effective_parameters),
        "system2_parameters": added,
        "candidate_effective_parameters": candidate,
        "model_state": {name: value.detach().cpu() for name, value in model.state_dict().items()},
        "report": dict(report or {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    metadata = {key: value for key, value in payload.items() if key != "model_state"}
    metadata.update({"sha256": sha256_file(path), "bytes": path.stat().st_size})
    return metadata


def load_system2_checkpoint(
    path: Path,
    *,
    expected_r1_2_checkpoint: Path | None = None,
) -> tuple[NeuralSystem2Workspace, dict[str, object]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=False)
    if payload.get("format") != CHECKPOINT_FORMAT:
        raise RuntimeError("unsupported R1.6 Neural System-2 checkpoint")
    if expected_r1_2_checkpoint is not None:
        actual = sha256_file(Path(expected_r1_2_checkpoint))
        if actual != payload.get("r1_2_sha256"):
            raise RuntimeError("parent checkpoint SHA-256 mismatch")
    architecture = payload.get("architecture") or {}
    model = NeuralSystem2Workspace(
        d_model=int(architecture["d_model"]),
        workspace_dim=int(architecture["workspace_dim"]),
        slot_count=int(architecture["slot_count"]),
        n_heads=int(architecture["n_heads"]),
        ff_mult=int(architecture["ff_mult"]),
        action_embedding_dim=int(architecture["action_embedding_dim"]),
        action_gru_hidden=int(architecture["action_gru_hidden"]),
        observation_embedding_dim=int(architecture.get("observation_embedding_dim", 128)),
        observation_gru_hidden=int(architecture.get("observation_gru_hidden", 320)),
        action_memory_dim=int(architecture.get("action_memory_dim", 256)),
        feedback_dim=int(architecture.get("feedback_dim", 3)),
        structured_atom_dim=int(architecture.get("structured_atom_dim", 256)),
        structured_layers=int(architecture.get("structured_layers", 2)),
        failure_penalty_weight=float(architecture.get("failure_penalty_weight", 1.0)),
        max_refinement_steps=int(architecture["max_refinement_steps"]),
    )
    incompatible = model.load_state_dict(payload["model_state"], strict=False)
    missing = set(incompatible.missing_keys)
    allowed_missing = {"structured_delta_encoder.weight"}
    allowed_missing.update(key for key in missing if key.startswith("readiness_head."))
    allowed_missing.update(key for key in missing if key.startswith("termination_head."))
    allowed_missing.update(key for key in missing if key.startswith("causal_memory_policy_key."))
    allowed_missing.add("causal_memory_policy_scale")
    allowed_missing.update(key for key in missing if key.startswith("causal_evidence_"))
    allowed_missing.update(key for key in missing if key.startswith("dual_role_causal_"))
    allowed_missing.update(key for key in missing if key.startswith("effect_progress_critic."))
    allowed_missing.update(key for key in missing if key.startswith("rule_program_"))
    allowed_missing.update(key for key in missing if key.startswith("distance_head."))
    allowed_missing.add("distance_policy_scale")
    allowed_missing.update(key for key in missing if key.startswith("plan_state_projection."))
    allowed_missing.update(key for key in missing if key.startswith("plan_action_projection."))
    allowed_missing.update(key for key in missing if key.startswith("plan_action_norm."))
    allowed_missing.update(key for key in missing if key.startswith("plan_update."))
    allowed_missing.add("plan_step_embedding")
    allowed_missing.add("plan_policy_scale")
    allowed_missing.update(key for key in missing if key.startswith("next_delta_magnitude_head."))
    allowed_missing.update(key for key in missing if key.startswith("psr_"))
    if missing - allowed_missing or incompatible.unexpected_keys:
        raise RuntimeError(
            f"checkpoint/model mismatch: missing={incompatible.missing_keys}, "
            f"unexpected={incompatible.unexpected_keys}"
        )
    metadata = {key: value for key, value in payload.items() if key != "model_state"}
    return model, metadata


def dual_role_trainable_parameter_names(model) -> list[str]:
    """Return the exact optimizer scope for the dual-role causal binder."""
    names = [name for name, _ in model.named_parameters() if name.startswith("dual_role_")]
    if not names:
        raise ValueError("model exposes no dual_role_ parameters")
    return names


def effect_progress_trainable_parameter_names(model) -> list[str]:
    """Return the isolated optimizer scope for the Effect-to-Progress critic."""
    names = [name for name, _ in model.named_parameters() if name.startswith("effect_progress_critic.")]
    if not names:
        raise ValueError("model exposes no effect_progress_critic parameters")
    return names


def rule_program_trainable_parameter_names(model) -> list[str]:
    """Return the isolated optimizer scope for the dynamic program prior."""
    names = [name for name, _ in model.named_parameters() if name.startswith("rule_program_")]
    if not names:
        raise ValueError("model exposes no rule_program_ parameters")
    return names
