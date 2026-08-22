# Multi-Agent Coordination Part XIII — Design Specification

## Status

Implements Issue #141 on accepted Parts I–XII.

Part XIII coordinates 67 durable permanent AI identities without turning the organization into 67 chat threads and without making Nolane Central a single context bottleneck. It composes the existing `EventLedger`, `TaskGraph`, `WakeSleepScheduler`, `AuthorityGraph`, `AgentRegistry`, Context Compiler and Part-XI semantic-delta machinery. Those primitives remain authoritative; Part XIII adds coordination governance around delivery, leasing, acknowledgement, cross-region conflict reduction, wake budgeting and deterministic recovery.

## 1. Architectural laws

1. Important coordination state is typed, content-addressed and replayable; raw chat is not an authoritative coordination channel.
2. Event order is logical and deterministic. Restart must reproduce the same accepted coordination state from the same snapshot.
3. A task has at most one destructive work lease at a time.
4. Lease transfer is explicit, evidenced and versioned; stale holders cannot complete work after transfer or revocation.
5. Sleeping is the default operating state. Events wake only relevant recipients subject to declared concurrency budgets.
6. Direct Central correction reaches the target without Regional Chief permission, while the Chief observes the same authoritative event.
7. Cross-region disagreement becomes a structured conflict packet with claims, evidence and authority ownership; it must not accumulate as unbounded conversational history.
8. No agent may silently mutate another region's authoritative artifact. Cross-region agents propose; the authoritative owner or explicit Central override decides.
9. Required acknowledgements are tracked explicitly. Missing acknowledgements become stale or escalation state rather than being assumed successful.
10. Duplicate, missing or out-of-order delivery metadata must fail closed or reconcile idempotently.
11. Coordination overhead is measured against deterministic workload budgets.
12. Part XIII is a coordination subsystem, not evidence that the system is AGI or that multi-agent behavior is globally optimal.

## 2. Recommended architecture: coordination overlay

Part XIII introduces `CoordinationControlPlane` rather than rewriting the core primitives.

Dependencies:
- `AgentRegistry` — identity, region, status and current-task truth;
- `EventLedger` — canonical event sequence, causal parents, typed payloads and subscriptions;
- `TaskGraph` — task lifecycle and underlying single-holder lease truth;
- `AuthorityGraph` — authoritative artifact owner and Central override truth;
- `WakeSleepScheduler` — checkpoint/wake primitives;
- Context/Part-XI delta — semantic resume context;
- `ArtifactStore` — evidence/artifact references where needed.

Part XIII owns only coordination-specific state:
- lease epochs and receipts;
- delivery/acknowledgement receipts;
- conflict packets and resolutions;
- wake reservations and resource budget counters;
- stale-agent/escalation records;
- replay checkpoints and coordination metrics.

## 3. Typed coordination events

Part XIII extends `EventKind` with:
- `TASK_LEASE_GRANTED`
- `TASK_LEASE_RENEWED`
- `TASK_LEASE_REVOKED`
- `COORDINATION_ACK`
- `COORDINATION_ESCALATED`
- `CONFLICT_OPENED`
- `CONFLICT_CLAIM_ADDED`
- `CONFLICT_RESOLVED`
- `WAKE_RESERVED`
- `WAKE_DEFERRED`
- `STALE_AGENT_DETECTED`

All new events use `EventLedger.append()` and inherit canonical logical sequence, digest, causal parents and deterministic serialization. Part XIII does not create a second event bus.

## 4. Delivery receipts and acknowledgement protocol

`DeliveryReceipt` records one event for one recipient: delivery id, event id, recipient id, source sequence, delivered logical token, requires-ack flag, status (`NOT_REQUIRED`, `PENDING`, `ACKED`, `ESCALATED`), optional ack event id and canonical digest.

Delivery is idempotent by `(event_id, recipient_agent_id)`. Re-delivery returns the same receipt.

ACK is accepted only when the event required ACK, the acknowledging agent is the receipt recipient, the original event still has the same digest, and the receipt has not already been incompatibly acknowledged or escalated. `COORDINATION_ACK` uses the original event as causal parent.

## 5. Task lease epochs

`TaskGraph.leased_to` remains underlying ownership truth. Part XIII adds epoch tokens so stale holders cannot complete after transfer.

