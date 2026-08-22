# Memory & Context Intelligence Part XI — Design Specification

## Status

Implements Issue #139 on accepted Parts I–X.

Part XI upgrades the existing `MemoryFabric`, `EventLedger`, `WakeSleepScheduler`, and `ContextCompiler` into an evidence-grounded Memory & Context Intelligence subsystem without replacing their canonical storage semantics. The existing five memory scopes and six lifecycle states remain authoritative primitives; new intelligence layers add lifecycle receipts, semantic relations, bounded retrieval, checkpoint continuity, semantic context deltas, overload measurement, direct Memory-Chief repair, and exact snapshot semantics.

## 1. Authority boundaries

1. `MemoryFabric` remains the canonical memory store.
2. `EventLedger` remains the canonical temporal/event history.
3. `WakeSleepScheduler` remains the canonical sleep/wake checkpoint owner.
4. `ContextCompiler` remains the ordinary ContextCapsule builder and is extended additively rather than replaced.
5. Part XI owns memory lifecycle governance, memory semantic relations, retrieval decisions, continuity checkpoints, semantic context-delta receipts, and context-budget measurements.
6. Memory/Context agents cannot silently mutate Requirements, Master Plan, Architecture, Coding, Verification, Operations, or Research state.
7. Nolane Central may intervene through existing authority channels, but intervention does not relabel quarantined/contradicted memory as healthy.

## 2. Organization and profiles

Exactly four permanent Memory/Context identities exist:

- `memory.chief` — cross-memory arbitration, difficult context repair, direct high-stakes memory work;
- `memory.context-compiler.01` — semantic context delta and bounded context reconstruction;
- `memory.knowledge-graph.01` — semantic relation graph, contradiction/support/dependency structure;
- `memory.lifecycle.01` — memory lifecycle, quarantine, consolidation, archival and verified promotion.

A `MemoryIntelligenceProfileRegistry` derives profiles from `AgentRegistry`, preserves current neural versions dynamically, and routes requests deterministically. Requests may originate from any registered region.

## 3. Canonical scopes and lifecycle

The existing memory scopes remain unchanged:

- `GLOBAL`
- `REGION`
- `PERSONAL`
- `TASK`
- `PRIVATE`

The existing memory states remain unchanged:

- `ACTIVE`
- `STALE`
- `SUPERSEDED`
- `CONTRADICTED`
- `QUARANTINED`
- `ARCHIVED`

Part XI does not invent a parallel memory-status enum.

`MemoryLifecycleLedger` creates immutable lifecycle receipts whenever a governed transition occurs. A receipt records:

- receipt id;
- memory id;
- previous status;
- new status;
- actor id;
- reason;
- evidence refs;
- logical event anchor;
- canonical digest.

Transitions are fail-closed:

- non-Memory identities cannot perform privileged lifecycle transitions;
- returning a memory to `ACTIVE` requires a corrective evidence-backed receipt;
- `QUARANTINED`, `CONTRADICTED`, `SUPERSEDED`, `STALE`, and `ARCHIVED` memories remain auditable but are absent from normal retrieval;
- status history is append-only even though `MemoryFabric` stores the current status.

## 4. Memory semantic relation graph

`MemoryRelationGraph` stores immutable typed edges between canonical memory ids.

Relation kinds:

- `SUPPORTS`
- `CONTRADICTS`
- `SUPERSEDES`
- `DEPENDS_ON`
- `DERIVED_FROM`

Every edge has producer, evidence refs, logical epoch/event anchor and digest. Unknown memories reject. Self-contradiction and meaningless self-supersession reject. Relation history is never deleted by a later resolution.

A contradiction set may contain multiple memories. Resolving a contradiction does not delete contrary memories; instead the lifecycle ledger marks rejected memories `CONTRADICTED` or `QUARANTINED`, and an evidence-backed corrected memory becomes the active conclusion.

## 5. Retrieval intelligence and isolation

`MemoryRetrievalEngine` consumes `MemoryFabric` rather than duplicating its store.

Visibility is always evaluated before ranking:

- `PRIVATE` — owner only;
- `PERSONAL` — owner only;
- `REGION` — same region only;
- `TASK` — only the matching active/requested task;
- `GLOBAL` — visible organization-wide.

No similarity score can override scope isolation.

Normal retrieval considers only `ACTIVE` memories. Inactive memories may be fetched only through an explicit audit path.

Ranking inputs include:

- direct task match;
- tag overlap;
- evidence presence;
- confidence;
- dependency relevance;
- recency/sequence;
- explicit semantic relation to already-selected memory.

`MemorySelectionReceipt` records candidate count, selected ids, dropped ids, drop reasons, applied budget, score summary and digest. The receipt makes context omission auditable.

## 6. Context budget and overload measurement

`ContextBudget` is explicit and deterministic. It includes:

- max memories;
- max events;
- max estimated units;
- minimum reserved units for authoritative state;
- minimum reserved units for task/identity continuity.

Part XI uses deterministic estimated context units rather than a model-specific tokenizer. Unit estimation is stable across snapshot restore and suitable for adversarial overload tests.

Budget policy prioritizes:

1. identity/task/authority continuity;
2. direct Central interventions and verification/security evidence;
3. changed plan/requirements/architecture state;
4. relevant active task memory;
5. high-confidence evidence-backed personal/region/global memory;
6. other relevant recent events.

Stale, contradicted, quarantined, superseded and archived memory are excluded before budget ranking.

`ContextBudgetReceipt` records total candidate units, selected units, dropped units, selected object ids, dropped object ids and reasons.

## 7. Mission continuity checkpoint

`MissionContinuityCheckpoint` augments the scheduler checkpoint without replacing it.

