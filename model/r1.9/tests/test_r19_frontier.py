from __future__ import annotations

import torch

from cogcoder.r19_frontier import FrontierRolloutHead, frontier_parameter_count


def _inputs(batch=3, horizon=2):
    g = torch.Generator().manual_seed(1901)
    state = torch.randn(batch, 128, generator=g)
    context = torch.randn(batch, 64, generator=g)
    actions = torch.randn(batch, horizon, 640, generator=g)
    parent = torch.randn(batch, horizon, 128, generator=g)
    return state, context, actions, parent


def test_frontier_head_shapes_and_zero_residual_parent_preservation():
    torch.manual_seed(19)
    head = FrontierRolloutHead()
    state, context, actions, parent = _inputs()
    out = head(state, context, actions, parent)
    assert out['residual_effect'].shape == (3, 128)
    assert out['predicted_effect'].shape == (3, 128)
    assert out['value'].shape == (3,)
    assert out['uncertainty'].shape == (3,)
    torch.testing.assert_close(out['residual_effect'], torch.zeros_like(out['residual_effect']))
    torch.testing.assert_close(out['predicted_effect'], parent.sum(dim=1))


def test_frontier_head_is_batch_permutation_equivariant():
    torch.manual_seed(19)
    head = FrontierRolloutHead()
    state, context, actions, parent = _inputs(batch=4)
    order = torch.tensor([2, 0, 3, 1])
    out_a = head(state, context, actions, parent)
    out_b = head(state[order], context[order], actions[order], parent[order])
    for key in ('residual_effect', 'predicted_effect', 'value', 'uncertainty'):
        torch.testing.assert_close(out_b[key], out_a[key][order])


def test_frontier_head_parameter_budget_is_small_and_fixed():
    head = FrontierRolloutHead()
    count = frontier_parameter_count(head)
    assert 1_000_000 < count < 2_000_000
    assert count == sum(p.numel() for p in head.parameters())
