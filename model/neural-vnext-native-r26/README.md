# Neural vNext Native R26 — development-rejected calibrated action-mass consensus

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R26 converted a supervised public hidden-goal ensemble into per-head probability mass over **causal actions**, rather than requiring exact goal identity.

## Learned authority

- successor parameters: **107,799**
- physical learned parameters: **985,341**
- checkpoint SHA-256: `1ad81a52406fccc4233e95a40f51c17dccc3fb138768576e71d3ba908cd05b38`
- state SHA-256: `72a964a565cfe82d96cb3eb6d488c07cfb4e9f86a91515ac302a3d190f1b6ad4`

## Train-only guard

Action-mass consensus substantially improved over R23-R25:

- 0.55: 28/37 = **75.68%**
- 0.65: 25/27 = **92.59%** — selected
- 0.75: 20/21 = **95.24%**
- 0.85: 20/20 = **100%**
- 0.90: 20/20 = **100%**
- 0.95: 19/19 = **100%**

The preregistered train-only gate therefore enabled the 0.65 candidate.

## Primary development — rejected

On `dev:1504..1535`:

- accepted R11: **120/128**
- R26: **117/128**
- implicit-goal: **28/32 → 25/32 (-3)**
- neural overrides: **14**
- visible-target family solved counts: exact

This shows a calibration-transfer failure: train-only action precision was high, but it did not generalize to the locked development identities. The dev block is not used for threshold retuning.

## Governance

- confirmation `1536..1567`: **UNOPENED**
- fresh `280..319`: **UNOPENED**
- no post-dev tuning of this candidate
- closes without merge

Workflow: `35497564155`.

Artifact: `10600861899`.

Artifact digest: `sha256:c19261c84be0f77d6a18c51a45dc3cd587209703a05fc7cee3c9f38a6acc1405`.

Canonical negative evidence: `evidence/DEV_REJECTED_001.json`.
