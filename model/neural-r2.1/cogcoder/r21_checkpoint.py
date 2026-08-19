from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import torch
from torch import Tensor

from .r21_recursive_core import (
    MAX_R21_DELTA_PARAMETERS,
    R20I_EFFECTIVE_PARAMETERS,
    R21_PARAMETER_CEILING,
    RecursiveLatentIntelligenceCore,
    r21_parameter_count,
)

R20I_BUNDLE_FORMAT = "nolane-r2.0i-hybrid-standalone-bundle-v1"
R21_DELTA_FORMAT = "nolane-neural-r2.1-recursive-latent-delta-v1"
R21_BUNDLE_FORMAT = "nolane-neural-r2.1-recursive-latent-one-weight-v1"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _state_for_storage(core: RecursiveLatentIntelligenceCore, storage_dtype: str) -> dict[str, Tensor]:
    if storage_dtype not in {"float16", "float32"}:
        raise ValueError("storage_dtype must be float16 or float32")
    dtype = torch.float16 if storage_dtype == "float16" else torch.float32
    return {
        name: value.detach().cpu().to(dtype=dtype) if value.is_floating_point() else value.detach().cpu()
        for name, value in core.state_dict().items()
    }


def save_r21_delta(
    path: str | Path,
    core: RecursiveLatentIntelligenceCore,
    *,
    parent_checkpoint: str | Path,
    storage_dtype: str = "float16",
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parent_checkpoint = Path(parent_checkpoint)
    if not parent_checkpoint.is_file():
        raise FileNotFoundError(parent_checkpoint)
    parent_payload = torch.load(parent_checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(parent_payload, dict) or parent_payload.get("format") != R20I_BUNDLE_FORMAT:
        raise ValueError("R2.1 requires an R2.0i one-weight parent")
    parent_effective = int(parent_payload.get("effective_parameters", 0))
    if parent_effective != R20I_EFFECTIVE_PARAMETERS:
        raise ValueError("unexpected R2.0i effective parameter count")

    delta_parameters = r21_parameter_count(core)
    candidate = parent_effective + delta_parameters
    if delta_parameters > MAX_R21_DELTA_PARAMETERS or candidate > R21_PARAMETER_CEILING:
        raise ValueError("R2.1 parameter budget exceeded")

    payload = {
        "format": R21_DELTA_FORMAT,
        "version": "Neural-R2.1-Recursive-Latent-Intelligence-Core",
        "architecture": core.architecture(),
        "parent_format": R20I_BUNDLE_FORMAT,
        "parent_sha256": sha256_file(parent_checkpoint),
        "parent_effective_parameters": parent_effective,
        "delta_parameters": delta_parameters,
        "candidate_effective_parameters": candidate,
        "storage_dtype": storage_dtype,
        "core_state": _state_for_storage(core, storage_dtype),
        "report": dict(report or {}),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    return {
        "format": R21_DELTA_FORMAT,
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "parent_sha256": payload["parent_sha256"],
        "delta_parameters": delta_parameters,
        "candidate_effective_parameters": candidate,
        "storage_dtype": storage_dtype,
    }


def _core_from_delta_payload(payload: dict[str, Any]) -> RecursiveLatentIntelligenceCore:
    if payload.get("format") != R21_DELTA_FORMAT:
        raise ValueError("unsupported R2.1 neural delta format")
    architecture = payload.get("architecture")
    state = payload.get("core_state")
    if not isinstance(architecture, dict) or not isinstance(state, dict):
        raise ValueError("R2.1 delta is incomplete")
    core = RecursiveLatentIntelligenceCore(**{key: int(value) for key, value in architecture.items()})
    incompatible = core.load_state_dict(state, strict=True)
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise ValueError("R2.1 delta state is incompatible with its architecture")
    expected = int(payload.get("delta_parameters", -1))
    if r21_parameter_count(core) != expected:
        raise ValueError("R2.1 delta parameter accounting mismatch")
    core.eval()
    return core


def load_r21_delta(
    path: str | Path,
    *,
    expected_parent_checkpoint: str | Path | None = None,
) -> tuple[RecursiveLatentIntelligenceCore, dict[str, Any]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict):
        raise ValueError("R2.1 delta payload must be a mapping")
    if expected_parent_checkpoint is not None:
        actual = sha256_file(expected_parent_checkpoint)
        if actual != payload.get("parent_sha256"):
            raise ValueError("parent checkpoint SHA-256 mismatch")
    core = _core_from_delta_payload(payload)
    metadata = {key: value for key, value in payload.items() if key != "core_state"}
    return core, metadata


def build_r21_one_weight_bundle(
    parent_checkpoint: str | Path,
    delta_checkpoint: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    parent_checkpoint = Path(parent_checkpoint)
    delta_checkpoint = Path(delta_checkpoint)
    parent_payload = torch.load(parent_checkpoint, map_location="cpu", weights_only=True)
    delta_payload = torch.load(delta_checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(parent_payload, dict) or parent_payload.get("format") != R20I_BUNDLE_FORMAT:
        raise ValueError("unsupported R2.0i parent format")
    if not isinstance(delta_payload, dict) or delta_payload.get("format") != R21_DELTA_FORMAT:
        raise ValueError("unsupported R2.1 delta format")
    parent_sha = sha256_file(parent_checkpoint)
    if delta_payload.get("parent_sha256") != parent_sha:
        raise ValueError("R2.1 delta is not bound to the supplied R2.0i parent")
    _core_from_delta_payload(delta_payload)
    effective = int(delta_payload["candidate_effective_parameters"])
    payload = {
        "format": R21_BUNDLE_FORMAT,
        "version": "Neural-R2.1-Recursive-Latent-Intelligence-Core",
        "effective_parameters": effective,
        "parent_sha256": parent_sha,
        "delta_sha256": sha256_file(delta_checkpoint),
        "r20i_bundle": parent_payload,
        "r21_delta": delta_payload,
        "claim_boundary": (
            "Single-file neural bundle containing the accepted R2.0i weights and the R2.1 recursive neural delta. "
            "Runtime depth reuses one R2.1 reasoning cell and does not add parameters."
        ),
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, output_path)
    return {
        "format": R21_BUNDLE_FORMAT,
        "path": str(output_path),
        "sha256": sha256_file(output_path),
        "bytes": output_path.stat().st_size,
        "effective_parameters": effective,
        "parent_sha256": parent_sha,
        "delta_sha256": payload["delta_sha256"],
    }


def load_r21_one_weight_bundle(
    path: str | Path,
) -> tuple[RecursiveLatentIntelligenceCore, dict[str, Any], dict[str, Any]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != R21_BUNDLE_FORMAT:
        raise ValueError("unsupported R2.1 one-weight bundle format")
    parent_payload = payload.get("r20i_bundle")
    delta_payload = payload.get("r21_delta")
    if not isinstance(parent_payload, dict) or parent_payload.get("format") != R20I_BUNDLE_FORMAT:
        raise ValueError("R2.1 bundle has an invalid parent payload")
    if not isinstance(delta_payload, dict):
        raise ValueError("R2.1 bundle is missing its neural delta")
    core = _core_from_delta_payload(delta_payload)
    effective = int(payload.get("effective_parameters", -1))
    if effective != int(delta_payload.get("candidate_effective_parameters", -2)):
        raise ValueError("R2.1 bundle effective-parameter accounting mismatch")
    metadata = {key: value for key, value in payload.items() if key not in {"r20i_bundle", "r21_delta"}}
    return core, parent_payload, metadata
