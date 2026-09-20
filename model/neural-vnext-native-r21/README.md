# Neural vNext Native R21 — confirmation-rejected supervised public hidden-goal belief

Status: **REJECTED BEFORE FRESH**.

R21 tested a dedicated neural hidden-goal belief model over accepted R11. Three neural heads were explicitly supervised on hidden-goal labels using train-only identities. Inference remained public-only and the exact public consistency mask remained a hard support boundary.

## Frozen primary winner

Selected candidate: `goalblend100`

- beta: **1.0**
- max support: **3**
- temperature: **2.0**
- successor trainable parameters: **107,799**
- physical learned parameters: **985,341**
- checkpoint SHA-256: `4b11f7580bb35e90c54d697d4fbad238640a16cd69c6f7a771f670eaf8e2718c`
- state SHA-256: `a3329d41d5138701617fc096d226045e0cae22f9e56945de3e35440ac795ca7e`

The exact checkpoint, manifest, and primary-result files reproduced byte-for-byte across the independent push and PR workflows.

## Primary development

On `dev:1184..1215`:

- accepted R11: **116/128**
- R21: **117/128**
- implicit-goal: **26/32 → 27/32 (+1)**
- visible-target family solved counts: exact

This passed the preregistered primary gate.

## Disjoint confirmation — rejected

The exact frozen checkpoint/config was then evaluated unchanged on `dev:1216..1247`:

- accepted R11: **116/128**
- R21: **115/128**
- implicit-goal: **27/32 → 26/32 (-1)**
- visible-target family solved counts: exact

Confirmation workflow: `35495563132`.

Artifact: `10599644791`.
Digest: `sha256:4cb009b24bf949114566c8e2a5fee45be917c5ec81ae98133849183f2d3bee2d`.

The confirmation reversal is treated as a real generalization failure. The gate is not relaxed and R21 is not retuned against this block.

## Governance

- R21 closes without merge.
- `dev:1216..1247` is consumed as R21 confirmation evidence.
- `fresh:280..319` was **never opened** and remains untouched.
- no post-confirmation tuning of this checkpoint is allowed.
- a future successor must use a new candidate identity and new train/dev/confirmation identities.

Canonical evidence: `evidence/CONFIRMATION_REJECTED_001.json`.
