# R1.8 Control Reliability v4 — Nonlinear Runtime Certificate

Date: 2026-08-13
Parent: accepted ControlEffect `ec50d7240d0f3c4073fd849e62e9832a2bde6ab24ecad5cc4c59251dfb3a9f20`.

Reliability v3 showed that the 256D hidden state is informative (BCE 0.693->0.393) but a linear confidence head cannot achieve broad 95%-precision certification in regime-switch worlds. V4 keeps the exact same safety/coverage gate and introduces one small nonlinear certificate over variables available at runtime.

## New certificate head
Input per dynamic action (451D):
- frozen ConditionalLaw hidden: 256D
- frozen predicted control effect: 64D
- context-compatible projected evidence effect: 64D
- absolute predicted-vs-evidence disagreement: 64D
- evidence metadata `(count, consistency, context_similarity)`: 3D

Architecture: `Linear(451,128) -> GELU -> Linear(128,1)` = **57,985 parameters**. Final layer zero-initialized. It is not connected to policy logits.

Final runtime score is `seen_evidence * sigmoid(certificate_logit)`. Context isolation and consistency are already explicit input features; unseen evidence is never certified.

## Isolation
FIGG-18 `train` only.
- fit indices: `112..123` inclusive per family (48 worlds)
- validation/calibration: `124..131` inclusive per family (32 worlds)
- seed: `180718`
- safe label: frozen ControlEffect 64D MSE `<=0.01`
- exploration prefix 6, max steps 16
No FIGG-18 dev/fresh task may be instantiated.

## Optimization
Train only `conditional_reliability_head.*` with BCE-with-logits, AdamW lr `1e-3`, weight decay `1e-4`, batch 512, 100 epochs. Choose epoch solely by lowest validation BCE.

After best-BCE weights are frozen, calibrate thresholds `{0.5,0.6,0.7,0.8,0.9,0.95,0.975}` once.

## Acceptance gate
- precision >=95% overall;
- precision >=95% in every family;
- coverage >=20% overall;
- coverage >=10% in every family;
- effective params <96M.
Among passing thresholds choose maximum coverage; ties choose higher threshold.

A pass authorizes train-internal active-control/forced-planning ablation only. If this small nonlinear certificate fails, R1.8 will stop increasing certificate-head capacity and switch to an explicit hypothesis/state-machine reliability mechanism. No FIGG-18 dev/fresh claim is made here.
