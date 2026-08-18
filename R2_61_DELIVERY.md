# R2.61 — Counterexample-Guided Version-Space Expansion

## Status

**ACCEPTED_BOUNDED_CAPABILITY — merged into `main` and post-merge release-bundle verified.**

R2.61 extends the accepted R2.60 active-diagnostic repository path with a bounded escape from a host-complete candidate list. When an R2.60-selected oracle observation is not represented by any surviving candidate, R2.61 records that public counterexample, generates new repository hypotheses from pre-existing trusted R2.47 `PatchMacro` transformations without consulting the target output during syntax/site generation, filters those hypotheses against accumulated public evidence, resumes diagnosis, and requires independent terminal verification before acceptance.

Added trainable parameters: **0**.

## Capability delta from R2.60

R2.60 can select an informative repository probe, but it must abstain with `oracle_outside_candidate_version_space` when the correct behavior was not supplied as an initial executable candidate. R2.61 changes that boundary in one narrow but material way: the candidate **membership** may expand after a diagnostic counterexample even though the candidate **language** remains fixed.

The expansion language is the trusted R2.47 `PatchMacro` representation already available to the runtime. R2.61 does not learn a new macro from oracle output, does not parse external target source, does not widen R2.55 authority, and does not permit arbitrary AST/code generation.

## Runtime mechanism

`cogcoder/r261_version_space_expansion.py` provides:

- deterministic content-addressed `ExpansionMutation` and `ExpansionCandidate` records;
- bounded single-site repository mutation over compatible R2.47 patch slots;
- complete-repository deduplication and deterministic ordering;
- hard candidate/site/round/oracle budgets;
- reuse of R2.60 minimax diagnostic-probe semantics;
- an out-of-version-space transition that converts the selected public oracle result into a `PatchTest` only **after** target-independent hypothesis generation is defined;
- fail-closed terminal reasons for missing authority/budget, unexpressible targets, oracle errors and failed independent verification;
- receipts exposing generated/admitted candidates, mutation provenance, oracle calls, evaluations, expansion rounds, false terminal accepts and verification failures.

The generator has no oracle parameter. Trusted wrapper macros may use only the already-defined pure wrapper primitives admitted by R2.47; R2.61 does not add arbitrary calls, imports, files, statements, effect classes or arbitrary literals.

## Content-addressed novelty proof

A concurrent complementary evidence layer was inspected and retained as part of R2.61:

- `cogcoder/r261_expansion_proof.py`
- `benchmarks/kfigg/r261_expansion_proof_audit.py`
- `R2_61_EXPANSION_PROOF_RESULT.json`

The proof hashes repository **content**, not caller-supplied candidate IDs. For each accepted authored repair it checks that:

1. the accepted repository content is absent from the initial version space;
2. the same content appears in the bounded generated evidence;
3. the accepted mutation ID is recorded by the solver receipt;
4. terminal verification is clean and false terminal accepts are zero.

Hosted novelty-proof tests also cover candidate-ID renaming, input-order invariance, missing generated evidence and a forged new ID that points to initial content.

Frozen proof result: **6/6 valid novelty proofs**, **0 false proofs**, **0 false terminal accepts**, **0 verification failures**, with six unique proof digests.

## Authored causal evidence

`R2_61_PHASE_A_RESULT.json` freezes six multi-file R2.52-compatible episodes:

- 3–5 files per episode;
- call depth 2–4;
- exact correct candidate absent from every initial version space;
- two compatible generated one-site hypotheses per episode (target site and decoy site);
- R2.60: **6/6 abstain** with `oracle_outside_candidate_version_space`;
- R2.61: **6/6 exact** after one counterexample-guided expansion round;
- **50 independent verification cases per episode**;
- candidate-order invariance: PASS;
- target-output-free generation: PASS;
- two adversarial negative episodes abstain correctly;
- false terminal accepts: **0**.

This is causal evidence for the version-space expansion mechanism: the correct repair is intentionally removed from the initial candidate set, so the R2.60 baseline cannot succeed by candidate selection alone.

## External callable-I/O transfer

`R2_61_EXTERNAL_TRANSFER.json` freezes a transfer against **NumPy 2.4.6 `numpy.remainder`**.

Boundary:

- public callable I/O only;
- NumPy implementation source is not inspected or parsed;
- a 5-file R2.52-compatible synthetic repository wrapper with call depth 4;
- correct repository candidate is absent initially and is not host-authored as an initial candidate;
- trusted `FloorDiv -> Mod` macro semantics pre-exist independently of target output.

