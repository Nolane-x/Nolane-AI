# Neural vNext Native R34 — trajectory-mechanism supervision

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R34 is the first successor after R31-R33 to change the **learning structure** rather than merely changing the static label surface.

R33 already predicts the complete four-way terminal outcome from a 774-dimensional candidate-vs-R11 pre-action representation, but its rescue selector did not generalize across guard blocks. R34 keeps that exact representation and keeps the exact same direct rescue/harm selector.

The only conceptual change is multi-task supervision of the shared decision trunk.

For each candidate-vs-R11 pair, the trunk must predict:

1. the same four joint terminal outcomes as R33;
2. R11 terminal mechanism: solved / rejected submit / budget exhausted;
3. candidate terminal mechanism: solved / rejected submit / budget exhausted;
4. eight coarse trajectory quantities describing branch duration, cumulative progress, positive-progress fraction, and information gain.

The future branch trajectory is **never an inference input**. It is training supervision only.

## Locked architecture

- pair feature width: **774**
- goal-belief parameters: **107,799**
- trajectory-mechanism parameters: **165,558**
- successor parameters: **273,357**
- physical learned parameters: **1,150,899**
- joint classes: both-fail / rescue / harm / both-solve
- terminal mechanisms: solved / rejected-submit / budget-exhausted
- trajectory regression targets: **8**

The rescue selector remains identical to R33 and reads only the direct joint rescue and harm probabilities. Auxiliary mechanism/trajectory predictions cannot directly unlock an action.

## New single-use courts

- goal train: train:16384..16895
- temperature fit: train:16896..17023
- mechanism train: train:17024..17407
- guard: train:17408..17663 in four disjoint 64-identity blocks
- primary dev: dev:2016..2047
- confirmation: dev:2048..2079
- reserved fresh: fresh:280..319 — **UNOPENED**

No same-dev retuning is permitted. Confirmation and fresh remain closed unless the exact locked candidate strictly improves both total solved count and implicit-goal solved count while preserving visible-target families exactly.


## Locked development result

R34 trained on **4,956** action-pair counterfactual rows: **493 both-fail**, **299 rescue**, **1,712 harm**, and **2,452 both-solve**.

The auxiliary tasks genuinely learned: terminal-mechanism accuracy reached about **81.8–82.9%**, trajectory MAE reached about **0.126–0.133**, and joint-outcome accuracy reached about **78.1–78.9%** across ensemble heads. Despite that, the unchanged rescue selector still failed every preregistered guard setting. Broad settings retained low rescue precision and harm; stricter settings collapsed rescue coverage.

On dev:2016..2047:
- accepted R11: **121/128**, implicit-goal **28/32**
- R34: **121/128**, implicit-goal **28/32**
- visible-target family solved counts: exact
- overrides: **0**
- confirmation: **UNOPENED**
- fresh: **UNOPENED**

This is stronger evidence than a simple classifier failure: coarse failure/trajectory structure is learnable, but auxiliary supervision alone does not make rare rescue separable. The next architecture should make **predicted branch sequence structure part of the decision computation itself**.

Canonical negative evidence: evidence/DEV_REJECTED_001.json.
