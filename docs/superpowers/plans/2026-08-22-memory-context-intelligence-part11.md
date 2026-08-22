# Memory & Context Intelligence Part XI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build durable, isolated, lifecycle-governed memory and bounded semantic context reconstruction for all permanent Nolane agents without replacing the existing canonical MemoryFabric/EventLedger/Scheduler primitives.

**Architecture:** Add focused profile, lifecycle/relation, retrieval, context-intelligence and orchestration modules. Extend `ContextCapsule`, `ContextCompiler`, and `OrganizationRuntime` additively; keep old snapshot/state shapes restorable through safe defaults. All implementation is test-first and must preserve Parts I–X regressions.

**Tech Stack:** Python dataclasses/enums, existing AgentRegistry/MemoryFabric/EventLedger/WakeSleepScheduler/SkillEvolutionEngine/OrganizationSnapshot, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-22-memory-context-intelligence-part11-design.md`

## Global Constraints

- Existing MemoryScope values remain exactly GLOBAL, REGION, PERSONAL, TASK, PRIVATE.
- Existing MemoryStatus values remain exactly ACTIVE, STALE, SUPERSEDED, CONTRADICTED, QUARANTINED, ARCHIVED.
- `MemoryFabric` remains canonical storage; no duplicate memory store.
- Scope isolation is evaluated before relevance ranking and cannot be bypassed by semantic relations.
- Normal context retrieval excludes every non-ACTIVE memory.
- Lifecycle/status history remains auditable and append-only through receipts.
- Valid continuity checkpoints prevent full-history replay on wake.
- Context budgeting is deterministic and measured.
- `ContextCapsule` changes are additive with safe defaults.
- Memory/Context cannot mutate non-memory authority state directly.
- Memory Chief must directly repair a difficult memory/context failure.
- Parts I–X remain regression clean.

---

### Task 1: Memory Intelligence profiles and routing

**Files:**
- Create: `cogcoder/organization/memory_profiles.py`
- Test: `tests/test_coding_agi_memory_profiles.py`

**Interfaces:**
- Produces `MemoryIntelligenceDomain`, `MemoryIntelligenceProfile`, `MemoryIntelligenceProfileRegistry`, `MemoryWorkRequest`, `MemoryAssignmentReceipt`.
- Consumes `AgentRegistry` and existing four `memory-context-knowledge` identities.

- [ ] **Step 1: Write RED profile/routing contracts**

```python
registry = AgentRegistry(build_first_generation_blueprint())
profiles = MemoryIntelligenceProfileRegistry(registry)
assert {p.agent_id for p in profiles.profiles()} == {
    'memory.chief', 'memory.context-compiler.01',
    'memory.knowledge-graph.01', 'memory.lifecycle.01',
}
assert profiles.route(MemoryWorkRequest(
    work_id='MW-1', object_id='mem-00000001',
    requested_domains=(MemoryIntelligenceDomain.LIFECYCLE,),
    scope_hints=('quarantine',), priority=80,
    requester_agent_id='debug.chief', evidence_refs=('EV-MW-1',),
)).selected_agent_id == 'memory.lifecycle.01'
```

- [ ] **Step 2: Run** `python -m pytest -q tests/test_coding_agi_memory_profiles.py` and confirm failure because `memory_profiles.py` does not exist.
- [ ] **Step 3: GREEN implement deterministic profile routing with dynamic accepted neural versions from AgentRegistry.**
- [ ] **Step 4: Re-run the focused test and preserve exact four identities.**

### Task 2: Lifecycle receipts and semantic relation graph

**Files:**
- Create: `cogcoder/organization/memory_lifecycle.py`
- Test: `tests/test_coding_agi_memory_lifecycle.py`

**Interfaces:**
- Produces `MemoryLifecycleReceipt`, `MemoryLifecycleLedger`, `MemoryRelationKind`, `MemoryRelation`, `MemoryRelationGraph`.
- Consumes canonical `MemoryFabric`, `MemoryStatus`, `AgentRegistry`, `EventLedger`.

- [ ] **Step 1: RED privileged lifecycle transitions.**

```python
memory = MemoryFabric()
row = memory.write(MemoryScope.PERSONAL, 'old belief', owner_agent_id='coding.backend.01', evidence_ids=('EV-OLD',))
ledger = MemoryLifecycleLedger(registry=registry, memory=memory, events=events)
with pytest.raises(PermissionError):
    ledger.transition(row.memory_id, actor_agent_id='coding.backend.01', new_status=MemoryStatus.QUARANTINED,
                      reason='self hide', evidence_refs=('EV-X',))
receipt = ledger.transition(row.memory_id, actor_agent_id='memory.lifecycle.01',
                            new_status=MemoryStatus.QUARANTINED,
                            reason='contradicted by verified evidence', evidence_refs=('EV-NEW',))