Observed result:

- R2.60 baseline: abstain, `oracle_outside_candidate_version_space`;
- R2.61: accept, `expanded_candidate_verified`;
- generated site hypotheses: **2**;
- admitted after counterexample: **1**;
- independent verification cases: **410/410**;
- false terminal accepts: **0**;
- R2.61 solver oracle calls: **411** = 1 diagnostic + 410 verification;
- total external calls including the initial label and the R2.60 causal baseline: **413**.

The harness does not hide extra target calls in a post-hoc exactness check.

## TDD and hosted verification

The production path followed hosted RED→GREEN development. The first RED run (`32120880271`) failed specifically because `cogcoder.r261_version_space_expansion` did not exist; later RED gates separately established the missing solver, benchmark and external harness before their implementations were added.

The proof-inclusive canonical hosted gate is GitHub Actions run **32123219112**:

- canonical job: **95668029445** — success;
- publish job: **95668982387** — success;
- PR merge tree: `e57c949eb94fe6ba9e027efcbdbe72029a37183a`;
- base `main`: `eef79e0ed6dd105ba8061945437841f3e284091c`;
- source lock: PASS;
- exact Phase-A recomputation: PASS;
- exact expansion-novelty-proof recomputation: PASS;
- exact NumPy external recomputation: PASS;
- R2.61 focused: **16/16 PASS**;
- Python 3.11 focused: PASS;
- Python 3.13 focused: PASS;
- protected R2.60→R2.41 parents: **205/205 PASS**;
- published context: `r261/full-gate = success`.

Frozen production/benchmark/transfer/proof/test blobs are listed in `R2_61_PRE_HOSTED_LOCK.json`. Any later change to a locked blob invalidates the receipt and requires complete remeasurement.

## Nolane World 0.8.0 audit

World: `world4_5368cf57101c48d0`.

After the proof-inclusive verifier was submitted:

- epoch: **9**;
- active seconds credited: **60**;
- fresh verifications: **2**;
- audit valid: **true**;
- audit digest: `a43654c603498845baba9948c92f28a4f64418470fac395cdd50c8a92710bd6a`;
- W5 convergence: **FAIL**, score **0.08333333333333337**.

W5 is intentionally not forced to pass. Remaining blockers include insufficient residency/epochs, unresolved critical unknowns, no independent challenger survival, insufficient robust/counterfactual worlds, insufficient representation diversity, material value-of-thought, and unfilled quality floors.

## Readiness calibration

Internal engineering readiness: **48.5/100**, up **+0.4** from R2.60's 48.1.

This is not an AGI probability. The increase is limited because R2.61 still has major boundaries:

- single-site expansion only;
- trusted patch vocabulary remains host-supplied;
- probe representation/domain remains host-supplied;
- multi-edit/compositional repair induction is unproven;
- no autonomous patch-language invention;
- stateful/effectful/filesystem/network experimentation is outside scope;
- no broad hidden-test repair over real external repositories;
- large candidate/site/macro/multi-round scaling is unproven;
- external breadth is one NumPy ufunc embedded in a synthetic repository wrapper;
- Nolane World W5 remains false.

## Post-merge verification

PR #15 was merged as `main` commit **`33042cbe92bea69580c7cc264cb35db09aaeee2f`**. The release workflow reran on that exact `main` commit as GitHub Actions run **32124011348**, job **95670466544**, and completed successfully across required release files, the ten frozen Git blobs, exact Phase-A/novelty/external recomputation, release-boundary assertions, R2.61/R2.60/R2.59 regressions, complete repository archive creation, archive integrity, artifact upload and `r261/release-bundle` status publication.

The uploaded `main` artifact is GitHub artifact **9319642259**. Its outer artifact SHA-256 is `6952c1c36008c9da58022bff450e4da8be8bfffc4abc54d289978daeb09869b0`. The contained repository archive `Nolane-AI-R2.61-COMPLETE.zip` has SHA-256 **`86624bcd9569bcf2f0f076aac9b4d962e69714c8cd5ca8d0daebfc70dea39a9c`**, matching the bundled sidecar. Independent post-download verification found **1,140 archive entries**, all required R2.61 files present, and `unzip -t` reported no errors for both outer and inner archives.

This post-merge check completes the release-acceptance rule. Subsequent documentation-only metadata commits do not alter any frozen capability/benchmark/transfer/proof/test blob; the release-bundle workflow must nevertheless rerun on such a commit before that newer `main` snapshot is treated as the canonical downloadable archive.
