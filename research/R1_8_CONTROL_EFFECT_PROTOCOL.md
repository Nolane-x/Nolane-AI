# R1.8 Control-Sufficient Effect Head Protocol

Date: 2026-08-13
Parent: accepted ConditionalLaw `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`.

Reliability v1/v2 were rejected before any FIGG-18 dev/fresh evaluation. Diagnostics show that neither model-memory agreement nor the existing linear confidence head provides broad high-precision certification in regime-switch worlds. A post-hoc projection of the already-trained 128D structured-delta prediction also fails to make reliability monotone. This indicates the transition objective itself is not sufficiently control-aligned.

## New objective
Infer a controllable numeric-vector role from **public dynamics**: after an intervention, accept a role only when exactly one multi-position public numeric vector changes. The role projection maps path-specific structured 128D deltas into a 64D position/value coordinate that ignores literal field names. Ambiguous/no-change transitions abstain rather than guess.

Once a role projection has been observed, every legal action's train-only counterfactual structured delta can be projected into the same 64D control-effect coordinates.

Add one zero-initialized head on the frozen accepted ConditionalLaw hidden state:
`conditional_control_effect_head: Linear(256, 64)` = **16,448 params**.
All accepted ConditionalLaw relation/state/context/action/evidence weights remain frozen in the first experiment.

## Train-only isolation
- fit indices: `68..83` per FIGG-18 family (64 worlds)
- internal-validation indices: `84..91` per family (32 worlds)
- seed: `180518`
- exploration prefix: 6, max steps 16
- rows are emitted only after a public controllable-role projection has been identified
- no FIGG-18 dev/fresh task may enter collection/training

## Optimizer
- only `conditional_control_effect_head.*`
- AdamW lr `1e-3`, weight decay `1e-4`
- 50 epochs, batch 256, clip 1.0

## Baseline and gate
Baseline is the **same role projection applied to context-compatible evidence memory**. Candidate is the new neural 64D control-effect head.

Acceptance requires:
1. aggregate held-out control-effect MSE strictly below projected evidence baseline;
2. no FIGG-18 family may have candidate MSE above its own baseline;
3. each family must contribute at least 64 evaluated action-effect rows;
4. effective parameter count <96M;
5. parent effect model and policies remain byte-behavior frozen.

A pass returns to reliability calibration on new train ranges. It is not a closed-loop or fresh claim.
