# R1.8 Nonlinear Reliability v4 — Rejected

Date: 2026-08-13
Parent: ControlEffect `ec50d7240d0f3c4073fd849e62e9832a2bde6ab24ecad5cc4c59251dfb3a9f20`
Fit: FIGG-18 train 112..123/family. Validation/calibration: 124..131/family. No FIGG-18 dev/fresh opened.

V4 added a 57,985-parameter nonlinear runtime certificate over `hidden256 + predicted_control64 + projected_evidence64 + disagreement64 + evidence_meta3`. It preserved the same preregistered safety gate as v3.

Validation BCE improved from **0.6931473 to 0.4117344** (best epoch 85), but no threshold in the locked grid simultaneously achieved >=95% precision overall/per-family and >=20% overall / >=10% per-family coverage. No accepted v4 checkpoint was created.

Follow-up diagnostics on consumed ranges also rejected two non-neural alternatives as standalone certificates:
- nearest-state evidence: at ~50% coverage, safe-effect precision is only ~67%; exact neighbors have negligible coverage;
- simple symbolic constant/categorical/periodic consensus hypotheses have only ~5% coverage and ~41% precision under the existing exploration trajectory.

Conclusion: static prediction certification is not providing enough broad, high-precision coverage for conditional/regime-switch control. Per the v4 protocol, R1.8 stops increasing certificate-head capacity.

Next direction: Verified Active Executive. The accepted ConditionalLaw/ControlEffect models remain proposal/world representations. A small recurrent executive learns explore-vs-exploit from public state/evidence/feedback, executes only one step at a time, verifies the actual public transition/progress after every action, and replans. Closed-loop held-out performance—not teacher-forced accuracy—will be the acceptance criterion.
