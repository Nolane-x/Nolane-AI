# R1.8 Conditional Neural Law Prior — Internal Acceptance

Date: 2026-08-13
Benchmark: FIGG-18 v1 (`train` only)
Parent: R1.7 Phase-C OperatorExecutor `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`

## Checkpoint
- path: `checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt`
- SHA-256: `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`
- effective parameters: **76,619,419**
- new conditional-law parameters: **1,231,873**
- checkpoint bytes: 108,479,069

## Locked protocol
- fit: indices `0..23` per family = 96 train worlds
- internal validation: indices `24..31` per family = 32 train worlds
- families: conditional_regimes, regime_switch, implicit_goal_regimes, causal_prerequisites
- seed: `180318`
- exploration prefix: 6
- max steps: 16
- epochs: 30
- AdamW lr `3e-4`, weight decay `1e-4`, batch 128
- only `conditional_law_*` parameters were trainable

## Held-out train-world transition gate
Evidence-memory baseline MSE: **0.007772307906519812**
Conditional-law candidate MSE: **0.0018936161919751809**
Relative improvement: **75.636%**

Per family:
- `causal_prerequisites`: 0.0046786675 -> **0.0011966237** (+74.424%)
- `conditional_regimes`: 0.0103292778 -> **0.0021993908** (+78.707%)
- `implicit_goal_regimes`: 0.0095951332 -> **0.0020729477** (+78.396%)
- `regime_switch`: 0.0100128476 -> **0.0028947432** (+71.090%)

Every preregistered family beat its own evidence-memory baseline. Best epoch was 30.

## Independent verification
Checkpoint was reloaded from disk and the same 32 held-out train worlds were recollected/re-evaluated. Candidate/baseline metrics reproduced within `1e-9` absolute tolerance. R1.8 + complete R1.7 focused regression: **98/98 passed**.

## Claim boundary
This accepts the Conditional Neural Law Prior for the next reliability-calibration stage. It proves held-out **train-world transition prediction** improvement over context-indexed evidence persistence. It does **not** prove closed-loop improvement, calibrated confidence, FIGG-18 dev performance, or AGI. FIGG-18 dev and fresh remain unopened by this training stage.
