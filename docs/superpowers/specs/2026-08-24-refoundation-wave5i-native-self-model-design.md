# Refoundation Epoch 0 — Wave 5I Native Self-model Design

## Parent acceptance
Wave 5I starts from exact hosted-green Wave 5H head `4a260c7957c07a026e9257306ab276ad9c0e2aea` (run `32679549372`).

## Objective
Move complete implementation authority for `external.self_model` from `cogcoder.organization.self_model` to `nolane.external_core.self_model` while preserving historical import identity and all accepted behavior.

The complete semantic owner is exactly:
- `SelfModel`
- `SelfModelRegistry`

## Why this tranche now
The Master Spec places self-model after experience in the shared substrate order. Wave 5H has accepted native Experience, while Identity and Evidence are already canonical. Self-model therefore has a dependency-clean migration path without pulling Skills, Knowledge, Context, planning, execution, evaluation, or Neural authority into the tranche.

A stale draft PR (#173) attempted the same semantic extraction from Wave 5E. It is not an implementation ancestor for Wave 5I because it predates accepted Canonical Digest, Identity Schemas, and Experience waves. Its behavioral contract is used only as historical design evidence.

## Canonical dependencies
The native implementation may depend only on accepted canonical owners required by the historical implementation:
- `AgentRegistry` from `nolane.organization.identity`
- `EvidenceRecord` from `nolane.external_core.evidence`

It must not executable-import `cogcoder.organization.self_model`, `cogcoder.organization.registry`, or `cogcoder.organization.types`.

## Preserved behavior
Wave 5I preserves without semantic expansion:
- initialization of one SelfModel for every permanent registry identity;
- propagation of each identity's existing `self_model_version`, with historical fallback `self-model-0.1`;
- exact `SelfModel.to_state` / `from_state` shape and defaults;
- `SelfModelRegistry.get` registry validation and missing-model failure;
- evidence-gated competence updates requiring passing evidence, zero false accepts, zero regressions, and a verifier external to the producer;
- competence score range `[0, 1]` and explicit nonblank domain validation;
- deterministic sorted domain competence state;
- evidence-id deduplication;
- revision advancement to `self-model-{revision:08d}`;
- optional synchronization through `registry.set_self_model_version` when available;
- state restoration including initialization of models missing from persisted state.

No new learning algorithm, calibration rule, tool-competence mutation, failure-mode mutation, trust policy, or blind-spot policy is introduced here.

## Compatibility and provenance
After cutover:
- `nolane.external_core.self_model` is the real canonical implementation owner;
- `cogcoder.organization.self_model` remains as an explicit exact compatibility bridge for both public objects;
- `external.self_model` leaves active facade debt and becomes `canonical_native` with canonical write authority;
- only `external.self_model` advances `0.0.0 → 0.0.1` in this tranche;
- pinned inventory preserves `cogcoder/organization/self_model.py → nolane/external_core/self_model.py` after facade retirement;
- no historical source is deleted or moved.

## Scope isolation
Wave 5I must leave these boundaries unchanged:
- `external.skills` remains a compatibility facade because `SkillScope` is still owned by the mixed historical types boundary;
- `external.knowledge` remains historical-only pending reconstruction;
- `external.context` remains a compatibility facade;
- `external.individual_evolution` remains a compatibility facade;
- execution, domains, evaluation and Neural authority remain unchanged.

## Expected debt delta
Wave 5H accepted debt:
- compatibility facade: 27
- legacy internal: 2
- historical only: 7
- frozen asset: 1
- total non-native: 37

Wave 5I target:
- compatibility facade: **26**
- legacy internal: **2**
- historical only: **7**
- frozen asset: **1**
- total non-native: **36**

The only intended debt reduction is retirement of the Self-model compatibility facade.

## TDD and acceptance
RED contracts must prove historical behavior first and fail only on the not-yet-cut-over authority/version/facade/provenance/debt conditions.

Acceptance requires one exact clean post-cleanup head proving:
- canonical ownership of both public Self-model objects;
- exact historical bridge identity;
- no executable reverse import of historical owners;
- preserved initialization, update, evidence, validation, revision and state behavior;
- Self-model removal from active facades while Context, Individual Evolution and Skills remain unmigrated;
- exact inventory provenance;
- deterministic repository audit with debt 36 and no archive-index drift;
- no temporary mutation workflow remaining;
- complete `Nolane-AI Refoundation Epoch 0` success on Python 3.11 and 3.13 through zero-loss evidence, full organization/campaign/execution regressions, and frozen Neural R2.3 metadata checks.

Wave 5I must never auto-merge.