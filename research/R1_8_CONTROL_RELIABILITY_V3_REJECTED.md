# R1.8 Control-Sufficient Reliability v3 — Rejected

Date: 2026-08-13
Parent: ControlEffect `ec50d7240d0f3c4073fd849e62e9832a2bde6ab24ecad5cc4c59251dfb3a9f20`
Fit: FIGG-18 train 92..103/family. Validation/calibration: 104..111/family. No FIGG-18 dev/fresh opened.

Only the existing 257-parameter linear confidence head was trained against `safe=1` when frozen 64D control-effect MSE <=0.01.

Validation BCE improved from **0.6931473 to 0.3930928** (best epoch 100), but the preregistered precision/coverage certificate gate failed, so no `CertifiedControl.pt` checkpoint was created.

Diagnostic on the now-consumed validation rows:
- safe rate: 68.78%, 996 rows.
- pure confidence threshold 0.8: 37.7% coverage, 92.8% overall precision; regime-switch precision only 73.5%.
- threshold 0.9: 16.7% coverage, 96.4% overall precision; conditional/implicit/prerequisite are 100/100/100%, but regime-switch only **80.65%**.
- threshold 0.95: 5.1% coverage and 100% precision in selected rows, but regime-switch family coverage is only **2.62%** (other non-prerequisite families also below 10%).
- multiplying by the evidence/context hard gate produces essentially the same regime-switch limitation.

Conclusion: the frozen hidden representation contains useful reliability information, but a single linear 256->1 confidence head cannot separate broad safe/unsafe regions under regime switches. The next experiment must keep the v3 gate unchanged and use new train-only ranges. A small nonlinear certificate may read runtime-available hidden state, predicted 64D control effect, projected evidence effect, their disagreement, and evidence metadata. V3 indices are consumed for certificate selection and cannot be reused to tune v4.
