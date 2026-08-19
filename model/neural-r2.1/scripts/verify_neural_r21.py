from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cogcoder.r21_causal_router import CausalEvidenceRouter, r21a_parameter_count  # noqa: E402
from cogcoder.r21_recursive_core import (  # noqa: E402
    R20I_EFFECTIVE_PARAMETERS,
    R21_PARAMETER_CEILING,
    RecursiveLatentIntelligenceCore,
    r21_parameter_count,
)


def inputs(batch: int = 2, actions: int = 6) -> dict[str, torch.Tensor]:
    g = torch.Generator().manual_seed(2101)
    return {
        "state": torch.randn(batch, 128, generator=g),
        "context": torch.randn(batch, 64, generator=g),
        "action_embeddings": torch.randn(batch, actions, 640, generator=g),
        "parent_effects": torch.randn(batch, actions, 128, generator=g),
        "imagined_effects": torch.randn(batch, actions, 128, generator=g),
        "evidence_effects": torch.randn(batch, actions, 128, generator=g),
        "action_memory": torch.randn(batch, actions, 7, generator=g),
        "imagined_uncertainty": torch.rand(batch, actions, generator=g),
        "imagined_value": torch.randn(batch, actions, generator=g),
        "base_action_logits": torch.randn(batch, actions, generator=g),
        "progress": torch.rand(batch, 1, generator=g),
        "budget_fraction": torch.rand(batch, 1, generator=g),
        "previous_feedback": torch.randn(batch, 3, generator=g),
        "base_stop_logit": torch.randn(batch, generator=g),
        "base_success_probability": torch.rand(batch, generator=g) * 0.8 + 0.1,
    }


def main() -> None:
    torch.manual_seed(21)
    manifest = json.loads((ROOT / "ARCHITECTURE.json").read_text())
    current_best = json.loads((ROOT / "CURRENT_BEST.json").read_text())
    assert int(manifest["parameter_ceiling"]) == R21_PARAMETER_CEILING

    # The admitted evidence-backed candidate and the experimental recursive
    # architecture are intentionally separate contracts.  Verify both so a
    # future manifest promotion cannot silently invalidate the other path.
    admitted = manifest["current_evidence_backed_candidate"]
    router = CausalEvidenceRouter(hidden_dim=int(admitted["hidden_dim"])).eval()
    admitted_delta = r21a_parameter_count(router)
    admitted_effective = R20I_EFFECTIVE_PARAMETERS + admitted_delta
    assert admitted_delta == int(admitted["delta_parameters"])
    assert admitted_effective == int(admitted["candidate_effective_parameters"])
    assert admitted_effective <= R21_PARAMETER_CEILING
    assert current_best["version"] == admitted["version"]
    assert int(current_best["delta_parameters"]) == admitted_delta
    assert int(current_best["candidate_effective_parameters"]) == admitted_effective
    assert current_best["fresh"]["weights_modified_after_fresh"] is False
    assert current_best["fresh"]["holdout_consumed"] is True

    x = inputs()
    router_inputs = {key: value for key, value in x.items() if key not in (
        "base_stop_logit", "base_success_probability"
    )}
    with torch.no_grad():
        router_out = router(**router_inputs)
    torch.testing.assert_close(router_out["action_logits"], x["base_action_logits"], rtol=0, atol=0)

    recursive_manifest = manifest["experimental_recursive_core"]
    model = RecursiveLatentIntelligenceCore().eval()
    delta = r21_parameter_count(model)
    effective = R20I_EFFECTIVE_PARAMETERS + delta
    assert delta == int(recursive_manifest["delta_parameters"])
    assert effective == int(recursive_manifest["candidate_effective_parameters"])
    assert effective <= R21_PARAMETER_CEILING

    with torch.no_grad():
        out = model(reasoning_steps=12, **x)
    torch.testing.assert_close(out["action_logits"], x["base_action_logits"], rtol=0, atol=0)
    torch.testing.assert_close(out["stop_logit"], x["base_stop_logit"], rtol=0, atol=0)
    torch.testing.assert_close(out["success_probability"], x["base_success_probability"], rtol=1e-6, atol=1e-7)
    assert out["latent_trajectory"].shape == (2, 12, 256)
    assert torch.isfinite(out["latent_trajectory"]).all()

    order = torch.tensor([4, 0, 5, 2, 1, 3])
    y = dict(x)
    for key in (
        "action_embeddings", "parent_effects", "imagined_effects", "evidence_effects",
        "action_memory", "imagined_uncertainty", "imagined_value", "base_action_logits",
    ):
        y[key] = x[key][:, order]
    with torch.no_grad():
        permuted = model(reasoning_steps=12, **y)
    torch.testing.assert_close(permuted["action_logits"], out["action_logits"][:, order], rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(permuted["latent_state"], out["latent_state"], rtol=1e-5, atol=1e-6)

    router_y = {key: value for key, value in y.items() if key not in (
        "base_stop_logit", "base_success_probability"
    )}
    with torch.no_grad():
        router_permuted = router(**router_y)
    torch.testing.assert_close(
        router_permuted["action_logits"], router_out["action_logits"][:, order], rtol=1e-5, atol=1e-6
    )

    print(json.dumps({
        "status": "PASS",
        "admitted_candidate": admitted["version"],
        "admitted_delta_parameters": admitted_delta,
        "admitted_effective_parameters": admitted_effective,
        "experimental_recursive_delta_parameters": delta,
        "experimental_recursive_effective_parameters": effective,
        "parameter_ceiling": R21_PARAMETER_CEILING,
        "verified_depth": 12,
        "shared_reasoning_cell": True,
        "initial_parent_policy_preserved": True,
        "action_permutation_equivariant": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
