# R2.60 Complementary Causal Experiment Program — Design

## Status
Approved for inline execution by the user's standing instruction to continue building Nolane-AI immediately, coordinate through the shared GitHub repository, prioritize quality over speed, and avoid intermediate approval stops.

## Goal
Extend accepted R2.59 from finding one causally useful intervention to discovering a **complementary two-experiment program**: neither intervention/probe is sufficient alone, but a discovered composition of both is exact on disjoint validation and creates a bounded hierarchical synthesis result that a matched flat local synthesizer fails to find.

## Scientific claim boundary
R2.60 may claim only bounded, deterministic, zero-trainable-parameter complementary pure-input experiment-program discovery over a finite intervention anchor basis and finite numeric composition language, plus separately frozen evidence on an independently sourced I/O-only function family. It must not claim arbitrary experiment invention, effectful intervention design, unrestricted scientific autonomy, general coding autonomy, AGI, or frontier-model equivalence.

## Architecture
1. Reuse R2.58 positional canonicalization and intervention identities and R2.59 finite-anchor derivation discipline.
2. Enumerate legal positional interventions without semantic-name ordering.
3. Build intervention output profiles on discovery contexts, failing closed on invalid contexts or non-finite outputs.
4. Search unordered intervention pairs under a finite numeric composition language (`add`, `sub`, `rsub`, `mul`, `min`, `max`).
5. Admit a pair only when the full composition is exact on discovery **and disjoint validation**, each singleton is non-exact, and each side is essential on at least one case.
6. After structural pair discovery, synthesize each selected probe independently with the inherited bounded local expression synthesizer. The pair receives two equal local budgets; the flat target baseline receives their summed candidate budget.
7. Compose the two verified probe expressions using the discovered operation. Verify the composed expression on disjoint validation and later fresh challenge/heldout cases.
8. Preserve strict accounting: oracle calls, intervention count, pair/operation count, baseline synthesis candidates, per-probe synthesis candidates, proper-subset failures, and zero trainable parameters.

## External evidence
Use pinned `WarrenWeckesser/ufunclab@f1fbe6769850823a1976ccc28d14cd966130b645`, callable `ufunclab.deadzone`, through an I/O-only harness. The researcher selected this family; the learner receives only callable I/O, ordered opaque fields, finite anchors, context validity predicate, and bounded synthesis grammar. This is new function-family breadth relative to R2.58/R2.59's `linearstep`, but not blind task selection.

## Fairness and falsifiers
- Flat target baseline gets synthesis candidate budget equal to the sum of the two probe budgets.
- Both flat and probe synthesis use the same local depth bound.
- Any exact singleton intervention invalidates complementary-program admission.
- Any pair that works only on discovery but not disjoint validation is rejected.
- Any selected program whose result changes under field renaming without positional-role change is rejected.
- Any argument permutation that changes semantic roles without corresponding positional remapping must not be treated as invariant.
- Hosted source lock and pinned external commit are required before acceptance.
- Nolane World W5 may remain false; no convergence claim is required for a bounded capability.

## Files
- `cogcoder/r260_complementary_experiment_program.py`: core pair discovery, causal admission, hierarchical probe synthesis, accounting.
- `benchmarks/kfigg/r260_complementary_experiment_program.py`: frozen authored benchmark and invariance checks.
- `research/r260_external_complementary_transfer.py`: I/O-only external harness.
- `tests/test_r260_complementary_experiment_program.py`: core/TDD tests.
- `tests/test_r260_external_complementary_transfer.py`: local external-harness behavior with a pure Python oracle double.
- `tests/test_r260_complementary_benchmark.py`: frozen benchmark contract.
- `.github/workflows/r260-complementary-experiment-program.yml`: focused, lineage, cross-Python, pinned external gates.
