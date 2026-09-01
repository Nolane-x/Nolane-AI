# E. Acting End-to-End Proof Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close E. Acting proof continuity across exact external-core contract identity, workspace execution epochs, transactional dispatch, concrete receipts, persisted step receipts, and restart projection.

**Architecture:** Add two orthogonal proof axes: `core_contract_digest` binds an external invocation to the exact `ExternalCoreSpec`, while `workspace_epoch_id` binds dispatch/checkpoint/receipt/projection to one exclusive execution epoch of a `RepositoryWorkspace`. Modern execution-control sessions pin the registry digest + workspace epoch; historical state stays loadable but cannot gain modern forward authority by omission.

**Tech Stack:** Python 3.11/3.13, dataclasses, canonical SHA-style digests via `nolane.core.canonical_digest`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-31-e-acting-proof-continuity-design.md`

## Global Constraints

- Nolane World is a reasoning input only; no Nolane World runtime import or schema dependency.
- E does not acquire planning, candidate-selection, strategic-authorization, or policy ownership.
- No durable restoration of process-local workspace checkpoints.
- No distributed workspace lock service.
- No fake `ExternalCoreSpec` rows for built-in canonical tools.
- A changed external-core registry requires a new modern execution session; no silent mid-session migration.
- Historical records remain loadable where possible but cannot become proof-v2 forward execution authority.
- Every authority check occurs before concrete side effects or recovery ledger mutation.

---

### Task 1: Establish RED workspace-epoch contracts

**Files:**
- Create: `tests/test_refoundation_acting_workspace_epochs.py`
- Modify: `.github/workflows/refoundation-e-acting.yml`

**Interfaces:**
- Consumes: current `RepositoryWorkspace.checkpoint()`, `restore()`, `release_checkpoint()`, `OrganizationExecutionControlPlane.start()`.
- Produces test requirements for `RepositoryWorkspace.claim_execution_epoch(owner_id) -> str`, `active_execution_epoch_id`, and epoch-bound `WorkspaceCheckpoint`.

- [ ] **Step 1: Write failing epoch ownership tests**

```python
def test_workspace_rejects_second_live_execution_epoch_owner(tmp_path):
    workspace = _repository_workspace(tmp_path)
    first = workspace.claim_execution_epoch("execution-00000001")
    assert first
    with pytest.raises(PermissionError, match="execution epoch"):
        workspace.claim_execution_epoch("execution-00000002")
```

Add a control-plane test proving two `start()` calls cannot share one live workspace object.

- [ ] **Step 2: Write failing stale-checkpoint test**

```python
def test_checkpoint_from_released_epoch_cannot_restore_in_new_epoch(tmp_path):
    workspace = _repository_workspace(tmp_path)
    epoch_a = workspace.claim_execution_epoch("execution-a")
    checkpoint = workspace.checkpoint(label="epoch-a")
    workspace.release_execution_epoch("execution-a", epoch_a)
    workspace.claim_execution_epoch("execution-b")
    with pytest.raises(PermissionError, match="checkpoint.*epoch"):
        workspace.restore(checkpoint)
