# Coding Organization Part V Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the seven persistent core-coding identities into a governed engineering region with deterministic routing, safe source claims, patch provenance, evidence readiness and direct Coding-Chief work.

**Architecture:** Add a focused `CodingControlPlane` beside TaskGraph/Planning/Architecture/Integration. Task leases remain task authority; code claims prevent concurrent source mutation; patch candidates are evidence-bearing objects and cannot self-certify verification.

**Tech Stack:** Python standard library/dataclasses/enums, existing `cogcoder.organization`, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-22-coding-organization-part5-design.md`

## Global Constraints

- Seven persistent core-coding identities from the accepted 67-agent blueprint.
- All retain universal cognitive floor, learning capability, private memory/skills/self-models and <100M physical parameters.
- Coding Chief remains a direct worker.
- Code claims do not grant Plan/Architecture authority.
- Overlapping exclusive source claims fail atomically.
- Patches cannot self-certify verification or merge themselves.
- Stale architecture/plan and missing compile/test/verifier evidence block readiness.
- Existing Parts I–IV state/evidence authority remains canonical.

---

### Task 1: Coding profiles and deterministic router

**Files:**
- Create: `cogcoder/organization/coding_profiles.py`
- Test: `tests/test_coding_agi_coding_profiles.py`

- [ ] RED: exactly seven profiles derived from `core-coding`; all learning/direct-work capable as declared; profiles have non-identical specialization domains.
- [ ] RED: backend/service work routes to Backend Coder; low-level/concurrency work routes to Systems Coder; cross-system high-complexity work can route to Coding Chief.
- [ ] RED: same request/state produces identical ranked candidates/receipt digest.
- [ ] Implement `CodingDomain`, `CodingProfile`, `CodingWorkRequest`, `CodingAssignmentReceipt`, `CodingProfileRegistry.route`.
- [ ] Require focused PASS.

---

### Task 2: CodeClaimLedger

**Files:**
- Create: `cogcoder/organization/code_claims.py`
- Test: `tests/test_coding_agi_code_claims.py`

- [ ] RED: normalized disjoint file claims coexist.
- [ ] RED: overlapping exclusive path/symbol claims from different active agents fail with no partial mutation.
- [ ] RED: release/abort preserves history and removes active conflict.
- [ ] Implement `ClaimMode`, `ClaimStatus`, `CodeClaim`, `CodeClaimLedger` with canonical counters/state.
- [ ] Require focused PASS.

---

### Task 3: Patch and tool provenance

**Files:**
- Create: `cogcoder/organization/coding_patches.py`
- Test: `tests/test_coding_agi_coding_patches.py`

- [ ] RED: patch candidate references task/work, base plan/architecture versions, touched scopes and patch artifact.
- [ ] RED: touched files/symbols outside producer's active claims block readiness.
- [ ] RED: tool invocation receipts are content-addressed/provenance-bearing and survive restore.
- [ ] Implement `CodingPatchStatus`, `ToolInvocationReceipt`, `CodingPatchCandidate`, `CodingPatchLedger`.
- [ ] Require focused PASS.

---

### Task 4: Evidence readiness and feedback protocols

**Files:**
- Create: `cogcoder/organization/coding.py`
- Test: `tests/test_coding_agi_coding_readiness.py`
- Test: `tests/test_coding_agi_coding_feedback.py`

- [ ] RED: current task lease, plan version, architecture version, source claims, compile evidence, test evidence and independent verifier evidence are all required for readiness.
- [ ] RED: verifier identity equal to producer cannot independently authorize readiness.
- [ ] RED: false-accept/regression/failed evidence blocks readiness.
- [ ] RED: coder can emit existing plan-gap and architecture-concern events without changing authority.
- [ ] Implement `CodingReadinessReceipt` and `CodingControlPlane` using existing TaskGraph/Planning/Architecture/Verification/EventLedger stores.
- [ ] Require focused PASS.

---

### Task 5: Direct Chief, personal learning and restart

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Test: `tests/test_coding_agi_coding_direct_work.py`
- Test: `tests/test_coding_agi_coding_snapshot.py`
- Create: `.github/workflows/coding-agi-coding-part5.yml`

- [ ] RED: Coding Chief completes a leased implementation task through ordinary `chief_direct_work` with patch artifact provenance.
- [ ] RED: successful/failed coding episode can create a personal skill candidate but it remains candidate/personal until normal Part-I promotion.
- [ ] RED: profiles, requests, assignments, claims, patches and tool receipts round-trip exactly through `OrganizationSnapshot`.
- [ ] Integrate `runtime.coding` after Planning/Architecture stores and before Context/Central construction; preserve older snapshot defaults.
- [ ] Add Python 3.11/3.13 workflow for Part V plus Parts I–IV regressions.
- [ ] Capture RED before production code, then exact-head GREEN before merge.

## Self-review

- Every Issue #133 acceptance gate maps to a testable task.
- No neural coding competence is inferred from role names or tool availability.
- No TODO/TBD placeholders.
- UI/frontend coding remains Part VII; debugging specialization remains Part VI; independent full Verification/Security remains Part VIII.
