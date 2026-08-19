from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import torch

from .r21_causal_router import CausalEvidenceRouter, r21a_parameter_count

R20I_FORMAT = "nolane-r2.0i-hybrid-standalone-bundle-v1"
R21A_DELTA_FORMAT = "nolane-neural-r2.1a-causal-evidence-router-delta-v1"
R21A_BUNDLE_FORMAT = "nolane-neural-r2.1a-causal-evidence-router-one-weight-v1"

# Compatibility accounting inherited from the pre-existing neural release line.
# The name R20I_EFFECTIVE_PARAMETERS remains public for old callers, but must
# not be interpreted as a physical unique tensor count.
R20I_LEGACY_EFFECTIVE_PARAMETERS = 78_779_253
R20I_EFFECTIVE_PARAMETERS = R20I_LEGACY_EFFECTIVE_PARAMETERS
EXPECTED_DELTA_PARAMETERS = 120_151
R21A_LEGACY_EFFECTIVE_PARAMETERS = 78_899_404
EXPECTED_EFFECTIVE_PARAMETERS = R21A_LEGACY_EFFECTIVE_PARAMETERS
PARAMETER_ACCOUNTING_MODE = "legacy_effective_compatibility_only"
PHYSICAL_PARAMETER_COUNT_STATUS = "requires_artifact_specific_audit"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stored_state(router: CausalEvidenceRouter, storage_dtype: str) -> dict[str, torch.Tensor]:
    if storage_dtype not in {"float16", "float32"}:
        raise ValueError("storage_dtype must be float16 or float32")
    dtype = torch.float16 if storage_dtype == "float16" else torch.float32
    return {
        key: value.detach().cpu().to(dtype=dtype) if value.is_floating_point() else value.detach().cpu()
        for key, value in router.state_dict().items()
    }