```

- [ ] **Step 3: Run RED tests**

Run:

```bash
python -m pytest -q tests/test_refoundation_acting_workspace_epochs.py
```

Expected: failures because epoch APIs/fields do not exist and concurrent workspace ownership is currently accepted.

- [ ] **Step 4: Add new test file to permanent E workflow**

Append `tests/test_refoundation_acting_workspace_epochs.py` to the explicit transactional contract invocation in `.github/workflows/refoundation-e-acting.yml`.

- [ ] **Step 5: Commit RED evidence**

```bash
git add tests/test_refoundation_acting_workspace_epochs.py .github/workflows/refoundation-e-acting.yml
git commit -m "test(e-acting): expose workspace epoch authority gap"
```

---

### Task 2: Implement workspace execution epochs and checkpoint fencing

**Files:**
- Modify: `nolane/external_core/execution_workspace.py`
- Test: `tests/test_refoundation_acting_workspace.py`
- Test: `tests/test_refoundation_acting_workspace_epochs.py`

**Interfaces:**
- Produces:
  - `RepositoryWorkspace.claim_execution_epoch(owner_id: str, *, expected_epoch_id: str | None = None) -> str`
  - `RepositoryWorkspace.release_execution_epoch(owner_id: str, workspace_epoch_id: str) -> None`
  - `RepositoryWorkspace.active_execution_epoch_id -> str | None`
  - `WorkspaceCheckpoint.workspace_epoch_id: str`
  - `WorkspaceCheckpoint.checkpoint_generation: int`

- [ ] **Step 1: Add epoch state to `RepositoryWorkspace.__init__`**

```python
self._execution_epoch_generation = 0
self._active_execution_epoch_id: str | None = None
self._active_execution_epoch_owner: str | None = None
self._checkpoint_generations: dict[Path, tuple[str, int]] = {}
```

- [ ] **Step 2: Implement epoch claim/release**

Epoch ids are deterministic over workspace identity, generation, and owner:

```python
digest = canonical_digest({
    "workspace_root": str(self.root),
    "base_revision": self.base_revision,
    "generation": self._execution_epoch_generation,
    "owner_id": owner,
})
epoch_id = "workspace-epoch-" + digest[:24]
```

`expected_epoch_id` is used by restore/reattach: if no epoch is active, claim only when the newly generated epoch equals the expected persisted epoch; otherwise fail closed. Reclaim by the same owner returns the active id. A different owner raises `PermissionError`.

- [ ] **Step 3: Fence checkpoints**

`checkpoint()` must reject when no active epoch exists. Include epoch id and per-epoch checkpoint generation in checkpoint digest and dataclass fields. `_validate_checkpoint()` must reject an epoch mismatch before examining restore payload.

- [ ] **Step 4: Invalidate epoch/checkpoint authority on release/close**

Release removes remaining checkpoint snapshots for that epoch and clears active owner/id. `close()` clears epoch state after snapshot/worktree cleanup.

- [ ] **Step 5: Run targeted workspace tests**

```bash
python -m pytest -q \
  tests/test_refoundation_acting_workspace.py \
  tests/test_refoundation_acting_workspace_epochs.py \
  tests/test_refoundation_acting_workspace_fencing.py
```

Expected: PASS.

- [ ] **Step 6: Commit workspace primitive**

```bash
git add nolane/external_core/execution_workspace.py tests/test_refoundation_acting_workspace_epochs.py
git commit -m "feat(e-acting): fence workspace rollback by execution epoch"
```

---

### Task 3: Establish RED core-contract proof tests

**Files:**
- Create: `tests/test_refoundation_acting_core_proof_continuity.py`
- Modify: `.github/workflows/refoundation-e-acting.yml`

**Interfaces:**
- Consumes: `ExternalCoreSpec.contract_digest`, `ExternalCoreExecutor`, `TransactionalExternalCoreExecutor`.
- Produces test requirements for `core_contract_digest` + `workspace_epoch_id` on contracts and receipts.

- [ ] **Step 1: Write failing external-core receipt test**

Construct two specs with the same `core_id` but different version/capability contract. Invoke under spec A and assert the receipt exposes spec A’s digest.

```python
assert receipt.core_contract_digest == spec_a.contract_digest
assert receipt.workspace_epoch_id == workspace.active_execution_epoch_id
```

Old code fails because the fields do not exist.

- [ ] **Step 2: Write substituted-receipt tests**

Create a fake core executor returning a receipt with correct action/workspace digests but wrong `core_contract_digest`, then wrong `workspace_epoch_id`. `TransactionalExternalCoreExecutor.invoke()` must reject before commit.

- [ ] **Step 3: Write registry-drift session test**

Persist a modern session under registry A, restore the control plane with registry B whose digest differs, and assert restoration/reattach/forward execution fails closed.

- [ ] **Step 4: Run RED tests**

```bash
python -m pytest -q tests/test_refoundation_acting_core_proof_continuity.py
```

Expected: FAIL on absent fields / absent registry fence checks.

- [ ] **Step 5: Add test to permanent E workflow and commit**

```bash
git add tests/test_refoundation_acting_core_proof_continuity.py .github/workflows/refoundation-e-acting.yml
git commit -m "test(e-acting): expose core contract proof gap"
```

---

### Task 4: Bind concrete core receipts to core contract + workspace epoch

**Files:**
- Modify: `nolane/external_core/execution_executor.py`
- Modify: `nolane/external_core/invokable.py`
- Test: `tests/test_refoundation_acting_core_proof_continuity.py`
- Test: existing execution-executor Refoundation tests selected by `tests/test_refoundation_*.py`

**Interfaces:**
- `ExternalCoreExecutor.invoke(..., core_contract_digest: str = "", workspace_epoch_id: str = "") -> CoreInvocationReceipt`
- `CoreInvocationReceipt.core_contract_digest: str`
- `CoreInvocationReceipt.workspace_epoch_id: str`

- [ ] **Step 1: Extend `CoreInvocationReceipt` compatibility shape**

New receipts include the two proof fields in `payload()` and digest. `from_state()` uses empty-string defaults for historical receipts so old serialized rows remain loadable.

- [ ] **Step 2: Add per-core digest resolver**

In `ExternalCoreExecutor`:

```python
def core_contract_digest(self, tool_id: str) -> str:
    if tool_id not in self.external_core_ids:
        return ""
    return self.external_cores.get(tool_id).contract_digest
