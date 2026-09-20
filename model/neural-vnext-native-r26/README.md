# Neural vNext Native R26 — calibrated action-mass consensus

Status: **PREDEVELOPMENT LOCKED; FRESH UNOPENED**.

R26 is a learned Neural Core successor experiment over accepted R11.

## Why R26 differs

R23 required every goal inside a conservative conformal set to imply the same action. That produced perfect train-only candidate precision but only three actual override opportunities, below the locked coverage requirement.

R24 and R25 moved toward direct learned intervention and gained coverage, but precision collapsed.

R26 keeps the **action-equivalence** insight while replacing hard unanimity over a conformal goal set with calibrated probability mass.

Each of three supervised public goal-belief heads:

1. predicts only over the exact public-consistent goal support;
2. maps every supported goal through the unchanged accepted R11 causal planner;
3. sums goal probability into the resulting action;
4. exposes its highest-mass causal action.

A neural override is possible only when all three heads select the same action and the **minimum** mass assigned to that action across heads passes a disjoint train-only threshold.

## Learned architecture

- ensemble: 3 heads
- hidden dimension: 96
- successor parameters: **107,799**
- total physical learned parameters: **985,341**
- accepted R4 checkpoint remains frozen
- private goal labels are train-only

## Locked identities

- training: `train:7488..7743`
- temperature fit: `train:7744..7807`
- action-mass guard: `train:7808..7871`
- primary dev: `dev:1504..1535`
- confirmation: `dev:1536..1567`
- reserved fresh: `fresh:280..319`

## Guard

Preregistered minimum action-mass candidates: 0.55, 0.65, 0.75, 0.85, 0.90, 0.95.

The selected threshold must demonstrate **>=90% train-only teacher-action precision on >=12 actual R11-changing rows**. At most one neural override is allowed per episode. If no threshold qualifies, behavior is exact accepted R11.

Visible-target episodes never use the neural action-mass path.

## Promotion

Primary requires total solved +>=1 and `implicit_goal_regimes` solved +>=1 with exact solved counts in all visible-target families. An exact frozen primary winner must pass disjoint confirmation before fresh may be opened.
