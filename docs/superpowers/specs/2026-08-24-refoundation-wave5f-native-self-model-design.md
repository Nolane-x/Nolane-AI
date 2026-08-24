# Refoundation Epoch 0 — Wave 5F Native Self-model Design

## Parent acceptance
Wave 5F starts from exact hosted-green Wave 5E head `e10a948894653f33c3df30091e3bd456f489bba7`.

## Objective
Move complete implementation authority for `external.self_model` from `cogcoder.organization.self_model` to `nolane.external_core.self_model` while preserving historical import identity and accepted behavior.

The smallest complete semantic unit is exactly:
- `SelfModel`
- `SelfModelRegistry`

## Canonical dependencies
The native implementation consumes only already canonical owners:
- `AgentRegistry` from `nolane.organization.identity`
- `EvidenceRecord` from `nolane.external_core.evidence`

It does not require `core.canonical_digest`, so Wave 5F remains isolated from mixed `cogcoder.organization.types` debt.

## Preserved behavior
Wave 5F must preserve registry initialization for every permanent identity, default/self-model version propagation, state round-trip, evidence-gated competence updates, producer-external verifier requirement, clean-evidence requirement, score bounds, explicit competence domain, deterministic sorted competence state, evidence ID deduplication, revision advancement, and optional registry self-model-version synchronization.

## Compatibility/provenance
After cutover:
- historical `cogcoder.organization.self_model` remains as an exact bridge for both public objects;
- `external.self_model` leaves active facade debt and becomes `canonical_native` with canonical write authority;
- only this component advances `0.0.0 → 0.0.1`;
- pinned inventory preserves `cogcoder/organization/self_model.py → nolane/external_core/self_model.py` after facade retirement;
- no historical source is deleted or moved.

## Non-goals
No Skills, Experience, Knowledge, Context, Individual Evolution, canonical-digest, planning, execution, evaluation, or Neural migration occurs here.

## Expected debt delta
Wave 5E accepted debt: compatibility facade 28, legacy internal 4, historical only 7, frozen asset 1, total 40.

Wave 5F target: compatibility facade **27**, legacy internal **4**, historical only **7**, frozen asset **1**, total **39**.

## Acceptance
One exact final head must prove canonical ownership and exact bridge identity; no reverse historical import; preserved self-model behavior/state; Self-model removal from active facades while Individual Evolution/Context remain unmigrated; exact inventory provenance; deterministic debt 39 with archive no-drift; no temporary write bootstrap; and complete Python 3.11/3.13 Refoundation workflow success through zero-loss evidence, full regressions, and frozen Neural R2.3 checks.