A continuity checkpoint records:

- agent id;
- scheduler checkpoint event id;
- current task id;
- plan version;
- requirements version;
- architecture version;
- latest visible memory sequence;
- memory-state digest;
- skill frontier digest;
- authoritative artifact frontier;
- compiler version;
- canonical digest.

When an agent sleeps, the ordinary scheduler checkpoint remains canonical. Part XI may capture a continuity checkpoint tied to that scheduler event.

On wake, reconstruction uses:

`continuity checkpoint + events since scheduler checkpoint + active relevant memories + current task/plan/authoritative versions -> semantic context delta -> bounded ContextCapsule`

The system does not replay full event history merely because the agent slept for a long time.

## 8. Semantic Context Delta

`SemanticContextDelta` is a compact, content-addressed summary of changes since a continuity anchor.

Delta items are typed, for example:

- `TASK_CHANGED`
- `PLAN_CHANGED`
- `REQUIREMENTS_CHANGED`
- `ARCHITECTURE_CHANGED`
- `MEMORY_ADDED`
- `MEMORY_SUPERSEDED`
- `MEMORY_CONTRADICTED`
- `MEMORY_QUARANTINED`
- `SKILL_CHANGED`
- `CENTRAL_INTERVENTION`
- `EVIDENCE_CHANGED`
- `ARTIFACT_FRONTIER_CHANGED`

Each delta item retains object refs/evidence refs and the originating event or lifecycle receipt where available.

`ContextCompilationReceipt` records:

- agent/task;
- checkpoint id;
- delta digest;
- memory-selection receipt id;
- context-budget receipt id;
- authoritative frontier;
- resulting capsule digest;
- overload metrics;
- stale-context warnings;
- compiler version.

## 9. ContextCapsule compatibility

Part XI keeps all existing `ContextCapsule` fields intact. New fields are additive with safe defaults:

- `semantic_delta_digest`;
- `context_compilation_receipt_id`;
- `context_budget_units`;
- `context_overload_ratio`;
- `stale_context_warnings`.

Older snapshots and existing call sites remain valid.

## 10. Context privacy and private region state

Memory/Context agents receive a private authoritative artifact `memory-intelligence-state` containing only the control-plane digest.

Other regions do not receive the entire Memory intelligence ledger. They receive only ordinary visible memories plus their compiled semantic delta/capsule.

A non-owner cannot obtain another agent's `PRIVATE` or `PERSONAL` memory via:

- tag overlap;
- semantic relation;
- shared task references;
- high confidence;
- high priority;
- context overload fallback;
- wake reconstruction.

## 11. Direct Memory Chief work

Memory Chief must personally repair a difficult context failure.

Acceptance scenario:

1. a worker has an active high-confidence memory that is stale/contradicted by newer evidence;
2. the stale memory would produce an incorrect resumed context if untreated;
3. Memory Chief directly inspects the relation/evidence history;
4. Chief records contradiction/quarantine lifecycle evidence;
5. Chief creates or identifies a corrected evidence-backed memory;
6. Chief recompiles the affected agent's context;
7. old memory remains auditable but absent from normal retrieval;
8. corrected memory and semantic delta appear in the resumed capsule;
9. Chief completes the assigned task through ordinary `chief_direct_work`.

Delegating the repair to `memory.lifecycle.01` or `memory.context-compiler.01` does not satisfy this Chief gate.

## 12. Learning and evolution

Verified memory/context lessons may be proposed through `SkillEvolutionEngine` as personal skill candidates. They remain `SkillScope.CANDIDATE` until ordinary governed promotion.

No memory lesson rewrites live neural weights directly.

## 13. Adversarial tests

Part XI acceptance includes explicit adversarial contracts for:

- private-memory leakage attempt;
- personal-memory leakage attempt;
- stale-memory poisoning;
- contradicted high-confidence poisoning;
- quarantined-memory bypass;
- huge-history overload;
- long-sleep resume without full replay;
- plan version drift while sleeping;
- task reassignment while sleeping;
- semantic relation trying to bypass scope isolation.

Measured overload evidence must include candidate count, selected count, dropped count and deterministic budget ratio.

## 14. Snapshot and restore

Snapshot round-trip preserves exactly:

- canonical MemoryFabric entries and statuses;
- lifecycle receipts and counters;
- relation graph and counters;
- continuity checkpoints;
- memory selection receipts;
- context budget receipts;
- semantic delta records;
- compilation receipts;
- profile state;
- compiler version.

Part XI state is added under a new runtime key with `{}` default on restore, preserving older snapshots.

## 15. Fail-closed rules

- Scope isolation happens before relevance scoring.
- Inactive memories do not enter normal context.
- Unknown lifecycle transition actors reject.
- Reactivation without corrective evidence rejects.
- Contradiction resolution never deletes historical memory or relation evidence.
- Semantic relation cannot broaden memory visibility.
- Context overload never falls back to unfiltered history.
- Wake reconstruction never requires full history replay when a valid checkpoint exists.
- Memory/Context cannot mutate non-memory authority state directly.
- Central override does not relabel memory truth state.

## 16. Acceptance evidence

Part XI is accepted only after:

1. RED contracts first fail because the new production memory-intelligence modules/ContextCapsule fields do not exist;
2. Python 3.11 and 3.13 exact-head GREEN run Part XI plus Parts I–X organization regressions;
3. independent prior-Part workflows pass on the same exact head;
4. snapshot round-trip is exact;
5. adversarial isolation, stale poisoning, overload and long-sleep continuity contracts pass;
6. Memory Chief direct repair contract passes.

No claim is made that Part XI provides human-equivalent autobiographical memory, unlimited context, or infallible retrieval.