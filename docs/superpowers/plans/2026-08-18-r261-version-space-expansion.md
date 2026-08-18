# R2.61 Counterexample-Guided Version-Space Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Nolane-AI recover when R2.60 discovers that the correct repository behavior is absent from the supplied candidate version space by generating bounded new candidates from trusted patch primitives and public counterexamples.

**Architecture:** Add a deterministic single-site repository mutation generator over existing R2.47 `PatchMacro` semantics and an R2.60-compatible active diagnosis loop that invokes expansion only after a successful out-of-version-space oracle observation. Generated syntax is target-label-independent; oracle labels only filter generated candidates. Terminal acceptance remains independently verified.

**Tech Stack:** Python 3.11/3.13, dataclasses, `ast`, existing `cogcoder.r247_executable_patch_cegis`, `cogcoder.r252_repository_query`, `cogcoder.r260_active_repository_probes`, pytest, GitHub Actions, NumPy 2.4.6 for pinned external I/O-only transfer.

**Spec:** `docs/superpowers/specs/2026-08-18-r261-version-space-expansion-design.md`

## Global Constraints
- Added trainable parameters: exactly 0.
- No arbitrary code generation, new imports, new calls, new files, new statements, or effect semantics.
- Mutation syntax and sites must be generated without target oracle outputs.
- Oracle labels may only filter already-generated hypotheses.
- Hard budgets for expansion rounds, generated candidates, mutation sites, selection oracle calls, and independent verification.
- R2.60/R2.59→R2.41 behavior must remain protected.
- W5 non-convergence must not be overridden.

---

### Task 1: RED gate for targeted candidate expansion

**Files:**
- Create: `tests/test_r261_version_space_expansion.py`
- Create: `.github/workflows/r261-version-space-expansion.yml`

**Interfaces:**
- Consumes: `PatchMacro`, `PatchTest`, `RepositoryPatchCandidate`, `RepositoryProbe`.
- Produces expected future API: `expand_repository_candidates(...)`, `solve_repository_patch_with_version_space_expansion(...)`.

- [ ] **Step 1: Write failing generator tests**

Create tests that import the missing R2.61 module and assert these behaviors once implemented:

```python
from cogcoder.r247_executable_patch_cegis import PatchMacro, PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_version_space_expansion import (
    expand_repository_candidates,
    solve_repository_patch_with_version_space_expansion,
)


def _macro(slot, src, dst, mid='pm:test'):
    return PatchMacro(mid, slot, 'replace' if slot in {'binop', 'compare'} else 'wrap', src, dst, support=1)


def test_expander_generates_single_site_content_addressed_mutations_without_oracle():
    seed = RepositoryPatchCandidate(
        'seed', (),
        (('a.py', 'def f(x, y):\n    a = x // y\n    b = x // y\n    return a + b\n'),),
        0, 0,
    )
    rows = expand_repository_candidates(
        (seed,), (_macro('binop', 'FloorDiv', 'Mod'),),
        max_generated_candidates=16, max_sites_per_macro=8,
    )
    assert len(rows) == 2
    assert len({row.candidate_id for row in rows}) == 2
    assert all(row.edit_count == 1 for row in rows)
    assert all(sum(source.count('%') for _path, source in row.files) == 1 for row in rows)


def test_expander_is_seed_and_macro_order_invariant():
    # Build two seeds and two macros; reversed inputs must yield identical candidate ids/files.
    ...


def test_expander_budget_is_hard_and_deterministic():
    # More compatible sites than budget; exactly budgeted deterministic prefix must be returned.
    ...
```

Replace each `...` in the committed test with concrete repositories and assertions before committing.

- [ ] **Step 2: Write failing solver tests**

Cover:
- R2.60 baseline returns `oracle_outside_candidate_version_space`.
- R2.61 consumes that counterexample, expands, admits the generated correct candidate, resumes diagnosis, and independently verifies.
- no macro/seed, expansion budget exhaustion, unsupported/unexpressible target, oracle error, and verification failure all abstain.
- target oracle must not be passed into `expand_repository_candidates`.

- [ ] **Step 3: Add RED workflow**

