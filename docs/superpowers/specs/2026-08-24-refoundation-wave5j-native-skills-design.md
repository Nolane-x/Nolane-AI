# Refoundation Epoch 0 — Wave 5J Native Skills Design

## Parent acceptance
Wave 5J starts from exact hosted-green Wave 5I head `9423b5c6e7c0a4b821c44a78e300a4dd4855b5eb`.

## Objective
Move complete implementation authority for `external.skills` from the historical `cogcoder.organization.evolution` implementation into `nolane.memory.skills` without leaving the canonical owner dependent on the mixed historical `cogcoder.organization.types` module.

The complete semantic unit is:
- `SkillScope`
- `SkillRecord`
- `SkillEvolutionEngine`

`SkillScope` moves with Skills because it is a skill-lifecycle schema, not an identity schema. This closes the mixed-schema boundary honestly instead of marking Skills native while retaining a reverse dependency on historical types.

## Canonical dependencies
The native implementation may consume only already accepted canonical owners:
- `EvidenceRecord` from `nolane.external_core.evidence`
- `canonical_digest` from `nolane.core.canonical_digest`

No import from `cogcoder.organization.evolution` or `cogcoder.organization.types` is permitted in canonical Skills.

## Preserved behavior
Wave 5J preserves the accepted historical behavior exactly:
- deterministic proposal digest and `skill-<digest[:20]>` identity;
- idempotent duplicate proposal handling;
- explicit owner/region/name/body validation;
- evidence-ID rebinding rejection and deterministic evidence ordering;
- only passing evidence with zero false accepts/regressions counts toward promotion;
- independent verifier thresholds: Personal=1, Regional=2, Global=3;
- Candidate is not a promotion target;
- promotion cannot silently demote scope;
- quarantined skills cannot be promoted;
- quarantine requires an explicit reason;
- visibility rules for personal, regional and global skills;
- quarantined/candidate skills remain excluded from `skills_for`;
- exact state round-trip.

## Compatibility and provenance
After cutover:
- `cogcoder.organization.evolution` becomes an exact compatibility bridge for `SkillScope`, `SkillRecord`, and `SkillEvolutionEngine`;
- historical dependency names `EvidenceRecord` and `canonical_digest` remain available from the historical bridge to avoid accidental surface loss;
- `cogcoder.organization.types.SkillScope` becomes an exact bridge to `nolane.memory.skills.SkillScope`;
- the mixed `types.py` file does **not** receive a whole-file canonical destination to Skills;
- `external.skills` leaves active facade debt and becomes `CANONICAL_NATIVE` with write authority;
- only `external.skills` advances from `0.0.0` to `0.0.1`;
- inventory pins `cogcoder/organization/evolution.py → nolane/memory/skills.py` after facade retirement;
- no historical source is deleted or moved.

## Non-goals
No Knowledge reconstruction, Context cutover, Individual Evolution cutover, planning/execution/evaluation migration, new skill-learning semantics, new event emission, or Neural changes occur in Wave 5J.

## Expected debt delta
Wave 5I accepted debt:
- compatibility facade: 26
- legacy internal: 2
- historical only: 7
- frozen asset: 1
- total non-native: 36

Wave 5J target:
- compatibility facade: **25**
- legacy internal: **2**
- historical only: **7**
- frozen asset: **1**
- total non-native: **35**

## Acceptance
One exact post-cleanup head must prove native class/schema ownership, exact historical bridge identities including `types.SkillScope`, no executable historical reverse import, preserved skill behavior/state, correct inventory provenance without false whole-file `types.py` mapping, deterministic debt 35, repository-audit freshness, absence of temporary write carriers, and complete Python 3.11/3.13 Refoundation workflow success through zero-loss evidence, regressions and frozen Neural R2.3 contracts.
