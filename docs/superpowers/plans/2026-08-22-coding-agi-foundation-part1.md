# Nolane Coding AGI Foundation Part I Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the executable organizational substrate that lets persistent Nolane AI identities coordinate, sleep/wake, remember, exchange typed evidence, learn skills, receive direct Central intervention, and evolve through reversible evidence-gated promotion.

**Architecture:** Add a focused `cogcoder.organization` package with immutable public records plus deterministic in-memory authorities that can snapshot/restore to canonical JSON. Keep the first implementation model-agnostic: it defines the organization contract around existing/future neural agents rather than pretending 67 trained AGI models already exist. A six-agent vertical slice and the full 67-identity blueprint exercise the same contracts.

**Tech Stack:** Python 3.11/3.13 standard library, dataclasses, enum, hashlib/json, pytest, GitHub Actions.

**Spec:** `docs/coding-agi-organization/PART_I_FOUNDATION.md`

## Global Constraints

- Every permanent AI identity is a working intelligence; Chiefs cannot be represented as pure routers.
- Nolane Central has global direct-intervention authority; interventions are always ledgered and visible to the affected Regional Chief.
- Initial neural accounting must remain strictly below 100,000,000 physical trainable parameters per AI.
- Shared physical parameters and local specialization parameters must be reported separately and never double-counted as unique physical parameters.
- Context windows are working memory; durable state lives in explicit memory/event/task stores.
- Cross-region authoritative writes require ownership authority or an explicit Central override.
- Skill and neural promotions are evidence-gated, reversible, and fail closed.
- The implementation must not claim that configured identities are already AGI.

---

## File map

- `cogcoder/organization/__init__.py` — stable public exports.
- `cogcoder/organization/types.py` — immutable canonical records and enums.
- `cogcoder/organization/blueprint.py` — 15-region / 67-identity first-generation blueprint and parameter-accounting validation.
- `cogcoder/organization/registry.py` — persistent identity registry and immutable neural-version bookkeeping.
- `cogcoder/organization/authority.py` — ownership, permissions, Central override, independent-block semantics.
- `cogcoder/organization/events.py` — append-only typed cognitive-event ledger and subscription replay.
- `cogcoder/organization/memory.py` — global/region/personal/task/private memory namespaces and promotion rules.
- `cogcoder/organization/context.py` — context compiler and semantic delta construction.
- `cogcoder/organization/tasks.py` — task leases, plan graph, artifact authority and plan-gap proposals.
- `cogcoder/organization/scheduler.py` — wake/sleep state and trigger evaluation.
- `cogcoder/organization/evolution.py` — personal/regional/global skill candidate lifecycle and quarantine.
- `cogcoder/organization/verification.py` — evidence gate, champion/challenger promotion and rollback receipts.
- `cogcoder/organization/runtime.py` — vertical-slice orchestration and Central direct intervention.
- `cogcoder/organization/snapshot.py` — canonical organization snapshot/restore across process restarts.
- `tests/test_coding_agi_foundation_blueprint.py` — 67 identities, 15 regions, Chief-worker and parameter invariants.
- `tests/test_coding_agi_foundation_authority_events.py` — ownership, direct intervention and audit visibility.
- `tests/test_coding_agi_foundation_memory_context.py` — scoped memory, context deltas and sleeping-agent continuity.
- `tests/test_coding_agi_foundation_tasks_runtime.py` — task leasing, plan-gap workflow and Chief direct-work path.
- `tests/test_coding_agi_foundation_evolution.py` — skill promotion/quarantine and reversible neural promotion.
- `tests/test_coding_agi_foundation_snapshot.py` — deterministic snapshot/restore.
- `.github/workflows/coding-agi-foundation.yml` — Python 3.11/3.13 focused gate.

---

### Task 1: Canonical organization types

**Files:**
- Create: `cogcoder/organization/types.py`
- Create: `cogcoder/organization/__init__.py`
- Test: `tests/test_coding_agi_foundation_blueprint.py`

**Interfaces:**
- Produces `AgentRank`, `AgentStatus`, `MemoryScope`, `EventKind`, `ParameterAccounting`, `AgentIdentity`, `CognitiveEvent`, `EvidenceRecord`, `ContextCapsule`.

- [ ] Write tests that reject physical totals at or above 100M and require immutable accepted neural version identifiers.
- [ ] Run the focused test and observe failure before implementation.
- [ ] Implement frozen dataclasses/enums with strict validation and canonical serialization helpers.
- [ ] Re-run the focused test on Python 3.11-compatible syntax.
- [ ] Commit the type contract.

### Task 2: Full 67-identity blueprint

