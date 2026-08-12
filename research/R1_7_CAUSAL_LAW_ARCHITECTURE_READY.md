# R1.7 Causal Law Slots — neutral architecture ready

Date: 2026-08-12
Parent: R1.6 EffectProgress `0a1688062f7640739847070a54ea079a28c10c010b286c5b640645214e912ace`

## Architecture

Eight content-addressed recurrent law slots (256D) bind public pre-action structured state, dynamic action embeddings, and observed public structured successor deltas. Retrieval is shared across dynamic actions and is action-permutation equivariant. Confidence begins at zero. A zero-initialized policy scale makes the R1.6 parent behavior-neutral before R1.7 training.

## Parameter audit

- R1.6 EffectProgress effective parameters: 71,848,959
- R1.7 neutral Causal Law architecture: 73,642,371
- new `causal_law_*` parameters: 1,381,762
- R1.7 hard ceiling: 96,000,000

## Verification

Focused R1.7/R1.6 model+benchmark stack: **79/79 passed**.

A frozen deterministic input was evaluated before and after adding the neutral law path. EffectProgress parent logits remain:

`[0.3384998441, 0.7971160412, -0.8996449709]`

within absolute tolerance `2e-6`.

## Source hashes

- `cogcoder/neural_system2.py`: `6e6c6d26cb183056efcd05477f901ef02d1580d2459521e053f257e2d9b2580d`
- `cogcoder/neural_system2_training.py`: `8195a3f44324b90ac67a017a1a4eaf3b23e760a431a4e7853a5c8cb9595aaf86`
- `tests/test_r17_causal_law_slots.py`: `275ac32559afb1cfa3d3d5ef74015dd2b461aa7fb8aba6c8d5cb691e14c24e7c`

The three neural-system patch parts concatenate to SHA-256 `2f577f6953bd28113ea40273a751f629148eba114874ade6344d604561c4da0e`.

No R1.7 dev or fresh task has been used to train or select this architecture.
