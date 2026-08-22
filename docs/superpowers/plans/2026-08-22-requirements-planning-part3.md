# Requirements & Planning Part III Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build versioned Requirements and Master Plan authorities linked to the operational TaskGraph, with proposal-only worker access, Chief-owned authoritative revisions, drift reconciliation and exact restart.

**Architecture:** Add separate immutable RequirementGraph and MasterPlanGraph stores, then bridge them to the existing TaskGraph through explicit ids. Requirements/Planning control planes perform evidence-gated mutations under Part-I authority; reconciliation produces findings rather than silently mutating state.

**Tech Stack:** Python standard library, dataclasses/enums, existing `cogcoder.organization` runtime, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-22-requirements-planning-part3-design.md`

## Global Constraints

- Requirements authority owner remains `requirements.chief`.
- Master-plan authority owner remains `planning.chief`.
- Non-owner workers may propose but cannot silently mutate authoritative graphs.
- Every accepted revision has parent, actor, reason, evidence refs and canonical digest.
- Requirement and plan dependency cycles fail with no partial mutation.
- Reconciliation findings never auto-authorize a plan/requirement change.
- Part-I task leases, verification, memory, event and authority rules remain intact.

---

### Task 1: Versioned Requirement Graph

**Files:**
- Create: `cogcoder/organization/requirements.py`
- Modify: `cogcoder/organization/types.py`
- Test: `tests/test_coding_agi_requirements_graph.py`

**Produces:** `RequirementKind`, `RequirementStatus`, `AcceptanceCriterion`, `RequirementNode`, `RequirementRevision`, `RequirementGraph`, `RequirementsControlPlane`.

- [ ] Write failing tests that create an initial accepted requirement revision, verify required reason/evidence, reject unknown dependencies/cycles and reject an authoritative write by `coding.backend.01`.
- [ ] Run `python -m pytest -q tests/test_coding_agi_requirements_graph.py` and confirm RED because the module is absent.
- [ ] Implement immutable nodes/criteria/revisions with canonical digest and owner check through `AuthorityGraph.require_write(actor, 'requirements')`.
- [ ] Add proposal methods that emit `REQUIREMENT_AMBIGUITY`, `REQUIREMENT_CHANGE_PROPOSED` or `ACCEPTANCE_GAP` without mutating the graph.
- [ ] Run the test file and require PASS.

Representative ownership contract:

```python
with pytest.raises(PermissionError):
    runtime.requirements.apply_revision(
        actor_agent_id='coding.backend.01',
        reason='silent rewrite',
        evidence_refs=('ev-rq-1',),
        upserts=(requirement,),
    )
```

---

### Task 2: Versioned Master Plan Graph

**Files:**
- Create: `cogcoder/organization/planning.py`
- Test: `tests/test_coding_agi_master_plan.py`

**Produces:** `PlanNodeStatus`, `PlanNode`, `Milestone`, `PlanRisk`, `PlanRevision`, `MasterPlanGraph`.

- [ ] Write failing tests for plan revisions, dependency-cycle rejection, requirement coverage, milestones/risks and rollback history.
- [ ] Verify RED.
- [ ] Implement copy-on-revision graph state; rollback creates a new revision whose source is a prior revision instead of deleting history.
- [ ] Implement deterministic topological order, ready-node calculation and longest dependency depth as critical-path proxy.
- [ ] Run tests and require PASS.

Cycle test must assert graph state is byte-for-byte unchanged after a rejected mutation.

---

### Task 3: Plan-gap application and intent-to-task traceability

**Files:**
- Modify: `cogcoder/organization/planning.py`
- Modify: `cogcoder/organization/tasks.py` only for explicit plan-link metadata if required
- Test: `tests/test_coding_agi_planning_gap_flow.py`

**Produces:** `PlanningControlPlane` methods `apply_gap`, `link_task`, `plan_delta`.

- [ ] Write failing end-to-end test: Backend Coder emits `PLAN_GAP_DETECTED`; Planning Chief applies a revision; affected task receives a valid plan link; `PLAN_AMENDED` records old/new revision and affected task.
- [ ] Verify RED.
- [ ] Implement owner/evidence validation and requirement->plan->task reference checks.
- [ ] Implement semantic delta fields for added/superseded nodes, dependency changes, requirement coverage, milestone/risk changes and affected tasks.
- [ ] Run focused tests plus existing Part-I `test_coding_agi_foundation_tasks_runtime.py`.

---

### Task 4: Reconciliation and direct Chief acceptance scenarios

**Files:**
- Create: `cogcoder/organization/reconciliation.py`
- Test: `tests/test_coding_agi_plan_reconciliation.py`
- Test: `tests/test_coding_agi_requirements_planning_direct_work.py`

**Produces:** `DriftClass`, `ReconciliationFinding`, `PlanReconciler`.

- [ ] Write failing tests injecting orphan tasks, uncovered requirements, dependency drift, completion drift and stale plan nodes.
- [ ] Verify RED.
- [ ] Implement deterministic findings with evidence/object refs and no mutation side effects.
- [ ] Add direct-work scenarios using existing `runtime.chief_direct_work` for Requirements Chief and Planning Chief; each must personally own/complete the task and produce artifacts.
- [ ] Run focused tests and require PASS.

---

### Task 5: Runtime integration, Context delta, snapshot and hosted acceptance

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Modify: `cogcoder/organization/context.py`
- Create: `tests/test_coding_agi_requirements_planning_snapshot.py`
- Create: `tests/test_coding_agi_requirements_planning_context.py`
- Create: `.github/workflows/coding-agi-requirements-planning-part3.yml`

**Runtime interface:**
- `runtime.requirements: RequirementsControlPlane`
- `runtime.planning: PlanningControlPlane`
- `runtime.to_state()` includes exact requirement/plan states;
- `runtime.from_state()` reconstructs them against restored Part-I stores.

- [ ] Write failing snapshot test that applies requirement + plan revisions, captures `OrganizationSnapshot`, restores it and compares exact revisions/digests.
- [ ] Write failing context test proving an agent checkpointed before a plan revision receives only the semantic authoritative delta after waking.
- [ ] Verify RED.
- [ ] Integrate control planes and context sections without replaying full history.
- [ ] Add Python 3.11/3.13 workflow running `tests/test_coding_agi_requirements_*.py`, `tests/test_coding_agi_master_plan.py`, `tests/test_coding_agi_planning_*.py`, `tests/test_coding_agi_plan_reconciliation.py` and all Part-I regression tests.
- [ ] Open a stacked draft PR against the Part-I branch, record RED evidence before implementation, then require GREEN before integration.

## Plan self-review

- Spec coverage: requirement authority, acceptance criteria, versioned plan, DAG analysis, plan-gap flow, reconciliation, semantic delta, direct Chief work and restart all map to tasks.
- Placeholder scan: no TBD/TODO or unspecified implementation step remains.
- Type consistency: Requirements/Planning control-plane names are fixed across tasks.
- Scope: architecture/integration graph behavior remains Part IV; Part III only accepts observation refs from those future systems.