```

- [ ] **Step 3: Validate expected proof before dispatch**

For external cores, expected digest must be non-empty and equal current spec digest. For built-ins, expected digest must be empty. `workspace_epoch_id` must equal `workspace.active_execution_epoch_id` and be non-empty for modern transactional execution.

- [ ] **Step 4: Persist proof fields on success and failure receipts**

Thread both fields through `_failure()` and `_persist()` so failures cannot escape the same proof chain.

- [ ] **Step 5: Run core proof + executor tests**

```bash
python -m pytest -q \
  tests/test_refoundation_acting_core_proof_continuity.py \
  tests/test_refoundation_acting_runtime.py \
  tests/test_refoundation_acting_receipt_provenance.py
```

- [ ] **Step 6: Commit concrete receipt proof**

```bash
git add nolane/external_core/invokable.py nolane/external_core/execution_executor.py tests/test_refoundation_acting_core_proof_continuity.py
git commit -m "feat(e-acting): bind core receipts to versioned execution proof"
```

---

### Task 5: Extend acting contracts and transactional validation

**Files:**
- Modify: `nolane/external_core/acting_protocol.py`
- Modify: `nolane/external_core/acting_runtime.py`
- Test: `tests/test_refoundation_acting_protocol.py`
- Test: `tests/test_refoundation_acting_runtime.py`
- Test: `tests/test_refoundation_acting_receipt_provenance.py`
- Test: `tests/test_refoundation_acting_core_proof_continuity.py`

**Interfaces:**
- `ExecutionContract.core_contract_digest: str = ""`
- `ExecutionContract.workspace_epoch_id: str = ""`
- `TransactionalExternalCoreExecutor.invoke(..., core_contract_digest: str, workspace_epoch_id: str, ...)`

- [ ] **Step 1: Put proof fields into contract semantic identity**

Add both fields to `ExecutionContract.semantic_payload()`, `to_state()`, and `from_state()` with historical empty defaults. This makes idempotency conflict detection sensitive to core-version/epoch substitution.

- [ ] **Step 2: Require modern epoch at transactional dispatch**

`TransactionalExternalCoreExecutor.invoke()` rejects blank/mismatching `workspace_epoch_id` before `protocol.propose()`. It does not require an external-core digest for canonical built-ins.

- [ ] **Step 3: Forward proof context into concrete executor**

```python
receipt = self.executor.invoke(
    ...,
    core_contract_digest=contract.core_contract_digest,
    workspace_epoch_id=contract.workspace_epoch_id,
)
```

- [ ] **Step 4: Extend `_validate_core_receipt()`**

Expected provenance includes `core_contract_digest` and `workspace_epoch_id` in addition to agent/task/tool/operation/input/before/after/authorization.

- [ ] **Step 5: Run protocol/runtime suites**

```bash
python -m pytest -q \
  tests/test_refoundation_acting_protocol.py \
  tests/test_refoundation_acting_runtime.py \
  tests/test_refoundation_acting_receipt_provenance.py \
  tests/test_refoundation_acting_core_proof_continuity.py