def _legacy_effective(payload: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return int(value)
    return -1


def _accounting_fields(*, legacy_effective_parameters: int) -> dict[str, Any]:
    return {
        "parameter_accounting_mode": PARAMETER_ACCOUNTING_MODE,
        "legacy_effective_parameters": int(legacy_effective_parameters),
        "physical_loaded_parameters": None,
        "physical_parameter_count_status": PHYSICAL_PARAMETER_COUNT_STATUS,
        "effective_parameters_note": (
            "Compatibility alias for historical legacy-effective accounting; "
            "not a physical unique tensor parameter count."
        ),
    }


def save_r21a_delta(
    path: str | Path,
    router: CausalEvidenceRouter,
    *,
    parent_checkpoint: str | Path,
    storage_dtype: str = "float16",
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parent_checkpoint = Path(parent_checkpoint)
    parent = torch.load(parent_checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(parent, dict) or parent.get("format") != R20I_FORMAT:
        raise ValueError("R2.1a requires the accepted R2.0i one-weight parent")
    parent_legacy = _legacy_effective(parent, "legacy_effective_parameters", "effective_parameters")
    if parent_legacy != R20I_LEGACY_EFFECTIVE_PARAMETERS:
        raise ValueError("unexpected parent legacy-effective parameter count")

    delta_parameters = r21a_parameter_count(router)
    if delta_parameters != EXPECTED_DELTA_PARAMETERS:
        raise ValueError("unexpected R2.1a delta parameter count")
    candidate_legacy = parent_legacy + delta_parameters
    if candidate_legacy != R21A_LEGACY_EFFECTIVE_PARAMETERS:
        raise ValueError("unexpected R2.1a legacy-effective parameter count")

    payload = {
        "format": R21A_DELTA_FORMAT,
        "version": "Neural-R2.1a-Causal-Evidence-Router",
        "architecture": router.architecture(),
        "parent_sha256": sha256_file(parent_checkpoint),
        # Old fields remain compatibility aliases.
        "parent_effective_parameters": parent_legacy,
        "candidate_effective_parameters": candidate_legacy,
        # New explicit fields make the accounting semantics unambiguous.
        "parent_legacy_effective_parameters": parent_legacy,
        "candidate_legacy_effective_parameters": candidate_legacy,
        "parameter_accounting_mode": PARAMETER_ACCOUNTING_MODE,
        "physical_loaded_parameters": None,
        "physical_parameter_count_status": PHYSICAL_PARAMETER_COUNT_STATUS,
        "effective_parameters_note": (
            "Compatibility aliases only; physical count requires an artifact-specific audit."
        ),
        "delta_parameters": delta_parameters,
        "storage_dtype": storage_dtype,
        "state_dict": _stored_state(router, storage_dtype),
        "training_provenance": dict(provenance or {}),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "delta_parameters": delta_parameters,
        "candidate_effective_parameters": candidate_legacy,
        "candidate_legacy_effective_parameters": candidate_legacy,
        "parameter_accounting_mode": PARAMETER_ACCOUNTING_MODE,
        "physical_loaded_parameters": None,
        "physical_parameter_count_status": PHYSICAL_PARAMETER_COUNT_STATUS,
        "parent_sha256": payload["parent_sha256"],
    }


def load_r21a_delta(
    path: str | Path,
    *,
    expected_parent_checkpoint: str | Path | None = None,
) -> tuple[CausalEvidenceRouter, dict[str, Any]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != R21A_DELTA_FORMAT:
        raise ValueError("unsupported R2.1a delta format")
    if expected_parent_checkpoint is not None:
        if sha256_file(expected_parent_checkpoint) != payload.get("parent_sha256"):
            raise ValueError("parent checkpoint SHA-256 mismatch")

    router = CausalEvidenceRouter(**dict(payload["architecture"]))
    state = payload.get("state_dict")
    if not isinstance(state, dict):
        raise ValueError("R2.1a delta is missing state_dict")
    incompatible = router.load_state_dict(state, strict=True)
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise ValueError("R2.1a state is incompatible with architecture")
    if r21a_parameter_count(router) != int(payload.get("delta_parameters", -1)):
        raise ValueError("R2.1a delta parameter accounting mismatch")

    candidate_legacy = _legacy_effective(
        payload, "candidate_legacy_effective_parameters", "candidate_effective_parameters"
    )
    if candidate_legacy != R21A_LEGACY_EFFECTIVE_PARAMETERS:
        raise ValueError("R2.1a legacy-effective parameter accounting mismatch")

    router.eval()
    metadata = {key: value for key, value in payload.items() if key != "state_dict"}
    # Backfill explicit semantics when loading the already-frozen legacy delta,
    # whose bytes cannot be changed after fresh evaluation.
    metadata.setdefault("candidate_legacy_effective_parameters", candidate_legacy)
    metadata.setdefault("parent_legacy_effective_parameters", R20I_LEGACY_EFFECTIVE_PARAMETERS)
    metadata.setdefault("parameter_accounting_mode", PARAMETER_ACCOUNTING_MODE)
    metadata.setdefault("physical_loaded_parameters", None)
    metadata.setdefault("physical_parameter_count_status", PHYSICAL_PARAMETER_COUNT_STATUS)
    metadata.setdefault(
        "effective_parameters_note",
        "Compatibility aliases only; physical count requires an artifact-specific audit.",
    )
    return router, metadata


def build_r21a_one_weight(
    parent_checkpoint: str | Path,
    delta_checkpoint: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    parent_checkpoint = Path(parent_checkpoint)
    delta_checkpoint = Path(delta_checkpoint)
    parent = torch.load(parent_checkpoint, map_location="cpu", weights_only=True)
    delta = torch.load(delta_checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(parent, dict) or parent.get("format") != R20I_FORMAT:
        raise ValueError("invalid R2.0i parent")
    if not isinstance(delta, dict) or delta.get("format") != R21A_DELTA_FORMAT:
        raise ValueError("invalid R2.1a delta")
    parent_sha = sha256_file(parent_checkpoint)
    if delta.get("parent_sha256") != parent_sha:
        raise ValueError("R2.1a delta is not bound to supplied parent")
    load_r21a_delta(delta_checkpoint, expected_parent_checkpoint=parent_checkpoint)

    legacy_effective = _legacy_effective(
        delta, "candidate_legacy_effective_parameters", "candidate_effective_parameters"
    )
    if legacy_effective != R21A_LEGACY_EFFECTIVE_PARAMETERS:
        raise ValueError("invalid R2.1a legacy-effective accounting")
    accounting = _accounting_fields(legacy_effective_parameters=legacy_effective)
    payload = {
        "format": R21A_BUNDLE_FORMAT,
        "version": "Neural-R2.1a-Causal-Evidence-Router",
        # Preserved compatibility alias. Never present this as a physical count.
        "effective_parameters": legacy_effective,
        "legacy_effective_parameters": legacy_effective,
        "effective_parameters_note": accounting["effective_parameters_note"],
        "parameter_accounting": accounting,
        "parent_sha256": parent_sha,
        "delta_sha256": sha256_file(delta_checkpoint),
        "r20i_bundle": parent,
        "r21a_delta": delta,
        "claim_boundary": (
            "Single neural bundle; deployment router receives public R2.0i tensors only. "
            "Physical tensor count requires artifact-specific audit."
        ),
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, output_path)
    return {
        "path": str(output_path),
        "sha256": sha256_file(output_path),
        "bytes": output_path.stat().st_size,
        "effective_parameters": legacy_effective,
        "legacy_effective_parameters": legacy_effective,
        "parameter_accounting_mode": PARAMETER_ACCOUNTING_MODE,
        "physical_loaded_parameters": None,
        "physical_parameter_count_status": PHYSICAL_PARAMETER_COUNT_STATUS,
        "parent_sha256": parent_sha,
        "delta_sha256": payload["delta_sha256"],
    }
