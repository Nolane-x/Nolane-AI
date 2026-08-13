# Nolane R2.0i Active Causal Discovery — Reality Report

Date: 2026-08-13

## Verdict

**ACCEPTED for the bounded FIGG-18 hybrid closed-loop runtime after TRAIN -> DEV -> FRESH.**

R2.0i does not add neural parameters. It combines the frozen R1.9 one-weight plus the accepted-for-policy R2.0e EvidenceEffect executive (**78,779,253 effective neural parameters**) with a **zero-parameter public active-causal discovery controller**. The runtime detects prerequisite-like public auxiliary dynamics, actively experiments with opaque actuators, infers prerequisite-building/enabling/move roles from observed transitions, then navigates to the public target. Non-prerequisite families use the exact R2.0e fixed-depth-1 fallback.

This distinction is essential: the fresh causal gain is a property of the **hybrid runtime**, not evidence that the 78.8M neural weight alone learned the causal-discovery algorithm.

## Bound artifacts

- R1.9 parent SHA-256: `6081a38f65142ae06dc36cba1c9a567a9d0754c08d683d89a8e76f7aade9c52a`
- Frozen R2.0e delta SHA-256: `cb56914f3c9be1c2b0f0b77ff8cb14c16fbca5b2e42d16f227410fc335bf0e0e`
- R2.0i controller SHA-256: `cc254838dd42e1081e888619f71276a3d1af1cf7ba0a55af7796ddbf39eec672`
- Effective neural parameters: **78,779,253**
- R2.0i new neural parameters: **0**
- One-weight deployment: `Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt`
- One-weight bytes: **59,773,663**
- One-weight SHA-256: `b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e`

The one-weight contains the complete R1.9 parent/frontier state plus the R2.0e executive state. The zero-parameter R2.0i runtime source is SHA-bound in the checkpoint metadata and must be present to obtain the active-causal hybrid behavior.

## Integrity before admission

The causal controller was tested through a public-only proxy that rejects private/non-contract attribute access. On train probe indices 1950..1959 it solved **10/10 causal prerequisite worlds** using only public `observe`, `step`, action descriptions, public state/target, and name-agnostic auxiliary numeric changes.

The controller does not read `_action_kinds`, `_goal`, `_resource`, `_gate`, transition internals, oracle plans, hidden answers, or private simulator fields. Opaque non-submit action labels are not interpreted.

## Locked TRAIN gate

FIGG-18 train indices `2000..2019`, 20 worlds per family:

| Family | R2.0e depth1 | R2.0i hybrid |
|---|---:|---:|
| conditional regimes | 45% | 45% |
| regime switch | 30% | 30% |
| implicit goal regimes | 60% | 60% |
| causal prerequisites | 15% | **100%** |
| **Aggregate** | **37.5% (30/80)** | **58.75% (47/80)** |

Aggregate gain: **+21.25 percentage points**. Causal gain: **+85 points**. Maximum family regression: **0**.

## Locked DEV

DEV indices `256..275`, selected specifically to avoid R1.9's previously consumed low-index evaluation region:

- baseline: **29/80 = 36.25%**
- R2.0i: **48/80 = 60.0%**
- gain: **+23.75 points**
- causal prerequisites: **5% -> 100%**
- maximum family regression: **0**

No controller/model/evaluator tuning followed DEV.

## Locked FRESH

Pre-fresh lock bound source hashes, neural parents, fresh split and indices before opening. R1.9's consumed fresh 0..7 region was not reused. R2.0i used fresh indices `512..531` per family.

- baseline: **29/80 = 36.25%**
- R2.0i hybrid: **48/80 = 60.0%**
- gain: **+23.75 points**
- conditional: **50% -> 50%**
- regime switch: **25% -> 25%**
- implicit goal: **65% -> 65%**
- causal prerequisites: **5% -> 100%**
- maximum family regression: **0**

The fresh split is now **consumed**. Post-fresh tuning is forbidden.

## Deployment reproduction

The accepted neural components were repackaged into the single deployment weight without additional quantization or training. The one-weight loader was then run across all **80 already-consumed fresh episodes** and compared with the acceptance run:

- solve count: **48/80**
- action/solve mismatches: **0/80**

This is a deployment-reproduction check, not a new untouched-fresh evaluation.

## R2.0 research negatives retained

R2.0a-h were not hidden when they failed. The sequence established that:

- longer imagination alone did not improve closed-loop control;
- full-trajectory supervision alone was insufficient;
- public action/effect memory materially strengthened shallow control;
- evidence-conditioned depth2 could regress action ranking;
- goal-directed future value removed some regressions but did not pass +10 pp;
- per-step and per-episode depth routing had complementarity signal but failed admission gates;
- the causal prerequisite block remained the dominant failure until active public experimentation was introduced.

These failures motivated R2.0i rather than parameter inflation.

## Verification status

Current R1.9-frontier + R2.0e-i focused release suite (tests that can run from the one-weight-oriented workspace):

```text
51 passed, 28 PyTorch warnings
```

A broader invocation also ran seven historical R1.9 rollout/training tests that require the old split `Nolane-R1.8-CCSM-ConditionalLaw.pt` file. Those seven stopped with `FileNotFoundError` because the new release intentionally carries one deployment weight instead of restoring historical split weight binaries. They are reported as a legacy test-fixture dependency, not claimed green and not hidden.

## What this proves

Within the bounded FIGG-18 environment, a sub-79M neural core combined with a zero-parameter public active-experimentation controller can materially improve closed-loop generalization on prerequisite tasks and preserve other tested family behavior across locked train, DEV and FRESH procedural splits.

## What this does not prove

R2.0i is **not** proof of AGI, broad language intelligence, open-world scientific discovery, or superiority to >100B models. The causal controller is still tailored to a structural class of publicly observable prerequisite environments, even though it does not know the benchmark's hidden action roles. ARC-AGI-2, HLE, FrontierMath, Terminal-Bench and other external frontier suites still need to be run under exact official/verifier-backed protocols before any broad frontier claim is permitted.