`TaskLeaseReceipt` contains lease id, task id, agent id, monotonically increasing task epoch, status (`ACTIVE`, `REVOKED`, `COMPLETED`, `EXPIRED`), grant event id, optional superseded lease id, evidence refs, heartbeat token, stale-after budget, renewal count and canonical digest.

Rules:
- at most one ACTIVE lease per task;
- first grant calls `TaskGraph.lease()`;
- duplicate grant to current holder is idempotent;
- transfer requires explicit revocation then a new epoch;
- completion requires current `TaskGraph.leased_to`, current active lease id and current epoch;
- stale/revoked epochs cannot complete;
- Central may revoke any lease with explicit reason/evidence;
- a Regional Chief may revoke only agents in its own region;
- specialists cannot revoke another agent's lease.

## 6. Lease renewal and staleness

Liveness uses logical tokens, not wall-clock time. `heartbeat_lease()` accepts only current holder/current epoch. `detect_stale_leases(current_token)` identifies a stale lease when `current_token - last_heartbeat_token >= stale_after_tokens`.

Detection appends `STALE_AGENT_DETECTED` and creates escalation state. It never silently transfers work. Reassignment still requires revocation + new epoch.

## 7. Cross-region conflict packets

`ConflictPacket` reduces multi-region disagreement into structured state. It contains conflict id, subject artifact id, authoritative owner from `AuthorityGraph`, opener, status (`OPEN`, `READY_FOR_DECISION`, `RESOLVED`, `ESCALATED`), ordered claim ids, causal event ids, optional resolution and canonical digest.

`ConflictClaim` contains claim id, claimant id/region, proposition, evidence refs, requested action and digest.

Rules:
- a claim never directly writes the artifact;
- cross-region claimants may propose without write authority;
- non-Central resolution requires `AuthorityGraph.require_write(resolver, subject_artifact_id)`;
- Central resolution uses normal authority or an explicit override receipt when blocks exist;
- resolved packets are immutable except through a later superseding conflict;
- identical claims by the same claimant are idempotent.

## 8. Direct Central correction + Chief reconciliation

For a Central correction/intervention targeting a regional specialist:
1. target receives a delivery receipt;
2. Regional Chief receives a delivery receipt for the exact same event id/digest;
3. Chief is an observer/reconciler, not an approval gate;
4. target ACK cannot replace Chief visibility;
5. unacknowledged required deliveries escalate without duplicating the source event.

For Central actions targeting a Chief, only that Chief is mandatory unless subscriptions add more recipients.

## 9. Relevant-agent wake planning

Part XIII adds deterministic `WakeBudget` and `WakeReservation`.

Default normal budget:
- `max_active_agents = 8`;
- `max_region_active_agents = 4`;
- Central may reserve one global slot.

Explicit high-severity mode may raise organization ceiling to `18`, matching the accepted architecture envelope, only through recorded configuration.

`plan_wakes(event_id)` candidates come from direct target, canonical subscriptions, mandatory Chief observer for Central regional interventions, and conflict owner/participants where applicable.

Ordering: event priority descending, direct target before subscription-only, coordination authority rank, then lexical agent id. ACTIVE agents consume no new reservation. Sleeping candidates receive reservations until budget exhaustion; excess candidates receive `WAKE_DEFERRED` records and remain sleeping. Existing scheduler performs actual wake.

## 10. Backpressure and priority

`CoordinationBudget` records max active agents, max active per region, max pending ACKs, max unresolved conflicts and max coordination events per workload window.

Limits never drop canonical events. High-priority Central/security/verification blockers may preempt lower-priority deferred wake reservations. Ordinary work is deferred. Pending-ACK/conflict/event-budget overflow creates `COORDINATION_ESCALATED` state.

## 11. Coordination metrics

For a declared workload window, `CoordinationMetrics` reports source workload event count, coordination-generated event count, delivery/ACK counts, wake reservation/defer counts, lease transitions, open/resolved conflicts, peak active agents and `coordination_event_ratio = generated / max(1, source)`.

Part-XIII normal synthetic acceptance budget:
- coordination event ratio `<= 6.0`;
- peak active agents `<= 8`;
- no more than one active lease per task;
- no replay dependency on raw chat history.

The ratio is a bounded engineering test budget, not a universal scaling claim.

## 12. Deterministic replay and restart

Runtime state adds `coordination` with backward-compatible default `{}`.

