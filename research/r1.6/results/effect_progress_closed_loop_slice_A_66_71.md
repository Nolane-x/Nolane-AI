# Effect-to-Progress Critic — closed-loop gate slice A

Date: 2026-08-12 (Asia/Bangkok)

Preregistered held-out slice: dev indices 66–71 per family. No tuning occurred after opening this slice.

## CurrentBest control

- solved: **3/18**
- causal identification: **0/6**
- delayed resource: **3/6**
- compositional rule: **0/6**
- mean steps: `7.1667`

## EffectProgress candidate

- solved: **7/18**
- causal identification: **1/6**
- delayed resource: **6/6**
- compositional rule: **0/6**
- mean steps: `6.8333`

Candidate checkpoint SHA-256: `0a1688062f7640739847070a54ea079a28c10c010b286c5b640645214e912ace`.

Slice A therefore shows a strict total gain and a causal gain, with no family regression in solved count. **This is not yet an accepted R1.6 capability update** because the preregistered gate also requires non-regression on slice B (dev72–77), strict aggregate total gain, and strict aggregate causal gain across both slices.