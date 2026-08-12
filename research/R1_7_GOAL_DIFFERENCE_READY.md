# R1.7 Phase B Goal-Difference Workspace — neutral architecture ready

Date: 2026-08-12
Parent: accepted R1.7 CausalLaws checkpoint `e6c99e5944b68c2fde7f89e7dec478b54e93f3a3250adfd806e1020b46239dbc`

## Purpose

Phase A proved that Causal Law Slots generalize as a successor-dynamics model (~52% MSE improvement over last-effect persistence), but a simple law-policy residual failed its train-internal causal action gate. The missing relation is explicit: **does a predicted action effect move the current world toward the desired world?**

The Goal-Difference Workspace introduces two learned, field-name-agnostic attention roles over public structured atoms. One role may specialize to current-like evidence and the other to target-like evidence. Their relational difference is compared with the Causal Law model's predicted structured delta for every dynamic action.

## Invariants

- no hard-coded JSON key such as `state` or `goal` is used by the neural scorer;
- dynamic actions share the same scorer and remain permutation-equivariant;
- policy scale starts at zero, so the accepted CausalLaws checkpoint remains behavior-neutral before Phase-B training;
- old R1.6/R1.7 checkpoints may omit only the new `goal_difference_*` keys;
- FIGG-17 fresh remains unopened.

## Parameter audit

- accepted CausalLaws architecture: 73,642,371 effective parameters
- Goal-Difference parameters: 1,018,626
- Phase-B neutral candidate: **74,660,997**
- R1.7 hard ceiling: 96,000,000
- headroom: 21,339,003

## Verification

Freshly executed after implementation:
- Goal-Difference/R1.7/R1.6 focused stack: **91/91 passed**
- rebuild/transfer/benchmark-integrity set available in the restored tree: **31/31 passed**

## Source hashes

- `cogcoder/neural_system2.py`: `49113a22fe2ba1d38f9c88dec8a54a5268a1b7b69b7865f09466830732c29295`
- `cogcoder/neural_system2_training.py`: `28b78711f1e9f8b3076b024a38f888766d64c627aee64f50c51d12a8235b8342`
- `cogcoder/r17_training.py`: `4423194f2478ae55a4797ab0e67ebccc3a15e0fa1569239779b852c21954bebb`
- `tests/test_r17_goal_difference.py`: `f29feeaa4e2ffdcfbbc00d5286fc443c57d5499325f8c474f1e7527dd9459dab`

No Phase-B weight has been trained yet. The next permitted step is train-only counterfactual-progress learning with `goal_difference_policy_scale` held at zero.
