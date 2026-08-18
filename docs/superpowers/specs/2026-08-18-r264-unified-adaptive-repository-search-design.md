# R2.64 Unified Adaptive Repository Search — Design

## Context

Accepted R2.63 composes multiple trusted repository mutations after a candidate space has already collapsed to a singleton and a refinement probe exposes another error. It deliberately abstains when an active diagnostic observation is outside the initial multi-candidate version space. Accepted R2.61 can escape such an out-of-space diagnostic observation, but its first independently verified singleton is terminal and cannot continue learning from a separate refinement pool.

R2.64 unifies those two bounded capabilities in one evidence-preserving repository search loop. This is a capability-composition milestone, not a new patch language.

## Goal

When multiple supplied repository candidates survive and a diagnostic oracle label is outside their behavior partitions, generate a bounded target-output-free trusted-macro frontier, retain only candidates consistent with the complete public evidence ledger, resume diagnosis, then continue R2.63-style singleton refinement and further bounded expansion if another independent public counterexample appears. Final verification stays disjoint and terminal.

## Evidence classes

1. `initial_tests`: already-public labeled evidence.
2. `diagnostic_inputs`: active R2.60-style probes while more than one candidate survives. Every successful label is public evidence. An out-of-space label may trigger bounded expansion.
3. `refinement_inputs`: probes consumed only after a singleton survives. Every successful label is public evidence. A contradictory label may trigger another expansion.
4. `final_verification_inputs`: unique and disjoint from all learning evidence. They can reject an answer but can never be converted into a counterexample for additional search.

## Candidate generation and authority

`expand_adaptive_repository_frontier(...)` has no oracle, target or expected-output parameter. It applies only pre-existing trusted R2.47 `PatchMacro` transformations through the R2.61 expansion machinery. Generated candidates are bounded by composition depth, generated-candidate count and sites-per-macro. Complete repository content defines search identity; caller IDs do not. Seen content is rejected to prevent cycles. Mutation provenance is content-addressed and retained so the accepted multi-step chain is inspectable.

The generator cannot add arbitrary imports, files, statements, effects or patch semantics, and cannot infer a new macro from oracle output.

## Unified control loop

- Compile and filter canonicalized initial candidates against public initial tests.
- While multiple candidates survive, choose the R2.60 minimax diagnostic probe.
  - If the oracle label matches an existing partition, retain that partition and continue.
  - If the label is outside the current version space, record it as public evidence, increment the diagnostic-counterexample receipt, and expand the current authorized frontier without target-output access.
- Filter generated candidates against the entire accumulated public ledger. If multiple survive, resume active diagnosis.
- When one candidate survives, consume unused refinement inputs deterministically.
  - Matching labels are still retained as public evidence.
  - A mismatch becomes a refinement counterexample and can trigger another bounded expansion from the authorized singleton.
- After refinement is exhausted, execute the disjoint final verification pool. A mismatch or oracle error here is terminal and never re-enters expansion.

## Causal evidence requirement

The authored positive family must require both expansion modes in sequence:

- at least two valid initial repository candidates survive;
- the active diagnostic oracle outcome is absent from every initial partition;
- accepted R2.63 therefore abstains before any expansion;
- the exact two-edit target is absent from both the initial version space and the complete one-step trusted-macro frontier;
- R2.64 uses the diagnostic label to generate a one-edit partial repair;
- a separate refinement input exposes a second independent error;
- R2.64 composes a second edit and passes a disjoint heldout pool;
- target-output-free generation, content identity invariance and zero false terminal accepts remain explicit gates.

Adversarial cases must cover diagnostic/refinement/oracle/round/depth/generation/site budgets, missing macro authority, oracle failures, unexpressible targets, duplicate or overlapping final evidence, caller-ID/order permutations, content-cycle suppression and terminal-verification non-recycling.

## External transfer

Use pinned NumPy 2.4.6 `numpy.square` as callable-I/O-only behavior, not implementation source. The wrapper must contain two independently necessary `Add -> Mult` repository edits plus an initial wrong executable hypothesis so the external diagnostic output is outside all initial behaviors. The exact target repository is evaluation-only and cannot be supplied to the solver. Accepted R2.63 must fail causally at the initial version-space boundary; R2.64 must first expand from the diagnostic counterexample, then compose the second edit through the refinement pool, then pass a disjoint heldout set.

A second external family may be retained only as robustness/non-regression evidence; readiness movement must be attributed to the causal R2.63→R2.64 delta, not reused evidence.

## Claim boundary

R2.64 is bounded unified search over a host-supplied repository representation, probe pools and pre-existing trusted patch vocabulary. It is not arbitrary code generation, autonomous patch-language invention, unrestricted search, effectful/filesystem/network experimentation, broad real-repository autonomy or AGI. Added trainable parameters: exactly 0.
