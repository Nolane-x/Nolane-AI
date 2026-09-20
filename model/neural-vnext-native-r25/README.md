# Neural vNext Native R25 — development-rejected selective R11 error correction

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R25 separated the intervention problem into a learned R11-mistake detector and a mistake-only action corrector.

## Learned authority

- ensemble size: 3
- hidden dimension: 64
- successor parameters: **75,846**
- total physical learned parameters: **953,388**
- checkpoint SHA-256: `69a73cf7c330ecde760db457d2fb435131a7bf036a428f66ba207f021005d4d8`
- state SHA-256: `c036bf29236c0c15333894f8243bc561091e5160085a95e01425f8d4ea567956`

Private hidden goals were used only to construct train-only teacher labels. Dev/inference remained public-only.

## Train-only guard result

No preregistered detector threshold achieved the required **>=90% precision with >=12 actual overrides**:

- 0.5: **15/70 = 21.43%**
- 0.6: **12/41 = 29.27%**
- 0.7: **8/24 = 33.33%**
- 0.8: **7/14 = 50.00%**
- 0.9: **0/1 = 0%**

The guard therefore failed closed before primary development.

## Primary development

On `dev:1440..1471`:

- accepted R11: **124/128**
- R25: **124/128**
- implicit-goal: **31/32 → 31/32**
- neural overrides: **0**
- visible-target family solved counts: exact

R25 is rejected at development.

## Governance

- confirmation `1472..1503`: **UNOPENED**
- fresh `280..319`: **UNOPENED**
- no threshold relaxation or same-dev retuning
- closes without merge

Workflow: `35497341903`.

Artifact: `10601136414`.

Artifact digest: `sha256:27efa91e8a7e3ae87f569cecbea9fb311e49c5d82e6a2f216a4e77bf70b65911`.

Canonical negative evidence: `evidence/DEV_REJECTED_001.json`.
