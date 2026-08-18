# R2.64 Unified Adaptive Repository Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Keep hosted RED→GREEN evidence for each major layer.

**Goal:** Unify R2.61 diagnostic out-of-space expansion and accepted R2.63 multi-round refinement composition in one bounded repository search loop.

**Architecture:** Canonicalize repository states by content, maintain one public evidence ledger, allow trusted PatchMacro expansion after diagnostic or refinement counterexamples, preserve content-addressed mutation provenance, and reserve final verification as unique/disjoint terminal evidence.

**Tech Stack:** Python 3.11/3.13, existing R2.47/R2.52/R2.60/R2.61/R2.63 primitives, pytest, GitHub Actions, NumPy 2.4.6.

**Spec:** `docs/superpowers/specs/2026-08-18-r264-unified-adaptive-repository-search-design.md`

## Global constraints

- Added trainable parameters = 0.
- No oracle/target/expected-output channel in candidate generation.
- Only trusted pre-existing PatchMacro transformations may change repositories.
- Complete repository content, not caller IDs, defines semantic candidate identity.
- All diagnostic/refinement observations are retained as public PatchTests.
- Final verification is unique, disjoint and terminal.
- Hard selection/refinement/round/depth/generation/site budgets fail closed.
- Accepted R2.63 and protected lineage must remain green.
- Nolane World W5 must not be forced to pass.

## Task 1 — Hosted RED and minimal unified solver

**Files:**
- `tests/test_r264_unified_adaptive_repository_search.py`
- `cogcoder/r264_unified_adaptive_repository_search.py`
- `.github/workflows/r264-unified-adaptive-repository-search.yml`

- [x] Define a valid one-root multi-file repository with at least two initial executable hypotheses whose diagnostic partitions do not contain the target outcome.
- [x] Confirm accepted R2.63 abstains at its initial version-space boundary.
- [x] Run hosted RED while the R2.64 module does not exist.
- [x] Implement content-canonicalized bounded adaptive frontier and unified solver.
- [x] Preserve diagnostic + refinement evidence and content-addressed selected mutation chain.
- [x] Keep final verification terminal and reject duplicates/learning overlap.
- [x] Debug the original invalid multi-root fixture at the fixture source rather than weakening production compilation semantics.
- [x] Run Python 3.11/3.13 focused tests and accepted R2.63 parent first.

## Task 2 — Authored causal benchmark

**Files:**
- `tests/test_r264_unified_adaptive_benchmark.py`
- `benchmarks/kfigg/r264_unified_adaptive_repository_search.py`
- `R2_64_PHASE_A_RESULT.json` after hosted measurement.

- [ ] Write benchmark test before benchmark module exists and record hosted RED.
- [ ] Build six structurally varied multi-file positive episodes with a connected decoy site.
- [ ] Prove exact target absent initially and from complete one-step trusted-macro space.
- [ ] Require accepted R2.63 = diagnostic out-of-space abstain on every positive episode.
- [ ] Require R2.64 = exact on every positive episode with one diagnostic + one refinement counterexample and exactly two expansion rounds.
- [ ] Require at least 24 disjoint final verification cases per positive episode.
- [ ] Add fail-closed negative/adversarial gates and ordering/identity invariance.
- [ ] Freeze hosted exact JSON only after all gates pass.

## Task 3 — Causal external callable-I/O transfer

**Files:**
- `tests/test_r264_external_unified_transfer.py`
- `research/r264_external_unified_transfer.py`
- `R2_64_EXTERNAL_TRANSFER.json` after hosted measurement.

- [ ] Write external test before harness module exists and record hosted RED.
- [ ] Use pinned NumPy 2.4.6 `numpy.square` via callable I/O only.
- [ ] Construct an initial wrong executable hypothesis so square behavior is outside all initial diagnostic partitions.
- [ ] Prove exact two-edit target absent from initial and complete one-step spaces.
- [ ] Require accepted R2.63 baseline to abstain at the initial version-space boundary.
- [ ] Require R2.64 diagnostic expansion + refinement composition + disjoint heldout verification.
- [ ] Report all external oracle calls by evidence class without hidden post-hoc target calls.
- [ ] Freeze exact hosted result.

## Task 4 — Source lock and canonical protected-lineage gate

**Files:**
- `R2_64_TDD_RED.json`
- `R2_64_PRE_HOSTED_LOCK.json`
- workflow update.

- [ ] Freeze exact production/benchmark/external/test Git blobs after adversarial hardening.
- [ ] Verify PR base is the exact accepted R2.63 release commit (or update to current main and remeasure if main moved).
- [ ] Recompute Phase-A and external JSON byte-for-byte on the PR merge tree.
- [ ] Run R2.64 focused and Python 3.11/3.13.
- [ ] Run accepted R2.63 through protected R2.41 lineage; record exact pass counts from logs.
- [ ] Publish `r264/full-gate` only after every dependency succeeds.

## Task 5 — Nolane World, readiness and release

**Files:**
- `R2_64_HOSTED_VERIFICATION.json`
- `R2_64_WORLD_FINAL.json`
- `R2_64_DELIVERY.md`
- `R2_64_RELEASE_MANIFEST.json`
- `R2_READINESS_RECALIBRATION.md`
- `.github/workflows/r264-release-bundle.yml`

- [ ] Submit canonical hosted evidence to Nolane World 0.8.0 using a runtime-recognized verifier principal.
- [ ] Preserve W5 failure unless the runtime's convergence requirements genuinely pass.
- [ ] Recalibrate readiness conservatively from accepted R2.63's 49.1/100; no score inflation from CI alone.
- [ ] Build complete repository ZIP only after source lock/exact evidence/claim-boundary/regression checks pass.
- [ ] Merge only from current main and expected head SHA.
- [ ] Rerun the release bundle on the exact post-merge main commit.
- [ ] Independently verify artifact checksum, required files and ZIP integrity.
- [ ] Persist the final verified ZIP and checksum to Library.
