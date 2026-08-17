# R2.52 Repository Multi-File Query Induction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded repository-level static import reasoning and atomic multi-file query-guided patch transactions on top of R2.51.

**Architecture:** Build a repository fact graph over immutable `path -> source` snapshots, resolve direct `from module import function` edges across files, learn the same identifier-invariant relational queries at repository scope, localize once on the pre-edit graph, then apply selected edits atomically across cloned module ASTs. Compile the repository in import-DAG order for executable CEGIS verification.

**Tech Stack:** Python 3.11+, stdlib `ast`, dataclasses, hashlib, itertools; pytest; existing R2.47/R2.50/R2.51 patch/query primitives.

## Global Constraints

- No new runtime dependencies.
- Keep all learnable features identifier-invariant: no file path, module name, function name, import alias, or variable name in query node attributes.
- Supported imports are acyclic direct `from module import function [as alias]` imports only.
- Localize all macros on the immutable pre-edit repository graph before applying any edit.
- Reject unsupported/ambiguous repositories and abstain on failed executable verification.
- Preserve R2.51 and R2.41 cross-Python behavior.

---

### Task 1: Repository snapshot, import resolver, and graph

**Files:**
- Create: `cogcoder/r252_repository_query.py`
- Test: `tests/test_r252_repository_query.py`

**Interfaces:**
- Produces `RepositorySnapshot`, `RepositoryFactGraph`, `build_repository_fact_graph()`, and repository/module normalization helpers.

- [ ] Write a failing test that builds three files (`entry.py -> bridge.py -> core.py`) and asserts `MODULE_CONTAINS`, `IMPORTS_SYMBOL`, `CALL_TARGET`, `ARG_BIND`, `FLOW`, and `FLOW*` are present with at least one cross-file call target.
- [ ] Run `PYTHONPATH=. pytest -q tests/test_r252_repository_query.py::test_repository_graph_resolves_cross_file_import_call_flow` and confirm RED because the module does not exist.
- [ ] Implement snapshot normalization, parsing, direct import resolution, graph construction, and transitive flow closure.
- [ ] Re-run the focused test and confirm GREEN.

### Task 2: Repository macro induction and atomic apply

**Files:**
- Modify: `cogcoder/r252_repository_query.py`
- Modify: `tests/test_r252_repository_query.py`

**Interfaces:**
- Produces `RepositoryQueryMacro`, `learn_repository_query_macro()`, `learn_repository_query_library()`, `apply_repository_query_macros()`.

- [ ] Add failing tests showing a macro learned from two shallow multi-file demonstrations patches only the imported causally relevant site and leaves syntax-identical decoys in other files unchanged.
- [ ] Add a failing test proving a three-macro transaction changes exactly three files and returns no partial snapshot on invalid localization.
- [ ] Implement repository-wide candidate enumeration/labels, trace extraction, query induction, pre-edit localization, and cloned-AST atomic apply.
- [ ] Run `PYTHONPATH=. pytest -q tests/test_r252_repository_query.py` and confirm all focused unit tests pass.

### Task 3: Repository candidate compilation and sparse CEGIS

**Files:**
- Modify: `cogcoder/r252_repository_query.py`
- Modify: `tests/test_r252_repository_query.py`

**Interfaces:**
- Produces `RepositoryPatchCandidate`, `enumerate_repository_candidates()`, `compile_repository_candidate()`, `solve_repository_patch_with_sparse_tests()`.

- [ ] Add failing tests for import-DAG execution, unique-root inference, unsupported import cycle rejection, and executable sparse-test convergence.
- [ ] Implement topological dependency ordering, import stripping/injection, candidate deduplication, root compilation, and CEGIS using the existing receipt semantics.
- [ ] Run focused tests and confirm GREEN.

### Task 4: Frozen R2.52 transfer benchmark

**Files:**
- Create: `benchmarks/kfigg/r252_repository_multifile_transfer.py`
- Create: `tests/test_r252_repository_query_benchmark.py`

**Interfaces:**
- Produces `training_demo()`, `grouped_training_demos()`, `learn_r252_library()`, `run_heldout_episode()`, and `run_frozen_heldout()`.

- [ ] Build ten edit families mirroring R2.51 but with demonstrations at 3 files / cross-file depth 2.
- [ ] Build six held-out opaque repositories with 5–6 files / cross-file depth 4–5 and three essential edits in three distinct files.
- [ ] Assert 75 candidates, 6/6 exact, zero false accepts, exact macro set 6/6, three changed files 6/6, R2.51 boundary rejection 6/6, global syntax baseline 0/6, direct target 6/6, sparse feedback <=6/2401, and exhaustive 2401-test verification.
- [ ] Run the frozen benchmark test and fix only causal/representation defects, never relax exactness gates.

### Task 5: Regression, cross-Python CI, and evidence

**Files:**
- Create: `.github/workflows/r252-repository-multifile-query.yml`
- Create: `research/R2_52_PHASE_A_RESULT.json`
- Create: `research/R2_52_VERIFY_RESULT.json`
- Create: `R2_51_TO_R2_52_EVOLUTION.md`
- Create: `R2_52_DELIVERY.md`

**Interfaces:**
- CI verifies R2.52 focused/frozen gates, R2.51→R2.41 parent lineage, and Python 3.11/3.13 focused determinism.

- [ ] Run R2.52 unit + frozen benchmark locally.
- [ ] Run parent regression groups R2.51→R2.41.
- [ ] Freeze exact benchmark summary into Phase A/Verify evidence without overstating generality.
- [ ] Add CI path triggers for the new files and every parent primitive R2.52 depends on.
- [ ] Push an atomic candidate commit to `main`, observe clean-runner results, and fix any runtime-specific issue at source.

### Task 6: Nolane World audit and complete release bundle

**Files:**
- Create: `research/R2_52_WORLD_FINAL.json`
- Create: `R2_52_RELEASE_MANIFEST.json`
- Create/modify: `.github/workflows/r252-release-bundle.yml`

**Interfaces:**
- Release records the accepted bounded capability, unresolved frontier, commit/run IDs, exact benchmark metrics, World audit digest, and complete ZIP checksum.

- [ ] Run a W5 Nolane World adversarial audit against import privilege, graph closure, single-family leakage, repository-scale complexity, unsupported dynamic semantics, and false AGI conclusions.
- [ ] Keep convergence false unless the runtime itself authorizes it.
- [ ] Generate a complete repository ZIP from the accepted GitHub commit and verify SHA-256 plus `unzip -t`.
- [ ] Persist ZIP + checksum + delivery/evidence files to ChatGPT Library.
