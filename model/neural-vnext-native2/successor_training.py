from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import torch

HERE = Path(__file__).resolve()
ROOT = HERE.parent
MODEL_ROOT = ROOT.parent
PARENT_ROOT = MODEL_ROOT / "neural-vnext-native"
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (PARENT_ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task, oracle_plan  # noqa: E402
from native_core import NativeRecurrentPolicy, parameter_count, state_dict_sha256  # noqa: E402
from native_training import (  # noqa: E402
    configure_training_scope,
    evaluate_policy,
    load_lock,
    train_native_policy,
)
from successor_core import SuccessorResidualPolicy, successor_parameter_count  # noqa: E402

SUCCESSOR_CHECKPOINT_FORMAT = "nolane-neural-vnext-native2-residual-v1"


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def configure_deterministic_runtime(seed: int) -> dict[str, Any]:
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    torch.use_deterministic_algorithms(True)
    torch.backends.mkldnn.enabled = False
    torch.set_float32_matmul_precision("highest")
    torch.set_flush_denormal(True)
    torch.manual_seed(int(seed))
    return {
        "seed": int(seed),
        "deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "mkldnn_enabled": bool(torch.backends.mkldnn.enabled),
        "float32_matmul_precision": str(torch.get_float32_matmul_precision()),
        "num_threads": int(torch.get_num_threads()),
        "num_interop_threads": int(torch.get_num_interop_threads()),
    }


def _new_parent(architecture: Mapping[str, Any]) -> NativeRecurrentPolicy:
    return NativeRecurrentPolicy(
        global_dim=int(architecture["public_global_features"]),
        action_dim=int(architecture["public_action_features"]),
        hidden_dim=int(architecture["hidden_dim"]),
        attention_heads=int(architecture["attention_heads"]),
    )


def _clone_state_dict(model: torch.nn.Module) -> dict[str, torch.Tensor]:
    return {
        name: tensor.detach().cpu().clone()
        for name, tensor in model.state_dict().items()
    }


def reproduce_accepted_parent(
    *,
    parent_lock_path: str | Path = PARENT_ROOT / "PREDEV_LOCK.json",
    parent_authority_path: str | Path = PARENT_ROOT / "ACCEPTED_AUTHORITY.json",
) -> tuple[NativeRecurrentPolicy, dict[str, Any]]:
    lock = load_lock(parent_lock_path)
    authority = json.loads(Path(parent_authority_path).read_text(encoding="utf-8"))
    accepted = authority["accepted_candidate"]
    training = lock["training"]
    benchmark = lock["benchmark"]
    architecture = lock["architecture"]
    seed = int(training["seed"])

    runtime = configure_deterministic_runtime(seed)
    families = tuple(str(value) for value in benchmark["families"])
    train_indices = tuple(int(value) for value in benchmark["training_indices"])
    dev_indices = tuple(int(value) for value in benchmark["development_indices"])

    torch.manual_seed(seed)
    base = _new_parent(architecture)
    base_scope = configure_training_scope(base, "base")
    base_cfg = training["base_curriculum"]
    base_summary = train_native_policy(
        base,
        make_task=make_r18_task,
        oracle_plan=oracle_plan,
        families=families,
        train_indices=(train_indices[0], train_indices[1]),
        family_train_indices=training["base_family_training_indices"],
        seed=seed,
        expert_epochs=int(base_cfg["expert_epochs"]),
        dagger_teacher_mix=[float(value) for value in base_cfg["dagger_teacher_mix"]],
        learning_rate=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
        max_grad_norm=float(training["max_grad_norm"]),
        goal_loss_weight=0.0,
    )
    base_state = _clone_state_dict(base)

    selected_name = str(accepted["selected_candidate"])
    selected = None
    for candidate in training["hidden_goal_specialists"]:
        if str(candidate["name"]) == selected_name:
            selected = candidate
            break
    if selected is None:
        raise ValueError(f"accepted parent candidate missing from lock: {selected_name}")

    torch.manual_seed(seed)
    parent = _new_parent(architecture)
    parent.load_state_dict(base_state, strict=True)
    specialist_scope = configure_training_scope(parent, "hidden_goal")
    specialist_ranges = training["hidden_goal_family_training_indices"]
    specialist_summary = train_native_policy(
        parent,
        make_task=make_r18_task,
        oracle_plan=oracle_plan,
        families=("implicit_goal_regimes",),
        train_indices=(
            int(specialist_ranges["implicit_goal_regimes"][0]),
            int(specialist_ranges["implicit_goal_regimes"][1]),
        ),
        family_train_indices={
            "implicit_goal_regimes": specialist_ranges["implicit_goal_regimes"],
        },
        seed=seed,
        expert_epochs=int(selected["expert_epochs"]),
        dagger_teacher_mix=[float(value) for value in selected["dagger_teacher_mix"]],
        learning_rate=float(selected.get("learning_rate", training["learning_rate"])),
        weight_decay=float(training["weight_decay"]),
        max_grad_norm=float(training["max_grad_norm"]),
        goal_loss_weight=float(selected.get("goal_loss_weight", 0.0)),
    )

    actual_state = state_dict_sha256(parent.state_dict())
    expected_state = str(accepted["state_dict_sha256"])
    if actual_state != expected_state:
        raise ValueError(
            f"accepted parent state reproduction failed: expected {expected_state}, got {actual_state}"
        )
    if parameter_count(parent) != int(accepted["parameters"]):
        raise ValueError("accepted parent parameter count mismatch")

    dev = evaluate_policy(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=(dev_indices[0], dev_indices[1]),
    )
    expected_dev = int(authority["acceptance"]["development"]["solved"])
    if int(dev["solved"]) != expected_dev:
        raise ValueError(
            f"accepted parent dev reproduction failed: expected {expected_dev}, got {dev['solved']}"
        )

    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    parent.eval()
    return parent, {
        "runtime": runtime,
        "parent_state_dict_sha256": actual_state,
        "parent_parameters": parameter_count(parent),
        "parent_dev": {key: value for key, value in dev.items() if key != "rows"},
        "base_scope": base_scope,
        "specialist_scope": specialist_scope,
        "base_training": base_summary,
        "specialist_training": specialist_summary,
        "selected_parent_candidate": selected_name,
    }


def train_successor_candidate(
    *,
    parent_state: Mapping[str, torch.Tensor],
    parent_architecture: Mapping[str, Any],
    candidate: Mapping[str, Any],
    benchmark_families: Sequence[str],
    dev_indices: tuple[int, int],
    seed: int,
    weight_decay: float,
    max_grad_norm: float,
) -> tuple[SuccessorResidualPolicy, dict[str, Any], dict[str, Any]]:
    torch.manual_seed(int(seed))
    parent = _new_parent(parent_architecture)
    parent.load_state_dict(parent_state, strict=True)
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    parent.eval()

    torch.manual_seed(int(seed) + 1)
    model = SuccessorResidualPolicy(parent)
    scope = model.configure_successor_training()

    family_ranges = candidate["family_training_indices"]
    training_families = tuple(str(value) for value in family_ranges)
    unknown_families = set(training_families) - set(str(value) for value in benchmark_families)
    if unknown_families:
        raise ValueError(f"unknown successor training families: {sorted(unknown_families)}")
    summary = train_native_policy(
        model,
        make_task=make_r18_task,
        oracle_plan=oracle_plan,
        families=training_families,
        train_indices=(0, 0),
        family_train_indices=family_ranges,
        seed=int(seed) + 1,
        expert_epochs=int(candidate["expert_epochs"]),
        dagger_teacher_mix=[float(value) for value in candidate["dagger_teacher_mix"]],
        learning_rate=float(candidate["learning_rate"]),
        weight_decay=float(weight_decay),
        max_grad_norm=float(max_grad_norm),
        goal_loss_weight=0.0,
    )
    dev = evaluate_policy(
        model,
        make_task=make_r18_task,
        families=tuple(str(value) for value in benchmark_families),
        split="dev",
        indices=dev_indices,
    )
    return model, {
        "training": summary,
        "scope": scope,
        "parameters": successor_parameter_count(model),
    }, dev


def save_successor_checkpoint(
    model: SuccessorResidualPolicy,
    path: str | Path,
    *,
    lock_sha256: str,
    selected_candidate: str,
    training_summary: Mapping[str, Any],
    dev_result: Mapping[str, Any],
    parent_state_dict_sha256: str,
) -> dict[str, Any]:
    state = _clone_state_dict(model)
    state_sha = state_dict_sha256(state)
    counts = successor_parameter_count(model)
    payload = {
        "format": SUCCESSOR_CHECKPOINT_FORMAT,
        "status": "TRAINED_DEV_ONLY_FRESH_UNOPENED",
        "architecture": model.architecture(),
        "parameter_counts": counts,
        "predev_lock_sha256": str(lock_sha256),
        "parent_state_dict_sha256": str(parent_state_dict_sha256),
        "selected_candidate": str(selected_candidate),
        "training_summary": dict(training_summary),
        "dev_result": {key: value for key, value in dev_result.items() if key != "rows"},
        "state_dict_sha256": state_sha,
        "state_dict": state,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, destination)
    return {
        key: value for key, value in payload.items() if key != "state_dict"
    } | {"checkpoint_sha256": sha256_file(destination)}


def load_successor_checkpoint(
    path: str | Path,
) -> tuple[SuccessorResidualPolicy, dict[str, Any]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != SUCCESSOR_CHECKPOINT_FORMAT:
        raise ValueError("unsupported Neural vNext Native-2 checkpoint")
    architecture = payload.get("architecture")
    state = payload.get("state_dict")
    if not isinstance(architecture, dict) or not isinstance(state, dict):
        raise ValueError("successor checkpoint missing architecture/state")
    if state_dict_sha256(state) != payload.get("state_dict_sha256"):
        raise ValueError("successor checkpoint tensor digest mismatch")

    parent_architecture = architecture.get("parent_architecture")
    if not isinstance(parent_architecture, dict):
        raise ValueError("successor checkpoint missing parent architecture")
    parent = NativeRecurrentPolicy(**parent_architecture)
    model = SuccessorResidualPolicy(parent)
    model.load_state_dict(state, strict=True)

    counts = successor_parameter_count(model)
    if counts != payload.get("parameter_counts"):
        raise ValueError("successor parameter audit mismatch")
    model.eval()
    metadata = {key: value for key, value in payload.items() if key != "state_dict"}
    metadata["checkpoint_sha256"] = sha256_file(path)
    return model, metadata
