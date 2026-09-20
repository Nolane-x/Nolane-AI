# Neural vNext Native R24 — sequential public evidence filter

Status: **PREDEVELOPMENT LOCKED; FRESH UNOPENED**.

R24 is a learned Neural Core successor experiment over accepted R11.

## Why this mechanism

R21 demonstrated that supervised hidden-goal learning can produce a real primary gain, but the exact frozen checkpoint reversed on disjoint confirmation. R22/R23 then made snapshot belief increasingly conservative and failed closed from insufficient precision or coverage.

R24 changes the representation rather than relaxing a gate.

Each public transition produces a learned **evidence increment** over the 125 hidden-goal hypotheses. These increments are accumulated through the episode. Exact public consistency remains a hard support mask, and accepted R11 remains the behavioral fallback.

The model receives no private goal at inference.

## Locked learned architecture

- 3 independently initialized evidence heads
- hidden dimension: 96
- expected successor parameters: **83,607**
- accepted R4 learned substrate remains frozen
- evidence inputs: before/after public state, selected public action features, public progress/information/failure feedback, step and remaining budget
- evidence is additive across time rather than a direct snapshot classifier

## Safety/generalization boundary

Before any neural override:

- at least 2 public transitions must have been observed;
- exact public support must be between 2 and 6 hypotheses;
- all neural heads must agree on the top goal;
- train-only calibrated confidence must pass;
- a disjoint train-only action guard must demonstrate at least 90% teacher-action precision over at least 12 actual R11-changing opportunities;
- at most **one** neural override is permitted per episode.

If the calibration gate fails, R24 becomes exact accepted R11 behavior.

## Locked identities

- training: `train:6784..7039`
- temperature fit: `train:7040..7103`
- action-guard validation: `train:7104..7167`
- primary dev: `dev:1376..1407`
- confirmation: `dev:1408..1439`
- reserved fresh: `fresh:280..319`

The fresh block is **UNOPENED**.

## Promotion rule

R24 must strictly improve both total solved and `implicit_goal_regimes` solved count versus accepted R11 while preserving exact solved counts for every visible-target family. A primary pass is insufficient: the exact frozen checkpoint/config must pass the disjoint confirmation court before fresh may be opened.
