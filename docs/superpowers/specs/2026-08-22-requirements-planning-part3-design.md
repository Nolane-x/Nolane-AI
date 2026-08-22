# Requirements & Planning Intelligence Part III — Design Specification

## Status and authority

This specification formalizes GitHub Issue #131 on top of the Part-I organizational substrate. It is intentionally independent of Part-II implementation details: Central may observe and intervene through the shared Part-I event/authority layer, but Requirements and Planning retain their own authoritative ownership.

## Goal

Replace static project intent with two durable, versioned, machine-readable authorities:

1. a **Requirement Graph** owned by Requirements Chief; and
2. a **Master Plan Graph** owned by Planning Chief.

Workers may discover ambiguity, conflicts, missing dependencies and plan gaps, but they cannot silently rewrite either authority. Requirements Chief and Planning Chief remain direct technical workers, not dispatch-only managers.

## Design approaches considered

### A. Extend `TaskGraph` into a universal project graph

Pros: fewer files and fewer types.
Cons: mixes requirements, plans, task leases and execution history; rollback becomes ambiguous; ownership boundaries become difficult to enforce.

### B. Store canonical Markdown and infer structure on demand

Pros: human-readable and easy to edit.
Cons: weak machine authority, non-deterministic interpretation, poor provenance and drift detection.

### C. Separate versioned intent graphs + operational `TaskGraph` bridge — chosen

`RequirementGraph` and `MasterPlanGraph` are immutable-version authorities. Existing `TaskGraph` remains the execution graph. Explicit links connect requirements -> plan nodes -> tasks. This keeps authority, planning semantics and execution state separately testable while allowing Context Compiler to combine them.

## 1. Requirement Graph

### Requirement node

Each requirement contains:
- `requirement_id`;
- title and canonical statement;
- requirement kind (`FUNCTIONAL`, `NON_FUNCTIONAL`, `CONSTRAINT`, `SECURITY`, `COMPATIBILITY`, `QUALITY`);
- priority;
- acceptance criteria ids;
- dependency requirement ids;
- source/evidence refs;
- status (`ACTIVE`, `AMBIGUOUS`, `SUPERSEDED`, `REJECTED`);
- owner authority;
- introduced revision;
- superseded-by id where relevant.

### Acceptance criterion

Each criterion is a concrete verifiable condition with:
- criterion id;
- requirement id;
- statement;
- verification class;
- evidence expectations;
- status.

### Requirement revisions

A revision is immutable and contains:
- revision number/id;
- parent revision;
- actor;
- reason;
- evidence refs;
- added/changed/superseded requirement ids;
- canonical digest.

Only `requirements.chief` may authoritatively apply a revision unless Part-I Central override semantics are explicitly invoked and audited.

### Requirement proposals

Any agent may propose:
- `REQUIREMENT_AMBIGUITY`;
- `REQUIREMENT_CHANGE_PROPOSED`;
- `ACCEPTANCE_GAP`.

Proposal events do not mutate the graph. Requirements Chief reviews and applies or rejects them.

## 2. Master Plan Graph

### Plan node

A plan node contains:
- node id;
- title/objective;
- linked requirement ids;
- predecessor plan node ids;
- milestone id (optional);
- risk ids;
- linked task ids;
- owner region/agent;
- status (`PLANNED`, `READY`, `ACTIVE`, `BLOCKED`, `DONE`, `SUPERSEDED`);
- acceptance criterion ids;
- evidence/provenance refs.

### Milestones

Milestones group plan nodes around an evidence-bearing outcome, not a date-only label. They have completion criteria and optional target ordering.

### Risks

A risk record contains likelihood/severity scores, evidence, mitigation plan nodes and current status. Risk score is derived from bounded integer values rather than free-form prose alone.

### Plan revisions

Every authoritative plan change creates an immutable revision with parent, actor, proposal/event refs, evidence and digest. Rollback selects a prior accepted revision and creates a new rollback revision; history is never deleted.

## 3. Operational TaskGraph bridge

Existing `TaskGraph` remains responsible for:
- concrete task ids;
- leases;
- task dependencies;
- completion/abort state;
- output artifacts.

Part III adds explicit links:
`Requirement -> PlanNode -> TaskRecord`.

Rules:
- a task may link to one authoritative plan node;
- every plan node that executes code/research must reference at least one requirement or an explicit maintenance/system requirement;
- task dependency cycles remain rejected by `TaskGraph`;
- plan dependency cycles are separately rejected by `MasterPlanGraph`.

## 4. Plan-gap flow

The existing `PLAN_GAP_DETECTED` event is retained.

