# Neural vNext Native R22 — development-rejected conformal singleton goal belief

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R22 attempted to repair R21's confirmation overfit by permitting neural intervention only when a train-only conformal-style prediction set collapsed to one public-consistent goal and all three neural heads agreed.

The safety gate behaved correctly but proved too strict for this learned signal.

On `dev:1248..1279`:

- accepted R11: **122/128**
- R22: **122/128**
- implicit-goal: **28/32 → 28/32**
- overrides vs R11: **0**
- guarded steps: **0**
- visible-target family solved counts: exact

Train-only calibration:

- best preregistered alpha: **0.2**
- gated validation rows: **167**
- correct rows: **133**
- empirical precision: **79.64%**
- required precision: **90%**

Because no guard candidate met the locked precision requirement, R22 failed closed instead of weakening the gate after seeing development.

The same promotion-relevant result and checkpoint/state digests reproduced in both exact-head workflow runs.

- confirmation `1280..1311`: **UNOPENED**
- fresh `280..319`: **UNOPENED**
- no retuning on `dev:1248..1279`

Canonical negative evidence: `evidence/DEV_REJECTED_001.json`.
