# R1.7 CRGM retrieved-law world model — REJECTED

Date: 2026-08-13
Benchmark: FIGG-17 v1.1 train-only
Parent: accepted Goal-Difference world model

Protocol: causal_laws + causal_switch, fit 170..185/family, internal validation 186..193/family, 40 epochs, seed 170617. Policy scale remained zero. Gate required CRGM to beat frozen Goal-Difference on both progress MSE and top-action ranking.

## Validation baseline

Frozen Goal-Difference:
- MSE: `0.0464132152733932`
- top-action ranking accuracy: `0.5766871165644172`
- causal_laws rank: `0.42168674698795183`
- causal_switch rank: `0.7375`

## CRGM behavior

Initial CRGM:
- MSE: `0.047562809596276234`
- rank: `0.50920245398773`

During training CRGM MSE approached the baseline but never produced the preregistered ranking gain. Typical late result:
- MSE: approximately `0.04655319`
- rank: approximately `0.57055`
- causal_laws rank: approximately `0.38554` (worse than baseline)
- causal_switch rank: `0.7625` (better than baseline)

No epoch satisfied the full MSE + ranking + per-family gate. `best_epoch=0`; no CRGM checkpoint was created and FIGG-17 dev/fresh remained unopened.

## Interpretation

The parameter-free role binder is not the failure: it identified causal current/target roles perfectly in the preceding 100-world diagnostic and passed real-world regression tests. The failure is the interface from accepted Causal Law latent retrieval to role-relative action utility. A generic MLP over `[need, retrieved_law, interaction]` cannot reliably decode action effects, especially in `causal_laws`.

Next direction: represent observed/predicted causal effects directly in the **same role-relative position/value coordinate system** as the goal need, rather than decoding them from the 256D latent law representation.
