# Debugging Organization Part VI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the six persistent debugging identities into an evidence-bearing failure-intelligence organization with deterministic routing, reproducible cases, hypothesis governance, dedicated concurrency/regression evidence and verified Coding Part-V handoff.

**Architecture:** Add focused DebugProfile, DebugCase/Evidence/Hypothesis ledgers and a `DebugControlPlane` beside the Coding control plane. Debugging owns failure truth/provenance; Coding owns patch execution; Verification evidence remains independent.

**Tech Stack:** Python standard library/dataclasses/enums, existing `cogcoder.organization`, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-22-debugging-organization-part6-design.md`

## Global Constraints

- Exactly six persistent `debugging-failure` identities from the accepted blueprint.
- Debug Chief remains a direct technical worker.
- Rejected hypotheses are immutable negative knowledge, not current truth.
- Concurrency root causes require concurrency-specific evidence.
- Regression root causes require bisect/regression evidence.
- Debugging cannot bypass Part-V CodeClaim/Patch/Readiness rules.
- No source merge or AGI/frontier claim is authorized by this Part.
- Existing Parts I–V authority and snapshots remain compatible.

---

### Task 1: Debug profiles and routing

**Files:**
- Create: `cogcoder/organization/debug_profiles.py`
- Test: `tests/test_coding_agi_debug_profiles.py`

- [ ] RED: derive exactly six debugging profiles from the registry; all remain learning/direct-work capable and keep universal cognitive floor.
- [ ] RED: reproduction, runtime-trace, static-root-cause, concurrency-state, regression-bisect and cross-failure requests route to their intended identities deterministically.
- [ ] Implement `DebugDomain`, `DebugProfile`, `DebugWorkRequest`, `DebugAssignmentReceipt`, `DebugProfileRegistry`.
- [ ] Require focused PASS.

---

### Task 2: Failure cases, reproduction and evidence timeline

**Files:**
- Create: `cogcoder/organization/debug_evidence.py`
- Test: `tests/test_coding_agi_debug_evidence.py`

- [ ] RED: opening a case preserves reporter/symptom/scope/evidence; duplicate case rebinding fails.
- [ ] RED: nondeterministic reproduction receipt is preserved but case remains OPEN; deterministic reproduction advances to REPRODUCED.
- [ ] RED: evidence artifacts append in logical sequence and round-trip exactly.
- [ ] Implement `FailureClass`, `DebugCaseStatus`, `FailureCase`, `ReproductionReceipt`, `DebugEvidenceKind`, `DebugEvidenceArtifact`, `DebugEvidenceLedger`.
- [ ] Require focused PASS.

---

### Task 3: Hypothesis lifecycle and specialist evidence gates

**Files:**
- Create: `cogcoder/organization/debug_hypotheses.py`
- Test: `tests/test_coding_agi_debug_hypotheses.py`
- Test: `tests/test_coding_agi_debug_concurrency_regression.py`

- [ ] RED: competing hypotheses coexist; rejecting one preserves it and refutation evidence.
- [ ] RED: rejected hypothesis cannot be accepted in place; only one accepted root cause is current.
- [ ] RED: acceptance requires Debug Chief, deterministic reproduction and supporting evidence.
- [ ] RED: concurrency case without `CONCURRENCY_TRACE` is rejected; regression case without `BISECT` is rejected.
- [ ] Implement `HypothesisStatus`, `DebugHypothesis`, `DebugHypothesisLedger` and acceptance gates.
- [ ] Require focused PASS.

---

### Task 4: Coding handoff and verified resolution

**Files:**
- Create: `cogcoder/organization/debugging.py`
- Test: `tests/test_coding_agi_debug_coding_handoff.py`

- [ ] RED: accepted root cause creates a `DebugPatchHandoff` through existing `runtime.coding.request_work` and stores assignment digest.
- [ ] RED: wrong work/task/patch or non-ready Coding receipt cannot resolve a case.
- [ ] RED: valid Part-V patch + independent ready receipt produces `DebugResolutionReceipt` and marks case RESOLVED.
- [ ] Implement `DebugPatchHandoff`, `DebugResolutionReceipt`, `DebugControlPlane` orchestration.
- [ ] Require focused PASS with Part-V coding tests.

---

### Task 5: Direct Debug Chief, personal learning, snapshot/context and CI

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Modify: `cogcoder/organization/context.py`
- Test: `tests/test_coding_agi_debug_direct_work.py`
- Test: `tests/test_coding_agi_debug_snapshot.py`
- Test: `tests/test_coding_agi_debug_context.py`
- Create: `.github/workflows/coding-agi-debugging-part6.yml`

- [ ] RED: Debug Chief directly owns a difficult debug task, records reproduction/evidence/root cause and completes through ordinary `chief_direct_work`.
- [ ] RED: resolution may propose a personal skill candidate but remains Part-I `CANDIDATE` until governed promotion.
- [ ] RED: full debugging state round-trips exactly through `OrganizationSnapshot`.
- [ ] RED: debugging agent wake capsule contains `debugging-state` digest and relevant event delta; non-debug agents do not receive full debug state by default.
- [ ] Integrate `runtime.debugging` after Coding and before Context/Central; old snapshots default to empty debugging state.
- [ ] Add Python 3.11/3.13 workflow running Part VI plus Parts I–V organization regressions.
- [ ] Capture RED before production code and exact-head GREEN before merge.

## Self-review

- Every Issue #134 acceptance gate maps to a contract.
- Reproduction, evidence, hypotheses and Coding patch authority remain separate.
- Concurrency and regression have explicit specialist evidence gates, not role-name-only distinction.
- No TODO/TBD placeholders.
- Debug skill learning reuses Part-I evidence-gated promotion instead of bypassing it.
