# Neural vNext Native R35 — fixed-policy branch sequence decoder

Status: **PREDEVELOPMENT LOCKED; PRIMARY DEV PENDING**.

R35 changes how counterfactual future structure enters the decision.

R16-R18 learned one-step public transition models and used those models for imagined planning. R35 does **not** do that. It never recursively applies a learned world transition and never searches through imagined states.

Instead, for each candidate-vs-R11 decision pair, two recurrent decoders directly forecast a short outcome sequence under a fixed continuation policy:

- baseline branch: take the R11 action, then continue with accepted R11;
- candidate branch: take the alternative action once, then continue with accepted R11.

Each decoder predicts six steps of:

1. progress delta;
2. information gain;
3. done probability;
4. solved probability.

The final recurrent state of both forecast branches, together with the pre-action context, is consumed directly by the four-way joint terminal head. This is the key difference from R34: sequence structure is now **inside the rescue decision path**, not merely an auxiliary loss.

## Locked architecture

- pair feature width: **774**
- branch forecast horizon: **6**
- channels per branch step: **4**
- decoder hidden: **64**
- time embedding: **16**
- goal-belief parameters: **107,799**
- sequence-decoder parameters: **283,716**
- successor parameters: **391,515**
- physical learned parameters: **1,269,057**

The rescue selector remains the same strict direct rescue/harm selector used in R33/R34.

## New single-use courts

- goal train: train:17664..18175
- temperature fit: train:18176..18303
- branch-sequence train: train:18304..18687
- guard: train:18688..18943 in four disjoint 64-identity blocks
- primary dev: dev:2080..2111
- confirmation: dev:2112..2143
- reserved fresh: fresh:280..319 — **UNOPENED**

No same-dev retuning is permitted.
