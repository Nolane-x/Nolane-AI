# R2.65 Verified Patch Primitive Induction — Design

## Context

Accepted R2.64 unifies diagnostic out-of-version-space expansion with later refinement composition, but its repair language remains host-complete: the exact trusted `PatchMacro` needed for a repair must already be supplied. If that primitive is absent, R2.64 fails closed with `no_expansion_macros` or an unexpressible-target outcome even when a bounded authorized syntax alternative would explain every public observation.

## Goal

Allow Nolane-AI to derive a specific repository patch primitive from a finite host-authorized AST rewrite grammar rather than requiring the exact `PatchMacro` to be pre-specified. Primitive hypotheses must be generated without oracle or target-output access, challenged on public learning inputs, promoted only after a minimum independent challenge count, and accepted only after a unique/disjoint terminal verification pool.

## Closed grammar

R2.65 initially supports only pure binary-operator replacement:

- slot: `binop`;
- operation: `replace`;
- source operator: inferred from AST operators actually present in authorized expansion seeds;
- target operator: chosen from a host-authorized finite set such as `Add`, `Sub`, `Mult`, `Div`, `FloorDiv`, `Mod`;
- primitive ID: content-addressed over `(slot, operation, source_value, target_value)` and therefore independent of caller candidate IDs.

The grammar does not add imports, calls, files, statements, literals or effect classes. It is deliberately narrower than arbitrary patch-language invention.

## Evidence protocol

1. Compile/filter initial candidate repositories using public initial tests.
2. While multiple candidates survive, use R2.60 minimax diagnostic selection.
3. When the oracle label is outside the supplied candidate partitions, retain that label as a public diagnostic counterexample.
4. Enumerate all authorized patch primitive hypotheses without oracle access.
5. Apply each hypothesis through the trusted R2.61 repository expander; filter generated repositories against the complete public evidence ledger.
6. Consume a unique challenge pool disjoint from diagnostics and final verification. Every successful challenge label becomes public evidence. A hypothesis may be promoted only after `min_independent_challenges` have passed and exactly one `(primitive, repository-content)` pair remains.
7. Run unique/disjoint terminal verification. Any mismatch or oracle error is terminal and cannot be recycled into primitive learning.

## Receipts

The final receipt records the learned `PatchMacro`, promotion state, initial unique candidates/survivors, diagnostic/challenge/final oracle calls, hypotheses enumerated, generated candidates, survivors after the diagnostic counterexample, independent challenges passed, public observation IDs, accepted repository content digest, false terminal accepts and verification failures. `generation_used_target_outputs` is explicitly false for the closed generator.

## Causal benchmark

Across multiple source→target operator families, remove the exact patch primitive from the host input. Supply at least two initial executable wrong repository behaviors so the target diagnostic label is outside the initial version space. The accepted R2.64 baseline with an empty macro set must fail, while R2.65 must derive the correct primitive from the closed grammar, localize the correct site among a connected decoy site, pass independent challenges and then a disjoint heldout set.

Adversarial gates cover a grammar that omits the target, zero hypothesis/generation budget, insufficient challenges, diagnostic/challenge oracle failure, duplicate/overlapping evidence, caller-ID/order invariance and terminal-verification non-recycling.

## External transfer

Use a pinned callable-I/O target whose required primitive is not pre-supplied. Preferred target: NumPy 2.4.6 `numpy.multiply`, with a small multi-file repository initially implementing `Add`, an additional wrong executable behavior to establish the R2.64 causal boundary, and a closed grammar containing multiple legal alternatives including `Mult`. The exact target repository is evaluation-only. NumPy implementation source must not be inspected.

## Claim boundary

R2.65 is bounded induction of a specific pure AST replacement primitive inside a finite host-authorized grammar. It is not arbitrary code generation, open-ended patch-language invention, effectful/filesystem/network experimentation, unrestricted search, broad real-repository autonomy or AGI. Added trainable parameters: exactly 0.
