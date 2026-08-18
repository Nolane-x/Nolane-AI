# R2.61 Counterexample-Guided Version-Space Expansion — Design

## Status
Design accepted for continuation under the user's instruction to continue evolving Nolane-AI beyond accepted R2.60 without duplicating concurrent work.

## Problem
R2.60 can actively choose a diagnostic repository probe, but it must abstain when the oracle outcome is absent from every supplied candidate behavior (`oracle_outside_candidate_version_space`). This leaves the candidate ecology host-complete: if the correct repair was not enumerated before diagnosis, active querying cannot recover.

## Goal
Add a bounded, zero-parameter expansion path that converts an informative out-of-version-space oracle counterexample into newly generated repository patch hypotheses using only pre-existing trusted `PatchMacro` primitives, then resumes active diagnosis and independent verification.

## Non-goals / claim boundary
R2.61 is not arbitrary code generation, not new effect semantics, not self-authorized tool use, not unrestricted AST synthesis, not filesystem/network experimentation, and not a proof of broad autonomous repository repair. Expansion is limited to the existing R2.47 patch primitive language and R2.52 repository representation. All oracle use remains explicit and budgeted.

## Architecture

### 1. Targeted repository mutation generator
Create `cogcoder/r261_version_space_expansion.py`.

Given one or more seed `RepositoryPatchCandidate`s and trusted `PatchMacro`s, enumerate deterministic single-site candidate mutations. A mutation may only apply a macro at an AST site already compatible with that macro's R2.47 semantics. Candidate identity is content-addressed over resulting repository files plus mutation provenance.

The generator must:
- preserve repository file set and import structure;
- use only synchronous Python already admitted by R2.52;
- never add imports, files, statements, effect classes, arbitrary calls, or arbitrary literals; all syntax changes remain limited to pre-existing trusted `PatchMacro` transformations, including only already-defined pure wrapper primitives where that macro slot permits them;
- deduplicate by complete repository contents;
- expose hard `max_generated_candidates` and `max_sites_per_macro` budgets;
- be invariant to seed/macro ordering;
- fail closed on malformed snapshots or unsupported macro slots.

### 2. Counterexample-guided expansion loop
Add `solve_repository_patch_with_version_space_expansion(...)`.

The loop starts with the R2.60 candidate version space and active probe selection. If the selected oracle outcome is represented by existing candidates, normal filtering continues. If it is outside the version space, the observed probe/outcome becomes a new public `PatchTest`; the expander generates bounded hypotheses from the supplied seeds and trusted macro library; only candidates satisfying all observed tests survive; diagnosis then resumes.

Expansion is allowed only when:
- oracle execution succeeded;
- an expansion-round budget remains;
- trusted macros and expansion seeds are non-empty;
- candidate-generation and candidate-evaluation budgets remain.

No oracle target output may be read while generating mutation sites or mutation syntax. The oracle label may only filter generated hypotheses after generation.

### 3. Receipts and rollback-safe evidence
The solver returns a receipt containing initial/final survivor counts, selection calls, verification calls, expansion rounds, candidates generated, candidates admitted after counterexample filtering, candidate evaluations, exact mutation provenance, false terminal accepts, verification failures, and terminal reason.

Terminal acceptance still requires independent verification on a separately supplied verification set. A generated candidate that fails verification is not retained as accepted evidence.

## Authored causal gate
Construct multi-file R2.52-compatible episodes where:
- sparse initial evidence leaves multiple wrong supplied candidates;
- the correct repair is intentionally absent from the initial candidate version space;
- one R2.60-selected probe produces an out-of-version-space label;
- generic trusted patch macros can generate the missing repair without reading target outputs during generation;
- R2.60 baseline abstains;
- R2.61 expands and reaches the exact target;
- candidate/macro ordering permutations do not change the accepted repository;
- unsupported oracle behavior, exhausted budgets, or absent expressible repairs abstain with zero false accepts.

## External transfer
Use a pinned callable I/O-only oracle that is not the R2.60 `numpy.gcd` behavior. The preferred external target is NumPy 2.4.6 `numpy.remainder`, represented through a multi-file repository whose correct `FloorDiv -> Mod` repair is absent from supplied candidates but expressible by a trusted macro learned independently of the target source.

The harness must not parse NumPy implementation source. It may import/call the public oracle only. It must report all oracle calls, generated candidate count, selected diagnostic probes, heldout verification coverage, and whether the external repair originated from expansion rather than a host-authored candidate.

## Security / trust boundary
`PatchMacro`s are capability-limited syntax rewrite primitives, not executable retrieved text. R2.61 cannot introduce a new macro from oracle output. It cannot widen R2.55 authority envelopes or create side effects. Expansion provenance is content-addressed and public.

## Success criteria
- R2.60 baseline deterministically abstains on authored out-of-space episodes.
- R2.61 reaches exact repairs on all frozen authored positive episodes.
- Negative/unsupported episodes abstain; false terminal accepts = 0.
- At least one accepted repair is absent from the original candidate set and generated only after a diagnostic counterexample.
- External I/O-only transfer succeeds on a fresh target behavior with the correct repository candidate absent initially.
- All R2.60 focused tests and protected R2.59→R2.41 lineage remain green.
- Python 3.11 and 3.13 focused R2.61 tests pass.
- Nolane World audit remains valid and W5 is not forced to pass.
- Added trainable parameters = 0.
