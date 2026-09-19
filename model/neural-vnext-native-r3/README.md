# Neural vNext Native R3 — Action-Attributed Feedback Belief

Status: **DEVELOPMENT ONLY — fresh:80..119 unopened**.

R3 starts from the accepted R2 authority merged at `32999ae86a5a5c5f846dc233a2344ad4b4d2958d`. The exact R2 checkpoint in Git LFS is the parent authority; R3 does not retrain or mutate R2.

## Motivation

R2 improved the untouched fresh court from the frozen parent's 128/160 to 141/160, but `implicit_goal_regimes` remained the weakest family at 27/40.

R2's transition trace retains ordered public state/feedback changes, while the accepted Native action memory retains per-action aggregate statistics. What is still missing is an ordered memory that explicitly binds **which public action evidence preceded each observed transition and progress change**.

R3 tests that specific hypothesis rather than merely increasing width or depth.

## Architecture

Each R3 attribution token is exactly:

- the selected action's 25-dimensional public action-feature row **before** the action;
- the 25-dimensional R2 public transition token observed **after** the action.

The resulting 50-dimensional tokens are kept in an ordered length-12 trace and encoded by a new GRUCell.

A successor-only residual scorer receives:

1. the frozen Native action token;
2. the frozen Native recurrent hidden state;
3. the frozen R2 transition-trace hidden state;
4. the R3 action-attribution hidden state.

The R3 final layer is zero-initialized. At initialization R3 is exactly behaviorally equivalent to R2.

The R3 residual is multiplied by `1 - target_visible`. Therefore visible-target episodes bypass R3 exactly; R3 is allowed to change only hidden-target behavior.

## Locked data boundary

`PREDEV_LOCK.json` freezes:

- R2 parent checkpoint: `bb18c0b0f398400aa0d8ab5a7a646c0ed57eec46cfb3415abe2693ab46a30c14`
- R2 state dict: `20a2dcefbe6d5f22184569186716a31053231aa0599b3b52d4650fc30084f2bf`
- R3 train: `train:1024..1535`, hidden-goal family only
- R3 dev: `dev:96..127`
- reserved untouched future fresh: `fresh:80..119`
- consumed fresh blocks: `0..39` and `40..79`

No R3 training or dev code is permitted to instantiate `fresh:80..119`.

## Development promotion rule

A development candidate is eligible only if on `dev:96..127` it:

- strictly improves `implicit_goal_regimes` solved count versus frozen R2;
- strictly improves total solved count versus frozen R2;
- matches frozen R2 solved counts exactly on `conditional_regimes`, `regime_switch`, and `causal_prerequisites`.

Fresh evaluation is not authorized by development success. A later candidate must first be frozen with exact checkpoint/state/source authority and a separate PRE_FRESH_LOCK.