Flow:
1. worker discovers missing/incorrect plan structure;
2. event records task, reason, suggested nodes and evidence;
3. Planning Chief/Plan Auditor inspect proposal;
4. `PlanningControlPlane.apply_gap(...)` validates ownership and evidence;
5. Master Plan revision is created;
6. linked TaskGraph/plan-node mapping is updated where necessary;
7. `PLAN_AMENDED` event contains old/new plan revision ids and affected task ids;
8. Context Compiler exposes the semantic delta to affected sleeping/active agents.

## 5. Reconciliation engine

`PlanReconciler` compares authoritative intent with observed project state.

Inputs may include:
- current RequirementGraph revision;
- MasterPlanGraph revision;
- TaskGraph state;
- integration/verification observation refs;
- repository/architecture observation summaries from later Parts.

Drift classes:
- `ORPHAN_TASK` — task has no valid plan link;
- `MISSING_TASK` — executable plan node has no task;
- `REQUIREMENT_UNCOVERED` — active requirement has no plan coverage;
- `DEPENDENCY_DRIFT` — task/plan dependency mismatch;
- `COMPLETION_DRIFT` — plan says done but required task/evidence incomplete;
- `STALE_PLAN_NODE` — superseded requirement still drives active plan;
- `VERIFICATION_GAP` — completion lacks required verification evidence.

Reconciliation emits findings; it does not silently repair authority. Planning Chief applies evidence-backed amendments.

## 6. Critical path and readiness

Part III provides deterministic graph analysis:
- topological ordering;
- ready nodes based on predecessor completion;
- longest dependency depth / critical-path proxy without inventing task durations;
- blocked-node explanation;
- milestone completion coverage;
- risk-weighted attention ordering.

No fabricated time estimate is derived unless explicit duration evidence exists.

## 7. Semantic plan delta

A delta between accepted plan revisions records:
- nodes added/removed/superseded;
- changed dependencies;
- changed requirement coverage;
- milestone changes;
- risk changes;
- affected task ids;
- reason/evidence.

Context Compiler consumes this object instead of replaying all plan history.

## 8. Direct Chief work

Part I already requires Chiefs to work directly. Part III adds bounded acceptance scenarios:
- Requirements Chief personally resolves an ambiguous multi-constraint requirement set and authors a verified revision;
- Planning Chief personally repairs a dependency/risk plan and authors a verified revision.

Direct-work receipts continue to use Part-I `chief_direct_work`/artifact/event authority rather than a separate manager-only path.

## 9. Runtime integration

Part III introduces two focused aggregates:
- `RequirementsControlPlane`;
- `PlanningControlPlane`.

`OrganizationRuntime` serializes them under `requirements` and `planning` when present. Their state is reconstructed against the already-restored registry, authority, ledger and task graph.

Part III does not require Part II Central internals. Central observes the new state through ordinary authoritative runtime/world-state mechanisms after integration.

## 10. Event vocabulary additions

Add typed events only where Part I lacks a precise event:
- `REQUIREMENT_AMBIGUITY`
- `REQUIREMENT_CHANGE_PROPOSED`
- `REQUIREMENT_CHANGED`
- `ACCEPTANCE_GAP`
- `PLAN_RECONCILIATION_FINDING`
- `PLAN_ROLLED_BACK`

Existing `PLAN_GAP_DETECTED`, `PLAN_CHANGE_PROPOSED`, `PLAN_AMENDED`, task and verification events remain canonical.

## 11. Fail-closed rules

- non-owner authoritative requirement/plan write -> reject;
- empty mutation reason/evidence -> reject;
- requirement or plan dependency cycle -> reject with no partial mutation;
- unknown requirement/plan/task reference -> reject;
- plan completion without linked acceptance/verification requirements -> cannot be promoted to authoritative done;
- rollback does not delete later history;
- reconciliation finding is evidence, not an automatic mutation;
- restore with non-canonical revisions/digests/counters -> reject.

## 12. Test strategy

Contract suites cover:
- requirement revision ownership and provenance;
- acceptance criteria and ambiguity flow;
- plan DAG cycle rejection and exact rollback;
- requirement->plan->task traceability;
- `PLAN_GAP_DETECTED` -> authoritative revision -> affected context delta;
- deterministic ready/critical-path analysis;
- injected drift detection;
- direct Requirements/Planning Chief work receipts;
- snapshot/restore exactness;
- Part-I regressions.

## Acceptance boundary

Part III establishes bounded requirements/planning intelligence and governance. It does not prove open-world program management or AGI. External performance claims remain subject to Part XV.
