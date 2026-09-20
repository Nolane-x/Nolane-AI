# Neural vNext Native R12 — confirmation-rejected neural causal residual

Status: **REJECTED BEFORE FRESH**.

R12 was the first successor after accepted R11 to move causal reasoning back into a learned neural residual.

## Primary result

On locked `dev:608..639`:

- accepted R11: **122/128**
- R12 `neural_causal_broad`: **124/128**
- implicit-goal: **29/32 → 31/32 (+2)**
- visible-target family solved counts: exact

The exact checkpoint reproduced bitwise across independent push/PR workflows:

- checkpoint SHA-256: `830cc54af53309757f7558d5725a525766a346984e41e8702e7cc49035c7852c`
- successor-state SHA-256: `b1ae10542cfa15a5dabc7869c118cd41af055f0ef95175c913488b7080b53b03`
- trainable successor parameters: **67,265**
- physical parameters: **944,807**

## Disjoint confirmation — REJECTED

The exact frozen checkpoint was evaluated unchanged on `dev:640..671`.

- accepted R11: **123/128**
- R12: **121/128**
- implicit-goal: **29/32 → 27/32 (-2)**
- visible-target family solved counts: exact

Confirmation workflow: `35489209358`.
Artifact: `10598885228`.
Digest: `sha256:2a4b375d5fa05d2b6470d4966d9ba08d85f4960e43d5f9cf9bec84cf061dbfbe`.

This reverses the primary gain and is treated as genuine overfit.

## Governance

R12 closes without merge.

- no post-confirmation tuning of this checkpoint;
- confirmation identities are consumed for R12;
- `fresh:280..319` was **never opened** and remains untouched;
- a future successor must use a new candidate identity and new train/dev identities before it may request that fresh block.

Canonical rejection evidence: `evidence/CONFIRMATION_REJECTED_001.json`.
