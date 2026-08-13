# R1.8 Control-Sufficient Reliability v3 Protocol

Date: 2026-08-13
Parent checkpoint: `Nolane-R1.8-CCSM-ControlEffect.pt` SHA `ec50d7240d0f3c4073fd849e62e9832a2bde6ab24ecad5cc4c59251dfb3a9f20`.

Reliability v1/v2 were rejected because they certified the full 128D structured-delta prediction, a representation that includes non-control changes. The accepted ControlEffect head instead predicts a 64D key-name-agnostic controllable-role successor effect and improves held-out projected-evidence MSE by 69.44%.

## Isolation
FIGG-18 `train` only.
- fit indices: `92..103` inclusive per family (48 worlds)
- validation/calibration indices: `104..111` inclusive per family (32 worlds)
- seed: `180618`
- exploration prefix: 6; max steps: 16
No FIGG-18 dev/fresh task may be instantiated.

## Labels
A legal non-submit action is `safe=1` iff the frozen accepted ControlEffect prediction has 64D role-relative MSE `<=0.01` against the train-only counterfactual target; otherwise `safe=0`.

The 0.01 threshold was fixed before these ranges were touched, using only the already-consumed ControlEffect internal-validation distribution (84..91), where it yields 66.2% overall safe rate with 63.6–67.7% per-family safe rates.

## Trainable scope
Exactly the already-existing 257 parameters:
- `conditional_law_confidence_head.weight`
- `conditional_law_confidence_head.bias`

ControlEffect, ConditionalLaw effect/relation weights, evidence memory, R1.7 parent, program executor and policies remain frozen. No parameters are added.

## Optimization
- BCE-with-logits
- AdamW lr `1e-3`, weight decay `1e-4`
- batch 512
- 100 epochs
- select checkpoint only by lowest validation BCE

## Certificate
After best-BCE weights are frozen:
`score = seen_evidence * consistency * context_similarity * sigmoid(confidence_head(hidden))`.

Threshold candidates: `{0.5,0.6,0.7,0.8,0.9,0.95,0.975}`.

Acceptance requires:
- precision >=95% overall;
- precision >=95% in every FIGG-18 family;
- coverage >=20% overall;
- coverage >=10% in every family.
Among passing thresholds choose maximum coverage; ties choose the higher threshold.

A pass authorizes train-internal active-control/forced-planning ablation only. It is not a FIGG-18 dev/fresh or AGI claim.
