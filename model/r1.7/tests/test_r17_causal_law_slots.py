import json
from pathlib import Path

import torch

from cogcoder.neural_system2 import (
    CausalLawState,
    NeuralSystem2Workspace,
    encode_action_descriptions,
    encode_public_observation,
    encode_structured_observation,
    system2_parameter_count,
)
from cogcoder.neural_system2_training import load_system2_checkpoint


def test_causal_law_state_starts_uncertain_and_policy_neutral():
    torch.manual_seed(17)
    model = NeuralSystem2Workspace()
    state = model.init_causal_law_state(batch_size=2, device=torch.device("cpu"))
    assert isinstance(state, CausalLawState)
    assert state.slots.shape == (2, model.causal_law_slot_count, model.causal_law_dim)
    assert torch.count_nonzero(state.confidence) == 0
    assert torch.count_nonzero(state.usage) == 0
    sketch = torch.zeros(2, model.psr_sketch_dim)
    actions = torch.randn(2, 4, model.workspace_dim)
    scores = model.causal_law_scores(sketch, actions, state)
    assert torch.count_nonzero(scores["policy_bonus"]) == 0
    assert float(scores["confidence"].max().detach()) == 0.0


def test_causal_law_update_and_scoring_are_action_permutation_equivariant():
    torch.manual_seed(23)
    model = NeuralSystem2Workspace()
    batch, actions = 1, 3
    sketch = torch.randn(batch, model.psr_sketch_dim)
    action_embeddings = torch.randn(batch, actions, model.workspace_dim)
    delta = torch.randn(batch, model.psr_sketch_dim)
    initial = model.init_causal_law_state(batch_size=batch, device=torch.device("cpu"))
    updated = model.update_causal_laws(
        sketch, action_embeddings, torch.tensor([1]), delta, initial
    )
    original = model.causal_law_scores(sketch, action_embeddings, updated)

    perm = torch.tensor([2, 0, 1])
    permuted_actions = action_embeddings[:, perm]
    permuted_index = torch.tensor([2])  # original action 1 is now position 2
    initial_2 = model.init_causal_law_state(batch_size=batch, device=torch.device("cpu"))
    updated_2 = model.update_causal_laws(
        sketch, permuted_actions, permuted_index, delta, initial_2
    )
    permuted = model.causal_law_scores(sketch, permuted_actions, updated_2)

    assert torch.allclose(updated.slots, updated_2.slots, atol=1e-6)
    assert torch.allclose(updated.confidence, updated_2.confidence, atol=1e-6)
    assert torch.allclose(permuted["predicted_delta"], original["predicted_delta"][:, perm], atol=1e-6)
    assert torch.allclose(permuted["confidence"], original["confidence"][:, perm], atol=1e-6)
    assert torch.allclose(permuted["policy_bonus"], original["policy_bonus"][:, perm], atol=1e-6)


def test_effectprogress_parent_loads_with_causal_law_path_exactly_neutral():
    root = Path(__file__).resolve().parents[1]
    torch.manual_seed(1234)
    model, metadata = load_system2_checkpoint(
        root / "checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt",
        expected_r1_2_checkpoint=root / "checkpoints/Nolane-Rebuild-R1.2-ACE.pt",
    )
    model.eval()
    assert metadata["candidate_effective_parameters"] == 71_848_959
    assert float(model.causal_law_policy_scale.detach()) == 0.0

    latent = torch.linspace(-0.5, 0.5, 640).unsqueeze(0)
    descriptions = [
        "opaque actuator Alpha",
        "opaque actuator Beta",
        "submit current hypothesis",
    ]
    action_tokens = encode_action_descriptions(descriptions, max_bytes=48).unsqueeze(0)
    text = json.dumps(
        {
            "state": [0, 1, 2],
            "goal": [2, 1, 0],
            "step": 0,
            "budget_remaining": 10,
            "last_event": "start",
            "actions": descriptions,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    observation_tokens = encode_public_observation(text, max_bytes=384).unsqueeze(0)
    ids, values = encode_structured_observation(text, max_atoms=64)
    with torch.no_grad():
        out = model(
            latent,
            action_tokens,
            observation_tokens=observation_tokens,
            structured_ids=ids.unsqueeze(0),
            structured_values=values.unsqueeze(0),
            refinement_steps=1,
            policy_mode="full",
        )
    expected = torch.tensor([[0.33849984407424927, 0.7971160411834717, -0.8996449708938599]])
    assert torch.allclose(out.action_logits, expected, atol=2e-6, rtol=0)
    assert out.state.causal_laws is not None
    assert torch.count_nonzero(out.state.causal_laws.confidence) == 0


def test_recurrent_public_transition_updates_causal_law_confidence():
    torch.manual_seed(29)
    model = NeuralSystem2Workspace()
    model.eval()
    latent = torch.zeros(1, 640)
    descriptions = ["opaque actuator A", "opaque actuator B", "submit current hypothesis"]
    action_tokens = encode_action_descriptions(descriptions, max_bytes=48).unsqueeze(0)

    def encode_obs(state, step):
        text = json.dumps(
            {"state": state, "goal": [2, 0, 0], "step": step, "budget_remaining": 8 - step, "actions": descriptions},
            sort_keys=True,
            separators=(",", ":"),
        )
        obs = encode_public_observation(text, max_bytes=384).unsqueeze(0)
        ids, values = encode_structured_observation(text, max_atoms=64)
        return obs, ids.unsqueeze(0), values.unsqueeze(0)

    obs0, ids0, vals0 = encode_obs([0, 0, 0], 0)
    with torch.no_grad():
        first = model(
            latent,
            action_tokens,
            observation_tokens=obs0,
            structured_ids=ids0,
            structured_values=vals0,
            refinement_steps=1,
        )
    assert torch.count_nonzero(first.state.causal_laws.confidence) == 0

    obs1, ids1, vals1 = encode_obs([1, 0, 0], 1)
    with torch.no_grad():
        second = model(
            latent,
            action_tokens,
            state=first.state,
            observation_tokens=obs1,
            structured_ids=ids1,
            structured_values=vals1,
            previous_action=0,
            previous_feedback=(0.1, 1.0, 0.0),
            refinement_steps=1,
        )
    assert float(second.state.causal_laws.confidence.max()) > 0.0
    assert float(second.state.causal_laws.usage.sum()) > 0.0


def test_r17_causal_law_parameter_budget_stays_below_hard_ceiling():
    model = NeuralSystem2Workspace()
    effective = 49_528_677 + system2_parameter_count(model)
    assert 71_848_959 < effective < 96_000_000
