from __future__ import annotations

from pathlib import Path
import sys

import torch

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
PARENT_ROOT = HERE.parents[2] / "neural-vnext-native"
R18_ROOT = HERE.parents[2] / "r1.8"
for path in (ROOT, PARENT_ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task  # noqa: E402
from native_core import NativeRecurrentPolicy, PublicActionMemory, encode_public_state, state_dict_sha256  # noqa: E402
from successor_core import SuccessorResidualPolicy, successor_parameter_count  # noqa: E402
from successor_training import load_successor_checkpoint, save_successor_checkpoint  # noqa: E402


def _encoded(family: str = "conditional_regimes"):
    task = make_r18_task(family, "train", 3)
    observation = task.observe()
    memory = PublicActionMemory(len(task.action_descriptions))
    return encode_public_state(
        observation,
        memory,
        previous_feedback=(0.0, 0.0, 0.0),
    )


def test_zero_init_successor_is_exact_parent_policy() -> None:
    torch.manual_seed(41)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = SuccessorResidualPolicy(parent)
    global_features, action_features, valid = _encoded()
    hidden = model.init_hidden(1)

    parent.eval()
    model.eval()
    parent_output = parent.forward_step(
        global_features.unsqueeze(0),
        action_features.unsqueeze(0),
        valid.unsqueeze(0),
        hidden,
    )
    successor_output = model.forward_step(
        global_features.unsqueeze(0),
        action_features.unsqueeze(0),
        valid.unsqueeze(0),
        hidden,
    )
    assert torch.equal(
        parent_output["action_logits"],
        successor_output["action_logits"],
    )
    assert torch.count_nonzero(successor_output["successor_residual_logits"]) == 0


def test_successor_training_scope_freezes_entire_parent() -> None:
    torch.manual_seed(43)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = SuccessorResidualPolicy(parent)
    scope = model.configure_successor_training()
    assert scope["parent_frozen_parameters"] > 0
    assert scope["successor_trainable_parameters"] > 0
    assert all(not parameter.requires_grad for parameter in model.parent.parameters())
    assert all(parameter.requires_grad for parameter in model.successor_parameters())


def test_successor_action_permutation_equivariance() -> None:
    torch.manual_seed(47)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = SuccessorResidualPolicy(parent)
    model.eval()
    global_features, action_features, valid = _encoded("regime_switch")
    hidden = model.init_hidden(1)

    base = model.forward_step(
        global_features.unsqueeze(0),
        action_features.unsqueeze(0),
        valid.unsqueeze(0),
        hidden,
    )["action_logits"][0]
    permutation = torch.tensor(list(reversed(range(action_features.shape[0]))))
    permuted = model.forward_step(
        global_features.unsqueeze(0),
        action_features[permutation].unsqueeze(0),
        valid[permutation].unsqueeze(0),
        hidden,
    )["action_logits"][0]
    restored = torch.empty_like(permuted)
    restored[permutation] = permuted
    assert torch.allclose(base, restored, atol=1e-6)


def test_successor_checkpoint_roundtrip_preserves_tensor_digest(tmp_path: Path) -> None:
    torch.manual_seed(53)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = SuccessorResidualPolicy(parent)
    checkpoint = tmp_path / "successor.pt"
    manifest = save_successor_checkpoint(
        model,
        checkpoint,
        lock_sha256="lock",
        selected_candidate="test",
        training_summary={"fresh_opened": False},
        dev_result={"split": "dev", "episodes": 0, "solved": 0, "solve_rate": 0.0, "steps": 0, "families": {}},
        parent_state_dict_sha256=state_dict_sha256(parent.state_dict()),
    )
    loaded, metadata = load_successor_checkpoint(checkpoint)
    assert metadata["state_dict_sha256"] == manifest["state_dict_sha256"]
    assert state_dict_sha256(loaded.state_dict()) == manifest["state_dict_sha256"]
    assert successor_parameter_count(loaded) == manifest["parameter_counts"]