**Files:**
- Create: `cogcoder/organization/blueprint.py`
- Extend: `tests/test_coding_agi_foundation_blueprint.py`

**Interfaces:**
- Produces `build_first_generation_blueprint() -> tuple[AgentIdentity, ...]` and `validate_blueprint(...)`.

- [ ] Write assertions for exactly 67 identities, one Central, 15 Chiefs, 51 specialists and exactly 15 non-Central regions.
- [ ] Assert every Chief has `direct_work_capable=True` and every permanent identity has `learning_capable=True`.
- [ ] Assert all physical parameter totals are `<100_000_000` and Central/Chief bands match the architecture spec.
- [ ] Implement the declarative region roster and deterministic identity names.
- [ ] Run blueprint tests and commit.

### Task 3: Persistent identity registry

**Files:**
- Create: `cogcoder/organization/registry.py`
- Extend: `tests/test_coding_agi_foundation_blueprint.py`

**Interfaces:**
- Produces `AgentRegistry.register`, `get`, `set_status`, `bind_task`, `accept_neural_version`, `to_state`, `from_state`.

- [ ] Test duplicate-id rejection, restart-safe identity state, immutable accepted versions and task bindings.
- [ ] Implement deterministic registry state transitions.
- [ ] Run focused tests and commit.

### Task 4: Authority and ownership graph

**Files:**
- Create: `cogcoder/organization/authority.py`
- Test: `tests/test_coding_agi_foundation_authority_events.py`

**Interfaces:**
- Produces `AuthorityGraph.claim_owner`, `can_write`, `require_write`, `record_block`, `central_override`.

- [ ] Test that a Backend Coder can propose but cannot authoritatively mutate the Master Plan.
- [ ] Test Planning Chief ownership, independent verifier blocking and explicit Central override receipts.
- [ ] Implement fail-closed permissions and auditable overrides.
- [ ] Run focused tests and commit.

### Task 5: Typed cognitive event fabric

**Files:**
- Create: `cogcoder/organization/events.py`
- Extend: `tests/test_coding_agi_foundation_authority_events.py`

**Interfaces:**
- Produces `EventLedger.append`, `events_since`, `subscribe`, `deliverable_for`, `to_state`, `from_state`.

- [ ] Test monotonically ordered immutable event ids and hash-stable payloads.
- [ ] Test `CENTRAL_INTERVENTION`, `PLAN_GAP_DETECTED`, `PLAN_AMENDED`, `TEST_FAILED`, `VERIFICATION_REJECTED` delivery.
- [ ] Implement append-only ledger with deterministic canonical digest.
- [ ] Run focused tests and commit.

### Task 6: Persistent scoped memory fabric

**Files:**
- Create: `cogcoder/organization/memory.py`
- Test: `tests/test_coding_agi_foundation_memory_context.py`

**Interfaces:**
- Produces `MemoryFabric.write`, `read_namespace`, `retrieve`, `promote`, `to_state`, `from_state`.

- [ ] Test GLOBAL, REGION, PERSONAL, TASK and PRIVATE scope isolation.
- [ ] Test that private memory cannot become global without an explicit promotion receipt.
- [ ] Implement immutable versioned memory entries and deterministic retrieval ranking by exact tags/recency.
- [ ] Run focused tests and commit.

### Task 7: Context compiler and semantic delta

**Files:**
- Create: `cogcoder/organization/context.py`
- Extend: `tests/test_coding_agi_foundation_memory_context.py`

**Interfaces:**
- Produces `ContextCompiler.compile(agent_id, task_id, since_event_id=None) -> ContextCapsule`.

- [ ] Test that a sleeping agent receives only relevant global/region/personal/task memory plus events since checkpoint.
- [ ] Test that unrelated region private memory is absent.
- [ ] Test context delta summaries preserve event ids and authoritative artifact versions.
- [ ] Implement bounded deterministic capsule assembly.
- [ ] Run focused tests and commit.

### Task 8: Task graph, plan ownership and plan-gap protocol

**Files:**
- Create: `cogcoder/organization/tasks.py`
- Test: `tests/test_coding_agi_foundation_tasks_runtime.py`

**Interfaces:**
- Produces `TaskGraph.add_task`, `lease`, `complete`, `add_dependency`, `propose_plan_gap`, `apply_plan_amendment`.

- [ ] Test one active responsible identity per lease unless shared explicitly.
- [ ] Test coder plan-gap proposal cannot mutate plan version itself.
- [ ] Test Planning Chief can accept proposal, increment plan version and emit machine-readable affected nodes.
- [ ] Implement DAG cycle rejection and ownership checks.
- [ ] Run focused tests and commit.

