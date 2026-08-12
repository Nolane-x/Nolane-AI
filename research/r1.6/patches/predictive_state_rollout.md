# R1.6 Recursive Predictive-State Rollout

Date: 2026-08-12 (Asia/Bangkok)

## Purpose

Use the retained PSR world model for recursive model-predictive planning without feeding self-generated Stage-2 text latents back into a real-observation-only world model.

## Rollout

`predictive_state_rollout_scores(state_sketch, enriched_actions, horizon, discount)`:

1. predicts all first-action next-state sketches and outcomes;
2. scores immediate utility from progress + information - failure + successful-done bonus;
3. keeps one branch per first action;
4. evaluates every future action **from each predicted PSR successor**;
5. soft-backs up future action utility;
6. recursively updates branch state using expected predicted next-state sketches.

The same shared dynamic action representation is reused at every level. No fixed action slots or task-family rules are introduced.

This feature adds **0 parameters**.

## TDD detail

The PSR delta head is intentionally zero-initialized. Therefore an untrained model must give the same future-state continuation to every first-action branch. The future-dependence test explicitly simulates learned nonzero transition weights before checking branch divergence; this preserves the persistence-neutral initialization invariant rather than weakening it.

Verified properties:

- action permutation equivariance;
- learned first-action successor affects future backed-up value;
- PSR persistence initialization remains unchanged.

Full focused R1.6 gate:

```text
45 passed in 20.10s
```

## Source hashes

- `cogcoder/neural_system2.py`: `8896f825ee996a79bceff9bef9452a229c8f3b409ab63c7b457035edde3c2212`
- `tests/test_neural_system2.py`: `96fa281a76d9ba05cade95816158f08a02871fafc77c6354d17da7b7492c8a7d`

The rollout is not yet integrated into production action logits. Next gate: learn one scalar policy weight on train-only calibration worlds, lock it, then evaluate closed-loop on a separate untouched dev slice. Fresh remains unopened.