```

- [ ] **Step 6: Commit transactional proof closure**

```bash
git add nolane/external_core/acting_protocol.py nolane/external_core/acting_runtime.py tests/test_refoundation_acting_*.py
git commit -m "feat(e-acting): carry core and epoch proof through acting contract"
```

---

### Task 6: Close Execution Control session/step/recovery proof chain

**Files:**
- Modify: `nolane/external_core/execution.py`
- Test: `tests/test_refoundation_acting_workspace_fencing.py`
- Test: `tests/test_refoundation_acting_control_provenance.py`
- Test: `tests/test_refoundation_acting_control_commit_projection.py`
- Test: `tests/test_refoundation_acting_control_reconciliation.py`
- Test: `tests/test_refoundation_acting_core_proof_continuity.py`
- Test: `tests/test_refoundation_acting_workspace_epochs.py`

**Interfaces:**
- `ExecutionSession.execution_proof_version: int = 1`
- `ExecutionSession.external_core_registry_digest: str | None = None`
- `ExecutionSession.workspace_epoch_id: str | None = None`
- `ExecutionStepReceipt.core_contract_digest: str = ""`
- `ExecutionStepReceipt.workspace_epoch_id: str = ""`

- [ ] **Step 1: Add proof-v2 session validation/serialization**

Version 1 keeps historical compatibility. Version 2 requires non-empty registry digest + workspace epoch and existing workspace-provenance-v2 fields. Field stripping from a v2 record must raise rather than downgrade.

- [ ] **Step 2: Claim/release workspace epoch atomically**

`start()` computes the next session id, claims the workspace using that id, builds the session with proof-v2 fields, and releases on construction failure. `_terminal()` releases the session epoch only after the terminal/session update succeeds.

- [ ] **Step 3: Validate registry + epoch on attach and step**

Modern attach/step requires:

```python
self.external_cores.contract_digest == session.external_core_registry_digest
workspace.active_execution_epoch_id == session.workspace_epoch_id
```

`attach_workspace()` claims the persisted epoch for the session and rejects other live owners.

- [ ] **Step 4: Resolve per-action core digest and dispatch proof**

For externally registered tools use `self.external_cores.get(tool_id).contract_digest`; built-ins use `""`. Pass core digest + session epoch into `acting_executor.invoke()`.

- [ ] **Step 5: Add step receipt proof fields**

`ExecutionStepReceipt.create()` includes both fields in the payload/digest. `_validate_state()` checks modern steps against session epoch and, where applicable, core receipt/core contract identity.

- [ ] **Step 6: Strengthen recovery global preflight**

Before any acting mutation or committed projection, require acting contract/session/core receipt agreement on workspace epoch and core contract digest. Registry drift prevents restoration of RUNNING authority.

- [ ] **Step 7: Run control-plane targeted suites**

```bash
python -m pytest -q \
  tests/test_refoundation_acting_workspace_epochs.py \
  tests/test_refoundation_acting_workspace_fencing.py \
  tests/test_refoundation_acting_core_proof_continuity.py \
  tests/test_refoundation_acting_control_provenance.py \
  tests/test_refoundation_acting_control_commit_projection.py \
  tests/test_refoundation_acting_control_reconciliation.py
