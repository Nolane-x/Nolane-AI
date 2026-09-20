# Neural vNext Native R20 — advantage consensus distillation

Status: **PRIMARY DEV LOCKED; FRESH UNOPENED**.

R20 tests a learned Neural Core mechanism over accepted R11 without replacing the accepted fallback.

Three independently initialized neural advantage scorers are trained only on `implicit_goal_regimes/train`. The train-only teacher may use the benchmark oracle, but inference never reads the private goal.

At inference an alternative action is allowed only when:

1. all three scorers independently choose the same alternative over R11;
2. the public hidden-goal posterior support is within the preregistered support cap;
3. the minimum ensemble advantage margin passes a threshold selected only on a disjoint train-only calibration block.

Otherwise R20 returns accepted R11 exactly.

## Locked identities

- train: `5248..5503`
- train-only calibration: `5504..5631`
- primary dev: `1120..1151`
- disjoint confirmation: `1152..1183`
- reserved fresh: `280..319` — **UNOPENED**

Candidate configs are fixed before dev:

- `consensus_guarded`: support <= 3
- `consensus_broad`: support <= 6

Calibration requires at least 95% teacher precision over at least 8 accepted override opportunities. If calibration cannot establish that, the candidate fails closed.

Strict promotion still requires total solved gain, implicit-goal solved gain, and exact visible-family solved counts versus accepted R11.
