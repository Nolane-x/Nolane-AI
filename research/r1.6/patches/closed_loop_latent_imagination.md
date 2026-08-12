# R1.6 Closed-Loop Latent Imagination

Date: 2026-08-12 (Asia/Bangkok)

## Motivation

The previous Neural Plan Rollout learned future action sequences but did not improve closed-loop dev. Its limitation was structural: future actions were predicted while the same latent world context was retained, so it learned a sequence prior rather than model-predictive planning.

This patch adds parameter-free **action-conditioned latent model-predictive scoring** using the already learned world model.

## Mechanism

`latent_model_predictive_scores(latent, thought, enriched_actions, horizon, discount)`:

1. predicts an immediate world latent for every dynamic first action;
2. applies `next_latent_head` so every first-action branch moves to a distinct imagined latent state;
3. projects each imagined latent back into workspace context;
4. evaluates all possible next actions from that new state with the shared `world_state + world_action` model;
5. performs a soft differentiable backup over future actions;
6. applies the expected next transition and repeats for the requested horizon.

The method introduces **no new parameters**. It uses the existing learned transition, progress, information and failure heads. It remains action-ontology agnostic and permutation-equivariant.

## TDD evidence

RED first: two tests failed because `latent_model_predictive_scores` did not exist.

GREEN after implementation:

- rollout score permutes exactly with dynamic action order;
- horizon=2 future value differs across first-action branches, proving the imagined state is actually updated by the first action rather than reused unchanged.

Full focused R1.6 gate after refactor:

```text
37 passed in 13.82s
```

## Parameter accounting

- System-2 parameters: **20,739,854**
- This feature adds: **0 parameters**

It is not yet integrated into the production action logits. The next required step is a dev-only diagnostic/sweep to determine whether the learned world transition contains useful multi-step planning signal. Only if it improves closed-loop dev will a policy integration be retained.

## Source integrity

- `cogcoder/neural_system2.py`: `9226233be1ad00cad8992f7bffea25b7f3e8309356329e5ac4b68e82374acd18`
- `tests/test_neural_system2.py`: `360d3e80ee32c63bee7b8c1b1edf24a4b95d8980473046236361d6e72c69e92c`

Fresh remains unopened.
