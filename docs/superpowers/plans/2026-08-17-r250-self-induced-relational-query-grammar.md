# R2.50 Self-Induced Relational Query Grammar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded representation-induction layer that synthesizes minimal relational path queries from low-level Python program facts and uses them to localize executable patch macros on held-outs where R2.49's complete handcrafted feature vocabulary cannot distinguish target from decoy.

**Architecture:** Build a low-level identifier-invariant fact graph, enumerate and normalize bounded typed path traces, induce minimal discriminative trace conjunctions from positive/negative edit sites, and compose those learned queries with existing R2.47 patch macros. Reuse sparse executable CEGIS for candidate selection and certify with exhaustive held-out tests.

**Tech Stack:** Python 3.11+, stdlib `ast`, `dataclasses`, `hashlib`, `itertools`, existing `cogcoder` patch/CEGIS modules, `pytest`, GitHub Actions.

## Global Constraints

- No raw identifier, line-number, AST-position, hidden-label, or task-specific constant may appear in learned query signatures.
- Do not call `relational_features_for_site()` from the R2.50 learner or matcher.
- R2.49 target and decoy feature sets must be exactly equal in the adversarial benchmark.
- Held-out search feedback must remain <= 1% before exhaustive final certification.
- Parent R2.49-R2.41 tests must remain green.
- Deterministic output for identical inputs.
- Fail closed when demonstrations are not separable by the induced query grammar.

---

### Task 1: Low-level program fact graph and trace grammar

**Files:**
- Create: `cogcoder/r250_relational_query.py`
- Test: `tests/test_r250_relational_query.py`

**Interfaces:**
- Produces: `ProgramFactGraph`, `TracePattern`, `build_program_fact_graph(source: str)`, `trace_patterns_for_site(graph, site_node, max_depth=6)`.
- Consumes: `_parse_function`, `PatchMacro`, and AST helpers from existing R2.47/R2.49 modules only for parsing/candidate-node selection; it must not consume handcrafted R2.49 features.

- [ ] **Step 1: Write failing tests** for identifier-invariant graph construction, parameter-origin versus call-origin traces, alias-depth normalization, and raw-name exclusion.
- [ ] **Step 2: Run** `PYTHONPATH=. pytest -q tests/test_r250_relational_query.py` and verify RED because the module does not exist.
- [ ] **Step 3: Implement** typed graph nodes/edges, binding resolution, bounded path enumeration, and generic consecutive-alias repetition normalization.
- [ ] **Step 4: Run** the focused test file and verify GREEN.
- [ ] **Step 5: Commit** the isolated local branch checkpoint.

### Task 2: Minimal discriminative relational query induction

**Files:**
- Modify: `cogcoder/r250_relational_query.py`
- Test: `tests/test_r250_relational_query.py`

**Interfaces:**
- Produces: `InducedRelationalQuery`, `learn_induced_query(positive_trace_sets, negative_trace_sets)`, `query_matches(query, trace_set)`.

- [ ] **Step 1: Add failing tests** proving the learner chooses the shortest trace conjunction covering all positives and rejecting all negatives, is deterministic under input order reversal, and fails closed when positive/negative sites are inseparable.
- [ ] **Step 2: Run focused tests** and verify the new tests fail.
- [ ] **Step 3: Implement** canonical signatures, increasing-description-length conjunction search, deterministic tie-breaking, support validation, and content-addressed IDs.
- [ ] **Step 4: Run focused tests** and verify GREEN.
- [ ] **Step 5: Commit** the isolated local branch checkpoint.

### Task 3: Query-conditioned patch macros

**Files:**
- Modify: `cogcoder/r250_relational_query.py`
- Test: `tests/test_r250_relational_query.py`

**Interfaces:**
- Produces: `QueryPatchMacro`, `learn_query_patch_macro(demos)`, `learn_query_patch_library(grouped_demos)`, `apply_query_patch_macros(source, macros)`, `enumerate_query_patch_candidates(source, macros)`.
- Reuses: R2.47 `infer_patch_macro`, `PatchCandidate`, base rewrite helpers.