Workflow installs pytest and runs only `tests/test_r261_*.py` on `r261-version-space-expansion-gpt56sol` and pull requests. It is allowed to fail before production code exists.

- [ ] **Step 4: Run hosted RED**

Expected: test collection/import fails specifically because `cogcoder.r261_version_space_expansion` does not yet exist. Record run/job IDs in `R2_61_TDD_RED.json` only after seeing the failure.

---

### Task 2: GREEN — deterministic targeted mutation generator

**Files:**
- Create: `cogcoder/r261_version_space_expansion.py`
- Modify: `tests/test_r261_version_space_expansion.py`

**Interfaces:**
- Produces:
  - `ExpansionMutation(mutation_id, seed_candidate_id, macro_id, path, site_index)`
  - `ExpansionCandidate(candidate, mutation)`
  - `expand_repository_candidates(seeds, macros, *, max_generated_candidates, max_sites_per_macro) -> tuple[ExpansionCandidate, ...]`

- [ ] **Step 1: Implement compatibility enumeration**

Use R2.52 parsing constraints and R2.47 patch slots. For each seed/file/macro, enumerate only compatible AST sites in deterministic path + AST-walk order. No oracle argument exists in this API.

- [ ] **Step 2: Implement single-site edit**

Deep-copy/reparse the target file, apply exactly one existing patch primitive to exactly one compatible node, `ast.fix_missing_locations`, `ast.unparse`, reconstruct the unchanged file set, and reject invalid repositories by constructing/compiling through R2.52.

- [ ] **Step 3: Content-address and deduplicate**

Hash canonical JSON containing resulting files and mutation provenance. Deduplicate by complete resulting file tuple. Sort by content/provenance, not caller input order.

- [ ] **Step 4: Run focused generator tests**

Expected: all generator tests PASS.

---

### Task 3: GREEN — counterexample-guided expansion solver

**Files:**
- Modify: `cogcoder/r261_version_space_expansion.py`
- Modify: `tests/test_r261_version_space_expansion.py`

**Interfaces:**
- Produces:
  - `ExpansionRoundReceipt`
  - `VersionSpaceExpansionReceipt`
  - `solve_repository_patch_with_version_space_expansion(candidates, initial_tests, probe_inputs, oracle, *, verification_inputs, expansion_seeds, expansion_macros, max_selection_oracle_calls=8, max_expansion_rounds=2, max_generated_candidates_per_round=256, max_sites_per_macro=64) -> VersionSpaceExpansionReceipt`

- [ ] **Step 1: Reuse R2.60 compilation/filtering/probe ranking semantics**

Import the tested R2.60 internal helpers rather than reimplementing ranking. Preserve R2.60 candidate identity/order invariance.

- [ ] **Step 2: Add out-of-space transition**

When a successful selected oracle outcome has no bucket:
1. append a public `PatchTest` containing only the observed probe args and oracle value;
2. call the target-independent expander;
3. filter generated candidates against all observed tests;
4. union/deduplicate admitted generated candidates;
5. resume active diagnosis.

- [ ] **Step 3: Add hard fail-closed budgets**

Explicit terminal reasons for no expansion seeds, no trusted macros, expansion-round budget exhausted, generated-candidate budget exhausted/no generated candidates, no candidate satisfies counterexample, selection oracle error, no informative probe, and independent verification failure.

- [ ] **Step 4: Run solver tests**

Expected: all R2.61 focused tests PASS, including zero false accepts in negative cases.

---

### Task 4: Authored causal benchmark

**Files:**
- Create: `benchmarks/kfigg/r261_version_space_expansion_transfer.py`
- Create: `tests/test_r261_version_space_expansion_benchmark.py`
- Create after frozen run: `R2_61_PHASE_A_RESULT.json`

**Interfaces:**
- Produces `run_frozen_heldout() -> dict`.

- [ ] **Step 1: Build at least six multi-file R2.52-compatible episodes**

Each episode contains multiple compatible edit sites. Initial supplied candidates must omit the exact target. Trusted macros are generic and shared across episodes.

- [ ] **Step 2: Prove causal baseline**

For every positive episode, run R2.60 with the same initial candidates/tests/probe space and assert it abstains because the oracle outcome is outside the candidate version space.