### Task 9: Wake/sleep scheduler

**Files:**
- Create: `cogcoder/organization/scheduler.py`
- Extend: `tests/test_coding_agi_foundation_memory_context.py`

**Interfaces:**
- Produces `WakeSleepScheduler.sleep`, `wake`, `notify_event`, `due_agents`.

- [ ] Test event-driven wake, checkpoint wake and periodic wake metadata.
- [ ] Test sleeping agents keep checkpoint ids and resume through Context Compiler instead of replaying whole history.
- [ ] Implement deterministic wake-reason queue.
- [ ] Run focused tests and commit.

### Task 10: Personal skill evolution and governed sharing

**Files:**
- Create: `cogcoder/organization/evolution.py`
- Test: `tests/test_coding_agi_foundation_evolution.py`

**Interfaces:**
- Produces `SkillEvolutionEngine.propose`, `verify`, `promote_personal`, `promote_regional`, `promote_global`, `quarantine`, `skills_for`.

- [ ] Test an unverified skill never appears in active personal/regional/global retrieval.
- [ ] Test personal -> regional -> global promotion requires progressively stronger evidence receipts.
- [ ] Test quarantine suppresses reuse without deleting provenance.
- [ ] Implement content-addressed immutable skill versions.
- [ ] Run focused tests and commit.

### Task 11: Neural champion/challenger gate and rollback

**Files:**
- Create: `cogcoder/organization/verification.py`
- Extend: `tests/test_coding_agi_foundation_evolution.py`

**Interfaces:**
- Produces `VerificationAuthority.evaluate_candidate`, `promote_candidate`, `rollback`, `PromotionReceipt`.

- [ ] Test challenger rejection on regression or false accept.
- [ ] Test accepted challenger stays below 100M physical parameters and becomes the new registry version only after verification.
- [ ] Test rollback restores the exact previous accepted version.
- [ ] Implement fail-closed evidence rules and immutable receipts.
- [ ] Run focused tests and commit.

### Task 12: Organization runtime and Central direct intervention

**Files:**
- Create: `cogcoder/organization/runtime.py`
- Extend: `tests/test_coding_agi_foundation_tasks_runtime.py`

**Interfaces:**
- Produces `OrganizationRuntime.central_intervene`, `report_plan_gap`, `chief_direct_work`, `checkpoint_agent`, `wake_agent`.

- [ ] Test Central directly corrects a specialist without routing through the Chief.
- [ ] Test the same intervention is automatically visible to the specialist's Chief via event subscription.
- [ ] Test a Chief has a direct-work record distinct from delegation and can own/complete a difficult task personally.
- [ ] Test a coder-detected plan gap flows to Planning Chief, plan amendment, task/context delta, then back to the coder.
- [ ] Implement the six-agent vertical slice over the shared subsystems.
- [ ] Run focused tests and commit.

### Task 13: Canonical snapshot/restore

**Files:**
- Create: `cogcoder/organization/snapshot.py`
- Test: `tests/test_coding_agi_foundation_snapshot.py`

**Interfaces:**
- Produces `OrganizationSnapshot.capture(runtime)`, `to_json`, `from_json`, `restore()`.

- [ ] Test byte-stable canonical JSON for identical state.
- [ ] Test restart restores identity/task/event/memory/skill/accepted-version continuity.
- [ ] Test snapshot digest changes when authoritative state changes.
- [ ] Implement schema-versioned canonical snapshots with SHA-256 digest.
- [ ] Run focused tests and commit.

### Task 14: Cross-version CI gate

**Files:**
- Create: `.github/workflows/coding-agi-foundation.yml`

**Interfaces:**
- Runs py_compile + focused pytest suite under Python 3.11 and 3.13.

- [ ] Add workflow path filters for `cogcoder/organization/**`, focused tests and Part-I docs.
- [ ] Compile every organization module.
- [ ] Run `python -m pytest -q tests/test_coding_agi_foundation_*.py`.
- [ ] Open PR and require fresh hosted evidence before any completion claim.

### Task 15: Part-I acceptance evidence

**Files:**
- Create after hosted verification: `research/CODING_AGI_PART1_FOUNDATION_RESULT.json`
- Create after hosted verification: `docs/coding-agi-organization/PART_I_DELIVERY.md`

**Interfaces:**
- Binds result to exact verified commit and reports only bounded foundation properties.

- [ ] Record exact commit SHA and hosted workflow evidence.
- [ ] Record identity counts, parameter-accounting invariants and focused test counts.
- [ ] Explicitly state that no AGI capability claim follows from the organizational substrate.
- [ ] Merge only after exact-head verification is green.
