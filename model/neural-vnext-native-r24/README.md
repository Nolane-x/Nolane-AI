# Neural vNext Native R24 — development-rejected sequential public evidence filter

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R24 tested a learned sequential evidence representation over accepted R11. Instead of fitting a snapshot-to-goal/action mapping, each public transition emitted a learned evidence increment over the 125 hidden-goal hypotheses and evidence accumulated through the episode.

## Learned architecture

- 3 independently initialized evidence heads
- hidden dimension: 96
- successor parameters: **83,607**
- total physical learned parameters with accepted R4 substrate: **961,149**
- checkpoint SHA-256: `cd8b0c73c76324475eb61dc92aa604e931c0d40c0a4baabe7633a4fbca5db2e6`
- state SHA-256: `06850a9ee528caa939ada1e99a963d850c36c5dfdaa6040486ed9bb38ec31296`

Private hidden-goal labels were train-only. Dev/inference remained public-only and exact public consistency remained a hard support mask.

## Train-only action guard result

The sequential representation produced substantially more possible R11-changing decisions than R23, but precision remained too low:

- threshold 0.45: **21/33 = 63.64%**
- threshold 0.55: **21/33 = 63.64%**
- threshold 0.65: **20/31 = 64.52%**
- threshold 0.75: **19/29 = 65.52%**
- threshold 0.85: **19/28 = 67.86%**
- preregistered requirement: **>=90% precision and >=12 overrides**

No candidate met the locked calibration gate, so the neural override path was disabled before development.

## Primary development

On `dev:1376..1407`:

- accepted R11: **120/128**
- R24: **120/128**
- implicit-goal: **27/32 → 27/32**
- neural overrides: **0**
- visible-target family solved counts: exact

R24 is therefore rejected at development.

## Governance

- confirmation `1408..1439`: **UNOPENED**
- fresh `280..319`: **UNOPENED**
- no threshold relaxation or same-dev retuning
- PR closes without merge
- a successor must use a new mechanism identity and new train/dev/confirmation identities

Workflow: `35496988556`.

Artifact: `10600736393`.

Artifact digest: `sha256:5b4d611b1c163821bd2edd281d1f7977914b972ed01fe2ff6023cb6e6a60e9f2`.

Canonical negative evidence: `evidence/DEV_REJECTED_001.json`.
