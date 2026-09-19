# Neural vNext Native R2 — Transition-Trace Successor

Status: **development successor; fresh:40..79 unopened**.

This line is a new neural candidate built on top of the accepted source-reproducible Neural vNext Native authority. It does **not** mutate or retune the accepted parent.

## Parent boundary

The accepted parent is reconstructed from repository source and must match exactly:

- checkpoint SHA-256: `7de154972ed8e06aaf64064d4d1a6d3ee99331955b3ffb0cfdd8813643fb4f4b`
- state-dict SHA-256: `ddd0e7d8744ed18c782febece06f419ec6fd339f62a5159fa1432b5a9d7c4098`
- physical parameters: 334,099

Every parent parameter is frozen. Successor training has optimizer authority only over R2-owned modules.

## New neural capability

R2 adds an ordered eight-transition public trace. Each transition token contains only public before/after observations and public step feedback:

- normalized before/after states;
- state deltas;
- progress before/after and progress delta;
- information gain and failure signal;
- state-change and regime-change indicators;
- target-visible bit;
- state parity before/after;
- public resource deltas.

A learned trace encoder + GRUCell turns this bounded sequence into a recurrent trace state. A shared per-action residual scorer conditions on:

1. the frozen parent's action token;
2. the frozen parent's recurrent hidden state;
3. the learned transition-trace hidden state.

The residual final layer is zero-initialized, so an untrained R2 model is exactly parent-equivalent.

## Why this successor exists

The accepted parent passed its untouched fresh court at 133/160, with its weakest families being:

- `implicit_goal_regimes`: 30/40;
- `regime_switch`: 31/40.

Both require reasoning over how public transition evidence evolves across time. R2 therefore adds sequence memory rather than increasing the shared parent or tuning accepted weights.

## New development court

R2 deliberately does not reuse the heavily iterated parent dev block.

- train: `train:128..511` across all four families;
- dev: `dev:32..63`;
- reserved future fresh: `fresh:40..79`;
- previously consumed parent fresh `0..39` is never reused for R2 promotion.

A candidate is eligible only if it:

- solves strictly more dev episodes than the frozen parent on `dev:32..63`;
- regresses no family by more than two solved episodes;
- improves at least one of `regime_switch` or `implicit_goal_regimes`.

Among eligible candidates, selection maximizes total dev solves, then minimum-family solves, then minimizes action steps.

## Claim boundary

R2 is development-only until an exact candidate is separately frozen, bitwise reproduced, and evaluated once on untouched `fresh:40..79`. No fresh task is permitted during the current development phase.
