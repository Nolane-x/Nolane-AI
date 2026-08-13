# Nolane R2.0i — Complete One-Weight Delivery

Date: 2026-08-13

Current accepted state: **R2.0i Active Causal Discovery**, 78,779,253 effective neural parameters plus a zero-parameter public active-causal runtime.

## User-facing weight

`Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt`

- bytes: 59,773,663
- SHA-256: `b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e`
- contains the complete R1.9 parent/frontier state and frozen R2.0e EvidenceEffect executive
- active-causal runtime source binding: `cc254838dd42e1081e888619f71276a3d1af1cf7ba0a55af7796ddbf39eec672`

## Complete ZIP

`Nolane-R2.0i-Active-Causal-Discovery-COMPLETE-2026-08-13.zip`

- bytes: 54,943,807
- SHA-256: `b81c2359856b2fc2d72f74a459142f7619707cb6790e9115afbb5e8fdb9d07d8`
- `unzip -t`: PASS, no compressed-data errors
- `.pt` files inside: exactly **1**
- includes source, tests, locks, accepted and rejected R2.0 evidence, benchmark contracts, audit logs, docs and the single current weight
- excludes transient caches and historical/rejected checkpoint binaries

## Final deployment verification

The verifier was run from the exact staging tree used to create the ZIP:

- release pytest: **8 passed, 1 PyTorch warning**
- one-weight metadata/SHA/controller integrity: PASS
- replay of all 80 already-consumed fresh episodes: **48/80 solved**
- action/solve mismatches vs acceptance artifacts: **0/80**

The replay is a packaging-reproduction test, not another untouched-fresh evaluation.

Research tests for older R2.0a-h branches remain in source. Many expect historical split R1.9/R2.0e checkpoint fixtures, which are intentionally omitted from the one-weight delivery; those fixture-dependent tests are not presented as a green final-deployment suite.

## Scientific boundary

R2.0i's causal improvement is a hybrid runtime result. The active discovery controller has zero trainable parameters and uses public interaction around the neural stack. This is not proof of AGI and not evidence that Nolane beats >100B models; external official/verifier-backed frontier benchmarks still need to be run.
