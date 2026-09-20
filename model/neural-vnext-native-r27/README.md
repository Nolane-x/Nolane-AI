# Neural vNext Native R27 — development-rejected robust action-mass consensus

Status: **DEV REJECTED; CONFIRMATION AND FRESH UNOPENED**.

R27 kept R26's learned action-equivalence mechanism but replaced single-block calibration with four disjoint train-only guard blocks.

## Learned authority

- successor parameters: **107,799**
- physical learned parameters: **985,341**
- checkpoint SHA-256: `bb087dec6fe1e0b68a1b5a24650c7434010515c30e1584d78c73177c0f9cbe10`
- state SHA-256: `7f22a64937503cd29cb102b951c02b802b3950552c1df7b55608396f60244ba5`

## Robust train-only guard

The selected threshold was **0.95**:

- block 8512..8575: **24/24 = 100%**
- block 8576..8639: **24/24 = 100%**
- block 8640..8703: **30/30 = 100%**
- block 8704..8767: **18/19 = 94.74%**
- aggregate: **96/97 = 98.97%**
- worst block precision: **94.74%**

This is the first Native successor in this line where train-only action precision and cross-block robustness both cleared the locked gate.

## Primary development — rejected

On `dev:1568..1599`:

- accepted R11: **117/128**
- R27: **117/128**
- implicit-goal: **24/32 → 24/32**
- neural overrides: **2**
- visible-target family solved counts: exact

R27 therefore fails the strict promotion rule.

The important negative result is that **teacher-action correctness is not sufficient evidence of episode-level rescue value**. A future learned successor should predict whether an intervention changes the terminal episode outcome, not merely whether it agrees with a true-goal one-step teacher.

## Governance

- confirmation `1600..1631`: **UNOPENED**
- fresh `280..319`: **UNOPENED**
- no post-dev threshold retuning
- closes without merge

Workflow: `35499188271`.

Artifact: `10601758836`.

Artifact digest: `sha256:c2b1a84e073b93017bbd1112331da377517c708cf33983a664ea269c59990291`.

Canonical negative evidence: `evidence/DEV_REJECTED_001.json`.
