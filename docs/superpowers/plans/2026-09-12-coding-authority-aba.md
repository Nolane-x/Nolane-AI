# ABA-Safe Coding Request Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a stale Neural execution decision from surviving a reversible `coding-state` A→B→A routing mutation during inference.

**Architecture:** Add one monotonic assignment-authority revision at the `CodingControlPlane` state owner. Fold it into the existing canonical coding semantic state so `ContextCapsule.authoritative_artifacts`, `ContextCompilationReceipt`, request cognition, and the post-inference context fence remain the only authority path. Preserve legacy snapshot readability and concrete `UICodingControlPlane` restore.

**Tech Stack:** Python 3.11/3.13, pytest, immutable dataclasses, canonical JSON/digests, GitHub Actions, repository component-version discipline.

**Spec:** `docs/superpowers/specs/2026-09-12-coding-authority-aba-design.md`

## Global Constraints

- Base is `main@96b7d6984e7ecbc25408d5728530c16f54f78883` unless main advances before merge.
- Strict RED before production behavior changes.
- No new `InferenceRequest`, `AgentDecisionReceipt`, execution-session, `ContextCapsule`, or `ContextCompilationReceipt` field.
- No event-ledger digest in request authority.
- No execution-only coding authority fence unless the canonical-state design is falsified.
- Legacy snapshots without `assignment_authority_revision` restore with revision `0`.
- Public execution/integration protocol versions remain unchanged unless executable repository discipline proves otherwise.
- Frozen Neural R2.3 artifacts remain untouched.

---

### Task 1: Prove the reversible coding-authority gap

**Files:**
- Modify: `tests/test_execution_post_inference_context_frontier_authority.py`

**Interfaces:**
- Consumes: `OrganizationRuntime.first_generation()`, `CodingWorkRequest`, `CodingDomain`, `runtime.coding.request_work(...)`, existing execution/context authority stack.
- Produces: one adversarial regression proving A→B→A can currently restore the exact request-time coding digest and let a stale WAIT decision persist.

- [ ] **Step 1: Add imports for canonical coding work routing**

Add:

```python
from nolane.external_core.coding_profiles import CodingDomain, CodingWorkRequest
```

- [ ] **Step 2: Add a helper that constructs one stable work request**

Use a fixed `work_id`, the execution task id, its `plan_node_id`, current architecture/plan versions, `CodingDomain.CROSS_SYSTEM`, requester `coding.chief`, and one evidence ref. Keep the same request object for all three routing operations.

- [ ] **Step 3: Write the failing execution regression**

The test must:

```python
runtime = OrganizationRuntime.first_generation()
identity = runtime.registry.get('coding.chief')
# create + lease task, create workspace
# request_work(... A='coding.chief', actor='nolane.central')
initial_digest = runtime.coding.digest

class _CodingABABackend:
    def decide(self, request):
        runtime.coding.request_work(work, override_agent_id='coding.backend.01', override_actor_id='nolane.central')
        assert runtime.coding.digest != initial_digest
        runtime.coding.request_work(work, override_agent_id='coding.chief', override_actor_id='nolane.central')
        assert runtime.coding.digest == initial_digest  # expected on unpatched RED base
        return AgentDecisionReceipt.create(... ExecutionAction.wait(...))

with pytest.raises(PermissionError, match='context.*authority|authority.*artifact|coding'):
    runtime.execution.step(session.session_id)
```

After rejection, assert no decision/session/task/workspace projection changed. The first RED must fail specifically because no `PermissionError` is raised, not because setup or routing is invalid.

- [ ] **Step 4: Run hosted focused RED on both supported Python versions**

Trigger the existing `Neural R2.4 Execution Result Projection` workflow on the test-only branch head. Require the new ABA test to be the only new failure and inspect both Python 3.11 and 3.13 logs.

- [ ] **Step 5: Commit the test-only RED**

Commit message:

```text
test(neural): reject coding authority ABA during inference
```

Do not add production behavior in this commit.

---

### Task 2: Add the minimal temporal witness at the coding state owner

**Files:**
- Modify: `nolane/external_core/coding.py`
- Modify: `nolane/external_core/ui_coding.py`
- Modify: `tests/test_execution_post_inference_context_frontier_authority.py`
- Test: relevant coding snapshot/control-plane tests discovered by repository test collection

**Interfaces:**
- Produces: `CodingControlPlane.assignment_authority_revision -> int`.
- Serialized key: `assignment_authority_revision` when positive.
- `request_work(...)` advances the revision only when `existing_assignment != new_receipt`.
- `CodingControlPlane.from_state(...)` consumes absent key as `0` and rejects negative values.
- `UICodingControlPlane.from_state(...)` passes the restored revision into the concrete constructor.

- [ ] **Step 1: Add failing revision-semantics assertions before production code**

Extend the regression or add a focused coding test requiring:

```text
initial revision = 0
first A assignment = 1
idempotent A assignment = 1
A -> B = 2
B -> A = 3
```

Also require `OrganizationRuntime.from_state(runtime.to_state()).coding.assignment_authority_revision == 3` and legacy restore without the key yields `0`.

- [ ] **Step 2: Verify these new assertions fail for the intended missing behavior**

Run the smallest direct coding test target. Expected failure is missing revision API/state, not fixture setup.

- [ ] **Step 3: Add revision storage and validation in `CodingControlPlane.__init__`**

Add parameter:

```python
assignment_authority_revision: int = 0
```

