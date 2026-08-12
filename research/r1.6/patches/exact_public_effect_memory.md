# R1.6 Exact Public Effect Memory -> PSR Highway

Date: 2026-08-12 (Asia/Bangkok)

## Motivation

The retained `PSRPlanner` replicated closed-loop gains on two independent dev slices, but causal identification remained the weakest family. Diagnostics showed the agent often probes opaque actuators correctly yet compresses the exact public effect through a 640D recurrent memory before planning.

This feature preserves the **exact generic structured numeric delta sketch** for each dynamic action and exposes it directly to the predictive-state world model.

## Recurrent state

`System2State` gains an optional `action_effect_sketch [B, A, 128]`.

- initialized to exact zeros;
- untried actions therefore contain no effect information and cannot receive oracle knowledge;
- after action `a` is executed and the next public structured observation is seen, the previous/current public observations are converted with `structured_numeric_delta_sketch(...)` and written only into action `a`'s effect slot;
- other dynamic actions remain untouched;
- legacy recurrent states with `action_effect_sketch=None` are interpreted as all-zero effect memory.

This is parameter-free episodic state, not a learned hidden answer channel.

## PSR effect highway

A new shared projection maps each exact 128D public effect sketch into the 256D PSR action representation:

```python
self.psr_effect_projection = nn.Linear(128, 256, bias=False)
nn.init.zeros_(self.psr_effect_projection.weight)
```

`predictive_state_transition(..., effect_sketch=...)` adds this projection to the shared dynamic action embedding before relational transition modeling. `predictive_state_rollout_scores` carries the same per-action evidence through all imagined branches.

Zero initialization preserves the retained `PredictiveState` / `PSRPlanner` behavior before this 32,768-parameter path is trained.

## TDD evidence

RED was observed first after fixing the test fixture shape:

- `System2State` had no `action_effect_sketch`;
- `NeuralSystem2Workspace` had no `psr_effect_projection`.

GREEN after implementation:

1. an observed structured delta is stored exactly in the previously selected action and all untouched actions stay zero;
2. PSR effect conditioning is dynamic-action permutation equivariant and changes predicted transitions once the projection/transition are nonzero.

Full focused R1.6 gate:

```text
49 passed in 15.18s
```

## Parameter accounting

- exact effect episodic state: **0 trainable parameters**
- PSR effect projection: **32,768 parameters**
- current System-2 live experimental parameters: **21,498,004**
- effective candidate accounting: **71,026,681**
- hard R1.6 research ceiling: **75,000,000**

## Source integrity

- `cogcoder/neural_system2.py`: `26cff057648d5721b473f72b51c4238f037fcbe6e15344d4e0e2f2d5a47aae4e`
- `tests/test_neural_system2.py`: `f144f612ccc0318db28f0761bc218e740d3e483af029577895b36eb66fc5f11b`

## Next gate

Train only the zero-initialized PSR effect projection (and only if necessary a tightly regularized causal PSR residual) on train-only worlds with public action-effect evidence. The retained PSR/PSRPlanner weights remain frozen. Keep the feature only if it improves a new held-out causal gate without regressing resource/rule planning.

Fresh remains unopened.
