# Neural R2.5 Skill Frontier Authority Design

## Status

W5-guided design for issue #377. The user's standing instruction is to continue without pausing for approval, so this document is the architecture gate before TDD implementation.

## Problem

A request's `ContextCapsule.applicable_skill_ids` is part of `CognitiveStateEncoder.capsule_payload(...)`, therefore it contributes to the request `context_digest` and can influence the model decision. The canonical execution authority fence introduced in #373 and hardened through #374/#376 revalidates `ContextCapsule.authoritative_artifacts` after inference, but the applicable skill set is not currently represented in those artifacts.

The skill set is mutable at runtime. `SkillEvolutionEngine.skills_for(...)` changes when a skill is promoted, quarantined, or otherwise moves into or out of the exact applicable set. In particular, `quarantine(...)` is a canonical public mutation that can revoke a previously applicable skill while `backend.decide(...)` is in progress.

Without an authority binding, a decision can be produced using a skill that was valid at context compilation time, have that skill quarantined before the decision is persisted, and still pass the request-bound authority fence because plan/requirements/architecture/integration/regional component artifacts remain unchanged.

## Existing evidence

The repository already treats the skill frontier as semantically meaningful:

- `ContextCapsule.applicable_skill_ids` is encoded into the inference context digest.
- `ContextDeltaKind.SKILL_CHANGED` exists.
- `ContinuityCheckpoint.skill_frontier_digest` already records the skill frontier across wake/sleep continuity.
- `ContextCompilationReceipt` now exposes every row of `ContextCapsule.authoritative_artifacts` after #376.
- `execution_context_authority` already performs exact post-inference comparison of the captured and live canonical authority artifact tuples.

The missing seam is therefore not a new execution mechanism. It is a missing canonical authority artifact.

## Rival approaches

### H1 — leave skills as freshness only

This is rejected if the decisive RED reproduces stale-decision persistence after mid-inference quarantine. A quarantined skill is revoked decision authority, not merely optional freshness.

### H2 — canonical `skill-frontier` authority artifact

Represent the exact applicable skill set as one deterministic digest row in `ContextCapsule.authoritative_artifacts`:

```text
("skill-frontier", canonical_digest({"skill_ids": [<exact ordered applicable IDs>]}))
```

This is the recommended design. It reuses receipt provenance, verifier integrity, and post-inference execution revalidation with no second authority channel.

### H3 — execution-only skill fence

Store a parallel skill snapshot in `execution_context_authority.py` and compare it after inference. This is rejected unless H2 is falsified because it recreates split authority: the execution fence would know provenance the canonical context receipt does not expose.

## Invariants

1. **Exact applicability authority.** The authority digest is derived only from the exact ordered tuple returned by `SkillEvolutionEngine.skills_for(agent_id, region=...)`.
2. **Single-snapshot compilation.** A compiled `ContextCapsule` must derive both `applicable_skill_ids` and its `skill-frontier` authority row from the same skill snapshot. `compile(...)` must not call `skills_for(...)` a second time to build authority.
3. **Claim-level provenance.** When evolution is configured, `skill-frontier` is present in `authoritative_artifacts` even when the applicable set is empty, so a later promotion changes the request frontier from one explicit digest to another rather than changing schema shape.
4. **Revocation fail-closed.** If the exact applicable skill IDs change during inference, lineage-v2 execution rejects before decision/session/task/workspace persistence.
5. **No overbinding.** Evidence or metadata changes that do not change the exact applicable IDs must not change `skill-frontier`.
6. **No protocol migration.** Do not add fields to `InferenceRequest`, execution sessions, decision receipts, frozen Neural R2.3 metadata, or the public skill record schema.
7. **Receipt continuity.** Because #376 projects all authority artifacts, `ContextCompilationReceipt.authoritative_frontier` must include the exact same `skill-frontier` row automatically and retain exact `to_state`/`from_state` round-trip semantics.
8. **Fallback consistency.** `ContextIntelligenceCompiler._fallback_capsule(...)` also exposes the skill frontier derived from its already-computed applicable skill tuple; fallback capsules must not create weaker provenance than canonical capsules.

