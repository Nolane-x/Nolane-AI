# Neural vNext Native R28 — counterfactual episode rescue value

Status: **PREDEVELOPMENT LOCKED; FRESH UNOPENED**.

R28 changes the learned target after R27 showed that highly precise teacher-action agreement is not enough to increase solved episodes.

## Core idea

R28 contains two learned components:

1. **public goal/action-mass ensemble** — generates a plausible alternative action from public evidence;
2. **counterfactual rescue ensemble** — predicts whether taking that one alternative now, then returning to accepted R11, changes the terminal episode outcome from **R11 fail → solve**.

The rescue target is therefore aligned directly with the promotion metric instead of with one-step teacher agreement.

## Counterfactual supervision

Only on train identities, the collector deep-copies the exact current FIGG-18 task and public runtime state into two branches:

- branch A takes R11's current action, then follows accepted R11;
- branch B takes the neural candidate action once, then follows accepted R11.

Labels:

- **rescue = 1** only when B solves and A fails;
- **harm = 1** when A solves and B fails;
- all other pairs are neutral.

No private goal is required to create rescue/harm labels.

## Learned architecture

- three goal-belief heads, hidden 96
- three rescue-value heads, hidden 64
- goal successor parameters: **107,799**
- rescue successor parameters: **52,035**
- total successor parameters: **159,834**
- total physical learned parameters with frozen accepted R4: **1,037,376**

## Locked identities

- goal training: `train:8768..9279`
- temperature fit: `train:9280..9407`
- rescue training: `train:9408..9727`
- rescue guard blocks: `9728..9791`, `9792..9855`, `9856..9919`, `9920..9983`
- primary dev: `dev:1632..1663`
- confirmation: `dev:1664..1695`
- reserved fresh: `fresh:280..319`

## Locked intervention rule

The action-mass generator requires:

- all three goal heads select the same causal action;
- minimum action mass >= **0.65**;
- exact public support in 2..8;
- candidate differs from R11.

Then all three rescue heads must exceed the selected train-only rescue threshold.

Rescue threshold selection uses four disjoint train-only blocks and requires:

- rescue precision >= **75% in every block**;
- at least 2 predicted rows in every block;
- at least 12 predicted rows total;
- **zero predicted harm** across all blocks.

At most one override is allowed per episode. Visible-target episodes never enter the R28 neural path.

## Promotion

Primary requires +1 or better total solved and +1 or better `implicit_goal_regimes` solved with exact visible-target family solved counts. An exact frozen primary winner must pass confirmation unchanged before fresh can open.
