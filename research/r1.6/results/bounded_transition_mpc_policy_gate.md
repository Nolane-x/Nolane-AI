# R1.6 Learned-Transition MPC — Closed-Loop Policy Gate

Date: 2026-08-12 (Asia/Bangkok)

## Setup

The retained `BoundedTransitionInternal` checkpoint had already passed a one-step held-out transition gate (~19.66% lower MSE than persistence overall on dev indices 6-11/family).

MPC policy calibration deliberately avoided dev hyperparameter sweeps:

- fixed horizon = 2;
- fixed discount = 0.7;
- one scalar alpha learned from teacher-action CE on **train indices 20-24/family** (15 procedural worlds), which were separate from transition fit/internal-validation worlds;
- learned alpha: **0.93882**;
- teacher CE improved from ~1.058 to ~1.033, while argmax teacher accuracy stayed ~52.2%;
- policy gate: **dev indices 12-17/family**, 18 previously unused policy-gate worlds;
- fresh: unopened.

## Closed-loop gate

| Policy | Solved | Causal | Resource | Rule | Mean steps |
|---|---:|---:|---:|---:|---:|
| transition model, no MPC (alpha=0) | **3/18** | 0/6 | **3/6** | 0/6 | 7.50 |
| transition model + MPC alpha=0.93882 | **0/18** | 0/6 | 0/6 | 0/6 | 10.39 |

## Verdict

**MPC POLICY REJECTED.**

A one-step transition model can generalize and beat persistence while still being unsuitable for recursive rollout. The current MPC feeds predicted Stage-2 latents back into `world_state`, but `world_state` was trained on cognitive states generated from real public observations, not its own imagined-latent distribution. Multi-step rollout therefore introduces a severe model-distribution shift and compounds errors.

The learned one-step bounded transition remains a retained capability/result. It must not be used recursively until the world model is trained on rollout-compatible state representations.

## Next direction

Build a compact Predictive State Representation (PSR) over **public structured state/effect atoms**, and supervise action-conditioned successor representations—including counterfactual legal actions—directly. Planning should roll out inside that explicitly trained predictive-state space rather than recursively hallucinating Stage-2 text latents.

Fresh remains unopened.
