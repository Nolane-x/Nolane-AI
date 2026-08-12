# R1.6 Distance-to-Go Planning Head

Date: 2026-08-12 (Asia/Bangkok)

## Motivation

Dev diagnostics repeatedly showed horizon failure across all three families: premature submit in compositional tasks, failure to finish causal correction after probing, and invalid prerequisite/termination timing in delayed-resource tasks. Prior termination-factorization and failure reweighting did not transfer.

This feature adds a **state-action distance-to-go estimator** rather than another action-type failure prior.

## Architecture

```python
self.distance_head = nn.Linear(workspace_dim, 1)
self.distance_policy_scale = nn.Parameter(torch.tensor(0.0))
```

The head reads the existing action-conditioned world latent and predicts a bounded distance:

```python
distance_to_go = torch.sigmoid(self.distance_head(world).squeeze(-1))
```

Policy adjustment:

```python
def distance_policy_adjustment(self, distance_to_go):
    return -torch.tanh(self.distance_policy_scale) * distance_to_go
```

The scale starts at exactly zero, so adding the feature cannot change legacy parent action logits before training. The adjustment is used only in the full imagination path.

## Planned leakage-safe supervision

No hidden shortest-path or hidden rule target is used. Training targets will be derived only from:

- selected teacher action -> number of **remaining teacher-visible steps**;
- counterfactual immediate failure -> high distance;
- counterfactual successful terminal action -> zero distance.

This avoids leaking opaque actuator mappings or hidden compositional test targets.

## TDD / verification

RED first: tests failed because `distance_to_go` and `distance_policy_scale` did not exist.

GREEN after implementation:

```text
33 passed in 13.56s
```

Focused suite: model + checkpoint loading + curriculum tests.

## Parameter accounting

- System-2 parameters in current experimental architecture: **20,015,117**
- Effective candidate accounting: **69,543,794**

The architecture still contains some explicitly rejected experimental heads for compatibility during the live R1.6 research session; final milestone pruning will remove any module without causal gain.

## Source hashes

- `cogcoder/neural_system2.py`: `dd7b27a128dc821452582d2d34fd9f7efc5cc82483b147dc6d41ed0d1b10d4f7`
- `cogcoder/neural_system2_training.py`: `6b35532b432a8fa10cdf9b3e20af661a950b4efd1f31a95080b8df10ea3e22f7`
- `tests/test_neural_system2.py`: `fe14a4c1047dfa61c2fa88deb57093d9ed6d804ac37dde760a26a6d09e282c01`

Fresh remains unopened.
