# R1.6 Dual-Role Causal Binder — pre-training checkpoint

Status: implemented locally and verified before training.

- Unit invariants: zero-neutral at scale/evidence zero; two learned roles produce distinct evidence; dynamic-action permutation equivariance preserved.
- Focused gate before training: 55/55 passed.
- Live experimental effective parameter count at this point: 71,750,141 (below the current 75M research ceiling).
- This file records architecture readiness only. No claim is made that the Dual-Role Binder improves closed-loop capability until train-only calibration and a held-out dev gate are completed.

This commit is intentionally created before any further experiment so the architecture cannot be lost if the local workspace disappears.