```

- [ ] **Step 8: Commit control-plane proof closure**

```bash
git add nolane/external_core/execution.py tests/test_refoundation_acting_*.py
git commit -m "feat(e-acting): close end-to-end execution proof chain"
```

---

### Task 7: Version, document, and permanently gate the new authority model

**Files:**
- Modify: `nolane/external_core/invokable.py`
- Modify: `nolane/external_core/execution_workspace.py`
- Modify: `nolane/external_core/execution_executor.py`
- Modify: `nolane/external_core/acting_protocol.py`
- Modify: `nolane/external_core/acting_runtime.py`
- Modify: `nolane/external_core/execution.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify: `tests/test_refoundation_component_versions.py`
- Modify: `tests/test_refoundation_wave5r_native_invokable_cores.py`
- Modify: `tests/test_refoundation_wave5s_native_execution_workspace.py`
- Modify: `tests/test_refoundation_wave5aa_native_execution_control.py`
- Modify: `CURRENT/E_ACTING.md`
- Modify: `.github/workflows/refoundation-e-acting.yml`

**Interfaces:**
- Publishes component versions from the spec and canonical documentation invariants.

- [ ] **Step 1: Update component versions**

Set:

```text
external.invokable_cores       0.0.3
external.execution.workspace   0.0.4
external.execution.executor    0.0.2
external.acting.protocol       0.1.5
external.acting.runtime        0.1.5
external.execution.control     0.0.8
```

Update metadata revision counters for component-version-managed components.

- [ ] **Step 2: Update `CURRENT/E_ACTING.md`**

Document exact new invariants: registry/session fence, per-core digest, workspace epoch exclusivity, stale-checkpoint rejection, acting/core/step proof agreement, legacy no-upgrade rule.

- [ ] **Step 3: Run component/version contracts**

```bash
python -m pytest -q \
  tests/test_refoundation_component_versions.py \
  tests/test_refoundation_wave5r_native_invokable_cores.py \
  tests/test_refoundation_wave5s_native_execution_workspace.py \
  tests/test_refoundation_wave5aa_native_execution_control.py
```

- [ ] **Step 4: Commit version/documentation closure**

```bash
git add CURRENT/E_ACTING.md nolane/metadata/component_versions.py nolane/external_core tests/test_refoundation_* .github/workflows/refoundation-e-acting.yml
git commit -m "docs(e-acting): canonize proof-continuity authority"
```

---

### Task 8: Hosted acceptance, integration, and cleanup

**Files:**
- No temporary patch generators in final tree.
- Permanent workflows only.

**Interfaces:**
- Produces exact tested feature head and exact latest-main integration head.

- [ ] **Step 1: Compile canonical E modules**

```bash
python -m py_compile nolane/external_core/*.py
```

Expected: PASS.

- [ ] **Step 2: Run all E Acting contracts**

```bash
python -m pytest -q tests/test_refoundation_acting_*.py
```

Expected: PASS.

- [ ] **Step 3: Run full Refoundation suite**

```bash
python -m pytest -q tests/test_refoundation_*.py
```

Expected: PASS.

- [ ] **Step 4: Verify diff hygiene**

```bash
git diff --check main...HEAD
```

Expected: no output.

- [ ] **Step 5: Push exact branch head and require hosted Python 3.11 + 3.13 workflow success**

Both `Refoundation E Acting Transactional Runtime` and the branch final-verification gate must be green on the exact head.

- [ ] **Step 6: Race-check latest `main`**

If `main` moved, build/test the synthetic integration commit over that exact new head. Do not reuse stale acceptance evidence.

- [ ] **Step 7: Inspect final changed-file set**

Reject temporary scripts, patch artifacts, unrelated specialist files, or accidental capability deletion.

- [ ] **Step 8: Merge only the exact accepted integration head**

Use expected-head/race guards. Never force-update `main` to an untested tree.

- [ ] **Step 9: Post-merge verify**

Confirm actual `main` SHA/tree, PR merged state, permanent workflows, and absence of temporary scaffolding.
