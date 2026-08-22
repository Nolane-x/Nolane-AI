# Nolane Central Part II — Design Specification

## Status and authority

This specification formalizes GitHub Issue #130 on top of the accepted Part-I organizational substrate. It does not claim AGI, frontier equivalence, or unrestricted autonomy. All capability claims remain bounded by executable evidence.

## Goal

Implement `nolane.central` as the strongest global working identity in the first-generation organization. Central must coordinate the organization, maintain replayable global state, directly intervene on any permanent agent, allocate bounded resources, resolve cross-region conflicts, and also perform bounded technical work itself. It must not degrade into a router.

## Design choice

Three approaches were considered:

1. **God-object Central runtime** — place all global logic inside `OrganizationRuntime`. Simple initially, but couples global cognition to every Part-I subsystem and becomes untestable.
2. **Prompt/controller-only Central** — add policies around existing methods with no durable state. Small, but fails restart/replay, resource accounting, conflict governance, and direct-work evidence requirements.
3. **Central control plane + direct-worker kernel** — chosen. Add focused Central components with explicit immutable records, attach them to `OrganizationRuntime`, and preserve Part-I stores as the authoritative substrate.

The chosen design keeps Central powerful without duplicating memory, event, authority, artifact, verification, or evolution systems.

## Components

### 1. `CentralCapabilityMap`

Maintains an evidence-linked view of each region and agent:
- declared capabilities and tool/core bindings;
- current status and task;
- latest health observations;
- evidence references supporting capability/health changes;
- availability and readiness score represented as bounded integers, never free-form self-ratings.

Rebuilds deterministically from registry plus persisted observations.

### 2. `CentralResourceArbiter`

Tracks bounded resource pools such as compute, concurrent-agent slots, tool-call budget, and high-cost external-core budget.

Every allocation is represented by a receipt containing:
- allocation id;
- actor (`nolane.central` only in Part II);
- beneficiary identity/region;
- resource name;
- amount;
- reason;
- evidence references;
- predecessor remaining budget;
- resulting remaining budget.

Rules:
- allocations cannot exceed available budget;
- negative/zero allocations are rejected;
- release cannot exceed the amount currently leased;
- state is replayable through snapshot/restore;
- resource decisions are auditable artifacts/events.

### 3. `CentralInterventionEngine`

Provides explicit actions:
`QUESTION`, `CORRECT`, `REDIRECT`, `PAUSE`, `ABORT`, `REQUEST_EVIDENCE`.

It uses the Part-I typed event ledger. Direct delivery goes to the target identity and the affected Regional Chief sees the exact same authoritative event through region subscription. `PAUSE` and `ABORT` additionally modify target/task state through existing registry/task authority rather than hidden prompt state.

Interventions require an explicit directive and evidence references for state-changing actions. Questions may carry evidence but do not require it.

### 4. `CentralConflictRegistry`

Creates structured cross-region conflict packets instead of accumulating free-form chat.

A packet contains:
- conflict id;
- submitting agents/regions;
- object references;
- competing claims;
- evidence references per claim;
- affected task/plan/architecture references;
- severity;
- status (`OPEN`, `RESOLVED`, `ESCALATED`);
- resolution decision, rationale, evidence, and resolver.

Resolution by Central is replayable and emits a typed event. If a Verification/Security block exists on the affected authoritative artifact, Central resolution does not erase that block; an explicit Part-I override receipt is still required.

### 5. `CentralWorldState`

A compact reconstructed global view, not a second database. It is generated from:
- agent registry;
- task graph;
- event ledger;
- authority owners/blocks/overrides;
- capability observations;
- resource allocations;
- open conflicts;
- verification state.

A canonical digest proves deterministic reconstruction before and after snapshot/restore.

### 6. `CentralDirectWorker`

Central can personally complete a bounded engineering task. Direct work must produce:
- input task id;
- reasoning/work mode label (not hidden chain-of-thought);
- artifact ids;
- evidence ids;
- verification requirement;
- completion event;
- direct-work receipt.

The API records outputs/evidence, but does not pretend that a language model has solved a real task unless concrete artifacts and verification exist.

### 7. Central tool/core policy

Central keeps its broad generic tools from the first-generation blueprint. It may query the registry to discover specialist external cores, but `can_invoke_external_core()` permits direct invocation only when:
- the core is owned by `nolane.central`, `global-command`, or `shared-governed-core`; or
- an explicit delegated-core lease exists with owner, reason, evidence, expiry token, and bounded call budget.

Region-private cores never become Central-owned merely because Central can observe them.

### 8. Central self-improvement hooks

Part II reuses:
- `SelfModelRegistry` for evidence-backed Central self-model updates;
- `SkillEvolutionEngine` for candidate/personal/regional/global skill lifecycle;
- `VerificationAuthority` for neural champion/challenger promotion and rollback.

No separate Central-only promotion bypass exists.

## Runtime integration

`OrganizationRuntime` gains a `central` aggregate or equivalent focused attributes. Serialization includes Central capability observations, resource state, conflicts, direct-work receipts, and delegated-core leases. `first_generation()` seeds conservative resource limits but no capability claims beyond the registry contract.

## Event additions

Part II may add typed events for:
- `CENTRAL_RESOURCE_ALLOCATED`
- `CENTRAL_RESOURCE_RELEASED`
- `CENTRAL_CONFLICT_OPENED`
- `CENTRAL_CONFLICT_RESOLVED`
- `CENTRAL_DIRECT_WORK`
- `CENTRAL_CORE_LEASE_GRANTED`
- `CENTRAL_CORE_LEASE_REVOKED`

All are canonicalized and replayable.

## Failure handling and fail-closed rules

- Missing evidence on state-changing Central action: reject.
- Resource over-allocation: reject without partial mutation.
- Unknown target/core/resource: reject.
- Region-private core without a valid lease: reject.
- Conflict resolution that encounters an independent block: keep block authoritative unless a separate audited Central override is created.
- Restore with non-canonical counters/digests: reject.
- Direct work without artifact/evidence references: remains incomplete.

## Test strategy

### Contract tests
- Central is still `<100M` physical parameters and has broad generic tools.
- Central cannot directly invoke a private regional core without an explicit lease.
- Direct correction reaches target and affected Chief as the same event id.
- pause/abort state changes are explicit and replayable.
- resource allocation/release enforces exact accounting.
- conflict packet resolution preserves independent blocks.
- Central direct work creates immutable artifact/evidence-linked receipt.
- world-state digest is identical after snapshot/restore.
- Central self-model/skill/neural improvements continue to use Part-I verification gates.

### Adversarial tests
- over-allocation;
- forged/unknown evidence ids where concrete store validation is required;
- lease expiry and exhausted call budget;
- cross-region conflict with contradictory claims;
- attempt to relabel an overridden verification block as successful verification;
- restart while leases/resources/conflicts are active.

## Acceptance boundary

Part II is accepted only as a bounded Central-control and direct-work substrate. It does not establish unrestricted coding AGI. Any stronger claim requires Part XV external evaluation.
