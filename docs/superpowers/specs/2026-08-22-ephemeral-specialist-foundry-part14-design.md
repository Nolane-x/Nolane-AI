# Part XIV — Ephemeral Specialist Foundry Design

## Status
Approved architectural design for Issue #142. This subsystem extends the accepted Parts I–XIII organization without changing the permanent 67-identity blueprint.

## Goal
Allow Nolane Central and Regional Chiefs to spawn bounded, task-scoped temporary experts for unusually deep work while preserving permanent authority, memory, verification, evolution, and coordination invariants.

## Non-goals
- Ephemeral workers are not permanent organization identities and are never inserted into `AgentRegistry`.
- They do not own authoritative artifacts in `AuthorityGraph`.
- They do not write directly into active permanent `MemoryFabric`.
- They do not self-promote skills, neural versions, or self-model competence.
- Foundry use is optional; the permanent organization must work correctly with zero ephemeral workers.

## Design choice
Use a `FoundryControlPlane` overlay rather than extending `AgentRegistry` or creating a peer registry with organization authority. Each temporary worker is a capability-bound execution identity sponsored by a permanent Central/Chief identity. Permanent primitives remain canonical: `AuthorityGraph` owns write authority, `ArtifactStore` owns durable artifacts, Part VIII owns independent assurance, Part XII owns skill promotion, Part XIII owns permanent task/event coordination, and `MemoryFabric` remains the permanent-memory store.

## Module boundaries

### `foundry_profiles.py`
Defines immutable capability templates and ephemeral identity manifests. Templates are capability contracts rather than prompt personas. Initial templates:
- `hypothesis-explorer`
- `repository-archaeologist`
- `fuzz-counterexample`
- `bug-reproducer`
- `migration-compatibility`

Each `EphemeralIdentityManifest` contains:
- `ephemeral_id`
- `team_id`
- `sponsor_agent_id`
- `parent_task_id`
- `template_id`
- `mission`
- `allowed_tools`
- `allowed_external_cores`
- `allowed_artifact_kinds`
- `memory_namespace`
- `generation`
- `created_token`
- `expires_token`
- `digest`

The ID and digest are content-addressed. Retired IDs are never rebound.

### `foundry_resources.py`
Defines hard budgets and immutable usage receipts.

`FoundryBudget` fields:
- `compute_units`
- `tool_calls`
- `external_core_calls`
- `max_workers`
- `lifetime_tokens`

`ResourceUsageReceipt` records one consumption event. Budget counters never go negative; exhaustion fails closed. A worker cannot mutate its own budget.

Default first-generation limits:
- maximum 12 active ephemeral workers organization-wide;
- maximum 4 active ephemeral workers per team;
- maximum 3 active teams per permanent sponsor;
- every spawn has explicit positive compute/tool/core/lifetime budgets.

### `foundry_lifecycle.py`
Defines:
`REQUESTED -> APPROVED -> INSTANTIATED -> ACTIVE -> VERIFYING -> HANDOFF -> RETIRED`

Failure terminal states:
`REJECTED`, `EXHAUSTED`, `QUARANTINED`, `ABORTED`.

Each transition creates a content-addressed `FoundryLifecycleReceipt`. Invalid backward transitions, reactivation after terminal state, or transition by an unauthorized actor fail closed.

Spawn authority:
- `nolane.central` may sponsor any temporary team;
- a Regional Chief may sponsor only a parent task currently leased/bound inside its own region or a task for which it is the direct permanent worker;
- permanent specialists cannot spawn workers directly.

### `foundry_memory.py`
Implements an isolated `EphemeralScratchVault`. Scratch entries are private to an ephemeral identity/team and never call `MemoryFabric.write()`.

Retirement policy:
- `DESTROY`: content is erased; only tombstone metadata/digest remains in state;
- `ARCHIVE_QUARANTINE`: content is retained only in quarantined archival state and is not visible to permanent context retrieval.

Snapshot restore must never resurrect destroyed scratch content.

### `foundry_evidence.py`
Defines durable output and evaluation receipts:
- `FoundryOutputReceipt`
- `FoundryVerificationReceipt`
- `FoundryHandoffReceipt`
- `FoundryBenefitObservation`
- `FoundryBenefitAssessment`

Outputs are stored in `ArtifactStore` using the ephemeral ID as producer provenance. Verification requires a clean external permanent verifier. For engineering-authorizing use, the handoff must reference a Part-VIII `VERIFIED` assurance decision; `PENDING`, `REJECTED`, and `OVERRIDDEN` are not independent verification.

Failed/quarantined output remains provenance-visible but cannot be distilled into active memory or promoted skill.

### `foundry.py`
`FoundryControlPlane` composes profiles, lifecycle, resources, scratch, artifacts, assurance, Part XII evolution, and Part XIII coordination.