- [ ] **Step 3: Prove expansion path**

R2.61 must generate the missing repair only after the diagnostic counterexample, reach exact repository files, and pass independent verification.

- [ ] **Step 4: Add adversarial negatives**

Include at least one unexpressible target, one exhausted expansion budget, one oracle error, and order permutations. Assert false terminal accepts = 0.

- [ ] **Step 5: Freeze exact JSON**

Write exact deterministic result to `R2_61_PHASE_A_RESULT.json` only after a green run.

---

### Task 5: Pinned external I/O-only transfer

**Files:**
- Create: `research/r261_external_version_space_expansion.py`
- Create: `tests/test_r261_external_version_space_expansion.py`
- Create after hosted run: `R2_61_EXTERNAL_TRANSFER.json`

**Interfaces:**
- Produces `run_external_transfer(oracle, source_id, source_version) -> dict`.

- [ ] **Step 1: Build NumPy remainder adapter without source parsing**

Use callable I/O only from pinned `numpy==2.4.6`; do not inspect NumPy implementation source. Build a multi-file repository with decoy `FloorDiv` sites. Initial host-supplied candidates exclude the correct `Mod` repair.

- [ ] **Step 2: Use a trusted macro learned independently of target source**

The `FloorDiv -> Mod` `PatchMacro` may be constructed from an independent demonstration or the same existing R2.47 primitive representation, but the correct repository candidate must be generated by R2.61 rather than authored in the harness.

- [ ] **Step 3: Verify external causal contrast**

Assert R2.60 baseline abstains out-of-space; R2.61 generates the correct candidate; heldout verification is exact; false terminal accepts = 0; all oracle calls and generated candidate counts are reported.

---

### Task 6: Source lock and hosted verification

**Files:**
- Update: `.github/workflows/r261-version-space-expansion.yml`
- Create: `R2_61_PRE_HOSTED_LOCK.json`
- Create after success: `R2_61_VERIFY_RESULT.json`

- [ ] **Step 1: Freeze source blob SHAs and parent release**

Parent must be accepted R2.60 main commit `482f79d71e95552475c918d3e4ff0e5ca819cb4e` unless `main` advances; if it advances, rebase and re-freeze rather than silently changing ancestry.

- [ ] **Step 2: Hosted gate**

Run focused R2.61, exact Phase-A recomputation, exact external recomputation, direct R2.60 tests, R2.59/R2.58, protected R2.57→R2.50, protected R2.49→R2.41, plus Python 3.11/3.13 focused jobs.

- [ ] **Step 3: Record only observed results**

Do not claim pass counts or readiness movement before hosted logs confirm them.

---

### Task 7: Nolane World audit, release evidence, bundle, and integration

**Files:**
- Create: `R2_61_WORLD_FINAL.json`
- Create: `R2_61_DELIVERY.md`
- Create: `R2_61_RELEASE_MANIFEST.json`
- Modify: `R2_READINESS_RECALIBRATION.md`
- Create: `.github/workflows/r261-release-bundle.yml`

- [ ] **Step 1: Run a fresh Nolane World 0.8.0 W5 world**

Credit only real verification/research time and verifier evidence. Preserve unresolved blockers and do not force W5 convergence.

- [ ] **Step 2: Recalibrate readiness conservatively**

Movement, if any, requires causal evidence that R2.61 succeeds where R2.60 cannot because the target candidate is initially absent. External breadth and bounded DSL limitations must cap the score.

- [ ] **Step 3: Build complete repository ZIP workflow**

Bundle the full repository, checksum, `unzip -t`, verify required R2.61 evidence and source files, upload artifact, and publish `r261/release-bundle` success only on full green.

- [ ] **Step 4: Merge only after frozen hosted gate**

Open PR from `r261-version-space-expansion-gpt56sol`; merge only after all relevant hosted evidence is green and branch contains no post-measurement production-code changes.

- [ ] **Step 5: Verify main artifact and persist complete ZIP**

After merge, verify the main-run bundle checksum and archive integrity. Persist the main artifact and checksum to the user's Nolane-AI Library release folder.
