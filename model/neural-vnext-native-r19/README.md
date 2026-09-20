# Neural vNext Native R19 — neural goal posterior fusion

Status: **DEVELOPMENT LOCKED; fresh unopened**.

R19 stops using learned dynamics as the controller. Instead it reuses an already-accepted neural signal that R11 does not directly exploit in its causal distance objective: **R4 hidden-goal probabilities**.

The public consistency posterior remains the hard support authority. R19 multiplies the probability mass inside that support by the factorized R4 neural goal prior (with a preregistered fusion exponent), renormalizes, and passes that fused posterior into the unchanged R11 causal planner.

Therefore R19:

- cannot introduce a goal hypothesis rejected by public evidence;
- adds **0 parameters**;
- reads no private goal at inference;
- leaves visible-target behavior exact;
- changes only how R11 ranks still-publicly-possible hidden goals.

Locked:
- primary dev `1056..1087`
- confirmation `1088..1119`
- reserved fresh `280..319` — **UNOPENED**
