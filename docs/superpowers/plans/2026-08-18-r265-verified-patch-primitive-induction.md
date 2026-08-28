# R2.65 Verified Patch Primitive Induction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task and preserve hosted RED→GREEN evidence.

**Goal:** Remove the requirement that the exact target-specific PatchMacro be supplied in advance by deriving a bounded primitive from a closed authorized AST rewrite grammar plus public counterexamples.

**Architecture:** Infer source operator families from authorized repository seeds, enumerate content-addressed primitive hypotheses without oracle access, instantiate bounded repository candidates through the R2.61 expander, filter them with diagnostic/challenge evidence, promote only a uniquely surviving primitive after independent challenges, and reserve final verification as disjoint terminal evidence.

**Tech Stack:** Python 3.11/3.13, `ast`, R2.47/R2.52/R2.60/R2.61/R2.64 primitives, pytest, GitHub Actions, NumPy 2.4.6.

**Spec:** `docs/superpowers/specs/2026-08-18-r265-verified-patch-primitive-induction-design.md`

## Global constraints

- Added trainable parameters = 0.
- Primitive enumeration has no oracle/target/expected-output parameter.
- Grammar is finite and host-authorized; R2.65 cannot create arbitrary AST semantics.
- Source operators must occur in authorized repository seeds.
- Challenge evidence is unique and disjoint from diagnostic and final evidence.
- Primitive promotion requires a configurable minimum challenge count and one surviving `(primitive, repository-content)` pair.
- Final verification is unique, disjoint and terminal.
- Accepted R2.64 and protected lineage remain green.
- Nolane World W5 cannot be forced to pass.

## Task 1 — Hosted RED and minimal primitive learner

**Files:** `tests/test_r265_verified_patch_primitive_induction.py`, `cogcoder/r265_verified_patch_primitive_induction.py`, `.github/workflows/r265-verified-patch-primitive-induction.yml`.

- [x] Write missing-primitive tests first.
- [x] Trigger hosted RED while the production module is absent.
- [x] Implement closed-grammar deterministic primitive enumeration.
- [x] Implement diagnostic-counterexample induction, challenge filtering and terminal verification.
- [x] Add grammar-missing-target, evidence-isolation and challenge-budget fail-closed tests.
- [ ] Confirm hosted Python 3.11/3.13 green with accepted R2.64 parent first.

## Task 2 — Authored causal benchmark

**Files:** `tests/test_r265_patch_primitive_benchmark.py`, `benchmarks/kfigg/r265_patch_primitive_induction.py`, later `archive/root-history/historical_r_series/R2_65_PHASE_A_RESULT.json`.

- [ ] Write benchmark contract before benchmark module exists and record hosted RED.
- [ ] Cover at least six source→target binop primitive families with structural/file variation.
- [ ] Include a connected same-source-op decoy site so primitive induction must also localize the behaviorally relevant mutation.
- [ ] Require accepted R2.64 with empty macro input to fail causally on every episode.
- [ ] Require R2.65 to learn the expected primitive, pass ≥4 independent challenges and ≥24 disjoint final heldouts on every positive episode.
- [ ] Add fail-closed negative/adversarial gates, caller-ID/order invariance and target-output-free enumeration proof.
- [ ] Freeze exact hosted Phase-A JSON.

## Task 3 — External callable-I/O transfer

**Files:** `tests/test_r265_external_patch_primitive_transfer.py`, `research/r265_external_patch_primitive_transfer.py`, later `archive/root-history/historical_r_series/R2_65_EXTERNAL_TRANSFER.json`.

- [ ] Write external contract before harness implementation and record hosted RED.
- [ ] Use pinned NumPy 2.4.6 `numpy.multiply` via callable I/O only.
- [ ] Do not supply `Add → Mult` as an input PatchMacro; supply only the closed authorized target-operator grammar.
- [ ] Require accepted R2.64 with an empty exact macro set to fail after an out-of-space diagnostic label.
- [ ] Require R2.65 to induce `Add → Mult`, promote it after independent challenges and pass a large disjoint heldout set.
- [ ] Prove exact target repository is absent from initial supplied candidates and not host-authored as a solver input.
- [ ] Count all external oracle calls without hidden post-hoc checks.
- [ ] Freeze exact hosted transfer JSON.

## Task 4 — Freeze and canonical verification

**Files:** `R2_65_TDD_RED.json`, `archive/root-history/historical_r_series/R2_65_PRE_HOSTED_LOCK.json`, canonical workflow update.

- [ ] Harden identity/provenance/evidence boundaries before lock.
- [ ] Freeze production, benchmark, transfer and tests by Git blob SHA.
- [ ] Recompute exact authored/external evidence on the current PR merge tree.
- [ ] Run R2.65 focused/cross-Python and accepted R2.64→R2.41 protected lineage; record exact counts from logs.
- [ ] Publish `r265/full-gate` only after all dependencies succeed.

## Task 5 — World, readiness and release

**Files:** `archive/root-history/historical_r_series/R2_65_HOSTED_VERIFICATION.json`, `archive/root-history/historical_r_series/R2_65_WORLD_FINAL.json`, `archive/root-history/historical_r_series/R2_65_DELIVERY.md`, `archive/root-history/historical_r_series/R2_65_RELEASE_MANIFEST.json`, `archive/root-history/historical_r_series/R2_READINESS_RECALIBRATION.md`, `.github/workflows/r265-release-bundle.yml`.

- [ ] Submit fresh canonical verifier plus an explicit surviving challenger to Nolane World 0.8.0.
- [ ] Preserve fail-closed W5 state unless genuine convergence occurs.
- [ ] Recalibrate readiness conservatively from accepted R2.64.
- [ ] Build complete repository ZIP only after exact evidence and boundary checks pass.
- [ ] Merge only against current main and expected head SHA.
- [ ] Rerun bundle on exact post-merge main and independently verify checksum/archive contents.
- [ ] Persist final ZIP + checksum to Library.
