# R1.6 Bounded Transition — New Held-Out Dev Gate

Date: 2026-08-12 (Asia/Bangkok)

## Gate discipline

The transition candidate was selected using train-internal validation only. It was then evaluated once on a **different dev slice**: indices 6-11 for every family, 18 worlds total. These are distinct from the historic first-six dev tasks and from the small MPC calibration slice.

Fresh remained unopened.

## One-step transition results

| Family | N transitions | Candidate MSE | Persistence MSE | Candidate cosine | Persistence cosine | Pred delta norm | Real delta norm |
|---|---:|---:|---:|---:|---:|---:|---:|
| causal identification | 56 | **0.0032474** | 0.0045053 | **0.997751** | 0.996752 | 0.539 | 1.262 |
| delayed resource | 51 | **0.0042166** | 0.0048739 | **0.996967** | 0.996492 | 0.648 | 1.247 |
| compositional rule | 21 | 0.0010109 | **0.0009330** | 0.999298 | **0.999347** | 0.292 | 0.671 |

Weighted overall:

- candidate MSE: **0.0032666**
- persistence MSE: **0.0040661**
- candidate/persistence ratio: **0.80339**
- improvement over persistence: **19.66%**

## Verdict

**PASS — retained transition capability.**

This is the first R1.6 transition candidate to beat the persistence prior on a genuinely held-out dev slice after being selected without dev feedback. Causal and resource dynamics generalize strongly; compositional-rule transitions remain slightly better served by persistence and are a known area for future confidence-gating.

Retained checkpoint:

- `Nolane-R1.6-NS2-BoundedTransitionInternal.pt`
- SHA-256: `94de757295368107099fd5d9060be2f617792d7e3da5c4bcf8b30d52260b1f0e`

Next step: retry model-predictive planning using this now-calibrated transition, with policy hyperparameters calibrated away from the new held-out gate and a separate untouched dev slice for policy validation.
