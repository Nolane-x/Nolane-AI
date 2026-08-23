# Organization Execution Bridge — Design

## Status

Implementation design for Issue #160. This milestone makes the accepted organization runtime operationally executable without changing accepted neural weights, parameter accounting, authority law, verification law or Part-XV claim authority.

## Problem

Nolane-AI currently has two real but disconnected lines:

1. the accepted organization runtime: 67 persistent identities, authority, task leasing, context compilation, memory, coding/debugging/assurance, operations, research, coordination, foundry, evaluation and real-repository campaign evidence;
2. the Neural R2.3 lineage: real PyTorch modules plus frozen one-weight hashes/audits.

The missing boundary is an evidence-carrying loop from identity/context to inference to authorized tool execution to repository side effects and back to event/memory/task state.

A campaign run before this bridge would measure the deterministic control/evidence harness rather than end-to-end coding intelligence.

## Scientific boundary

This milestone proves only that the organization can execute bounded agent/tool/repository loops under existing governance. It does not prove that Neural R2.3 is a strong coding model, that 67 agents outperform one agent, that the system is autonomous in unrestricted environments, or that Nolane-AI is AGI/frontier-equivalent. Part XV remains sole claim authority.

## Architecture

### 1. `execution_types.py`

Canonical immutable contracts:

- `ExecutionActionKind`: `TOOL`, `COMPLETE`, `WAIT`, `FAIL`.
- `ToolAction`: tool/core id, operation, arguments and declared mutation scope.
- `ExecutionBudget`: hard maxima for steps, tool calls, external-core calls and compute units.
- `ExecutionCounters`: consumed budget.
- `InferenceRequest`: identity, neural version, task id, compiled-context digest, encoder version, checkpoint digest, action schema and budget state.
- `AgentDecisionReceipt`: content-addressed decision record binding backend id, identity, neural version, checkpoint digest, encoder version, context digest, action schema digest, selected action and counters.
- `ExecutionStepReceipt`: decision + optional tool receipt + before/after workspace digest.
- `ExecutionTerminalReceipt`: final state, counters, output artifacts and termination reason.

All digests use the repository's canonical digest helpers.

### 2. `execution_inference.py`

`AgentInferenceBackend` is a small protocol: `backend_id`, `checkpoint_digest`, `decide(request) -> backend decision`.

`DeterministicFixtureBackend` is a frozen test/replay backend. It consumes an immutable action sequence and exists only to make execution behavior reproducible in tests and campaign smoke runs; it is never a neural capability claim.

`R23InferenceBackend` is the production Neural R2.3 adapter. It:

- receives an explicit checkpoint path because the one-weight binary is not committed to Git;
- reads `model/neural-r2.3/CURRENT_BEST.json` metadata;
- verifies the checkpoint SHA-256 against the accepted `one_weight_sha256` before loading;
- imports the accepted `r23.standalone.load_r23_one_weight` loader from the model directory;
- keeps the accepted weights frozen/eval-only;
- exposes the accepted checkpoint digest on every decision receipt.

The first bridge version deliberately separates `CognitiveStateEncoder` from the neural backend. The encoder creates deterministic fixed-size tensors from canonical organization state/action descriptions. Its version is receipt-bound so future learned encoders cannot silently reinterpret old decisions.

### 3. `execution_workspace.py`

`RepositoryWorkspace` owns one isolated exact-revision worktree/sandbox.

Production creation uses `git worktree add --detach <workspace> <revision>` from a source repository. Tests use a tiny temporary Git repository and the same code path.

Invariants:

- workspace root must differ from source repository root;
- all resolved file paths must remain inside the workspace;
- before/after workspace digests are deterministic over tracked working-tree content and status;
- mutations return content-addressed artifacts/receipts;
- cleanup never mutates the source checkout;
- restart state stores repository identity/revision/workspace metadata but never serializes live subprocesses.

### 4. `execution_tools.py`

`ExternalCoreExecutor` is the actual permission + invocation boundary.

Authorization derives from the existing `AgentIdentity.tool_permissions` and `external_core_bindings`. No model action can bypass this check.

Built-in handlers:

