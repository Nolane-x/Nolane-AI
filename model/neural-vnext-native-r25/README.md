# Neural vNext Native R25 — selective R11 error correction

Status: **PREDEVELOPMENT LOCKED; FRESH UNOPENED**.

R25 is a learned Neural Core successor experiment over accepted R11.

## Mechanism

R25 explicitly separates two questions that earlier successors mixed together:

1. **Is accepted R11 likely wrong on this public state?**
2. **If it is wrong, which public action should replace it?**

Each of three neural heads contains:

- an R11-mistake detector trained on every train-only hidden-goal decision;
- an action scorer trained only on rows where the true-goal causal teacher disagrees with R11.

The action scorer consumes action features directly, so its output is action-order aware only through public action representations rather than a fixed action ID vocabulary.

## Locked learned architecture

- ensemble size: 3
- hidden dimension: 64
- successor parameters: **75,846**
- accepted R4 learned substrate remains frozen
- total expected learned parameters: **953,388**

Public inputs include exact support, public state, progress/budget/step, prior public feedback, R11 causal-decision diagnostics, R11 selected-action features, and candidate-action features.

Private hidden goals are used only to construct train-only teacher labels.

## Guard

An override is possible only when:

- the episode is hidden-goal;
- exact public support is at most 6;
- all three correction heads agree on the same replacement action;
- every detector head exceeds the same train-only calibrated mistake threshold;
- the replacement differs from R11;
- the selected train-only guard achieves at least 90% teacher-action precision on at least 12 real R11-changing rows;
- at most one neural override occurs per episode.

If no threshold qualifies, R25 becomes exact R11 behavior.

## Locked identities

- training: `train:7168..7423`
- disjoint guard validation: `train:7424..7487`
- primary dev: `dev:1440..1471`
- confirmation: `dev:1472..1503`
- reserved fresh: `fresh:280..319`

Fresh remains **UNOPENED**.

## Promotion

Primary promotion requires +1 or better total solved, +1 or better `implicit_goal_regimes` solved, and exact visible-target family solved counts. A primary pass cannot open fresh: the frozen checkpoint/config must first pass confirmation unchanged.
