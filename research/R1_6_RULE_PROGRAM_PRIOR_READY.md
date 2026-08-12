# R1.6 Dynamic RuleProgramPrior — ready for train-only evaluation

Date: 2026-08-12 (Asia/Bangkok)

## Bottleneck

After EffectProgressCritic was promoted, held-out traces show delayed-resource is solved 12/12 across the two acceptance slices, causal improves but remains difficult, while compositional-rule is still only 1/12. The recurring rule failure is a plausible first/second public operation followed by premature or wrong continuation. The missing quantity is a persistent **program-position prior**, not another one-step world utility scalar.

## Module

A small shared dynamic-action prior was added with no fixed action slots and no family/action-name input:

- `rule_program_context: 640→256`
- `rule_program_action: 640→256` shared by every dynamic action
- shared `LayerNorm(256)`
- four learned program-step embeddings (positions 0..3)
- learned public-context applicability gate `640→128→1`
- zero-initialized global `rule_program_policy_scale`

The current program position is derived only from recurrent public action counts (`sum(action_counts)`, clamped to the four reusable step embeddings). Dynamic actions are scored by a shared query/key dot product, so action permutations only permute the residual scores.

The residual is added only to the full policy path. Scale zero makes accepted CurrentBest byte-behavior neutral before training.

## TDD / verification

RED: dedicated tests failed because the prior and optimizer selector did not exist.

GREEN: unit invariants passed, then the full focused R1.6 suite passed:

```text
61 passed in 19.84s
```

Verified invariants:
- zero policy scale => exact zero residual;
- dynamic-action permutation equivariance;
- changing executed-program position changes the residual;
- isolated optimizer scope selects only `rule_program_*`;
- accepted pre-feature CurrentBest checkpoint still loads.

## Parameter budget

- RuleProgramPrior: `411,650` parameters
- live experimental effective candidate: `72,260,609`
- hard R1.6 research ceiling: `75,000,000`

## Source SHA-256 after GREEN gate

- `cogcoder/neural_system2.py`: `ed54e1908d28b29946ba3c45a11e2cf506b5748301fa0f8521541b3c27ae98b2`
- `cogcoder/neural_system2_training.py`: `6fc0c6fc82670253bd7bd7da48155919e6ea100461ee64669a2909fc925cb1e7`
- `tests/test_neural_system2.py`: `c4d168a0e9fb2dd8e73d1034e1e3335eaa31fa4ef86c61b3517a139750eacb6e`
- `tests/test_neural_system2_training.py`: `99f6738ca07cae22632e7ef11be583b26130439e711c65d53729b9dd48857588`

No dev/fresh task was used to implement or verify this feature. Training must use a new train-only slice and the accepted EffectProgress CurrentBest as frozen parent.