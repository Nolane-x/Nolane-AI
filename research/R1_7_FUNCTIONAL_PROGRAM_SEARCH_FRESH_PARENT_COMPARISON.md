# R1.7 Functional Search vs frozen parent policy — FRESH composition

Date: 2026-08-13

Same frozen checkpoint: `Nolane-R1.7-NCPM-OperatorExecutor.pt`
SHA-256: `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`
Effective parameters: **75,387,546**

Evaluation: FIGG-17 v1.1 `composition_holdout/fresh`, indices `0..59`, six unseen length-4 program templates.

## Frozen parent policy, no Functional Search

- solved: **0/60 = 0%**
- mean interaction steps: **2.1167**

## Same checkpoint + Functional Program Search

- solved: **60/60 = 100%**
- demo-exact: **60/60 = 100%**
- false-exact: **0/60**
- mean action efficiency: **1.0**
- all six fresh templates: **10/10**

## Attribution

Functional Search introduces **0 trainable parameters**. The paired fresh gain is therefore attributable to inference architecture — learned operator simulation plus public-demonstration functional search — rather than parameter growth.

Absolute paired fresh solve-rate gain: **+100 percentage points**.

This comparison is post-hoc on the already-consumed fresh set and is used only for attribution, not model selection or tuning.