- `filesystem`: read/write text inside the workspace only;
- `git`: bounded read-only status/diff operations plus explicitly permitted local worktree operations;
- `terminal`: argv-only subprocess execution, no shell interpolation, fixed cwd=workspace, timeout and output limit;
- `code-search`: deterministic repository-local text search;
- `compiler`: bounded command execution through an allowlisted argv supplied by the caller;
- `test-runner`: bounded command execution through an allowlisted argv supplied by the caller.

Region-specific cores (`lsp`, `ast`, `symbol-graph`, etc.) use a registered-handler interface. A core may be authorized yet unavailable; this fails closed with an immutable failure receipt. Unsupported or unauthorized invocations never fall back to terminal.

Every invocation records input/output/failure evidence and also mirrors a `ToolInvocationReceipt` into the existing coding patch ledger when the executing identity is in a coding-capable task.

### 5. `execution.py`

`OrganizationExecutionControlPlane` binds existing runtime components rather than replacing them.

Per-agent loop:

1. require a live task lease owned by the agent;
2. wake/compile context using existing scheduler/context compiler;
3. encode canonical context/action schema;
4. ask the bound inference backend for a decision;
5. validate action against budget, authority/permission and code-claim boundaries;
6. invoke the tool/core inside the isolated workspace;
7. append immutable execution receipts/artifacts;
8. recompile context after evidence-producing effects;
9. continue, complete, wait, fail or honor a Central pause/abort;
10. return a terminal receipt.

No tool result automatically marks a coding patch verified or merged. Existing Coding/Assurance/Integration gates remain authoritative.

The control plane also stores backend bindings by agent id, active loop state and completed terminal receipts. Snapshot restore never replays a completed side effect: completed step ids and tool receipt ids are restored before execution resumes.

### 6. Central and Chief semantics

- Regional Chiefs use exactly the same execution loop as specialists and therefore remain direct workers.
- Central can issue existing pause/abort/correct events. The execution control plane checks current TaskGraph abort state and new relevant Central events before each side effect.
- Central override never becomes verification.

### 7. Runtime integration

The final `cogcoder.organization.runtime.OrganizationRuntime` remains layered over the accepted Campaign/Part-XV runtime and adds `runtime.execution`.

`to_state()` adds an `execution` key. `from_state()` accepts missing execution state and restores an empty/disabled bridge for all historical snapshots.

Inference backend objects and live subprocesses are not serialized. Snapshot stores binding descriptors; a restored runtime requires the caller to rebind executable backends before resuming.

### 8. Campaign adapter

`ExecutionCampaignAdapter` maps a terminal execution receipt to the existing `CampaignRunLedger.record_result` fields:

- compute units;
- tool calls;
- external-core calls;
- active-agent count;
- output artifact ids;
- termination reason.

It never invents pass/fail. Pass/fail is supplied only after the benchmark evaluator/verifier produces the required evidence.

## Security and safety invariants

- no shell-string execution; terminal uses argv sequences only;
- no path traversal outside workspace;
- no network core is enabled implicitly;
- no mutation without a task lease and appropriate tool/core permission;
- source writes additionally require existing exclusive code-claim coverage;
- bounded timeout/output/step/tool/compute budgets;
- checkpoint digest verified before R2.3 load;
- neural outputs are proposals, not authority;
- self-verification prohibitions remain unchanged;
- failures and timeouts are first-class evidence.

## Acceptance gates

1. tests fail before production bridge modules exist (RED);
2. deterministic fixture backend yields identical decision receipt for identical request;
3. R2.3 backend rejects missing/wrong-hash checkpoint before load;
4. unauthorized tool/core call fails closed and records failure evidence;
5. filesystem mutation is confined to an isolated exact-revision worktree and has before/after hashes;
6. write action without code-claim coverage is rejected;
7. Coding Chief executes a bounded write task directly;
8. specialist executes an authorized core while an unauthorized core is rejected;
9. Central abort prevents the next side effect;
10. snapshot/restore preserves completed steps and does not duplicate effects;
11. campaign adapter records an end-to-end smoke terminal receipt under an existing frozen campaign run spec;
12. Python 3.11/3.13 bridge tests plus Parts I–XV and campaign regressions pass on the exact GREEN head;
13. no production neural weight, accepted evidence, parameter accounting or capability claim changes.