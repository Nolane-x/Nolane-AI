import json
import torch

from cogcoder.neural_system2 import (
    NeuralSystem2Workspace,
    encode_structured_observation,
    infer_causal_numeric_roles,
)


def _enc(obj):
    text = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True)
    ids, values = encode_structured_observation(text, max_atoms=32)
    return ids.unsqueeze(0), values.unsqueeze(0)


def test_role_binding_finds_changed_vector_and_unique_invariant_same_shape_target():
    pids, pvals = _enc({"alpha": [0, 0, 0], "beta": [2, 1, 4], "step": 0})
    cids, cvals = _enc({"alpha": [1, 0, 0], "beta": [2, 1, 4], "step": 1})
    out = infer_causal_numeric_roles(pids, pvals, cids, cvals, sketch_dim=64)
    assert out["confidence"].shape == (1,)
    assert float(out["confidence"][0]) == 1.0
    assert out["need_sketch"].shape == (1, 64)
    assert float(out["need_sketch"].abs().sum()) > 0.0
    assert int(out["current_group_size"][0]) == 3
    assert int(out["target_candidate_count"][0]) == 1


def test_role_need_sketch_is_invariant_to_literal_key_renaming():
    a0, av0 = _enc({"state": [0, 0, 0], "goal": [2, 1, 4], "step": 0})
    a1, av1 = _enc({"state": [1, 0, 0], "goal": [2, 1, 4], "step": 1})
    b0, bv0 = _enc({"vector_one": [0, 0, 0], "vector_two": [2, 1, 4], "clock": 0})
    b1, bv1 = _enc({"vector_one": [1, 0, 0], "vector_two": [2, 1, 4], "clock": 1})
    left = infer_causal_numeric_roles(a0, av0, a1, av1, sketch_dim=64)
    right = infer_causal_numeric_roles(b0, bv0, b1, bv1, sketch_dim=64)
    assert float(left["confidence"][0]) == 1.0
    assert float(right["confidence"][0]) == 1.0
    assert torch.allclose(left["need_sketch"], right["need_sketch"], atol=1e-6)


def test_role_binding_refuses_ambiguous_invariant_targets():
    pids, pvals = _enc({"x": [0, 0, 0], "y": [2, 1, 4], "z": [4, 4, 4]})
    cids, cvals = _enc({"x": [1, 0, 0], "y": [2, 1, 4], "z": [4, 4, 4]})
    out = infer_causal_numeric_roles(pids, pvals, cids, cvals, sketch_dim=64)
    assert float(out["confidence"][0]) == 0.0
    assert int(out["target_candidate_count"][0]) == 2
    assert torch.count_nonzero(out["need_sketch"]) == 0


def test_causal_law_scores_expose_retrieved_law_equivariantly():
    torch.manual_seed(1707)
    model = NeuralSystem2Workspace()
    state = torch.randn(1, model.psr_sketch_dim)
    actions = torch.randn(1, 4, model.workspace_dim)
    law = model.init_causal_law_state(batch_size=1, device=torch.device("cpu"))
    base = model.causal_law_scores(state, actions, law)
    assert base["retrieved_law"].shape == (1, 4, model.causal_law_dim)
    perm = torch.tensor([2, 0, 3, 1])
    moved = model.causal_law_scores(state, actions[:, perm], law)
    assert torch.allclose(moved["retrieved_law"], base["retrieved_law"][:, perm], atol=1e-6)


def test_role_binding_is_unambiguous_on_real_figg_causal_worlds_after_safe_intervention():
    from cogcoder.r17_benchmark import make_r17_task, oracle_plan
    good = 0
    for family in ("causal_laws", "causal_switch"):
        for index in range(162, 170):
            task = make_r17_task(family, "train", index)
            before = task.render_observation()
            plan = oracle_plan(task)
            action = next((a for a in plan if "submit" not in task.action_descriptions[a].lower()), None)
            if action is None:
                continue
            pids, pvals = _enc(before)
            task.step(action)
            cids, cvals = _enc(task.render_observation())
            out = infer_causal_numeric_roles(pids, pvals, cids, cvals, sketch_dim=64)
            assert float(out["confidence"][0]) == 1.0
            assert int(out["current_group_size"][0]) == 3
            assert int(out["target_candidate_count"][0]) == 1
            good += 1
    assert good >= 12
