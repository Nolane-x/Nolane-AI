# R1.6 Effect-Conditioned Structured-Atom Causal Binder

Date: 2026-08-12 (Asia/Bangkok)

## Motivation

Two independent attempts to project raw/contrastive public action-effect sketches into the existing PSR action representation failed to improve closed-loop causal completion. The missing operation is not merely "add effect to action embedding"; the system must bind an observed opaque action effect to the **current structured world/goal fields** before choosing the next action.

## Architecture

The new binder is queried **only by an effect that has actually been observed**:

```text
contrastive public effect sketch 128D
        -> Linear(128, structured_atom_dim=256)
        -> per-action query
        -> dot attention over current structured atoms [N,256]
        -> attended public state/goal evidence
        -> relational features [q, evidence, q*evidence, |q-evidence|]
        -> MLP residual score
```

Components:

- `causal_evidence_query`: Linear(128 -> 256, no bias)
- `causal_evidence_scorer`: 1024 -> 256 -> 1
- `causal_evidence_policy_scale`: one global scalar, initialized to **0**

Observed-action gate:

- `action_counts > 0`
- effect sketch norm > 0

Therefore untried opaque actions get **exactly zero** causal-evidence bonus; there is no clairvoyance or fixed action-slot semantic.

The residual is included only in the full policy path. `semantic_only` remains a clean ablation.

## TDD evidence

RED first: `causal_evidence_policy_bonus` / `causal_evidence_policy_scale` were absent.

GREEN verifies:

1. no evidence -> exact zero bonus;
2. scale=0 -> exact zero bonus even with evidence;
3. dynamic action permutation permutes scores identically;
4. changing an observed effect changes that action's residual;
5. actions without evidence remain exactly zero.

Full focused R1.6 gate:

```text
53 passed in 24.64s
```

## Parameter accounting

- new causal-evidence binder: **295,938 parameters**
- live System-2 experimental parameters: **21,793,942**
- effective experimental accounting: **71,322,619**
- hard research ceiling: **75,000,000**

## Source integrity

- `cogcoder/neural_system2.py`: `73689bc24d7a089880432de73ceaee352c4cd375c9a269c23e61237d24f07978`
- `cogcoder/neural_system2_training.py`: `0e829d37f7d6c830f8662bd8d1c0461dc95db78ad7444322806bff40082cea5d`
- `tests/test_neural_system2.py`: `1844a06194bb98be4a60b8e496e800ff170ed70f3ebcc3f985bfc4e71bccf021`

## Next gate

Freeze the retained PSRPlanner and train only this 295,938-parameter residual on train-only worlds. Use exact/contrastive public effect memory and current structured atoms; select on train-internal validation only. Then evaluate on a new untouched closed-loop dev slice and reject the module if it fails to improve causal completion without cross-family regression.

Fresh remains unopened.
