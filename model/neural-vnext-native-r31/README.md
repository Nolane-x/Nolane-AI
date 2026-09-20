# Neural vNext Native R31 — latent-state action-conditioned rescue

Status: **PREDEVELOPMENT LOCKED; PRIMARY DEV PENDING**.

R31 is a controlled successor experiment over accepted R11. R30 already removed the major candidate-coverage failure of R29: it retained 5,064 action-conditioned counterfactual rows, including 298 true rescue rows. R30 still failed because its public/action/consequence feature surface could not safely separate rescue from harm.

R31 changes one variable only: it appends the frozen, already-accepted R4 pre-action neural inference state to every R30-style action-rescue feature.

## Added representation

The new 528-dimensional context is composed of inference-time tensors emitted by accepted R4 before the action is selected:

- belief hidden: 96
- goal embedding: 48
- native recurrent hidden: 128
- R2 trace hidden: 128
- R3 attribution hidden: 128

No private goal, counterfactual outcome, future branch state, or oracle signal is included.

The R30 base rescue representation remains 246 dimensions, producing a total R31 action-rescue feature width of **774**.

## Locked architecture

- goal-belief parameters: **107,799**
- latent action-rescue parameters: **162,633**
- successor parameters: **270,432**
- physical learned parameters: **1,147,974**
- rescue classes: neutral / rescue / harm

All-action generation, terminal counterfactual labels, optional certification geometry, threshold grid, zero-harm guard, selector semantics, maximum one override per episode, and promotion criteria remain unchanged from R30.

## New single-use courts

- goal train: train:12544..13055
- temperature fit: train:13056..13183
- rescue train: train:13184..13567
- guard: train:13568..13823 in four disjoint 64-identity blocks
- primary dev: dev:1824..1855
- confirmation: dev:1856..1887
- reserved fresh: fresh:280..319 — **UNOPENED**

R31 may open confirmation only after a strict primary solved-count gain with visible-target families exact. Fresh remains inaccessible until the exact frozen candidate passes confirmation unchanged.
