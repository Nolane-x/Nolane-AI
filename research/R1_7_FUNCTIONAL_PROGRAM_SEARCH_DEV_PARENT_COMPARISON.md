# R1.7 Functional Search vs frozen parent policy — DEV composition

Date: 2026-08-13

Same frozen checkpoint: `Nolane-R1.7-NCPM-OperatorExecutor.pt`
SHA-256: `bfea6717c5a59b485934b2c9b0f3a48c65ac749a2f638a48a3cfedce6902a735`
Effective parameters: **75,387,546**

Evaluation: FIGG-17 v1.1 `composition_holdout/dev`, indices `0..59` (60 held-out length-3 worlds).

## Frozen parent policy, no Functional Search

- solved: **5/60 = 8.33%**
- mean interaction steps: **2.15**

The parent used its normal full-policy forward path and recurrent state. Functional Program Search was disabled.

## Same checkpoint + Functional Program Search

- solved: **60/60 = 100%**
- demo-exact: **59/60 = 98.33%**
- false-exact: **0/60**
- mean action efficiency: **1.0**
- all six unseen dev templates: **10/10**

## Attribution

No new trainable parameters were introduced by Functional Search. The gain is therefore attributable to inference structure: public-demo parsing + frozen learned operator simulation + shortest functional program search + execution, not additional model capacity.

Absolute solve-rate gain on the paired 60-world dev set: **+91.67 percentage points**.

FIGG-17 fresh remains unopened at the time this comparison is recorded.
