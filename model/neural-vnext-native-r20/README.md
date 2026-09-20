# Neural vNext Native R20 — development-rejected advantage consensus

Status: **DEV REJECTED; confirmation and fresh never opened**.

R20 trained three neural action-advantage scorers and required all three to agree on the same alternative action. Override margins were calibrated only on a disjoint train-only block; calibration had to demonstrate at least 95% teacher precision on at least 8 accepted opportunities.

## Locked result

On `dev:1120..1151`:

- accepted R11: **122/128**, implicit-goal **29/32**
- `consensus_guarded`: **122/128**, implicit **29/32**, 0 overrides
- `consensus_broad`: **122/128**, implicit **29/32**, 0 overrides
- visible-target family solved counts remained exact.

The exact learned artifact reproduced across independent push/PR executions:

- checkpoint SHA-256: `634b3740612067805299a0e1c9b50783fb74dfebee622d22a87e471fa1507469`
- successor state SHA-256: `1231d88c0c5222e46f88c768b5ce865c20561c5904be6fe33b4016fa6600bb54`
- successor parameters: **112,323**
- physical parameters: **989,865**

## Falsification result

Train-only calibration observed:

- support <=3: **147** consensus alternative opportunities
- support <=6: **159** consensus alternative opportunities

But no threshold satisfied the preregistered requirement of **>=95% teacher precision with >=8 accepted examples**. Both candidates therefore failed closed and became behaviorally identical to R11 on dev.

The calibration requirement is not relaxed after seeing this result.

## Closure

- confirmation `1152..1183`: never opened
- fresh `280..319`: never opened and remains untouched
- no retuning on `dev:1120..1151`
- R20 closes without merge

Canonical negative evidence: `evidence/DEV_REJECTED_001.json`.
