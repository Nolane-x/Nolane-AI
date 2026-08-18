# R2.62 → R2.63 Evolution

R2.62 and R2.63 operate on different cognitive layers and are cumulative.

## R2.62

R2.62 discovers complementary pairs of pure-input causal experiments and composes their induced behaviors. It improves experiment structure but does not solve multi-edit repository repair.

## R2.63

R2.63 extends repository repair after R2.61's single-step expansion. Its central boundary is temporal: a **refinement counterexample** may legitimately update the learned repair hypothesis, but a **final verification failure** may not.

The resulting loop is:

`initial version space → public tests → diagnostic ambiguity resolution → refinement counterexample → target-output-free trusted mutation generation → filter against public evidence → next refinement counterexample → second trusted mutation → disjoint terminal verification`.

This changes a concrete failure mode. On the frozen two-edit family, R2.61 reaches a partial repair and then abstains at independent verification; R2.63 composes the second repair and verifies the final repository.

## Safety boundaries

- caller candidate IDs/order are not semantic identity;
- repository content is content-addressed;
- generation never receives target output as an input;
- refinement and final verification inputs are disjoint;
- final verification cannot trigger further learning;
- mutation provenance is retained per expansion round;
- all generation/refinement/oracle budgets fail closed;
- no new trainable parameters are added.

## Multi-AI coordination

The direction preserves the closed peer design PR #18 (`r263-compositional-repository-repair-gpt56sol`) while implementation and verification occur on the separate integration branch. The peer branch is not overwritten.

## Remaining frontier

The next meaningful barriers are not more naming/version increments. They are scaling composition beyond two edits, discovering or safely learning patch-language primitives, reducing verification cost, and transferring the mechanism to blind real-repository issue distributions with stateful/effectful tests.
