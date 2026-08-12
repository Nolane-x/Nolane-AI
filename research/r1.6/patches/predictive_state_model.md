# R1.6 Rollout-Compatible Predictive State Model (PSR)

Date: 2026-08-12 (Asia/Bangkok)

## Goal

Provide a world-model state space that can be recursively rolled out without feeding self-generated Stage-2 text latents back into modules trained only on real observations.

## Architecture

Predictive state sketch: **128D**  
PSR hidden state: **256D**

The model receives:

- a public structured numeric state sketch;
- dynamic **enriched actions** (action semantic embedding + causal action-memory evidence).

Shared transition:

```text
state 128 -> state encoder 256
action 640 -> action projection 256
relation = [s, a, s*a, |s-a|]  (1024D)
relation -> 384 -> 256
```

Heads predict for every dynamic action:

- next public state sketch (128D delta, bounded component-wise);
- progress;
- information gain;
- failure probability;
- done probability.

`psr_delta_head` is zero-initialized, so persistence is the safe initial transition prior.

The API accepts arbitrary leading branch dimensions. A state tensor `[B, branches, 128]` and actions `[B, branches, A, 640]` therefore produce `[B, branches, A, ...]`, enabling recursive planning without introducing fixed action slots.

## Causal semantics

Opaque causal actuators are not expected to be predicted from arbitrary labels. Training will use the existing **enriched action memory**: once an actuator has been probed and its public effect observed, the action representation carries that evidence. Unprobed causal actions can be masked/downweighted during PSR transition training rather than forcing impossible clairvoyance.

## TDD / verification

RED first: `psr_sketch_dim` / `predictive_state_transition` were absent.

GREEN:

- bounded next-state prediction;
- dynamic action permutation equivariance;
- recursive branch-prefix support;
- prior public-state sketch/counterfactual curriculum tests retained.

Full focused R1.6 gate:

```text
43 passed in 14.05s
```

## Parameter accounting

- PSR-specific parameters: **724,740**
- live System-2 experimental parameters: **21,465,235**
- PSR remains comfortably inside the 75M effective research ceiling even before final pruning of rejected dormant heads.

## Source hashes

- `cogcoder/neural_system2.py`: `a5bf93a62334115e819603ec697f01c22a4d90bf1763b1c1c5e26c78a2b06209`
- `cogcoder/neural_system2_training.py`: `c7aaa8eb0fa434e0a110bf034cd2464d15db9467e7e9028d59197bc3cd8a67ed`
- `tests/test_neural_system2.py`: `fc0e25119be3b5677e38801cc6771bfa10981547d468f0b18e1e89bbd754dd29`

PSR is not yet a capability win. Next gate: train it on all-action counterfactual successor sketches, then require held-out one-step state/outcome prediction improvement before any recursive PSR planning is allowed.

Fresh remains unopened.
