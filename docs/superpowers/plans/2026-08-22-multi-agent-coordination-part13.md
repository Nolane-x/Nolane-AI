# Multi-Agent Coordination Part XIII Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic, bounded multi-agent coordination for all 67 permanent identities using lease epochs, typed delivery/ACK receipts, conflict packets, wake/backpressure budgets, stale-agent escalation and exact replay.

**Architecture:** Keep `EventLedger`, `TaskGraph`, `WakeSleepScheduler` and `AuthorityGraph` authoritative. Add focused Part-XIII modules for lease state, delivery state and conflict state, then compose them in `CoordinationControlPlane`; runtime snapshot/restore owns only the overlay state.

**Tech Stack:** Python 3.11/3.13, stdlib dataclasses/enums/typing, canonical digest helpers already in `cogcoder.organization.types`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-22-multi-agent-coordination-part13-design.md`

## Global Constraints

- Preserve accepted Parts I–XII semantics and source-of-truth ownership.
- No second event bus; all coordination events append through `EventLedger`.
- One ACTIVE destructive lease per task.
- Normal first-generation wake ceiling is 8 organization-wide and 4 per region; explicit high-severity ceiling is 18.
- Never silently drop canonical events under backpressure.
- Cross-region proposals never write authoritative artifacts.
- Snapshot/restore must be deterministic and backward-compatible with state lacking `coordination`.
- Python matrix is exactly 3.11 and 3.13.

---

## File map

- Create `cogcoder/organization/coordination_leases.py`: immutable lease receipts, epoch ownership, heartbeats and stale detection.
- Create `cogcoder/organization/coordination_delivery.py`: per-recipient delivery receipts, ACKs, idempotence and causal-delivery validation.
- Create `cogcoder/organization/coordination_conflicts.py`: conflict packets, claims and authority-checked resolutions.
- Create `cogcoder/organization/coordination.py`: orchestration, wake budgets/reservations, Central+Chief delivery semantics, metrics, escalation and state composition.
- Modify `cogcoder/organization/types.py`: add Part-XIII typed event kinds only.
- Modify `cogcoder/organization/runtime.py`: construct/persist/restore `CoordinationControlPlane` and route Central interventions through coordination delivery notifications additively.
- Add seven focused Part-XIII test files.
- Add `.github/workflows/coding-agi-multi-agent-coordination-part13.yml`.

---

### Task 1: RED lease-epoch contracts

**Files:**
- Test: `tests/test_coding_agi_coordination_leases.py`
- Create later: `cogcoder/organization/coordination_leases.py`

**Interfaces:**
- Produces `TaskLeaseReceipt`, `StaleAgentReceipt`, `LeaseCoordinator`.
- `LeaseCoordinator(registry, tasks, events)`.
- `grant(task_id, agent_id, *, token=0, stale_after_tokens=3, evidence_refs=()) -> TaskLeaseReceipt`.
- `heartbeat(task_id, agent_id, *, lease_id, epoch, token) -> TaskLeaseReceipt`.
- `revoke(task_id, actor_agent_id, *, reason, evidence_refs=()) -> TaskLeaseReceipt`.
- `complete(task_id, agent_id, *, lease_id, epoch, output_artifact_ids=()) -> TaskRecord`.
- `detect_stale(current_token) -> tuple[StaleAgentReceipt, ...]`.

- [ ] **Step 1: Write failing tests** locking single ACTIVE lease, idempotent duplicate grant, explicit revoke-before-transfer, monotonic epoch, stale-holder completion rejection, Central revoke-anywhere, Chief revoke-own-region only, specialist revoke rejection and deterministic state round-trip.
- [ ] **Step 2: Run only lease tests.** Expected RED: module import failure because `coordination_leases` does not exist.
- [ ] **Step 3: Do not implement yet. Commit RED with all Part-XIII contracts together after Tasks 1–7.**

### Task 2: RED delivery/ACK and Central-Chief visibility contracts

**Files:**
- Test: `tests/test_coding_agi_coordination_delivery.py`
- Create later: `cogcoder/organization/coordination_delivery.py`

**Interfaces:**
- Produces `AckStatus`, `DeliveryReceipt`, `DeliveryCoordinator`.
- `DeliveryCoordinator(registry, events)`.
- `deliver(event_id, recipient_agent_id) -> DeliveryReceipt`.
- `acknowledge(delivery_id, agent_id) -> DeliveryReceipt`.
- `require_causal_ready(event_id, recipient_agent_id) -> None`.
- `to_state()/from_state()` validate event ids, digests and recipient coherence.

- [ ] **Step 1: Write tests** for duplicate-delivery idempotence, correct ACK, wrong-agent ACK rejection, duplicate ACK idempotence, fabricated event rejection, causal child-before-parent failure and state corruption rejection.
- [ ] **Step 2: Add an integration test** proving one Central correction event creates delivery receipts for both target specialist and exact Regional Chief with identical event id/digest; Chief cannot suppress target delivery.
- [ ] **Step 3: Run test file.** Expected RED import failure.

### Task 3: RED cross-region conflict governance contracts

**Files:**
- Test: `tests/test_coding_agi_coordination_conflicts.py`
- Test: `tests/test_coding_agi_coordination_authority.py`
- Create later: `cogcoder/organization/coordination_conflicts.py`

**Interfaces:**
- Produces `ConflictStatus`, `ConflictClaim`, `ConflictPacket`, `ConflictResolutionReceipt`, `ConflictCoordinator`.
- `open(opener_agent_id, subject_artifact_id, *, proposition, requested_action, evidence_refs=(), causal_event_ids=()) -> ConflictPacket`.
- `add_claim(conflict_id, claimant_agent_id, *, proposition, requested_action, evidence_refs=()) -> ConflictClaim`.
- `resolve(conflict_id, resolver_agent_id, *, decision, evidence_refs, override_id=None) -> ConflictResolutionReceipt`.

- [ ] **Step 1: Test** coding specialist proposal against `data-state` creates a packet but `AuthorityGraph.require_write()` still rejects coder.
- [ ] **Step 2: Test** `data.chief` can resolve, unrelated Chief cannot, Central can resolve through existing authority, and blocked state requires explicit Central override receipt.
- [ ] **Step 3: Test** identical claims are idempotent and resolved packets reject mutation.
- [ ] **Step 4: Run both files.** Expected RED import failure.

### Task 4: RED wake budget/backpressure contracts

**Files:**
- Test: `tests/test_coding_agi_coordination_wake_budget.py`
- Create later: `cogcoder/organization/coordination.py`

**Interfaces:**
- Produces `CoordinationBudget`, `WakeReservation`, `WakeDisposition`, `CoordinationControlPlane.plan_wakes()` and `execute_wakes()`.
- Normal defaults: organization 8, per-region 4, high-severity 18.

- [ ] **Step 1: Test** a fan-out event with >8 sleeping candidates yields at most 8 RESERVED and remaining DEFERRED without changing deferred agents to ACTIVE.
- [ ] **Step 2: Test** per-region cap 4 independently of global spare capacity.
- [ ] **Step 3: Test** deterministic ordering by direct-target, rank and lexical id and that ACTIVE recipients do not consume new reservations.
- [ ] **Step 4: Test** explicit high-severity mode permits up to 18 but default mode never does.
- [ ] **Step 5: Run file.** Expected RED import failure.

### Task 5: RED stale escalation and coordination metrics

**Files:**
- Test: `tests/test_coding_agi_coordination_metrics.py`

**Interfaces:**
- `CoordinationMetrics` exposes `source_workload_events`, `generated_coordination_events`, delivery/ack/wake/lease/conflict counts, `peak_active_agents`, `coordination_event_ratio`.
- `CoordinationControlPlane.metrics()` returns a frozen deterministic snapshot.
- `CoordinationControlPlane.escalate_stale(current_token)` returns stale receipts and appends escalation events.

- [ ] **Step 1: Test** stale specialist routes to Regional Chief and severe continuation includes Central; stale Chief routes to Central.
- [ ] **Step 2: Test** normal synthetic workload ratio `<= 6.0` and peak active `<=8`.
- [ ] **Step 3: Test** a deliberately tiny configured coordination-event budget emits escalation rather than dropping source events.
- [ ] **Step 4: Run file.** Expected RED import failure.

### Task 6: RED replay/reconciliation contracts

**Files:**
- Test: `tests/test_coding_agi_coordination_replay.py`

**Interfaces:**
- `CoordinationControlPlane.reconcile_delivery(event_id) -> tuple[DeliveryReceipt, ...]`.
- `to_state()/from_state()` exact round-trip.

- [ ] **Step 1: Test** exact runtime snapshot/restore equality after lease, delivery, ACK, conflict and wake-defer history.
- [ ] **Step 2: Test** old runtime state without `coordination` derives epoch-1 compatibility leases from `TaskGraph` and no fabricated historical ACK/conflict state.
- [ ] **Step 3: Test** corrupt snapshots: two active leases, TaskGraph mismatch, unknown delivery event, wrong ACK recipient and digest mismatch all fail closed.
- [ ] **Step 4: Test** lost delivery metadata can be deterministically reconstructed from canonical EventLedger/subscriptions.
- [ ] **Step 5: Run file.** Expected RED import/runtime-integration failure.

### Task 7: RED CI and prior-Part matrix

**Files:**
- Create: `.github/workflows/coding-agi-multi-agent-coordination-part13.yml`

- [ ] **Step 1: Add workflow** triggered by Part-XIII branch and PR paths.
- [ ] **Step 2: Matrix** Python `3.11` and `3.13`.
- [ ] **Step 3: Compile** `python -m py_compile cogcoder/organization/*.py`.
- [ ] **Step 4: Run** `tests/test_coding_agi_coordination_*.py`, then Part-XII evolution tests and the exact prior organization suites used by Part XII for Parts I–XI.
- [ ] **Step 5: Commit spec + plan + all tests + workflow as the RED head.**
- [ ] **Step 6: Open draft PR and capture both Python RED logs.** Expected package compile success followed by missing Part-XIII module/runtime failures.

### Task 8: GREEN lease and delivery primitives

**Files:**
- Create: `cogcoder/organization/coordination_leases.py`
- Create: `cogcoder/organization/coordination_delivery.py`
- Modify: `cogcoder/organization/types.py`

- [ ] **Step 1: Add EventKind members** exactly as listed in the spec.
- [ ] **Step 2: Implement immutable lease receipts** with canonical payload/digest validation and per-task epoch index.
- [ ] **Step 3: Implement grant/heartbeat/revoke/complete/stale detection** against authoritative TaskGraph and AgentRegistry.
- [ ] **Step 4: Implement delivery receipts/ACKs** using EventLedger as sole source and idempotence keys.
- [ ] **Step 5: Implement causal-delivery gate** requiring parent delivery for the same recipient before child processing.
- [ ] **Step 6: Run lease + delivery tests until GREEN, then run Parts I–XII regression subset affected by `types.py`, tasks and scheduler semantics.**

### Task 9: GREEN conflict governance

**Files:**
- Create: `cogcoder/organization/coordination_conflicts.py`

- [ ] **Step 1: Implement packet/claim/resolution immutable records with digest validation.**
- [ ] **Step 2: Resolve through AuthorityGraph only; do not mutate artifact state inside the conflict module.**
- [ ] **Step 3: Enforce explicit override id when blocked Central resolution requires one.**
- [ ] **Step 4: Run conflict + authority tests and existing authority/architecture/integration regressions.**

### Task 10: GREEN coordination orchestration, wakes, metrics and runtime

**Files:**
- Create: `cogcoder/organization/coordination.py`
- Modify: `cogcoder/organization/runtime.py`

**Interfaces:**
- `CoordinationControlPlane(registry, events, authority, tasks, scheduler, *, leases=None, deliveries=None, conflicts=None, budget=None, state...)`.
- `deliver_event(event_id)` computes mandatory recipients and returns receipts.
- `plan_wakes(event_id, mode='normal')` returns deterministic reservations/defer records.
- `execute_wakes(event_id)` invokes existing scheduler only for RESERVED sleeping recipients.
- `propose_cross_region_change(...)` wraps conflict open/add-claim only.
- `metrics()` returns deterministic snapshot.

- [ ] **Step 1: Implement budgets/reservations/backpressure and deterministic ordering.**
- [ ] **Step 2: Implement Central target+Chief mandatory-recipient rule without altering the canonical Central source event.**
- [ ] **Step 3: Implement stale escalation routing.**
- [ ] **Step 4: Wire runtime construction and add `coordination` to snapshot/restore with safe old-state default.**
- [ ] **Step 5: Keep existing `central_intervene()`/`central_action()` behavior additive; after source event creation call coordination delivery/wake planning, never require Chief approval.**
- [ ] **Step 6: Run all seven Part-XIII test files.**

### Task 11: Exact-head GREEN and independent regression evidence

- [ ] **Step 1: Commit production GREEN candidate without changing RED contracts except proven fixture bugs.**
- [ ] **Step 2: Wait for exact candidate SHA matrix on Python 3.11 and 3.13.**
- [ ] **Step 3: Read failure logs; fix only demonstrated defects and repeat with a new exact SHA if needed.**
- [ ] **Step 4: Require Part-XIII workflow GREEN on both Python versions.**
- [ ] **Step 5: Require independent organization workflows Parts I–XII GREEN on the same exact head.**
- [ ] **Step 6: Compare branch to base and verify no unexpected files/deletions.**

### Task 12: PR acceptance and merge

- [ ] **Step 1: Update PR body with RED exact head, GREEN exact head, matrix evidence and explicit legacy-workflow exclusions.**
- [ ] **Step 2: Re-read Issue #141 and map every acceptance gate to tests/evidence.**
- [ ] **Step 3: Mark PR ready only when mergeable and exact-head organization gates are green.**
- [ ] **Step 4: Merge with `expected_head_sha` to prevent head drift.**
- [ ] **Step 5: Verify PR state `closed + merged` and `main` points at returned merge commit.**
- [ ] **Step 6: Close Issue #141 with `state_reason=completed` only after post-merge receipt is confirmed.**

## Self-review result

- Spec coverage: every Issue #141 gate maps to Tasks 1–12.
- Placeholder scan: no TBD/TODO/"implement later" placeholders are present.
- Type consistency: lease, delivery, conflict and control-plane method names are defined once and reused consistently.
- Scope: Part XIII remains one coordination subsystem; ephemeral specialist foundry remains Part XIV and is intentionally excluded.