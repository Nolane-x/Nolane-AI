# R1.6 Predictive-State Rollout — Closed-Loop Capability Gate

Date: 2026-08-12 (Asia/Bangkok)

## Calibration discipline

The PSR transition had already passed an independent held-out state/outcome gate. Policy integration used:

- fixed horizon: **2**;
- fixed discount: **0.7**;
- one scalar alpha learned only from teacher-action CE on **train indices 25-29/family** (15 worlds), separate from PSR fit/internal-val and transition fit/internal-val;
- learned alpha: **1.2104157209**;
- fresh: unopened.

Train-only scalar calibration improved CE from ~1.0836 to ~1.0297. This was not treated as a capability result.

## Untouched closed-loop policy gate

Evaluation slice: **dev indices 24-29/family**, 18 worlds. This slice had not been used by prior transition, MPC, PSR transition, or policy gates.

| Policy | Total | Causal | Resource | Rule | Mean steps |
|---|---:|---:|---:|---:|---:|
| retained PSR checkpoint, alpha=0 | **2/18 (11.1%)** | 0/6 | 2/6 | 0/6 | 5.89 |
| PSR rollout, alpha=1.2104 | **4/18 (22.2%)** | 0/6 | **3/6** | **1/6** | 7.06 |

## Verdict

**PASS — closed-loop capability gain retained.**

For the same neural checkpoint and same public observations, rollout in the explicitly trained predictive-state representation doubled held-out task success from 2/18 to 4/18. Gains appeared in delayed-resource planning and compositional-rule execution. Causal identification remains unsolved on this slice and is the main remaining bottleneck.

This is the first R1.6 planning method in the current research line to beat its same-checkpoint no-planning control on an untouched closed-loop dev slice.

## Next step

Integrate a zero-initialized `psr_policy_scale` into production `forward()`, set it to the train-only calibrated value in a locked candidate checkpoint, verify exact reproduction of the external gate, then evaluate once on another untouched dev slice before considering an R1.6 fresh lock.

Fresh remains unopened.
