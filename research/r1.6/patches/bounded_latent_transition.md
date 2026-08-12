# R1.6 Bounded Next-Latent Transition

Date: 2026-08-12 (Asia/Bangkok)

## Motivation

Direct dev diagnostics showed the previous unconstrained `next_latent_head` was catastrophically miscalibrated: predicted delta norms were ~11-12 while real adjacent Stage-2 latent changes were ~0.8-1.3, and persistence MSE beat the learned transition by roughly two orders of magnitude.

## Architecture

The existing `next_latent_head` now predicts only a **direction**. A tiny state-action magnitude head predicts transition size:

```python
self.max_transition_delta_norm = 4.0
self.next_delta_magnitude_head = nn.Linear(workspace_dim, 1)
```

The magnitude head is initialized with zero weights and bias `-6`, so new models begin extremely close to the persistence prior.

Prediction:

```python
raw_direction = self.next_latent_head(world)
direction = F.normalize(raw_direction, dim=-1)
magnitude = 4.0 * sigmoid(next_delta_magnitude_head(world))
delta = direction * magnitude[..., None]
next_latent = current_latent[..., None, :] + delta
```

Properties:

- hard transition-delta norm cap of **4.0**;
- near-zero residual at initialization;
- shared over all dynamic actions;
- supports arbitrary leading imagined-branch dimensions;
- action permutation equivariant;
- reused by both real one-step prediction and multi-step latent imagination.

Legacy checkpoints may omit the magnitude-head parameters and still load.

## TDD / verification

RED first: tests failed because `predict_next_latent` did not exist.

GREEN after implementation:

- near-persistence initialization test passes;
- hard norm cap test passes;
- dynamic-action permutation equivariance passes;
- prior latent-MPC action-conditioning/permutation tests still pass.

Full focused R1.6 gate:

```text
39 passed in 13.65s
```

## Parameter accounting

- System-2 parameters: **20,740,495**
- Added magnitude head: **641 parameters**
- Effective candidate accounting before final pruning remains well below the 75M hard research ceiling.

## Next mandatory gate

Train only the transition direction+magnitude pathway directly on `(actual_next_latent - current_latent)` using train trajectories. Retain it only if held-out dev transition MSE beats the persistence baseline. Multi-step planning remains disabled until that gate is passed.

## Source hashes

- `cogcoder/neural_system2.py`: `8432b3233617c88ee27cfc5dd67fd580d2c98a8fad25c6702ac33010b674e70b`
- `cogcoder/neural_system2_training.py`: `cd75327b4b025773e67ee49f2b67de7ea3f614b3d551d7c65144e0c808188672`
- `tests/test_neural_system2.py`: `4c47b5df0aa622434e35ede8f46c0cb735485fcb4e97649f2ee6ddb994a28201`

Fresh remains unopened.