Normalize and reject negative values:

```python
revision = int(assignment_authority_revision)
if revision < 0:
    raise ValueError('coding assignment authority revision must be non-negative')
self._assignment_authority_revision = revision
```

Expose:

```python
@property
def assignment_authority_revision(self) -> int:
    return self._assignment_authority_revision
```

- [ ] **Step 4: Advance revision exactly on semantic assignment change**

In `request_work(...)`, after routing and before storing the receipt:

```python
if existing_assignment != receipt:
    self._assignment_authority_revision += 1
self._requests[request.work_id] = request
self._assignments[request.work_id] = receipt
```

The existing early idempotent return for no-override requests remains untouched. Explicit override A→A computes the same receipt and therefore does not advance.

- [ ] **Step 5: Bind the revision into canonical coding state**

In `to_state()`, build the existing state dict and add:

```python
if self._assignment_authority_revision:
    state['assignment_authority_revision'] = self._assignment_authority_revision
```

This keeps untouched legacy state byte-shape stable while making any positive revision part of `coding.digest`.

- [ ] **Step 6: Restore the revision canonically**

In `CodingControlPlane.from_state(...)`, parse:

```python
assignment_authority_revision = int(state.get('assignment_authority_revision', 0))
```

Pass it to `cls(...)`; constructor validation rejects negatives.

In `UICodingControlPlane.from_state(...)`, pass:

```python
assignment_authority_revision=base.assignment_authority_revision
```

when rebuilding the subclass.

- [ ] **Step 7: Update the adversarial digest expectation for GREEN**

After production behavior exists, the backend must assert:

```python
assert runtime.coding.digest != initial_digest
```

after B and again after the final A, because the final A value is now temporally distinct through revision `3`. The execution step must fail closed through the existing context-authority fence.

- [ ] **Step 8: Run focused GREEN**

Run the direct ABA regression, coding control-plane/snapshot tests, and `tests/test_execution_post_inference_context_frontier_authority.py` locally/hosted as available. Require no weakening of prior #373/#378 tests.

- [ ] **Step 9: Commit minimal production GREEN**

Commit message:

```text
fix(coding): make assignment authority ABA-safe
```

---

### Task 3: Prove persistence, compatibility, and ownership discipline

**Files:**
- Modify only files reported by executable version discipline after Task 2.
- Potential projection files must be discovered from the actual discipline output; do not pre-bump guessed owners.

**Interfaces:**
- Consumes: exact base `96b7d698...`, branch head after Task 2.
- Produces: clean `version_discipline_cli --check` and exact canonical component-version projections.

- [ ] **Step 1: Run executable version-discipline analysis**

Run:

```bash
python -m nolane.metadata.version_discipline_cli --base origin/main --head HEAD --json
python -m nolane.metadata.version_discipline_cli --base origin/main --head HEAD --check
```

Record every reported canonical owner and only those owners.

- [ ] **Step 2: Apply exact +1 revision/public-version changes required by the gate**

Update component constants, `nolane/metadata/component_versions.py`, and exact refoundation/projection sentinels surfaced by tests. Do not alter independent public execution/integration protocol versions unless a direct gate requires it.

- [ ] **Step 3: Run component projection tests and discipline again**

Require clean JSON findings and exit-zero `--check`.

- [ ] **Step 4: Commit version ownership closure**

Use a descriptive version-discipline commit; do not mix unrelated source changes.

---

### Task 4: Exact-head acceptance and guarded integration

**Files:**
- Update: PR body / issue #379 evidence only; no production changes unless a real regression is found.

**Interfaces:**
- Consumes: one final user-authored exact candidate SHA after all bot/helper commits.
- Produces: merged main commit with verified lineage and post-merge GREEN push workflows.

- [ ] **Step 1: Ensure no temporary helper workflow remains in the diff**

Audit the final PR diff and changed filenames.

- [ ] **Step 2: Trigger fresh exact-head acceptance**

At minimum require GREEN on the exact candidate for:

```text
External Core
Coding AGI Memory Context Intelligence Part XI
Memory Learning Substrate
Neural R2.4 Shared Core Acceptance
Neural R2.4 Runtime Cognition Activation
Neural R2.4 Execution Result Projection
Neural R2.4 Execution Decision Lineage
Refoundation E Acting Transactional Runtime
Nolane-AI Refoundation Epoch 0
R1.9 Integrity
R2.0i Integrity
```

Use broader bundle evidence only as supplemental. Historical frozen/baseline workflows must be classified by comparison, never silently ignored.

- [ ] **Step 3: Audit base drift and review state**

Re-fetch `main`, PR head, mergeability, changed files, reviews, and unresolved threads. If base advanced, reconcile and rerun affected exact-head gates.

- [ ] **Step 4: Update PR evidence and mark ready**

Document RED, surviving H2 architecture, revision semantics, version ownership, exact-head GREEN runs, and any baseline workflow classification.

- [ ] **Step 5: Guarded merge**

Merge only with `expected_head_sha=<exact verified candidate>`.

- [ ] **Step 6: Verify merge lineage and signature**

Require merge parents to be prior main + exact candidate, and GitHub commit verification to be valid.

- [ ] **Step 7: Verify every actual push workflow on the merge SHA**

Query all `event=push` runs for the merge SHA and require every triggered workflow to reach `completed/success`.

- [ ] **Step 8: Close evidence**

Post closure evidence to PR and #379, close #379 with reason `completed`, and only then call the change `integrated-complete`.