Core API:
- `request_spawn(...) -> SpawnRequest`
- `approve_spawn(...) -> SpawnRequest`
- `instantiate(...) -> EphemeralIdentityManifest`
- `activate(ephemeral_id, actor_agent_id) -> FoundryLifecycleReceipt`
- `consume(ephemeral_id, resource_kind, units, actor_agent_id) -> ResourceUsageReceipt`
- `write_scratch(ephemeral_id, text, actor_ephemeral_id) -> ScratchEntry`
- `emit_output(ephemeral_id, kind, content, evidence_refs) -> FoundryOutputReceipt`
- `record_verification(output_id, evidence) -> FoundryVerificationReceipt`
- `handoff(output_id, target_agent_id, assurance_decision_id=None) -> FoundryHandoffReceipt`
- `distill_skill(handoff_id, target_agent_id, name, body) -> SkillRecord`
- `retire(ephemeral_id, actor_agent_id, scratch_policy) -> FoundryLifecycleReceipt`
- `assess_benefit(baseline_id, team_id) -> FoundryBenefitAssessment`

## Authority and containment
1. Ephemeral workers never appear in `AgentRegistry`.
2. `AuthorityGraph.require_write(ephemeral_id, ...)` is never used as a valid path.
3. Foundry output is proposal/evidence until a permanent owner accepts it through normal organization paths.
4. Cross-region changes use Part XIII structured proposal/conflict handoff rather than direct mutation.
5. Sponsor authority does not grant global authority to the temporary worker.
6. A Regional Chief cannot spawn outside its authorized task/region boundary.

## Task and lease semantics
Foundry does not replace Part XIII permanent task leases. Each team is attached to a `parent_task_id` and stores the current permanent lease epoch when instantiated. Output/handoff created after that parent lease is revoked/reassigned is stale and cannot become authoritative or skill-distilled.

A Central-sponsored non-leased diagnostic task may use a synthetic Foundry parent scope only when the explicit spawn request is created by Central; this does not create TaskGraph ownership.

## Evidence and skill distillation
A temporary worker may discover a reusable technique, but Foundry never promotes it directly. `distill_skill()` creates a `SkillScope.CANDIDATE` for a permanent target agent via `SkillEvolutionEngine.propose()`. Part XII then owns verification and Personal/Regional/Global promotion thresholds.

Distillation requires:
- non-terminal-success output;
- clean permanent external verification;
- non-stale parent lease lineage;
- handoff target matching the permanent skill owner;
- no failed/quarantined Foundry state.

## Permanent-memory firewall
Foundry has no generic API that writes temporary observations to `MemoryFabric`. A permanent agent may later create memory from a verified handoff through existing memory governance. Failed/quarantined temporary work therefore cannot poison permanent memory automatically.

## Benefit evaluation
Benefit claims compare one permanent-agent baseline against a permanent+ephemeral-team result under the same declared budget regime digest. A positive `FoundryBenefitAssessment` requires:
- same task/benchmark ID;
- same regime digest;
- clean external evidence for both observations;
- team score strictly higher;
- no increase in false accepts or regressions;
- team resource use not above the matched budget.

Different regimes are incomparable, not improvements.

## Snapshot and restart
`FoundryControlPlane.to_state()` includes templates, spawn requests, manifests, lifecycle receipts, budgets, usage, scratch metadata, durable outputs, verification/handoff receipts, benefit observations, counters, and retired-ID tombstones.

Restore validates every digest, sponsor ID, target permanent ID, artifact reference, lifecycle transition, counter, and budget invariant. Destroyed scratch entries restore as tombstones with no content.

Pre-Part-XIV runtime snapshots use `state.get('foundry', {})` and restore to an empty Foundry. Zero-ephemeral behavior remains the default.

## Runtime integration
Preserve the accepted Part-XIII façade byte-for-byte in `runtime_part13.py`. New `runtime.py` subclasses it, constructs/restores `FoundryControlPlane`, and adds only the `foundry` snapshot key. No changes are required to `runtime_core.py`.

## RED acceptance contracts
Tests must prove before GREEN implementation:
1. only Central/authorized Regional Chief can approve spawn;
2. ephemeral identities are absent from permanent registry;
3. tool/core/artifact scope escalation fails closed;
4. compute/tool/core/lifetime quota exhaustion fails closed;
5. organization/team/sponsor concurrency caps are enforced;
6. ephemeral worker cannot own or directly mutate authoritative artifacts;
7. stale parent lease epoch blocks output handoff/distillation;
8. scratch is isolated and destroyed content never restores;
9. failed/quarantined work cannot write/promote permanent memory/skill;
10. external verification is required and self/sponsor-only verification is insufficient for authorizing handoff;
11. Part-VIII `OVERRIDDEN` is not equivalent to independently `VERIFIED`;
12. skill distillation creates only a candidate for a permanent target and Part XII remains promotion authority;
13. matched-budget benefit requires same regime and no worse false accepts/regressions;
14. runtime snapshot round-trip is exact and old snapshots restore an empty Foundry;
15. permanent organization behavior is unchanged with zero ephemeral workers.

## Capability claim boundary
This subsystem is an engineering mechanism for temporary specialist execution. It is not evidence that the system is AGI, that temporary teams always improve performance, or that more agents are inherently better. Benefit must be measured under matched conditions.