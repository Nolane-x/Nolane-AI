# Neural vNext Native R32 — factorized terminal action value

Status: **PREDEVELOPMENT LOCKED; PRIMARY DEV PENDING**.

R32 changes the learning target rather than adding more representation.

R30 and R31 trained a three-class intervention classifier: neutral / rescue / harm. That formulation collapses two opposite terminal realities into the same neutral label:

- R11 fails and candidate fails;
- R11 solves and candidate solves.

R32 instead learns a binary terminal solve value for each first action:

**Q(s, a) = P(episode solves after taking action a once, then following accepted R11).**

The R11 action itself is labeled once per decision. Every valid alternative action is labeled separately. Rescue and harm are then derived from the candidate and R11 value estimates rather than learned as a single mutually exclusive class.

## Inference score

For each ensemble head:

- rescue = P(candidate solves) × (1 − P(R11 solves))
- harm = P(R11 solves) × (1 − P(candidate solves))
- advantage = P(candidate solves) − P(R11 solves)

An alternative is eligible only when every head has positive advantage, conservative rescue probability clears a locked threshold, and conservative harm probability stays below a locked ceiling.

## Locked architecture

- public goal features: **146**
- accepted R4 latent context: **528**
- per-action value feature width: **727**
- goal parameters: **107,799**
- value parameters: **153,219**
- total successor parameters: **261,018**
- physical learned parameters: **1,138,560**

## New single-use courts

- goal train: train:13824..14335
- temperature fit: train:14336..14463
- terminal value train: train:14464..14847
- four guard blocks: train:14848..15103
- primary dev: dev:1888..1919
- confirmation: dev:1920..1951
- reserved fresh: fresh:280..319 — **UNOPENED**

No development threshold retuning is permitted. Confirmation opens only if the locked primary candidate strictly improves total and implicit-goal solved counts while preserving visible-target family solved counts exactly.
