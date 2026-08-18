# Nolane-AI R2.63 Delivery — Compositional Repository Refinement

Status: **ACCEPTED_BOUNDED_CAPABILITY**

R2.63 extends the accepted R2.61 repository version-space expansion path from one trusted repair step to bounded counterexample-guided composition of multiple trusted single-site PatchMacro mutations. It is implemented on top of accepted R2.62 without changing R2.62 production artifacts.

## Capability

R2.61 can recover when the correct candidate is absent from the initial version space, but once one partial repair survives it treats independent verification as terminal. R2.63 separates **refinement evidence** from **final verification**: a public refinement counterexample may trigger another target-output-free expansion round, while final verification remains disjoint and terminal.

The accepted R2.63 path:

- canonicalizes initial candidates by repository content rather than caller IDs;
- filters initial candidates against public tests;
- optionally uses active diagnostic probes to resolve ambiguity;
- treats bounded refinement probes as learnable counterexamples;
- generates trusted PatchMacro mutations without passing the oracle output into generation;
- filters generated candidates against accumulated public observations;
- records mutation provenance and repository-content digests;
- supports bounded multi-round refinement;
- makes final verification disjoint and non-learning;
- fails closed on budget exhaustion, ambiguity, oracle failure or final mismatch;
- adds **0 trainable parameters**.

## Hosted TDD

Core contract RED:

- run `32127260810`
- job `95680470378`
- head `cea5bd2cc6c9a4387dc518846e7e05179374d253`
- failure: `ModuleNotFoundError: No module named 'cogcoder.r263_compositional_repository_repair'`

External contract RED:

- run `32127796698`
- job `95682121067`
- failure: `ModuleNotFoundError: No module named 'research.r263_external_compositional_transfer'`

Both contracts subsequently turned GREEN after their production modules were added.

## Frozen authored evidence

Across six heldout multi-file synthetic repository episodes:

- repository size: **6–8 files**
- call depth: **4–5**
- R2.61 baseline terminal-verification abstains: **6/6**
- R2.63 exact repairs: **6/6**
- two expansion rounds: **6/6**
- two accepted edits: **6/6**
- refinement counterexamples: **12** total
- refinement oracle calls: **12** total
- disjoint final verification: **144 cases per episode / 864 total**
- accepted repository-content digests: **6 unique**
- target-output leakage into generation: **false**
- false terminal accepts: **0**
- verification failures: **0**
- trainable parameters added: **0**

A benchmark defect was found during development: an earlier seed-dependent bias used `% 3`, causing two content-equivalent heldout repositories and failing the episode-specific-final-repair gate. The benchmark was corrected to use `% 97`; production capability code was not changed to hide this failure.

## Pinned external transfer

Pinned oracle: NumPy **2.4.6** `numpy.subtract`, callable I/O only.

The host-authored repository wrapper initially contains two `Add` sites while the target behavior applies the external subtraction oracle twice. A trusted `Add → Sub` PatchMacro is available, but the initial version space contains only the unmodified repository.

- initial candidates: **1**
- R2.61: `abstain`, `independent_verification_failed`
- R2.63: `accept`, `compositional_candidate_verified`
- expansion rounds: **2**
- refinement counterexamples: **2**
- accepted edits: **2**
- mutation chain length: **2**, unique
- generated candidates: **5**
- admitted generated candidates: **2**
- target-output leakage into generation: **false**
- disjoint final verification: **256/256 exact**
- false terminal accepts: **0**
- verification failures: **0**
- total R2.63 oracle calls: **258**
- trainable parameters added: **0**

## Canonical hosted verification

Canonical run: `32128298353`.

- source-lock verification: PASS, **6 frozen production/test blobs**
- R2.63 focused tests: **7/7**
- frozen Phase-A recomputation: exact
- pinned NumPy external recomputation: exact
- accepted/protected R2.62→R2.41 tests: **227/227**
- total relevant tests: **234/234**
- Python 3.11 focused behavior: success
- Python 3.13 focused behavior: success
- Phase-A artifact: `9321192168`
- external artifact: `9321192097`

## Nolane World 0.8.0

World `world_c3eaeda4e13d` was used as an external audit/runtime around R2.63. The persisted canonical session JSON has SHA-256 `d34314b1825cd214a6d603af89d889e304f35176639e56ad62964bffe80f1987`.

The W5 gate remains deliberately **FAIL**. No active residency, independent challenger, broad robustness or convergence evidence is fabricated. Open questions remain around >2-edit scaling, real-repository hidden-test transfer, and safe learning of patch-language primitives.

## Readiness

Internal Coding-AGI engineering-readiness: **49.1/100**, delta **+0.3** from R2.62's 48.8.

The movement is intentionally small. R2.63 crosses a meaningful one-edit-to-compositional-repair boundary and has a distinct external NumPy transfer, but it still relies on a host-authored repository wrapper, trusted host-supplied PatchMacro language and a bounded two-edit evidence regime.

## Claim boundary

R2.63 demonstrates **bounded two-round counterexample-guided composition of trusted single-site repository patch mutations, with content identity, provenance, target-output-free generation, strict budgets and disjoint terminal verification**.

It does **not** establish arbitrary code generation, learned patch-language invention, scalable long repair chains, broad real-repository hidden-test autonomy, stateful/effectful experimentation, unrestricted program synthesis, AGI, or frontier-model equivalence.
