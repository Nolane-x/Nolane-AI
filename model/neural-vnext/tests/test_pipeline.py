from __future__ import annotations

import sys
from pathlib import Path

import torch

HERE = Path(__file__).resolve()
VNEXT_ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R23_ROOT = MODEL_ROOT / "neural-r2.3"
for root in (VNEXT_ROOT, R23_ROOT):
    text = str(root)
    if text not in sys.path:
        sys.path.insert(0, text)

from nvnext.pipeline import (  # noqa: E402
    CACHE_FORMAT,
    R23_ONE_WEIGHT_FORMAT,
    load_frozen_candidate,
    load_locked_r23_reasoner,
    load_verified_training_cache,
    run_training_epoch,
    save_frozen_candidate,
    sha256_file,
)
from nvnext.training import make_vnext_optimizer  # noqa: E402
from r23.ultra_core import ScaledRecursiveDistilledReasoner  # noqa: E402


def _lock() -> dict[str, object]:
    return {
        "schema_version": 1,
        "confirmatory_fresh": {
            "block_1_indices": [1120, 1139],
            "block_2_indices": [1140, 1159],
            "episodes_expected": 160,
        },
    }


def _record(index: int, *, family: str = "conditional_regimes", actions: int = 4) -> dict[str, object]:
    return {
        "source_index": index,
        "family": family,
        "source_kind": "expert" if index % 2 else "dagger",
        "proof_verified": True,
        "expert_action": index % actions,
        "proof_weight": 1.0,
        "inputs": {
            "state": torch.randn(128),
            "context": torch.randn(64),
            "action_embeddings": torch.randn(actions, 640),
            "parent_effects": torch.randn(actions, 128),
            "imagined_effects": torch.randn(actions, 128),
            "evidence_effects": torch.randn(actions, 128),
            "action_memory": torch.randn(actions, 7),
            "imagined_uncertainty": torch.rand(actions),
            "imagined_value": torch.randn(actions),
            "base_action_logits": torch.randn(actions),
            "progress": torch.rand(1),
            "budget_fraction": torch.rand(1),
            "previous_feedback": torch.randn(3),
            "base_stop_logit": torch.zeros(()),
            "base_success_probability": torch.tensor(0.5),
        },
    }


def test_verified_training_cache_rejects_parent_and_vnext_fresh_indices(tmp_path: Path) -> None:
    for forbidden in (1080, 1119, 1120, 1159):
        path = tmp_path / f"cache-{forbidden}.pt"
        torch.save({"format": CACHE_FORMAT, "records": [_record(forbidden)]}, path)
        try:
            load_verified_training_cache(path, predev_lock=_lock())
        except ValueError as exc:
            assert "locked fresh index" in str(exc)
        else:
            raise AssertionError("fresh-contaminated training cache must fail closed")


def test_verified_cache_drives_real_multidepth_training_epoch(tmp_path: Path) -> None:
    torch.manual_seed(31)
    path = tmp_path / "cache.pt"
    records = [_record(index) for index in range(40, 44)]
    torch.save({"format": CACHE_FORMAT, "records": records}, path)
    verified = load_verified_training_cache(path, predev_lock=_lock())

    model = ScaledRecursiveDistilledReasoner(latent_dim=192, n_heads=6, ff_mult=2)
    optimizer = make_vnext_optimizer(
        model,
        stage="depth_warmup",
        learning_rate=5e-4,
        weight_decay=0.0,
    )
    before = model.reasoning_cell.query.weight.detach().clone()
    metrics = run_training_epoch(
        model,
        verified,
        optimizer,
        batch_size=2,
        generator=torch.Generator().manual_seed(7),
        min_steps=2,
        max_steps=4,
    )

    assert metrics["batches"] == 2.0
    assert metrics["verified_samples"] == 2.0
    assert metrics["grad_norm"] > 0.0
    assert not torch.equal(before, model.reasoning_cell.query.weight.detach())


def test_frozen_candidate_round_trip_binds_tensor_and_bundle_digests(tmp_path: Path) -> None:
    torch.manual_seed(37)
    model = ScaledRecursiveDistilledReasoner(latent_dim=192, n_heads=6, ff_mult=2)
    destination = tmp_path / "candidate.pt"
    reasoner_parameters = sum(parameter.numel() for parameter in model.parameters())

    manifest = save_frozen_candidate(
        model,
        destination,
        parent_one_weight_sha256="1" * 64,
        predev_lock_sha256="2" * 64,
        physical_parameters=reasoner_parameters,
        physical_parameter_ceiling=80_000_000,
        adaptive_depth={
            "min_steps": 2,
            "max_steps": 4,
            "halt_threshold": 0.5,
            "stability_steps": 2,
        },
        training_summary={"verified_records": 4, "fresh_indices_consumed": False},
    )
    restored, metadata = load_frozen_candidate(
        destination,
        reasoner_factory=ScaledRecursiveDistilledReasoner,
    )

    assert metadata["state_dict_sha256"] == manifest["state_dict_sha256"]
    assert metadata["bundle_sha256"] == manifest["bundle_sha256"]
    assert sum(parameter.numel() for parameter in restored.parameters()) == reasoner_parameters
    for name, value in model.state_dict().items():
        assert torch.equal(value.cpu(), restored.state_dict()[name].cpu())


def test_locked_r23_reasoner_loader_avoids_historical_runtime_dependencies(tmp_path: Path) -> None:
    torch.manual_seed(41)
    source = ScaledRecursiveDistilledReasoner(latent_dim=192, n_heads=6, ff_mult=2)
    bundle = tmp_path / "r23-one-weight.pt"
    torch.save(
        {
            "format": R23_ONE_WEIGHT_FORMAT,
            "physical_parameters": 79_858_099,
            "r23_ultra_delta": {
                "architecture": source.architecture(),
                "state_dict": source.state_dict(),
            },
        },
        bundle,
    )
    reasoner, metadata = load_locked_r23_reasoner(
        bundle,
        reasoner_factory=ScaledRecursiveDistilledReasoner,
        expected_sha256=sha256_file(bundle),
        expected_physical_parameters=79_858_099,
    )

    assert metadata["one_weight_sha256"] == sha256_file(bundle)
    assert metadata["physical_parameters"] == 79_858_099
    assert metadata["reasoner_parameters"] == sum(
        parameter.numel() for parameter in source.parameters()
    )
    for name, value in source.state_dict().items():
        assert torch.equal(value.cpu(), reasoner.state_dict()[name].cpu())