## Canonical representation

Add a small shared helper in `nolane.external_core.context`:

```python
def skill_frontier_digest(skill_ids: tuple[str, ...]) -> str:
    return canonical_digest({'skill_ids': list(skill_ids)})
```

The helper accepts already-canonical ordered IDs. It does not inspect mutable runtime state.

`ContextCompiler` obtains the skill tuple exactly once through a private request snapshot helper. That same tuple is used for:

- `ContextCapsule.applicable_skill_ids`;
- the `skill-frontier` authority row.

The private helper also builds the existing plan/requirements/architecture/integration/regional authority rows, so the public `authoritative_artifacts(...)` path and `compile(...)` path share one authority-construction algorithm.

`ContextIntelligenceCompiler._fallback_capsule(...)` computes its existing `skills` tuple once and appends `('skill-frontier', skill_frontier_digest(skills))` to its fallback authority rows.

## Decisive RED

Use the public governed learning path to establish one PERSONAL skill for `memory.chief`:

1. `runtime.evolution.propose(...)`.
2. issue a `LearningEvidenceAuthority` lease and `runtime.evolution.verify(...)` with clean independent evidence.
3. `runtime.learning_substrate.record_skill_validation(...)` with independent regression and causal-ablation families.
4. `runtime.individual_evolution.promote_skill(..., SkillScope.PERSONAL)`.

Start a normal execution for `memory.chief`. In `backend.decide(request)`, call:

```python
runtime.evolution.quarantine(skill.skill_id, reason='revoke skill during inference')
```

then return a valid `WAIT` or `COMPLETE` decision.

The pre-fix implementation is expected to persist the decision instead of raising because none of the current authority artifacts change. The test must assert `PermissionError` and exact no-persistence invariants; this establishes a real RED.

A second focused contract asserts that the compiled capsule and context receipt carry the same `skill-frontier` digest as the exact `applicable_skill_ids`, and that one `skills_for(...)` snapshot is used during compilation.

## Persistence and compatibility

No new state field is introduced. Existing persisted capsules are not a standalone restore schema. `ContextCompilationReceipt.authoritative_frontier` already stores arbitrary `(name, str(value))` rows, so adding `skill-frontier` is an additive authority row, not a receipt-schema migration.

Historical receipts remain readable because `ContextCompilationReceipt.from_state(...)` does not prescribe frontier names.

## Component version discipline

The accepted semantic owner is `external.context`. The canonical context surface advances from implementation/public context version `0.0.4` to `0.0.5` and metadata revision `4` to `5`.

Because fallback support touches the shared `nolane.memory.context_intelligence` helper, repository ownership analysis may additionally require exact +1 revisions for reachable canonical owners. If the hosted `version_discipline_cli` identifies those owners, advance only the exact reported components by one and update their canonical projection sentinels; do not preemptively change independent protocol/surface versions.

This exception is deliberate: repository version discipline is the executable source of truth for transitive helper ownership, as demonstrated by #374/#376.

## Acceptance

The change is acceptable only if all of the following hold:

- hosted RED fails for the intended missing skill-authority reason on Python 3.11 and 3.13;
- minimal GREEN rejects mid-inference quarantine before persistence;
- capsule, receipt, and live post-inference authority agree on the exact skill frontier;
- skill evidence-only changes do not change the frontier when applicability is unchanged;
- exact receipt round-trip remains green;
- External Core version discipline is green;
- Part XI, Memory Learning, Shared Core Acceptance, Runtime Cognition, Execution Result Projection, Execution Decision Lineage, E Acting, Epoch 0, R1.9, and R2.0i are green on the exact final head;
- guarded merge uses the exact verified head SHA;
- every push workflow actually triggered by the merge commit finishes `completed/success` before integrated-complete is claimed.
