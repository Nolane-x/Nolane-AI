# R1.7 Causal Law held-out dev world-model preregistration

Date: 2026-08-12
Candidate: `Nolane-R1.7-NCPM-CausalLaws.pt`, SHA-256 `e6c99e5944b68c2fde7f89e7dec478b54e93f3a3250adfd806e1020b46239dbc`
Benchmark: FIGG-17 v1.1

This gate evaluates **world-model generalization only**. The rejected causal-law policy head is not used and its scale remains zero.

## Held-out tasks

- split: `dev`
- families: `causal_laws`, `causal_switch`
- indices: `64..79` inclusive (16 per family; 32 worlds total)
- exploration prefix: six safe non-submit interventions where possible
- max episode steps: 14

These model-evaluation indices have not been used by R1.7 training or internal validation. Earlier benchmark integrity tests exercised causal-law reachability on dev indices 0..47 only.

## Metrics and baseline

At every decision state, predict the public 128D structured successor delta for all non-submit actions. The baseline is per-action last-observed-effect persistence, identical to the train-internal gate.

## Acceptance rule

Causal Law Slots are accepted as a generalizing R1.7 world-model capability only if:
1. aggregate candidate MSE is lower than baseline MSE by at least 15%;
2. `causal_laws` candidate MSE is lower than its baseline by at least 15%;
3. `causal_switch` candidate MSE is lower than its baseline by at least 15%;
4. candidate checkpoint hash and source hashes match the pushed provenance before evaluation.

Passing this gate does **not** claim closed-loop agent improvement. It authorizes Phase B Goal-Difference integration on top of the accepted causal representation. FIGG-17 fresh remains unopened.