assert memory.get(row.memory_id).status is MemoryStatus.QUARANTINED
assert receipt.previous_status is MemoryStatus.ACTIVE
```

- [ ] **Step 2: RED reactivation requires corrective evidence and cannot erase historical receipts.**
- [ ] **Step 3: RED relation graph supports SUPPORTS/CONTRADICTS/SUPERSEDES/DEPENDS_ON/DERIVED_FROM, rejects unknown memory ids and invalid self-contradiction/self-supersession.**
- [ ] **Step 4: GREEN implement append-only lifecycle receipts and relation records with canonical digests.**
- [ ] **Step 5: Verify exact state round-trip for lifecycle and relation graph.**

### Task 3: Scope-safe retrieval and audit receipts

**Files:**
- Create: `cogcoder/organization/memory_retrieval.py`
- Test: `tests/test_coding_agi_memory_isolation.py`
- Test: `tests/test_coding_agi_memory_retrieval.py`

**Interfaces:**
- Produces `MemoryRetrievalBudget`, `MemorySelectionReceipt`, `MemoryRetrievalEngine`.
- Consumes `MemoryFabric` and optional `MemoryRelationGraph`.

- [ ] **Step 1: RED private/personal/region/task isolation before scoring.**

```python
private = memory.write(MemoryScope.PRIVATE, 'secret scratch', owner_agent_id='coding.backend.01', confidence=1.0)
engine = MemoryRetrievalEngine(memory=memory, relations=relations)
receipt = engine.select(agent_id='debug.chief', region='debugging-failure', task_id=None,
                        tags=('secret',), budget=MemoryRetrievalBudget(max_memories=32, max_estimated_units=4096))
assert private.memory_id not in receipt.selected_memory_ids
assert private.memory_id not in receipt.candidate_memory_ids
```

- [ ] **Step 2: RED semantic relation cannot broaden visibility.**
- [ ] **Step 3: RED inactive memories are absent from normal retrieval even with confidence=1.0 and exact tag match.**
- [ ] **Step 4: RED deterministic ranking and budget drop reasons.**
- [ ] **Step 5: GREEN implement visible-first selection, stable unit estimator, deterministic score ordering, audit-only inactive path.**

### Task 4: Context budget, semantic delta and continuity checkpoints

**Files:**
- Create: `cogcoder/organization/context_intelligence.py`
- Modify: `cogcoder/organization/types.py`
- Test: `tests/test_coding_agi_context_intelligence.py`
- Test: `tests/test_coding_agi_memory_resume.py`

**Interfaces:**
- Produces `ContextBudget`, `ContextBudgetReceipt`, `ContinuityCheckpoint`, `ContextDeltaKind`, `SemanticContextDeltaItem`, `SemanticContextDelta`, `ContextCompilationReceipt`, `ContextIntelligenceCompiler`.
- Extends `ContextCapsule` with safe-default fields `semantic_delta_digest`, `context_compilation_receipt_id`, `context_budget_units`, `context_overload_ratio`, `stale_context_warnings`.
- Consumes AgentRegistry, EventLedger, TaskGraph, MemoryRetrievalEngine, scheduler checkpoint ids, requirements/planning/architecture/evolution state and ordinary ContextCompiler output.

- [ ] **Step 1: RED ContextCapsule additive field compatibility.**
- [ ] **Step 2: RED huge-history overload uses a bounded event/memory selection and emits candidate/selected/dropped metrics.**
- [ ] **Step 3: RED long-sleep resume uses events since checkpoint rather than all historical events.**

```python
checkpoint = intelligence.capture_continuity('coding.backend.01', scheduler_checkpoint_event_id=checkpoint_event)
# append many irrelevant historical/current events, then one relevant task/plan change
capsule, receipt = intelligence.compile('coding.backend.01', continuity_checkpoint_id=checkpoint.checkpoint_id)
assert receipt.replayed_full_history is False
assert receipt.event_candidate_count < len(runtime.ledger.to_state()['events'])
assert capsule.semantic_delta_digest == receipt.semantic_delta_digest
```

- [ ] **Step 4: RED plan drift/task reassignment becomes typed semantic delta and stale-context warning.**
- [ ] **Step 5: GREEN implement deterministic ContextBudget and content-addressed semantic delta.**
- [ ] **Step 6: GREEN compilation receipt records authoritative frontier and overload ratio.**

### Task 5: Memory/Context control plane, direct Chief repair and learning

**Files:**
- Create: `cogcoder/organization/memory_context.py`
- Test: `tests/test_coding_agi_memory_direct_work.py`
- Test: `tests/test_coding_agi_memory_learning.py`

**Interfaces:**
- Produces `MemoryContextControlPlane` composing profiles, lifecycle, relations, retrieval and context intelligence.
- Consumes ArtifactStore only for optional repair artifacts, SkillEvolutionEngine for candidate lessons, and ordinary runtime `chief_direct_work` for task completion.

- [ ] **Step 1: RED difficult Chief repair scenario.**

```python
old = runtime.memory.write(MemoryScope.PERSONAL, 'API uses v1', owner_agent_id='coding.backend.01',
                           tags=('api-version',), evidence_ids=('EV-OLD',), confidence=1.0)