Snapshot preserves lease receipts/epochs, heartbeat metadata, delivery/ACK receipts, conflicts/claims/resolutions, wake reservations/deferrals, budgets, metrics and escalations.

Restore fails closed if two ACTIVE leases exist for one task, current lease disagrees with `TaskGraph.leased_to`, delivery references unknown event, ACK recipient/source mismatches, conflict resolution lacks authority evidence, ids/counters are non-canonical, or any receipt digest mismatches.

Old snapshots without `coordination` restore empty Part-XIII history while deriving currently leased TaskGraph tasks as epoch-1 compatibility leases.

## 13. Duplicate, lost and out-of-order handling

Part XIII never mutates EventLedger order.

- duplicate delivery => same receipt;
- causal child delivered before required parent => defer/fail closed until parent delivery exists for that recipient;
- lost delivery metadata => `reconcile_delivery(event_id)` rebuilds deterministic receipts from EventLedger/subscriptions;
- fabricated event id => reject;
- identical duplicate ACK => idempotent;
- mismatching ACK => reject.

## 14. Authority-safe cross-region proposals

`propose_cross_region_change()` always creates a structured conflict/proposal; it never writes the artifact. The authoritative owner receives delivery/wake candidacy. Only owner or Central may resolve into an authoritative change using existing ownership/override mechanisms.

Acceptance must demonstrate a coding specialist can propose a data-state migration change but cannot mutate `data-state`, while `data.chief` can resolve the packet.

## 15. Stale-agent escalation

`StaleAgentReceipt` records agent, task/lease, detection token, last heartbeat token, Regional Chief, escalation recipients and status.

Routes:
- stale specialist => Chief; Central joins for severe/continued stale state;
- stale Chief => Central;
- stale Central => organization-level recorded escalation only.

Part XIII may pause new lease grants to stale holders but does not quarantine neural weights or erase learning state.

## 16. Runtime integration

`OrganizationRuntime` gains `coordination: CoordinationControlPlane`. It is constructed from registry, ledger, authority, tasks and scheduler, plus existing state needed for integration. `to_state()` adds `coordination`; `from_state()` restores via `state.get('coordination', {})`.

Part XIII must not change Part-XII learning ownership, Part-XI memory visibility, Part-VIII verification authority or Part-II Central authority semantics.

## 17. Test surface

RED contracts:
- `tests/test_coding_agi_coordination_leases.py`
- `tests/test_coding_agi_coordination_delivery.py`
- `tests/test_coding_agi_coordination_conflicts.py`
- `tests/test_coding_agi_coordination_wake_budget.py`
- `tests/test_coding_agi_coordination_replay.py`
- `tests/test_coding_agi_coordination_authority.py`
- `tests/test_coding_agi_coordination_metrics.py`

Matrix CI uses Python 3.11 and 3.13, compiles `cogcoder/organization/*.py`, then runs all Part-XIII tests and all prior organization regressions Parts I–XII.

## 18. Adversarial acceptance

Explicitly test racing task leases, stale epoch completion, duplicate delivery/ACK, wrong-agent ACK, causal child before parent, lost delivery reconciliation, fabricated event id, Central direct-to-specialist correction with same-event Chief visibility, Chief suppression attempt, cross-region unauthorized write, unresolved conflict budget overflow, >8 normal wake candidates, per-region wake overflow, stale specialist/Chief escalation, corrupt snapshot with double lease, corrupt ACK recipient, exact replay equality and coordination ratio budget breach.

## 19. Acceptance gates

Part XIII is accepted only after:
1. RED contracts fail because Part-XIII production module/runtime integration do not exist;
2. RED is reproduced on Python 3.11 and 3.13 while Parts I–XII package compilation remains clean;
3. GREEN exact head passes Part XIII on Python 3.11 and 3.13;
4. the same head passes prior organization workflows Parts I–XII;
5. one task cannot have two active leases and stale epochs cannot complete;
6. Central target and Regional Chief observe the exact same canonical event;
7. cross-region conflicts reduce into packets and unauthorized writes fail closed;
8. normal wake peak remains <=8 and excess work is deferred rather than dropped;
9. duplicate/lost/out-of-order delivery reconciles deterministically or fails closed;
10. snapshot/restore is exact and rejects corrupt coordination state;
11. normal synthetic workload remains within declared coordination-overhead budget.

Part XIII establishes bounded, replayable and testable coordination semantics. It does not claim that 67 agents are always more effective than fewer agents.