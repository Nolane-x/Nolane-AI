# R1.8 Reliability Certificate v2 — Rejected

Date: 2026-08-13
Parent: ConditionalLaw `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`
Train-only fit: indices 48..59/family. Validation/calibration: 60..67/family. No FIGG-18 dev/fresh opened.

Only the existing 257-parameter `conditional_law_confidence_head` was trained. Validation BCE improved strongly from **0.6233056 to 0.3733177** (best epoch 96), proving the hidden law representation contains error-predictive information.

However the preregistered precision/coverage gate failed, so no `CertifiedLaw.pt` checkpoint was accepted.

Diagnostics on the now-consumed validation rows:
- threshold 0.8: 58.57% coverage, 90.29% overall precision; regime-switch precision 71.88%.
- threshold 0.9: 31.76% coverage, 93.72% overall precision; prerequisites 96.64%, conditional 94.34%, implicit-goal 95.52%, regime-switch only 71.43%.
- threshold 0.95: 6.79% coverage and 100% precision, but family coverage is only 14.87% prerequisites, 1.59% conditional, 1.11% implicit-goal, 0.37% regime-switch.
- threshold 0.975: only prerequisites are selected.

The v2 gate required >=95% precision overall and per family, >=20% overall coverage and >=10% family coverage. No threshold passed.

Interpretation: the linear confidence head can identify a small set of extremely safe predictions, but cannot provide sufficiently broad certified coverage, especially across regime switches. A likely missing variable is locality: the runtime evidence memory already stores the public pre-state where an action effect was observed, but v1/v2 certification ignored distance from the current state to that evidence state. Any v3 experiment must use new train-only ranges and must not relax the v2 gate on consumed indices.
