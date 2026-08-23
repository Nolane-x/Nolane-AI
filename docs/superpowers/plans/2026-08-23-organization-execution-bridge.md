# Organization Execution Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect persistent organization identities and compiled context to bounded inference, authorized repository tools, immutable execution receipts and the existing evaluation campaign ledger.

**Architecture:** Add a narrow execution layer outside the accepted Part-XV/Campaign runtime. Neural/model output remains a proposal; existing leases, code claims, authority, assurance and integration remain authoritative. R2.3 is loaded only from an explicitly supplied checkpoint whose SHA-256 matches frozen metadata.

**Tech Stack:** Python 3.11/3.13, stdlib dataclasses/pathlib/subprocess/hashlib/importlib, existing Nolane canonical digests, existing organization runtime/control planes, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-23-organization-execution-bridge-design.md`

## Global Constraints

- TDD RED must be observed before production bridge code.
- Do not modify accepted Neural R2.3/R2.69 frozen artifacts or parameter accounting.
- No shell-string execution and no path traversal outside an isolated workspace.
- No tool/core side effect without lease + permission; source writes also require code-claim coverage.
- No model output bypasses independent verification or merge authority.
- Historical runtime snapshots missing `execution` must still restore.
- Part XV remains sole capability/claim authority.

---

### Task 1: Canonical execution contracts and deterministic inference receipt

**Files:**
- Create: `cogcoder/organization/execution_types.py`
- Create: `cogcoder/organization/execution_inference.py`
- Test: `tests/test_coding_agi_execution_inference.py`

**Interfaces:**
- Produces `ExecutionActionKind`, `ToolAction`, `ExecutionBudget`, `ExecutionCounters`, `InferenceRequest`, `AgentDecisionReceipt`, `CognitiveStateEncoder`, `AgentInferenceBackend`, `DeterministicFixtureBackend`, `R23InferenceBackend`.

- [ ] Write tests asserting canonical round-trip/digest validation and identical fixture decisions for identical input.
- [ ] Run the bridge workflow and observe missing-module RED.
- [ ] Implement immutable contracts and canonical digest checks.
- [ ] Implement deterministic context/action encoding and fixture backend.
- [ ] Implement `R23InferenceBackend.from_checkpoint(...)` with SHA-256 verification before import/load; wrong or missing checkpoint must fail before any model code runs.
- [ ] Re-run focused tests.

### Task 2: Exact-revision isolated repository workspace

**Files:**
- Create: `cogcoder/organization/execution_workspace.py`
- Test: `tests/test_coding_agi_execution_workspace.py`

**Interfaces:**
- Produces `RepositoryWorkspace.create(...)`, `resolve_repo_path(...)`, `digest`, `read_text(...)`, `write_text(...)`, `run_argv(...)`, `close()`.

- [ ] Create a temporary Git repository fixture in the test and freeze an exact base commit.
- [ ] Assert source checkout remains unchanged while worktree mutation changes only workspace digest.
- [ ] Assert `../` and absolute path escape attempts fail closed.
- [ ] Implement `git worktree add --detach` creation, workspace digest and path guard.
- [ ] Re-run focused tests.

### Task 3: Permissioned ExternalCoreExecutor and failure receipts

**Files:**
- Create: `cogcoder/organization/execution_tools.py`
- Test: `tests/test_coding_agi_execution_tools.py`

**Interfaces:**
- Consumes `AgentRegistry`, `ExternalCoreRegistry`, `RepositoryWorkspace`, `ArtifactStore`, `CodingPatchLedger`.
- Produces `CoreInvocationReceipt`, `ExternalCoreExecutor.invoke(...)`, `register_handler(...)`.

- [ ] Test unauthorized core rejection with a persisted failure receipt.
- [ ] Test authorized filesystem read/write, terminal argv, git status, code search and registered region-core handler.
- [ ] Test timeout/failure preserves output/error evidence.
- [ ] Implement permission lookup from identity tool permissions/core bindings.
- [ ] Implement built-ins with fixed workspace cwd, timeout and output bound.
- [ ] Mirror tool receipts into existing coding patch ledger when available.

### Task 4: Source-write governance and code-claim enforcement

**Files:**
- Modify: `cogcoder/organization/execution_tools.py`
- Test: `tests/test_coding_agi_execution_code_claims.py`

**Interfaces:**
- Consumes existing `CodeClaimLedger.covers(...)` through `runtime.coding.claims`.

- [ ] Test coding write without exclusive coverage is rejected before filesystem mutation.
- [ ] Test same write succeeds after an active claim covers the file.
- [ ] Test a different agent's overlapping exclusive claim blocks the mutation.
- [ ] Implement mutation-scope extraction and pre-side-effect claim check.

### Task 5: Agent execution loop, budgets and Central stop semantics

**Files:**
- Create: `cogcoder/organization/execution.py`
- Test: `tests/test_coding_agi_execution_loop.py`
- Test: `tests/test_coding_agi_execution_central.py`

**Interfaces:**
- Produces `ExecutionState`, `ExecutionStepReceipt`, `ExecutionTerminalReceipt`, `OrganizationExecutionControlPlane`.
- Main method: `execute(agent_id, task_id, workspace, *, action_schema, budget) -> ExecutionTerminalReceipt`.

- [ ] Test lease is required.
- [ ] Test each step creates one decision receipt and at most one tool receipt.
- [ ] Test hard step/tool/core/compute limits fail closed.
- [ ] Test `COMPLETE` records output evidence but does not mark coding verification/merge.
- [ ] Test Coding Chief directly performs a source write under its own lease/claim.
- [ ] Test Central abort between decisions prevents the next side effect and yields aborted terminal state.
- [ ] Implement loop over existing context compiler/backend/executor without modifying governance semantics.

### Task 6: Runtime integration and restart without duplicate side effects

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Test: `tests/test_coding_agi_execution_snapshot.py`

**Interfaces:**
- Adds `runtime.execution`.
- Adds `execution` to `to_state()` and optional restoration in `from_state()`.

- [ ] Test first-generation runtime exposes execution control plane.
- [ ] Test old state with no `execution` key restores.
- [ ] Test decision/step/terminal history round-trips exactly.
- [ ] Test completed side-effect step ids are restored and cannot execute twice.
- [ ] Implement state integration while leaving backend/live subprocess objects un-serialized.

### Task 7: Evaluation campaign adapter and heldout smoke path

**Files:**
- Create: `cogcoder/organization/execution_campaign.py`
- Test: `tests/test_coding_agi_execution_campaign.py`

**Interfaces:**
- Produces `ExecutionCampaignAdapter.record_terminal_result(...)`.
- Consumes existing `CampaignRunLedger` and `ExecutionTerminalReceipt`.

- [ ] Build a tiny frozen repository/task/campaign fixture using existing campaign registries.
- [ ] Run one deterministic execution end-to-end in an isolated worktree.
- [ ] Have the test evaluator supply pass/fail explicitly.
- [ ] Record terminal counters/output artifacts into the existing campaign run ledger.
- [ ] Assert adapter never derives capability pass/fail from execution termination alone.

### Task 8: Hosted RED/GREEN matrix and protected regressions

**Files:**
- Create: `.github/workflows/coding-agi-execution-bridge.yml`

**Interfaces:** none.

- [ ] On RED head run `py_compile cogcoder/organization/*.py` then bridge tests; expect collection errors only for missing execution modules.
- [ ] After production implementation, run Python 3.11 and 3.13 matrix for `tests/test_coding_agi_execution_*.py` plus all campaign and Parts I–XV organization regression groups.
- [ ] Run Neural R2.3 contract verifier separately to prove frozen neural metadata remains unchanged.
- [ ] Record exact RED SHA, exact GREEN SHA, workflow run/job ids and any negative results in PR #160 implementation evidence.
- [ ] Merge only with `expected_head_sha=<exact-green-sha>` after fresh exact-head success.