# R2.53 External Cognitive Reflex Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-neural-parameter external cognitive reflex layer that detects cognitive deficits from safe observable telemetry, retrieves provenance-bound reasoning procedures, safely compiles them from registered primitives, executes/verifies them, and learns routing credit without changing model weights.

**Architecture:** Add a broad externalization catalog plus a compact executable core. The core reuses R2.1 knowledge retrieval concepts but generalizes retrieval from factual chunks to behavioral procedure cards. It never executes arbitrary retrieved code; procedure programs are bounded compositions of pre-registered primitive operators.

**Tech Stack:** Python 3.11+, dataclasses, existing Nolane evidence/retrieval types, pytest, GitHub Actions.

## Global Constraints
- Add 0 neural parameters.
- Do not persist private chain-of-thought.
- Objective verifier/failure signals override model self-confidence.
- Retrieved procedures may only reference registered primitive operators.
- All procedure cards carry source/version/hash/trust provenance.
- Unknown or untrusted behavioral knowledge fails closed.
- Keep AGI-readiness scoring conservative; mechanism benchmark alone cannot justify a large increase.

---

### Task 1: Externalization catalog and contracts

**Files:**
- Create: `cogcoder/r253_operator_catalog.py`
- Test: `tests/test_r253_operator_catalog.py`

**Interfaces:**
- Produces: `OperatorFamilyDescriptor`, `SubOperatorDescriptor`, `build_default_externalization_catalog()`.

- [ ] Write tests requiring all 22 original families plus 16 additional families, >=6 granular suboperators per family, unique ids, and explicit implementation status.
- [ ] Run the catalog test and confirm RED because the module does not exist.
- [ ] Implement immutable catalog descriptors and the default catalog.
- [ ] Run catalog tests to GREEN.

### Task 2: Deficit telemetry and objective metacognitive detection

**Files:**
- Create: `cogcoder/r253_external_cognition.py`
- Test: `tests/test_r253_external_cognition.py`

**Interfaces:**
- Produces: `CognitiveSnapshot`, `DeficitSignal`, `CognitiveDeficitDetector`.

- [ ] Write failing tests for knowledge gaps, verifier failures, search stagnation, representation mismatch, temporal conflicts, tool gaps, counterexample repetition, working-memory pressure, and stopping uncertainty.
- [ ] Include a high-self-confidence case where objective evidence still triggers a severe deficit.
- [ ] Implement deterministic multi-signal detection with evidence receipts.
- [ ] Run focused tests to GREEN.

### Task 3: Safe external operator registry and procedure compilation

**Files:**
- Modify: `cogcoder/r253_external_cognition.py`
- Test: `tests/test_r253_external_cognition.py`

**Interfaces:**
- Produces: `CognitiveOperatorSpec`, `CognitiveOperatorRegistry`, `ProcedureCard`, `ProcedureLibrary`, `CompiledProcedure`, `ProcedureCompiler`.

- [ ] Write RED tests for operator registration collisions, capability/precondition validation, provenance digest verification, risk/cost budgets, unregistered step rejection, and arbitrary-code fields being absent from the procedure contract.
- [ ] Implement operator registry, procedure retrieval/ranking, and safe compiler.
- [ ] Run focused tests to GREEN.

### Task 4: External state, counterexample memory, and credit

**Files:**
- Modify: `cogcoder/r253_external_cognition.py`
- Test: `tests/test_r253_external_cognition.py`

**Interfaces:**
- Produces: `ExternalWorkingState`, `EpisodeRecord`, `EpisodeMemory`, `CounterexampleRecord`, `CounterexampleMemory`, `ProcedureCreditLedger`.

- [ ] Write RED tests proving prior falsified procedure/context pairs are surfaced and successful procedures improve posterior competence without weight updates.
- [ ] Implement bounded searchable memories and beta-style credit.
- [ ] Run focused tests to GREEN.

### Task 5: Reflex router and interleaved procedure execution

**Files:**
- Modify: `cogcoder/r253_external_cognition.py`
- Test: `tests/test_r253_external_cognition.py`

**Interfaces:**
- Produces: `OperatorExecutionResult`, `ReflexReceipt`, `CognitiveReflexRouter`, `CognitiveReflexRuntime.run_cycle()`.

- [ ] Write RED tests for cost/risk/value routing, repetition penalty, verifier-required procedures, state-patch integration, fail-closed behavior, and counterexample quarantine.
- [ ] Implement router and runtime loop.
- [ ] Run focused tests to GREEN.

### Task 6: Frozen external cognitive reflex benchmark

**Files:**
- Create: `benchmarks/kfigg/r253_external_cognitive_reflex.py`
- Create: `tests/test_r253_external_cognitive_reflex_benchmark.py`

**Interfaces:**
- Produces: `run_frozen_heldout()`.

- [ ] Write a failing benchmark gate before implementing benchmark helpers.
- [ ] Build opaque multi-stage episodes with distractor cards and adversarially high self-confidence.
- [ ] Add no-reflex, self-confidence-only, and retrieve-once baselines.
- [ ] Require interleaved runtime to acquire different procedures mid-trajectory and avoid repeated counterexamples.
- [ ] Freeze result JSON only after exact local recomputation.

### Task 7: Regression, CI, World audit, and release evidence

**Files:**
- Create: `research/R2_53_PHASE_A_RESULT.json`
- Create: `.github/workflows/r253-external-cognitive-reflex.yml`
- Later create after clean CI: `R2_53_DELIVERY.md`, `R2_53_RELEASE_MANIFEST.json`, `research/R2_53_VERIFY_RESULT.json`, `R2_52_TO_R2_53_EVOLUTION.md`.

**Interfaces:**
- Consumes: all R2.53 capability files.

- [ ] Run R2.53 focused tests locally.
- [ ] Run R2.52-R2.41 regression in bounded groups.
- [ ] Push byte-exact candidate to GitHub and run Python 3.11/3.13 focused CI plus parent regression.
- [ ] Run Nolane World W5 adversarial audit with explicit unresolved frontiers.
- [ ] Freeze release evidence only after clean hosted verification.
- [ ] Create complete repository ZIP from GitHub release HEAD, verify SHA-256 and archive integrity, persist ZIP/evidence to Library.
