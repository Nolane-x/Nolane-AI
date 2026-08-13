# R1.7 Goal-Difference internal world-model gate — ACCEPTED

Date: 2026-08-13
Benchmark: FIGG-17 v1.1
Parent: accepted Causal Law checkpoint `e6c99e5944b68c2fde7f89e7dec478b54e93f3a3250adfd806e1020b46239dbc`

The preregistered 30-epoch run completed on train-only procedural worlds after fixing provenance serialization without changing the split, seed, objective, optimizer or model architecture.

## Protocol

- families: `causal_laws`, `causal_switch`
- fit indices: 56..71 inclusive per family (32 worlds)
- internal validation: 72..79 inclusive per family (16 worlds)
- seed: 170317
- exploration prefix: 6 reachability-safe non-submit probes
- maximum steps: 14
- optimizer scope: `goal_difference_*` except `goal_difference_policy_scale`
- policy scale remained exactly 0.0

## Accepted result

- baseline MSE: `0.09718381396184365`
- Goal-Difference MSE: `0.046589840832468754`
- relative improvement: `52.0600818869273%`
- `causal_laws`: `0.11418738775772222 -> 0.04593915689998029` (`59.76862436204253%` improvement)
- `causal_switch`: `0.08061622923765427 -> 0.04722384056156008` (`41.42142220228934%` improvement)
- best epoch: 30

## Checkpoint

- file: `checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt`
- SHA-256: `84c00198b9cc0d65e68789b445c3635dba8403e105b4fc9d05029e047ef3a11a`
- bytes: 100,619,499
- effective candidate parameters: 74,660,997
- hard ceiling: 96,000,000

## Verification

- checkpoint loader / lineage assertions: PASS
- Goal-Difference + CausalLaw + FIGG targeted suite: **34/34 passed**
- FIGG-17 fresh remains unopened.

This is evidence for held-out train-world counterfactual goal-progress modeling only. It is not yet a closed-loop policy capability claim. The next stage must calibrate policy use on a disjoint train-only slice and then pass a preregistered held-out dev gate.
