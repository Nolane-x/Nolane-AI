# Same-Request Self-Model Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development while implementing this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject any execution decision produced from a ContextCapsule whose canonical self-model authority changed before the decision can be persisted, including ABA changes that restore the original self-model value.

**Architecture:** Preserve the existing layered execution-authority chain. Add one `execution_self_model_authority.py` layer above `execution_frontier_authority.py`; capture the self-model version embedded in the actual compiled ContextCapsule together with a per-agent monotonic self-model authority revision, then re-attest both after inference. Keep request/session serialization unchanged.

**Tech Stack:** Python 3.11/3.13, pytest, ContextVar, existing OrganizationRuntime execution authority stack.

**Spec:** Approved in-chat #372 design on 2026-09-11; this plan is the canonical implementation record for that bounded seam.

## Global Constraints

- TDD only: test-only RED must be observed before production code is written.
- Use only the canonical public mutation API `AgentRegistry.set_self_model_version()` in adversarial tests.
- Detect both direct drift (`V1 -> V2`) and ABA drift (`V1 -> V2 -> V1`).
- Reject before decision persistence or result projection.
- Do not modify `InferenceRequest`, execution-session serialization, or frozen neural metadata.
- Preserve prior #371 same-session execution-frontier behavior and all existing authority gates.
- Keep context-frontier snapshot-to-request hardening outside this change as the separate #373 candidate.

---

### Task 1: Prove the missing temporal authority with adversarial RED

**Files:**
- Modify: `tests/test_backend_binding_authority_revision.py`

**Interfaces:**
- Consumes: `OrganizationRuntime.first_generation()`, `AgentRegistry.set_self_model_version()`, `OrganizationExecutionControlPlane.step()`.
- Produces: permanent regressions proving direct and ABA self-model changes are rejected before persistence.

- [ ] **Step 1: Add direct-drift regression**

Create a backend whose `decide(request)` calls `runtime.registry.set_self_model_version(agent_id, changed_version)` and then returns a canonical WAIT receipt. Assert `runtime.execution.step()` raises `PermissionError`; execution state, task state, and workspace frontier must remain unchanged.

- [ ] **Step 2: Add ABA regression**

Create a backend whose `decide(request)` changes `V1 -> V2 -> V1` before returning WAIT. Assert the same pre-persistence rejection even though the final self-model value equals the request-time value.

- [ ] **Step 3: Verify RED on GitHub Actions**

Open/update the PR with test-only changes. `Neural R2.4 Execution Result Projection` must fail specifically because the new tests report `DID NOT RAISE PermissionError`; unrelated existing tests must remain green.

### Task 2: Add monotonic self-model authority revision

**Files:**
- Modify: `nolane/organization/identity.py`

**Interfaces:**
- Produces: `AgentRegistry.self_model_authority_revision(agent_id: str) -> int`.
- Mutation rule: `set_self_model_version()` increments the revision only when the normalized self-model value actually changes.

- [ ] **Step 1: Add per-agent revision storage initialized to zero on registration**

Use a private dictionary keyed by canonical agent id, mirroring the existing neural-version authority revision pattern.

- [ ] **Step 2: Increment only on semantic self-model changes**

`V1 -> V2 -> V1` must advance the revision twice; setting `V1 -> V1` must remain idempotent.

- [ ] **Step 3: Expose the revision through a validating getter**

The getter must first validate the agent exists and then return its current revision.

### Task 3: Bind the exact compiled ContextCapsule to post-inference authority

**Files:**
- Create: `nolane/external_core/execution_self_model_authority.py`
- Modify: `cogcoder/organization/runtime.py`

**Interfaces:**
- Consumes: `execution_frontier_authority.OrganizationExecutionControlPlane`, `AgentRegistry.self_model_authority_revision()`, `ContextCapsule.identity_summary`.
- Produces: top-level `OrganizationExecutionControlPlane` that rejects stale self-model authority before parent post-inference checks persist any decision.

- [ ] **Step 1: Scope request-time authority with ContextVar**

Wrap `step()` with a ContextVar reset boundary so nested/re-entrant steps restore the outer request's captured self-model authority.

- [ ] **Step 2: Capture from the actual compiled capsule**

Override `_compile_context_capsule()`: read revision before compilation, call `super()`, read revision after compilation, reject if the revision changed during compilation, extract `self_model_version` from `capsule.identity_summary`, require it to match the live registry value, and store `(version, revision)` in the ContextVar.

- [ ] **Step 3: Re-attest after inference**

Override `_attest_post_inference_task_authority(request)`. For lineage-v2 requests, require a captured authority tuple, compare the live self-model value to the capsule-bound value, then compare the live revision to the captured revision. Any mismatch raises `PermissionError`. Delegate to `super()` so #371 and earlier authority fences still run.

- [ ] **Step 4: Compose the new layer at the runtime root**

Change `cogcoder/organization/runtime.py` to import the execution control plane from `execution_self_model_authority` instead of `execution_frontier_authority`.

### Task 4: Verify GREEN and regressions

**Files:**
- No additional production files unless verification exposes a real defect in #372.

**Interfaces:**
- Produces: exact-head evidence suitable for guarded merge.

- [ ] **Step 1: Confirm both new adversarial tests pass**

`Neural R2.4 Execution Result Projection` must be GREEN on Python 3.11 and 3.13.

- [ ] **Step 2: Confirm prior neural-core gates remain green**

Require GREEN for External Core, Neural R2.4 Execution Decision Lineage, Coding AGI Organization Execution Bridge, Memory Learning Substrate, R1.9 Integrity, and R2.0i Integrity. Record unrelated frozen historical release-bundle failures separately rather than changing unrelated files.

- [ ] **Step 3: Review the final diff**

Verify the PR contains only the plan, adversarial regressions, self-model revision support, the new authority layer, and the runtime import change. No frozen protocol, schema, or unrelated refactor changes.

- [ ] **Step 4: Guarded merge**

Merge only with the exact verified PR head SHA and then confirm `main` advanced to the expected merge commit.