- [ ] **Step 1: Add failing tests** with two identical R2.49-feature sites where only operand provenance separates the changed site.
- [ ] **Step 2: Verify RED** and explicitly assert `relational_features_for_site(target) == relational_features_for_site(decoy)`.
- [ ] **Step 3: Implement** positive/negative site extraction per demonstration, query induction, query-conditioned matching, base edit application, and candidate enumeration.
- [ ] **Step 4: Verify GREEN**, including no raw-name leakage in query signatures.
- [ ] **Step 5: Commit** the isolated local branch checkpoint.

### Task 4: Frozen adversarial executable benchmark

**Files:**
- Create: `benchmarks/kfigg/r250_self_induced_query_transfer.py`
- Create: `tests/test_r250_self_induced_query_benchmark.py`

**Interfaces:**
- Produces: `run_heldout_episode(seed)` and `run_frozen_heldout()` with a JSON-serializable summary/gate schema.
- Reuses: R2.47 `PatchTest` and sparse executable CEGIS.

- [ ] **Step 1: Add frozen seeds and failing benchmark tests** for six opaque held-outs with alias-depth/control-flow reshaping.
- [ ] **Step 2: Verify RED** until R2.50 solves the benchmark.
- [ ] **Step 3: Implement benchmark generation** so target/decoy complete R2.49 feature sets are equal, R2.49 learning fails or baseline is 0/6, and R2.50 receives only demonstrations plus sparse executable feedback.
- [ ] **Step 4: Verify** 6/6 exact, 0 false accepts, <=1% feedback, exhaustive final execution, deterministic learned queries, and causal baseline failure.
- [ ] **Step 5: Commit** the isolated local branch checkpoint.

### Task 5: GitHub clean-runner gate

**Files:**
- Create: `.github/workflows/r250-self-induced-relational-query.yml`

**Interfaces:**
- Workflow runs R2.50 tests, then R2.49/R2.48/R2.47, R2.46, R2.45/R2.44, and R2.43/R2.41 parent gates, then recomputes R2.50 frozen evidence from source.

- [ ] **Step 1: Write workflow** using Ubuntu 24.04, Python 3.11, focused dependencies, explicit assertions for all R2.50 acceptance metrics.
- [ ] **Step 2: Locally parse/review YAML text** and verify all referenced files exist.
- [ ] **Step 3: Commit R2.50 code/tests/benchmark/workflow atomically to GitHub `main`** using the current release HEAD as parent after a final race check.
- [ ] **Step 4: Observe GitHub Actions** to completion; if red, diagnose root cause and return to the relevant TDD task without weakening acceptance gates.
- [ ] **Step 5: Confirm all integrity workflows for the capability commit are green.**

### Task 6: Nolane World adversarial audit and bounded release

**Files:**
- Create: `R2_50_DELIVERY.md`
- Create: `R2_50_RELEASE_MANIFEST.json`
- Create: `research/R2_50_PHASE_A_RESULT.json`
- Create: `research/R2_50_VERIFY_RESULT.json`
- Create/modify: full-repository release workflow for R2.50 if needed.

**Interfaces:**
- Produces frozen evidence, World audit digest/status, readiness delta, and complete recovery bundle.

- [ ] **Step 1: Run Nolane World 0.5.0 W5 audit** against leakage, handcrafted-vocabulary fallback, alias-depth overfitting, sparse-test leakage, and synthetic-family overreach.
- [ ] **Step 2: Freeze evidence** with W5 status exactly as returned; never force convergence.
- [ ] **Step 3: Assign a conservative internal coding-AGI engineering-readiness score** only from verified causal gains and explicitly state it is not AGI probability.
- [ ] **Step 4: Commit release evidence atomically to GitHub `main`** and verify release/integrity workflows.
- [ ] **Step 5: Generate and integrity-test a complete repository ZIP**, compute SHA-256, save ZIP + evidence into ChatGPT Library, and provide the sandbox download link.
