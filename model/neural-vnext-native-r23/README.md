# Neural vNext Native R23 — development-rejected conformal action consensus

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R23 tested a stronger interpretation of uncertain hidden-goal belief: exact goal identity was not required when every goal in a conformal prediction set implied the same accepted causal action.

Train-only calibration measured action-level override precision versus the true-goal causal teacher action.

On `dev:1312..1343`:

- accepted R11: **120/128**
- R23: **120/128**
- implicit-goal: **26/32 → 26/32**
- overrides vs R11: **0**
- visible-target family solved counts: exact

The action guard improved precision compared with R22 but lacked coverage:

- alpha 0.1: **3/3 candidate overrides correct (100%)**
- locked minimum override rows: **12**
- therefore guard status: **disabled / fail-closed**

The gate was not weakened after observing development. Both exact-head workflow runs reproduced the same checkpoint/state digests and promotion-relevant result.

- confirmation `1344..1375`: **UNOPENED**
- fresh `280..319`: **UNOPENED**
- no retuning on `dev:1312..1343`

Canonical negative evidence: `evidence/DEV_REJECTED_001.json`.
