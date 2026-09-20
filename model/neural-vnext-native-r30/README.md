# Neural vNext Native R30 — action-conditioned counterfactual rescue

Status: **PREDEVELOPMENT LOCKED; PRIMARY DEV PENDING**.

R30 is a Neural Core successor experiment over accepted R11. It directly addresses the two negative findings established by R28 and R29:

1. R28 proved that real single-action terminal rescues and harms exist, but a fixed pre-action candidate was not reliably separable.
2. R29 added certified public consequence geometry, but mandatory dual certification reduced the training court to only four rescue examples and disabled all overrides.

## R30 mechanism

R30 does not choose one candidate before learning. At each eligible hidden-goal decision it constructs an action-conditioned feature vector for **every valid alternative action** other than R11's action.

Each action receives public hidden-goal support, learned posterior/action-mass geometry, R11/candidate action features, parent-logit margin, optional public causal next-state geometry, explicit certification flags/rule counts, and public action-memory coverage. Missing causal certification is represented explicitly and **does not delete the candidate row**.

Training labels every alternative using paired terminal outcomes: rescue when the alternative solves and R11 fails; harm when R11 solves and the alternative fails; neutral otherwise. After the first counterfactual action, both branches use accepted R11 only.

## Locked architecture

- goal-belief parameters: **107,799**
- action-rescue parameters: **61,257**
- successor parameters: **169,056**
- physical learned parameters: **1,046,598**
- action rescue feature dimension: **246**
- rescue classes: neutral / rescue / harm

## Guard

The guard is evaluated at the same granularity used at inference: alternatives are grouped by decision step and at most one action is selected. A threshold pair is eligible only if every preregistered guard block reaches the locked rescue precision/coverage requirements and the complete guard court contains **zero observed selected harms**. If no pair passes, the neural override path is disabled before primary development.

## Courts

- goal train: train:11264..11775
- temperature fit: train:11776..11903
- rescue train: train:11904..12287
- guard: train:12288..12543 in four disjoint 64-identity blocks
- primary dev: dev:1760..1791
- confirmation: dev:1792..1823
- reserved fresh: fresh:280..319 — **UNOPENED**

Fresh remains inaccessible unless primary and confirmation pass with the exact frozen checkpoint/configuration.