new = runtime.memory.write(MemoryScope.PERSONAL, 'API uses v2', owner_agent_id='coding.backend.01',
                           tags=('api-version',), evidence_ids=('EV-NEW',), confidence=1.0)
runtime.memory_context.relations.add(
    actor_agent_id='memory.chief', source_memory_id=new.memory_id,
    target_memory_id=old.memory_id, kind=MemoryRelationKind.CONTRADICTS,
    evidence_refs=('EV-NEW',),
)
runtime.memory_context.repair_contradiction(
    chief_agent_id='memory.chief', rejected_memory_ids=(old.memory_id,),
    corrected_memory_id=new.memory_id, reason='new verified contract', evidence_refs=('EV-NEW',),
)
resumed = runtime.memory_context.compile_context('coding.backend.01')
assert old.memory_id not in {m.memory_id for m in resumed.capsule.memories}
assert new.memory_id in {m.memory_id for m in resumed.capsule.memories}
```

- [ ] **Step 2: RED non-Chief cannot use Chief repair operation.**
- [ ] **Step 3: RED Chief must personally complete assigned task through `OrganizationRuntime.chief_direct_work`.**
- [ ] **Step 4: RED `propose_personal_skill` remains SkillScope.CANDIDATE.**
- [ ] **Step 5: GREEN implement orchestration without any non-memory authority mutation APIs.**

### Task 6: Runtime, ContextCompiler, snapshot and private state

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Modify: `cogcoder/organization/context.py`
- Test: `tests/test_coding_agi_memory_snapshot_context.py`

**Interfaces:**
- `OrganizationRuntime.memory_context: MemoryContextControlPlane`.
- Runtime authority artifact `memory-intelligence-state` owned by `memory.chief`.
- Memory/Context region gets `('memory-intelligence-state', runtime.memory_context.digest)` in ordinary ContextCompiler authoritative artifacts.
- Other regions never receive the private control-plane digest.

- [ ] **Step 1: RED exact OrganizationSnapshot round-trip after lifecycle transitions, relations and continuity checkpoints.**
- [ ] **Step 2: RED memory region receives private `memory-intelligence-state`; coding/debug/research regions do not.**
- [ ] **Step 3: RED old runtime state lacking `memory_context` restores successfully with an empty additive control plane.**
- [ ] **Step 4: GREEN wire runtime creation/restore/to_state and ContextCompiler private-state exposure.**

### Task 7: Adversarial acceptance and CI

**Files:**
- Test: `tests/test_coding_agi_memory_adversarial.py`
- Create: `.github/workflows/coding-agi-memory-context-part11.yml`

**Interfaces:** Uses the complete Part XI surface.

- [ ] **Step 1: RED private-memory leakage attack via tag/semantic relation/high-confidence fails.**
- [ ] **Step 2: RED stale/contradicted/quarantined poisoning fails.**
- [ ] **Step 3: RED huge-history overload produces deterministic bounded selection metrics.**
- [ ] **Step 4: RED long-sleep wake excludes pre-checkpoint replay and reports plan/task drift.**
- [ ] **Step 5: GREEN only production implementation; do not weaken tests.**
- [ ] **Step 6: CI matrix Python 3.11/3.13 runs:**

```bash
python -m py_compile cogcoder/organization/*.py
python -m pytest -q \
  tests/test_coding_agi_memory_*.py \
  tests/test_coding_agi_context_intelligence.py \
  tests/test_coding_agi_research_*.py \
  tests/test_coding_agi_ops_*.py \
  tests/test_coding_agi_assurance_*.py \
  tests/test_coding_agi_ui_*.py \
  tests/test_coding_agi_debug_*.py \
  tests/test_coding_agi_code_claims.py \
  tests/test_coding_agi_coding_*.py \
  tests/test_coding_agi_foundation_*.py \
  tests/test_coding_agi_central_*.py \
  tests/test_coding_agi_requirements_*.py \
  tests/test_coding_agi_master_plan.py \
  tests/test_coding_agi_planning_*.py \
  tests/test_coding_agi_plan_reconciliation.py \
  tests/test_coding_agi_architecture_*.py \
  tests/test_coding_agi_integration_*.py
```

- [ ] **Step 7: Capture RED on Python 3.11 and 3.13 before production modules exist.**
- [ ] **Step 8: Capture exact-head GREEN on Python 3.11 and 3.13 plus independent Parts I–X workflows.**
- [ ] **Step 9: Merge only with expected exact head SHA and close Issue #139.**

## Self-review

- Spec coverage: every Issue #139 acceptance gate maps to Tasks 2–7.
- Isolation is enforced before ranking, not by score penalties.
- No new memory store or duplicate lifecycle enum exists.
- No TODO/TBD placeholders exist.
- ContextCapsule changes are additive.
- Long-sleep continuity is tied to existing scheduler checkpoints.
- Chief direct work cannot be satisfied by delegation.
- Snapshot compatibility is explicit.
- No path grants Memory/Context authority over Planning/Architecture/Coding/Verification state.