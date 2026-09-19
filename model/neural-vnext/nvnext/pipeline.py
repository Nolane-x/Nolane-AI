from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import torch
from torch import Tensor, nn

from .multidepth import MultiDepthObjective
from .training import (
    VerifiedMultiDepthTargets,
    sample_multidepth_steps,
    train_vnext_step,
)

CACHE_FORMAT = "nolane-neural-vnext-verified-state-cache-v1"
CANDIDATE_FORMAT = "nolane-neural-vnext-multidepth-delta-v1"
PARENT_FRESH_RANGE = (1080, 1119)
MODEL_INPUT_KEYS = (
    "state",
    "context",
    "action_embeddings",
    "parent_effects",
    "imagined_effects",
    "evidence_effects",
    "action_memory",
    "imagined_uncertainty",
    "imagined_value",
    "base_action_logits",
    "progress",
    "budget_fraction",
    "previous_feedback",
    "base_stop_logit",
    "base_success_probability",
)


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json_file(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def load_predev_lock(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported Neural vNext predevelopment lock")
    return payload


def locked_fresh_indices(lock: Mapping[str, object]) -> frozenset[int]:
    fresh = lock.get("confirmatory_fresh")
    if not isinstance(fresh, Mapping):
        raise ValueError("predevelopment lock is missing confirmatory_fresh")
    result = set(range(PARENT_FRESH_RANGE[0], PARENT_FRESH_RANGE[1] + 1))
    for name in ("block_1_indices", "block_2_indices"):
        bounds = fresh.get(name)
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or type(bounds[0]) is not int
            or type(bounds[1]) is not int
            or bounds[0] > bounds[1]
        ):
            raise ValueError(f"{name} must be an exact integer inclusive range")
        result.update(range(bounds[0], bounds[1] + 1))
    return frozenset(result)


@dataclass(frozen=True)
class VerifiedStateRecord:
    source_index: int
    family: str
    source_kind: str
    expert_action: int
    proof_weight: float
    inputs: dict[str, Tensor]

    @property
    def action_count(self) -> int:
        return int(self.inputs["base_action_logits"].shape[0])


def _require_tensor(mapping: Mapping[str, object], name: str) -> Tensor:
    value = mapping.get(name)
    if not isinstance(value, Tensor):
        raise ValueError(f"{name} must be a tensor")
    return value


def _validate_record(raw: Mapping[str, object], *, forbidden_indices: frozenset[int]) -> VerifiedStateRecord:
    source_index = raw.get("source_index")
    if type(source_index) is not int or source_index < 0:
        raise ValueError("source_index must be an exact non-negative integer")
    if source_index in forbidden_indices:
        raise ValueError(f"training cache touches locked fresh index {source_index}")

    family = raw.get("family")
    if not isinstance(family, str) or not family.strip():
        raise ValueError("family must be a non-empty string")
    source_kind = raw.get("source_kind")
    if source_kind not in {"expert", "dagger"}:
        raise ValueError("source_kind must be 'expert' or 'dagger'")
    if raw.get("proof_verified") is not True:
        raise ValueError("training records require proof_verified=true")

    expert_action = raw.get("expert_action")
    if type(expert_action) is not int or expert_action < 0:
        raise ValueError("expert_action must be an exact non-negative integer")
    proof_weight = raw.get("proof_weight", 1.0)
    if (
        not isinstance(proof_weight, (int, float))
        or isinstance(proof_weight, bool)
        or not math.isfinite(float(proof_weight))
        or float(proof_weight) <= 0.0
    ):
        raise ValueError("proof_weight must be a finite positive number")

    inputs_raw = raw.get("inputs")
    if not isinstance(inputs_raw, Mapping):
        raise ValueError("inputs must be a mapping")
    missing = [name for name in MODEL_INPUT_KEYS if name not in inputs_raw]
    if missing:
        raise ValueError(f"training record is missing model inputs: {missing}")
    extra = sorted(set(inputs_raw) - set(MODEL_INPUT_KEYS))
    if extra:
        raise ValueError(f"training record contains unsupported model inputs: {extra}")
    inputs = {name: _require_tensor(inputs_raw, name) for name in MODEL_INPUT_KEYS}

    state = inputs["state"]
    context = inputs["context"]
    action_embeddings = inputs["action_embeddings"]
    if state.ndim != 1 or context.ndim != 1 or action_embeddings.ndim != 2:
        raise ValueError("state/context/action_embeddings must be unbatched tensors")
    actions = int(action_embeddings.shape[0])
    if actions < 1:
        raise ValueError("training record must contain at least one action")
    if expert_action >= actions:
        raise ValueError("expert_action is outside the available action set")

    for name in ("parent_effects", "imagined_effects", "evidence_effects", "action_memory"):
        value = inputs[name]
        if value.ndim != 2 or value.shape[0] != actions:
            raise ValueError(f"{name} must be unbatched [actions, features]")
    for name in ("imagined_uncertainty", "imagined_value", "base_action_logits"):
        value = inputs[name]
        if value.shape != (actions,):
            raise ValueError(f"{name} must be unbatched [actions]")
    if inputs["progress"].shape != (1,) or inputs["budget_fraction"].shape != (1,):
        raise ValueError("progress and budget_fraction must be [1]")
    if inputs["previous_feedback"].shape != (3,):
        raise ValueError("previous_feedback must be [3]")
    if inputs["base_stop_logit"].ndim != 0 or inputs["base_success_probability"].ndim != 0:
        raise ValueError("base stop/success values must be scalar tensors")

    return VerifiedStateRecord(
        source_index=source_index,
        family=family,
        source_kind=str(source_kind),
        expert_action=expert_action,
        proof_weight=float(proof_weight),
        inputs=inputs,
    )


def load_verified_training_cache(
    path: str | Path,
    *,
    predev_lock: Mapping[str, object],
) -> list[VerifiedStateRecord]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != CACHE_FORMAT:
        raise ValueError("unsupported Neural vNext training-cache format")
    raw_records = payload.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("verified training cache must contain records")
    forbidden = locked_fresh_indices(predev_lock)
    records: list[VerifiedStateRecord] = []
    seen: set[tuple[int, str, str]] = set()
    for raw in raw_records:
        if not isinstance(raw, Mapping):
            raise ValueError("training cache records must be mappings")
        record = _validate_record(raw, forbidden_indices=forbidden)
        identity = (record.source_index, record.family, record.source_kind)
        if identity in seen:
            raise ValueError(f"duplicate training record identity: {identity}")
        seen.add(identity)
        records.append(record)
    return records


def collate_verified_records(
    records: Sequence[VerifiedStateRecord],
) -> tuple[dict[str, Tensor], VerifiedMultiDepthTargets]:
    if not records:
        raise ValueError("cannot collate an empty verified batch")
    actions = records[0].action_count
    proof_weight = records[0].proof_weight
    if any(record.action_count != actions for record in records):
        raise ValueError("a training batch must use one action-count shape")
    if any(record.proof_weight != proof_weight for record in records):
        raise ValueError("a training batch must use one proof weight")
    inputs = {
        name: torch.stack([record.inputs[name] for record in records], dim=0)
        for name in MODEL_INPUT_KEYS
    }
    targets = VerifiedMultiDepthTargets(
        expert_actions=torch.tensor([record.expert_action for record in records], dtype=torch.long),
        proof_weight=torch.tensor([record.proof_weight for record in records], dtype=torch.float32),
    )
    return inputs, targets


def iter_verified_batches(
    records: Sequence[VerifiedStateRecord],
    *,
    batch_size: int,
    generator: torch.Generator | None = None,
) -> Iterable[tuple[dict[str, Tensor], VerifiedMultiDepthTargets]]:
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch_size must be a positive exact integer")
    groups: dict[tuple[int, float], list[VerifiedStateRecord]] = {}
    for record in records:
        groups.setdefault((record.action_count, record.proof_weight), []).append(record)
    for key in sorted(groups):
        group = groups[key]
        order = torch.randperm(len(group), generator=generator).tolist()
        for start in range(0, len(order), batch_size):
            yield collate_verified_records([group[index] for index in order[start : start + batch_size]])


def run_training_epoch(
    reasoner: nn.Module,
    records: Sequence[VerifiedStateRecord],
    optimizer: torch.optim.Optimizer,
    *,
    batch_size: int,
    generator: torch.Generator | None = None,
    objective: MultiDepthObjective | None = None,
    min_steps: int = 2,
    max_steps: int = 4,
    max_grad_norm: float = 1.0,
) -> dict[str, float]:
    totals: dict[str, float] = {}
    batches = 0
    for inputs, targets in iter_verified_batches(records, batch_size=batch_size, generator=generator):
        depth = sample_multidepth_steps(generator=generator, min_steps=min_steps, max_steps=max_steps)
        metrics = train_vnext_step(
            reasoner,
            inputs,
            targets,
            optimizer,
            reasoning_steps=depth,
            objective=objective,
            max_grad_norm=max_grad_norm,
        )
        for name, value in metrics.items():
            totals[name] = totals.get(name, 0.0) + float(value)
        batches += 1
    if batches < 1:
        raise ValueError("training epoch produced no batches")
    return {name: value / batches for name, value in totals.items()} | {"batches": float(batches)}


def state_dict_sha256(state_dict: Mapping[str, Tensor]) -> str:
    digest = sha256()
    for name in sorted(state_dict):
        tensor = state_dict[name]
        if not isinstance(tensor, Tensor):
            raise ValueError("candidate state_dict may contain tensors only")
        value = tensor.detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(json.dumps(list(value.shape), separators=(",", ":")).encode("ascii"))
        digest.update(b"\0")
        digest.update(value.reshape(-1).view(torch.uint8).numpy().tobytes())
        digest.update(b"\0")
    return digest.hexdigest()


def save_frozen_candidate(
    reasoner: nn.Module,
    path: str | Path,
    *,
    parent_one_weight_sha256: str,
    predev_lock_sha256: str,
    physical_parameters: int,
    adaptive_depth: Mapping[str, object],
    training_summary: Mapping[str, object],
    physical_parameter_ceiling: int = 80_000_000,
) -> dict[str, object]:
    for name, value in (
        ("parent_one_weight_sha256", parent_one_weight_sha256),
        ("predev_lock_sha256", predev_lock_sha256),
    ):
        if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    if type(physical_parameters) is not int or physical_parameters < 1:
        raise ValueError("physical_parameters must be a positive exact integer")
    if type(physical_parameter_ceiling) is not int or physical_parameter_ceiling < physical_parameters:
        raise ValueError("candidate exceeds the physical parameter ceiling")
    if not hasattr(reasoner, "architecture") or not callable(getattr(reasoner, "architecture")):
        raise ValueError("reasoner must expose architecture()")

    state = {name: value.detach().cpu().clone() for name, value in reasoner.state_dict().items()}
    state_sha = state_dict_sha256(state)
    reasoner_parameters = sum(parameter.numel() for parameter in reasoner.parameters())
    bundle = {
        "format": CANDIDATE_FORMAT,
        "status": "FROZEN_BEFORE_FRESH",
        "parent_one_weight_sha256": parent_one_weight_sha256,
        "predev_lock_sha256": predev_lock_sha256,
        "physical_parameters": physical_parameters,
        "reasoner_parameters": reasoner_parameters,
        "architecture": dict(reasoner.architecture()),
        "adaptive_depth": dict(adaptive_depth),
        "training_summary": dict(training_summary),
        "state_dict_sha256": state_sha,
        "state_dict": state,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(bundle, destination)
    manifest = {
        key: value
        for key, value in bundle.items()
        if key != "state_dict"
    }
    manifest["bundle_sha256"] = sha256_file(destination)
    return manifest


def load_frozen_candidate(
    path: str | Path,
    *,
    reasoner_factory: Callable[..., nn.Module],
) -> tuple[nn.Module, dict[str, object]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != CANDIDATE_FORMAT:
        raise ValueError("unsupported Neural vNext candidate bundle")
    if payload.get("status") != "FROZEN_BEFORE_FRESH":
        raise ValueError("candidate bundle is not frozen for fresh evaluation")
    architecture = payload.get("architecture")
    state = payload.get("state_dict")
    if not isinstance(architecture, dict) or not isinstance(state, dict):
        raise ValueError("candidate bundle is missing architecture/state")
    expected_digest = payload.get("state_dict_sha256")
    if state_dict_sha256(state) != expected_digest:
        raise ValueError("candidate tensor digest mismatch")
    reasoner = reasoner_factory(**architecture)
    reasoner.load_state_dict(state, strict=True)
    reasoner.eval()
    actual_parameters = sum(parameter.numel() for parameter in reasoner.parameters())
    if actual_parameters != payload.get("reasoner_parameters"):
        raise ValueError("candidate reasoner parameter audit mismatch")
    metadata = {key: value for key, value in payload.items() if key != "state_dict"}
    metadata["bundle_sha256"] = sha256_file(path)
    return reasoner, metadata
