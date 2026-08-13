# R1.7 Neural Operator Executor optimizer configuration

Date: 2026-08-13
Parent: accepted Goal-Difference checkpoint
Benchmark: FIGG-17 v1.1 train-only composition transitions

This file fixes optimizer/runtime choices **before any validation metric is observed**.

- fit worlds: composition train indices 282..481 inclusive (200 worlds, expected 1,000 one-step transitions)
- validation worlds: 482..521 inclusive (40 worlds, expected 200 transitions)
- seed: 170917
- optimizer: AdamW
- learning rate: 0.002
- weight decay: 0.0001
- epochs: 80
- batch size: 128
- gradient clip: 1.0
- trainable scope: exactly `program_executor_*`
- action encoder and all parent/world/policy parameters frozen
- checkpoint selection: first epoch satisfying the preregistered executor gate; if later epochs also pass, retain the epoch with highest exact-vector accuracy, then highest element accuracy as tie-break

Acceptance thresholds remain those in the main protocol: exact-vector >=0.98, per-element >=0.995, and each non-submit public operator-description group >=0.95 exact-vector accuracy. FIGG dev/fresh remain unopened.
