# R1.6 Public Predictive-State Counterfactual Curriculum

Date: 2026-08-12 (Asia/Bangkok)

## Purpose

Multi-step Stage-2 latent rollout failed because imagined latents were recursively fed into a world model trained only on cognitive states derived from real observations. This patch establishes a rollout-compatible state space grounded directly in public structured observations.

## Structured numeric state sketch

New `structured_numeric_state_sketch(ids, values, sketch_dim=128)` hashes every public numeric atom into the same identity buckets used by the existing causal delta sketch.

Verified invariant:

```text
state_sketch(next) - state_sketch(current)
== structured_numeric_delta_sketch(current, next)
```

for observations with the same numeric atom identities. This means causal action-memory effects and predictive world-state transitions can share one generic 128D space.

## All-action counterfactual collection

New `collect_predictive_state_trajectories(...)` walks teacher trajectories but, at every public state, deep-copies the train/dev simulator and executes **every available public action**. It records:

- current public state sketch;
- dynamic action byte tokens;
- counterfactual next-state sketch for every action;
- counterfactual progress / information / failure / done;
- teacher-selected action label.

Every next-state target is encoded from `StepResult.observation` returned by the public `step()` surface. Private environment fields are never passed to the predictive-state model. Oracle/private state remains restricted to curriculum construction/verification, as in the existing teacher pipeline.

## TDD / verification

RED first:

- state-sketch import/function missing;
- predictive-state collector missing.

GREEN after implementation:

- state-sketch delta invariant passes;
- independently replayed public counterfactual successors exactly match collector targets for every action;
- full focused R1.6 suite:

```text
41 passed in 14.17s
```

## Source hashes

- `cogcoder/neural_system2.py`: `9e2e6f2abc971c71a264520c5bc3f85683dd1737186087286f4a4806d693f4b3`
- `cogcoder/neural_system2_curriculum.py`: `5f3ff0b9953341341dc9743790861585b1ada720b9776689c2d2398dd6e6ceb4`
- `tests/test_neural_system2.py`: `4c884ea5ff01e326172125e10c5dc07c40c422a050f59c23ea23c10ff45c22bf`
- `tests/test_neural_system2_curriculum.py`: `2bc2d0a1714b4b906ea39c77490a8f6692f9630f21c6b111332db2739087fbe0`

Fresh remains unopened.
