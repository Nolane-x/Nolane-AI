# R2.52 — Repository Multi-File Query Induction

## Decision

**ACCEPTED_BOUNDED_CAPABILITY.** Capability commit: `e5d4985263d736a5cc9a01a30b1892c0b229e23a`.

GitHub Actions run `32030459417`, main job `95389072541`, completed successfully on Ubuntu 24.04 / Python 3.11.15. R2.52 passed 6/6 focused tests; R2.51–R2.47 passed 30/30; R2.46 passed 5/5; R2.45–R2.44 passed 15/15; R2.43–R2.41 passed 31/31. Separate focused R2.52 jobs passed on Python 3.11 and 3.13. R1.9, R2.0i and R2.2 integrity workflows also succeeded on the same capability commit. Local relevant lineage was independently re-run as 87/87 on Python 3.13.5.

## Capability

R2.52 moves the causal repair representation from one module to an immutable repository snapshot. It builds an identifier-invariant repository graph spanning files, static import bindings, direct call targets, argument binding, return flow and generic transitive `FLOW*`. A learned query can therefore localize a deep edit in one imported module from structural evidence that only becomes discriminative through callers in other files.

Localization is transactional at the representation layer: every macro is localized once on the same pre-edit repository graph, then all selected edits are applied to cloned module ASTs and emitted as one new `RepositorySnapshot`. This prevents early edits from changing the graph used to locate later edits and permits exact coordinated patches across files. Import cycles and ambiguous module names fail closed in the supported subset.

Frozen heldout result: 6/6 exact, zero false accepts, 10 learned macro families, 75 candidates, exact three-macro patch and exact three-file transaction in all six episodes. Heldout repositories contain 5–6 files at call depth 4–5, while identifiers are opaque. R2.51 applied independently per file scores 0/6; global syntax application scores 0/6; the independent direct oracle scores 6/6. Sparse CEGIS starts with four tests, reveals at most two counterexamples, observes at most 6/2,401 tests (0.2499%), and then certifies all 2,401 executable tests.

## Nolane World 0.5.0 audit

World `world5_bb72de0587d0c24f6282` was opened at W5 depth. Three trusted evidence lineages were registered: local TDD/regression, GitHub hosted clean-runner, and adversarial static review. The durable audit is valid with digest `55da0b87353cdfceeab935c1c274b70cc7f17d4b173004d5d97bb3b2fcb64a84` and seven events. W5 gate remains **false** with score `0.1429`. No active-time or compute credit was fabricated. World quality is correctness 0.94, evidence 0.91, robustness 0.78 and verification 0.93; remaining value-of-thought is 0.35.

The unresolved frontier is substantial: architect-provided `FLOW*`; only acyclic absolute direct `from` imports of top-level synchronous functions; no classes/methods/closures/recursion/relative imports/package side effects/higher-order or dynamic dispatch/async/external dependencies; an in-memory compiler that is intentionally not full CPython import semantics; snapshot atomicity rather than filesystem/VCS rollback semantics; only 5–6 heldout files; deterministic generated tests; and a bounded edit/query language.

## Coding-AGI engineering-readiness

Recalibrated internal rubric: **44.5/100**. The original R2.52 release recorded 56.0/100, but that value was later rejected as score inflation because the evidence was still a controlled generated repository family and mainly expanded an existing interprocedural mechanism across file boundaries. The corrected comparison also treats the historical R2.51 48.0 figure as an overestimate. See `R2_READINESS_RECALIBRATION.md`. This remains an engineering-readiness heuristic for general coding intelligence, **not a probability that the system is AGI**.
