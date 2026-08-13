# R1.8 Control-Sufficient Effect Head — Internal Acceptance

Date: 2026-08-13
Parent: accepted ConditionalLaw `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`
Benchmark: FIGG-18 v1 (`train` only)

## Checkpoint
- `checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt`
- SHA-256: `ec50d7240d0f3c4073fd849e62e9832a2bde6ab24ecad5cc4c59251dfb3a9f20`
- effective parameters: **76,635,867**
- new trainable head: **16,448 parameters**
- checkpoint bytes: 108,545,260

## Locked protocol
- fit indices: `68..83` per family = 64 train worlds
- internal validation: `84..91` per family = 32 train worlds
- seed `180518`
- exploration prefix 6; max steps 16
- 50 epochs, AdamW lr `1e-3`, weight decay `1e-4`, batch 256
- only `conditional_control_effect_head.{weight,bias}` trainable
- target: key-name-agnostic 64D controllable-role successor effect inferred from public dynamics
- baseline: context-compatible evidence memory projected into the exact same role coordinates

## Held-out control-effect gate
Evidence baseline MSE: **0.03246555411633598**
Candidate MSE: **0.00992167232141487**
Relative improvement: **69.439%**
Best epoch: **35**
Evaluated action-effect rows: **1,045**

Per family:
- causal_prerequisites: 0.0177591051 -> **0.0090160315** (+49.23%), 235 rows
- conditional_regimes: 0.0382823881 -> **0.0098694110** (+74.22%), 261 rows
- implicit_goal_regimes: 0.0419560943 -> **0.0104420322** (+75.11%), 264 rows
- regime_switch: 0.0304736918 -> **0.0102342716** (+66.42%), 285 rows

Every family beat its own projected-evidence baseline and exceeded the preregistered minimum of 64 rows.

## Independent verification
Reloaded checkpoint SHA and effective-parameter count match. Recollecting and re-evaluating the exact 32 held-out train worlds reproduced aggregate candidate MSE within `3.2e-11` and baseline exactly. R1.7+R1.8 regression suite: **112/112 passed**.

## Claim boundary
This accepts a control-sufficient learned successor representation for a new reliability calibration stage. It is not yet a closed-loop control result, does not authorize FIGG-18 dev/fresh, and is not an AGI claim.
