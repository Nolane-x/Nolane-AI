# Refoundation Epoch 0 — Wave 5H Native Experience Design

## Base
Exact accepted Wave-5G head: `5783e0c1e120152b30bfb0cb98b9128237e4399c`.

## Objective
Move real implementation authority for `external.experience` from `cogcoder.organization.experience` to the existing canonical public module `nolane.memory.experience`.

Complete semantic owner:

- `ExperienceOutcome`
- `LearningLayer`
- `ExperienceRecord`
- `AttributionRecord`
- `ExperienceLedger`

Component revision:

- `external.experience`: `0.0.0 -> 0.0.1`

## Why Experience is the next safe substrate tranche
The Master Spec places experience/self-model in the shared cognitive substrate before Context. At the accepted Wave-5G head:

- `external.knowledge` is still `historical_only` with no dedicated current organization implementation, so native cutover would require reconstruction rather than migration;
- `external.skills` still shares `SkillScope` with the mixed historical types module and therefore needs a broader schema decision;
- `external.experience` depends only on already accepted canonical Identity, Evidence, EventLedger and canonical digest primitives;
- Context remains blocked by Knowledge, Skills, Self-model, Planning and Architecture.

Experience is therefore the smallest active implementation boundary that can move without inventing new semantics.

## Canonical dependency direction
`nolane.memory.experience` must depend on:

- `nolane.organization.identity.AgentRegistry`
- `nolane.organization.events.EventLedger`
- `nolane.external_core.evidence.EvidenceRecord`
- `nolane.core.canonical_digest.canonical_digest`

It must not reverse-import its historical implementation owner.

## Preserved semantics
The cutover must preserve exactly:

- `ExperienceOutcome`: success/failure/mixed;
- `LearningLayer`: episodic/semantic/procedural/strategy/tool_use;
- content-addressed experience IDs from canonical digest payloads;
- identity-owned authoring (`author_agent_id == agent_id`);
- explicit non-empty domain/summary;
- object/evidence reference ordering as accepted;
- idempotent same-record creation and fail-closed ID rebinding;
- per-agent experience listing order;
- attribution lesson non-empty validation;
- verifier identity validation;
- positive attribution only from clean external evidence;
- self-verification rejection when it would create positive attribution;
- negative attribution for failed/regressed/false-accept evidence;
- content-addressed attribution IDs;
- exact `EvidenceRecord` state nesting;
- state round-trip;
- restore rejection when attribution references a missing experience.

## Compatibility contract
Historical `cogcoder.organization.experience` remains present as a compatibility bridge and exports the exact canonical enum/class identities.

No historical file deletion or move is permitted.

## Provenance
Because the historical implementation is a dedicated file rather than a mixed source, pinned inventory may preserve:

`cogcoder/organization/experience.py -> nolane/memory/experience.py`

once facade authority is retired.

## Native debt delta
Expected accepted delta from Wave 5G:

- total non-native: `38 -> 37`;
- `compatibility_facade`: `28 -> 27`;
- `legacy_internal`: stays `2`;
- `historical_only`: stays `7`;
- `frozen_asset`: stays `1`.

## TDD gates
RED must prove accepted behavior first and fail only because:

1. `external.experience` remains a facade/version `0.0.0`;
2. canonical class/enum ownership remains historical;
3. canonical module reverse-imports the historical owner;
4. pinned canonical destination is not yet authoritative after facade retirement;
5. debt remains 38 instead of 37.

GREEN must additionally prove:

- canonical owner/version/write authority;
- all five historical symbols resolve to exact canonical identities;
- no historical implementation reverse import;
- canonical dependencies point to accepted owners;
- behavior/state parity;
- inventory provenance;
- debt exactly 37 with expected categories;
- no tracked bytecode;
- no temporary write-enabled Wave-5H workflow before acceptance;
- full hosted Refoundation gate green on Python 3.11 and 3.13.

## Out of scope
- Knowledge reconstruction;
- SkillScope/Skills migration;
- Self-model migration;
- Context/Planning/Architecture migration;
- Coding legacy-internal migration;
- historical deletion/move;
- Neural changes.
