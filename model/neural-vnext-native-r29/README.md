# Neural vNext Native R29 — development-rejected certified rescue geometry

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R29 added exact public causal next-state geometry and a three-class neutral/rescue/harm learner.

## Learned authority

- goal successor parameters: **107,799**
- rescue-geometry parameters: **59,721**
- total successor parameters: **167,520**
- physical learned parameters: **1,045,062**
- checkpoint SHA-256: `52a7a01eb8c2001d3d0916ea7cde7180c242aa49d6d1f8b0d61d96b899c62753`
- state SHA-256: `9e46261031e4ea07c764ef0a40a347493d09a2a525760e2e28a5b299e9a815ba`

## Counterfactual training result

The dual-certification requirement sharply reduced the useful intervention court:

- **86 rows total**
- **72 neutral**
- **4 rescue**
- **10 harm**

This is much narrower than R28's 209 rows / 19 rescues / 19 harms.

## Guard — failed closed

No preregistered rescue-threshold × harm-ceiling pair achieved the locked cross-block rescue gate. Even the most permissive pairs produced at most two predicted rows across the four blocks and **zero true rescues**.

Thus the neural path was disabled before primary development.

## Primary development

On `dev:1696..1727`:

- accepted R11: **120/128**
- R29: **120/128**
- implicit-goal: **27/32 → 27/32**
- overrides: **0**
- visible-target solved counts: exact

## Interpretation

The failure is now localized further. Certified consequence geometry is public and principled, but requiring a **single action-mass candidate plus dual exact certification** collapses the rescue data distribution before the learner can discover useful intervention structure.

The next successor should stop treating candidate generation as fixed. It should learn terminal rescue/harm **for every available alternative action**, using certification as an optional feature rather than an eligibility requirement.

## Governance

- confirmation `1728..1759`: **UNOPENED**
- fresh `280..319`: **UNOPENED**
- no post-dev tuning
- closes without merge

Workflow: `35500141888`.

Artifact: `10602410861`.

Artifact digest: `sha256:7b02b3e50a23fc56419d2e1d6dc780081dbc41fb334625ae6cea0051cafc4c2d`.

Canonical negative evidence: `evidence/DEV_REJECTED_001.json`.
