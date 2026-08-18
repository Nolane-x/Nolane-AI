# R2.63 Compositional Version-Space Expansion — Design

## Context

Accepted R2.61 can expand a repository candidate space after an active diagnostic oracle outcome falls outside the supplied candidates. Its loop stops when one survivor remains; any later mismatch found by terminal verification causes `independent_verification_failed` and cannot trigger another expansion. Therefore a repair that needs two independently justified edits remains outside the accepted capability even when each edit is expressible by trusted `PatchMacro` semantics.

Accepted R2.62 adds complementary pure-input causal experiment programs. R2.63 is intentionally non-overlapping: it stays in the repository-repair path and does not alter R2.62's experiment-program mechanism.

## Goal

Add zero-parameter bounded composition of multiple trusted repository mutations. A singleton partial repair may be challenged by a separate refinement-probe pool; a successful contradictory refinement observation becomes public evidence and may trigger one more target-output-free expansion. Final verification remains disjoint and terminal.

## Evidence classes

1. `initial_tests`: public labeled examples supplied at entry.
2. `diagnostic_probes`: active R2.60-style oracle queries used while multiple candidates survive.
3. `refinement_inputs`: bounded oracle queries used after a singleton survives; each successful observation becomes a public `PatchTest` and may justify another expansion.
4. `verification_inputs`: strictly disjoint heldout inputs. Their outcomes are terminal evidence and can never be recycled into learning or candidate generation.

Every successful diagnostic/refinement observation is preserved in the public observation ledger, including labels that match the current candidate.

## Candidate generation

`expand_compositional_frontier(...)` has no oracle parameter. It applies only existing trusted R2.47/R2.61 `PatchMacro` operations to the current frontier one mutation step at a time. It preserves repository file sets and the R2.52 execution boundary, introduces no arbitrary imports/statements/files/effects/code, content-deduplicates states, rejects already-seen repository content to avoid cycles, carries parent/child content digests and mutation provenance, and obeys hard depth/generation/site budgets. Oracle labels may filter candidates only after the bounded frontier is generated.

## Solver

`solve_repository_patch_with_compositional_expansion(...)` reuses R2.60 candidate compilation/filtering/minimax diagnosis. While multiple candidates survive it selects a diagnostic probe, records the successful observation, and either follows the matching partition or expands when the observation is outside the current version space. When one candidate survives it consumes refinement inputs in deterministic order. A matching refinement label is retained as evidence; a mismatch may trigger another expansion from the singleton subject to authority and budgets. If expansion produces multiple survivors, active diagnosis resumes. After refinement is exhausted, the solver evaluates the disjoint final verification set. A final verification mismatch is terminal and never triggers expansion.

## Fail-closed conditions

Abstain on missing candidates/authority, oracle errors, no informative diagnostic probe, exhausted selection/refinement/expansion/depth/generation/site budgets, no generated hypotheses, no generated candidate satisfying the complete public observation ledger, unauthorized expansion seed, or final verification failure. False terminal accepts must remain zero.

## Causal benchmark

Use multi-file repositories with two independently necessary buggy sites on separately addressable execution paths. The exact two-edit target is absent from the initial version space and the complete one-step expansion space. One diagnostic counterexample admits a partial one-edit repair. Under identical initial candidate/macro authority R2.61 reaches that singleton then fails on the second path. R2.63 receives the second-path label only through the refinement pool, composes the second trusted edit, preserves all earlier observations, and passes a disjoint heldout set. Adversarial gates cover depth and oracle budgets, missing macro authority, oracle errors, terminal-verification non-recycling, ordering invariance, cycle/content deduplication, and absence of an oracle argument in candidate generation.

## External transfer

Use a pinned independently sourced callable-I/O target different from R2.60 `numpy.gcd`, R2.61 `numpy.remainder`, and R2.62 `ufunclab.deadzone`. The harness must hide implementation source, require two repository edits, prove the exact target repository is absent from the initial and complete one-step spaces, report all oracle calls by evidence class, and keep final heldout verification disjoint.

## Claim boundary

R2.63 is bounded trusted-macro multi-step repository repair. It is not arbitrary code generation, autonomous patch-language invention, effectful/filesystem/network experimentation, unrestricted search, broad real-repository autonomy, or AGI. Added trainable parameters: exactly 0.
