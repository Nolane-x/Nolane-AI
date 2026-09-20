# Neural vNext Native R33 — joint terminal outcome

Status: **PREDEVELOPMENT LOCKED; PRIMARY DEV PENDING**.

R33 tests a narrower hypothesis than R32. The pairwise representation returns to the same **774-dimensional candidate-vs-R11 feature surface used by R31**. The only conceptual target change is that the old neutral class is split into its two physically different terminal outcomes.

The model predicts one of four coupled outcomes for every alternative action:

1. **both-fail** — R11 fails and candidate fails;
2. **rescue** — R11 fails and candidate solves;
3. **harm** — R11 solves and candidate fails;
4. **both-solve** — R11 solves and candidate solves.

This avoids R31's neutral-label collapse and avoids R32's assumption that candidate and R11 terminal solves can be predicted independently and multiplied.

## Locked architecture

- pair representation: **774**
- goal-belief parameters: **107,799**
- joint-outcome parameters: **162,828**
- successor parameters: **270,627**
- physical learned parameters: **1,148,169**
- classes: both-fail / rescue / harm / both-solve

The selector uses the ensemble's **direct rescue probability** and **direct harm probability**. It may choose at most one override per episode, and the guard still requires at least 75% rescue precision in every preregistered block, minimum coverage, and zero observed harm.

## New single-use courts

- goal train: train:15104..15615
- temperature fit: train:15616..15743
- joint-outcome train: train:15744..16127
- guard: train:16128..16383 in four disjoint 64-identity blocks
- primary dev: dev:1952..1983
- confirmation: dev:1984..2015
- reserved fresh: fresh:280..319 — **UNOPENED**

No primary-dev retuning is allowed. Confirmation and fresh remain closed unless the exact locked candidate strictly improves solved counts while preserving visible-target families exactly.
