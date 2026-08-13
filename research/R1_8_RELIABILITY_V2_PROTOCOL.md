# R1.8 Reliability Certificate v2 — Learned Confidence Protocol

Date: 2026-08-13
Parent: accepted ConditionalLaw `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`.

V1 parameter-free model-memory agreement was rejected on train indices 32..47 and those rows are consumed for certificate selection.

## Isolation
FIGG-18 `train` only. Fit indices `48..59` per family (48 worlds). Validation/calibration indices `60..67` per family (32 worlds). No FIGG-18 dev/fresh task is instantiated.

## Trainable scope
Exactly the already-existing 257 parameters:
- `conditional_law_confidence_head.weight`
- `conditional_law_confidence_head.bias`

The accepted effect predictor, all other conditional-law parameters, evidence memory, R1.7 parent, program executor and policies remain frozen. No parameters are added.

## Labels and optimization
For every legal non-submit action on cached train-only states, target is `safe=1` iff frozen ConditionalLaw structured-effect MSE to the public counterfactual train target is <= `0.005`; otherwise `safe=0`.

Train with BCE-with-logits, AdamW lr `1e-3`, weight decay `1e-4`, batch 512, 100 epochs. No class weighting. Select the checkpoint only by lowest validation BCE, never by threshold-gate performance.

## Final certificate score
`seen_evidence * consistency * context_similarity * sigmoid(confidence_head(hidden))`.

After the best-BCE checkpoint is frozen, calibrate once on validation rows using thresholds `{0.5,0.6,0.7,0.8,0.9,0.95,0.975}`.

Acceptance requires:
- precision >=95% overall;
- precision >=95% in every family;
- coverage >=20% overall;
- coverage >=10% in every family.
Among passing thresholds choose maximum coverage; ties choose the higher threshold.

A pass authorizes only the next train-internal active-control/forced-planning ablation. It is not a FIGG-18 dev or fresh capability claim.
